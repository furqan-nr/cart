#!/usr/bin/env python3
"""Paper 3 confirmatory labeling session for ONE cohort (one Qiskit version), run on Kaggle after registration.

Stages (all resumable; each writes its own files under --out):
  1. hardware record and reference benchmark (start, after every event, end);
  2. operator construction check: every registered operator's transpiler is BUILT for every corpus unit's
     configuration, without compiling any circuit. An operator that fails to build for any unit is EXCLUDED from
     the cohort (registered rule E1) and reported;
  3. clean baseline: per corpus unit, the same measurements as session K1 (calibrate_costs.calibrate_unit):
     compile cost, cost and clean verdict of every check; plus the clean determinism lane;
  4. events, in a shuffled order (registered seed): per unit, compile the candidate (cost not charged, as in
     Paper 2); a candidate that raises is a crash, observed by every check of that unit; a candidate whose
     fingerprint and contract verdict equal the baseline's has no observable change, detects nothing and is
     charged the clean costs measured in stage 3; otherwise every applicable check runs once on the candidate and is
     charged its measured CPU time. A check DETECTS the event on a unit when it raises an alarm on the candidate and
     passed on that unit's clean baseline (registered rule L1). The determinism lane runs once per event over all
     units with the registered hash seeds.

Run from the cart source folder with cart/src and obsaware/src on PYTHONPATH:
    python ../obsaware/scripts/label_cohort.py --out /kaggle/working/out_<cohort> --cohort C261
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
for _k, _v in {"RAYON_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "TRUE",
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ.setdefault(_k, _v)

_spec = importlib.util.spec_from_file_location("calibrate_costs", Path(__file__).with_name("calibrate_costs.py"))
cal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cal)

from cart.events.mutations import baseline_transpiler  # noqa: E402
from cart.events.mutations_phase_c import MUTATION_OPERATORS_PHASE_C  # noqa: E402
from cart.labels.ground_truth import _base_config  # noqa: E402
from cart.manifest.circuits import build  # noqa: E402
from cart.manifest.static_manifest import enumerate_costhet_units  # noqa: E402
from cart.oracles.quality import QualityThresholds, evaluate_quality  # noqa: E402
from cart.oracles.semantic import check_semantic  # noqa: E402

from obsaware.bench import reference_benchmark  # noqa: E402
from obsaware.determinism import run_batch  # noqa: E402
from obsaware.mutations import MUTATION_OPERATORS_P3  # noqa: E402
from obsaware.oracles import PROBE_MAX_QUBITS, contract_v2, fingerprint, state_probe  # noqa: E402

CIRCUIT_SEED = 1234
EVENT_ORDER_SEED = 20261024
HASHSEEDS = ("0", "1", "2")


def registered_operators() -> dict:
    ops = {name: ("visible", op) for name, op in MUTATION_OPERATORS_PHASE_C.items()}
    ops.update({name: ("invisible", op) for name, op in MUTATION_OPERATORS_P3.items()})
    assert len(ops) == 18, len(ops)
    return ops


def _timed(fn, *a, **k):
    t0 = time.process_time()
    r = fn(*a, **k)
    return r, time.process_time() - t0


def alarms_and_costs(qc, base_out, cand, cfg, th) -> tuple[dict, dict]:
    sem, c_out = _timed(check_semantic, qc, cand, coupling_map=cfg["coupling_map"], basis_gates=cfg["basis_gates"])
    qual, c_q = _timed(evaluate_quality, base_out, cand, th)
    alarm = {"output": (sem.equivalent is False) or (sem.strength == "structural"
                                                     and sem.details.get("structural_ok") is False),
             "quality": bool(qual.is_regression)}
    cost = {"output": c_out, "quality": c_q}
    if cand.num_qubits <= PROBE_MAX_QUBITS:
        pr = state_probe(qc, cand, k=2)
        alarm["probe"] = bool(pr.assessable and (pr.record_ok is False or pr.phase_ok is False))
        cost["probe"] = pr.cost_s
    ct = contract_v2(qc, cand)
    alarm["contract"] = ct.holds is False
    cost["contract"] = ct.cost_s
    return alarm, cost


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--max-width", type=int, default=None, help="dry runs only")
    ap.add_argument("--only-events", default=None, help="dry runs only: comma-separated operator names")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "events").mkdir(parents=True, exist_ok=True)
    hw = cal.hardware()
    hw["cohort"] = args.cohort
    (out / "hardware.json").write_text(json.dumps(hw, indent=1))
    bench_path = out / "benchmark.jsonl"

    def bench(tag):
        r = reference_benchmark()
        r["tag"] = tag
        with bench_path.open("a") as f:
            f.write(json.dumps(r) + "\n")
        print(f"[bench {tag}] median {r['median_s']:.3f}s", flush=True)

    bench("start")
    th = QualityThresholds.load()
    units = enumerate_costhet_units()
    assert len(units) == 116
    if args.max_width:
        units = [u for u in units if u.n_qubits <= args.max_width]
    ops = registered_operators()
    if args.only_events:
        ops = {k: v for k, v in ops.items() if k in args.only_events.split(",")}

    # ---- stage 2: construction check (rule E1)
    cons_path = out / "construction_check.json"
    if not cons_path.exists():
        cons = {}
        for name, (_, op) in ops.items():
            errs = []
            for u in units:
                try:
                    op.transpiler(_base_config(u))
                except Exception as exc:
                    errs.append(f"{u.test_id}: {type(exc).__name__}: {str(exc)[:200]}")
            cons[name] = {"constructible": not errs, "errors": errs[:5], "n_errors": len(errs)}
        cons_path.write_text(json.dumps(cons, indent=1))
    cons = json.loads(cons_path.read_text())
    excluded = sorted(k for k, v in cons.items() if not v["constructible"])
    print("excluded by rule E1:", excluded, flush=True)

    # ---- stage 3: clean baseline (as K1)
    (out / "units").mkdir(exist_ok=True)
    order = list(units)
    random.Random(20261023).shuffle(order)
    for i, u in enumerate(order, 1):
        p = out / "units" / f"{u.test_id}.json"
        if not p.exists():
            rec = cal.calibrate_unit(u, th, 5)
            p.write_text(json.dumps(rec, indent=1))
            print(f"baseline {i:3d}/{len(order)} {u.test_id}", flush=True)
    spec = [dict(id=u.test_id, family=u.circuit_family, n=u.n_qubits, backend=u.backend_id,
                 level=_base_config(u)["optimization_level"], circuit_seed=CIRCUIT_SEED) for u in order]
    det_path = out / "determinism_lane.json"
    if not det_path.exists():
        res = run_batch(spec, operator=None, hashseeds=HASHSEEDS)
        per_launch_compile = [sum(v["compile_s"][j] for v in res.per_unit.values()) for j in range(len(HASHSEEDS))]
        det_path.write_text(json.dumps(dict(
            r=len(HASHSEEDS), launch_cpu_s=res.launch_cpu_s, launch_wall_s=res.launch_wall_s, import_s=res.import_s,
            fixed_cpu_per_launch_s=[c - k for c, k in zip(res.launch_cpu_s, per_launch_compile)],
            per_unit={k: dict(compile_s=v["compile_s"], deterministic=v["deterministic"]) for k, v in res.per_unit.items()},
            clean_nondeterministic=[k for k, v in res.per_unit.items() if not v["deterministic"]]), indent=1))
    bench("after_baseline")
    clean = {t: json.loads((out / "units" / f"{t}.json").read_text()) for t in [u.test_id for u in units]}
    det_clean = json.loads(det_path.read_text())

    # baseline compilations kept in memory for candidate comparison (cheap to recompute)
    base = {}
    for u in units:
        cfg = _base_config(u)
        qc = build(u.circuit_family, u.n_qubits, seed=CIRCUIT_SEED)
        bo = baseline_transpiler(cfg)(qc)
        base[u.test_id] = (qc, cfg, bo, fingerprint(bo), contract_v2(qc, bo).holds)

    # ---- stage 4: events
    names = sorted(ops)
    random.Random(EVENT_ORDER_SEED).shuffle(names)
    for name in names:
        ev_path = out / "events" / f"{name}.json"
        if ev_path.exists() or name in excluded:
            continue
        group, op = ops[name]
        t_ev = time.time()
        per_unit = {}
        for u in units:
            qc, cfg, bo, bfp, bct = base[u.test_id]
            crec = clean[u.test_id]
            appl = ["output", "quality", "contract"] + (["probe"] if crec.get("probe_applicable") else [])
            clean_cost = {c: float(crec[f"{c}_s"]) for c in appl}
            try:
                cand = op.transpiler(cfg)(qc)
            except Exception as exc:
                per_unit[u.test_id] = dict(status="crash", error=f"{type(exc).__name__}: {str(exc)[:200]}",
                                           detects={c: True for c in appl}, cost=clean_cost)
                continue
            if fingerprint(cand) == bfp and contract_v2(qc, cand).holds == bct:
                per_unit[u.test_id] = dict(status="unchanged", detects={c: False for c in appl}, cost=clean_cost)
                continue
            alarm, cost = alarms_and_costs(qc, bo, cand, cfg, th)
            passed_clean = crec["clean_verdicts_pass"]
            detects = {c: bool(alarm.get(c, False) and passed_clean.get(c, True)) for c in appl}
            per_unit[u.test_id] = dict(status="changed", detects=detects, alarms=alarm,
                                       cost={c: cost.get(c, clean_cost[c]) for c in appl})
        dres = run_batch(spec, operator=name, hashseeds=HASHSEEDS)
        per_launch_compile = [sum(v["compile_s"][j] for v in dres.per_unit.values()) for j in range(len(HASHSEEDS))]
        det = dict(fixed_cpu_per_launch_s=[c - k for c, k in zip(dres.launch_cpu_s, per_launch_compile)],
                   per_unit={t: dict(detects=(not v["deterministic"]) and det_clean["per_unit"][t]["deterministic"],
                                     cost=sum(v["compile_s"])) for t, v in dres.per_unit.items()})
        ev_path.write_text(json.dumps(dict(event=name, group=group, cohort=args.cohort, per_unit=per_unit,
                                           determinism=det, wall_s=time.time() - t_ev), indent=1))
        n_det = sum(any(v["detects"].values()) for v in per_unit.values()) + \
            sum(v["detects"] for v in det["per_unit"].values())
        print(f"event {name:36s} {group:9s} unit-detections {n_det:3d} ({time.time() - t_ev:.0f}s)", flush=True)
        bench(f"after_{name}")
    bench("end")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
