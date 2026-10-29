#!/usr/bin/env python3
"""Registration R3 labeling session: real Qiskit faults, re-injected into Qiskit 2.6.1 (run on Kaggle).

Like obsaware/scripts/label_cohort.py, with one difference: an event is a REAL fault (a merged Qiskit bug fix,
reverted), not an operator. Each fault is a FAULT SITE: a copy of the clean Qiskit package from the session's
install with the fault's overlay files (reverted Python files and, for faults with Rust changes, the rebuilt
compiled extension) written over it. Candidate compilations run in a separate interpreter with the fault site first
on PYTHONPATH and are returned pickled. Every check runs in this (clean) interpreter, so a fault never changes an
oracle. Everything else is as in label_cohort.py:

  1. hardware record and reference benchmark (start, after every event, end);
  2. fault import check (rule E1 for faults): a fault whose site does not import, or whose imported Qiskit is not
     loaded from the fault site, is EXCLUDED and reported;
  3. clean baseline: per corpus unit, the measurements of session K1 (calibrate_costs.calibrate_unit), and the
     clean determinism lane;
  4. events, in a shuffled order (seed 20261029): per unit, the candidate compilation (cost not charged); a
     candidate that raises is a crash, observed by every check of that unit; a candidate whose fingerprint and
     contract verdict equal the baseline's detects nothing and is charged the clean costs; otherwise every
     applicable check runs once on the candidate and is charged its measured CPU time. Rule L1: a check DETECTS
     the event on a unit when it raises an alarm on the candidate and passed on that unit's clean baseline. The
     determinism lane runs once per event over all units with hash seeds 0, 1, 2, in fault-site interpreters.

    python r3/label_faults.py --out /kaggle/working/out_R3 --faults <faults dataset dir> --site <clean site>
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pickle
import random
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
for _k, _v in {"RAYON_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "TRUE",
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ.setdefault(_k, _v)

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("label_cohort", ROOT / "obsaware" / "scripts" / "label_cohort.py")
lc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lc)
cal = lc.cal

from cart.events.mutations import baseline_transpiler  # noqa: E402
from cart.labels.ground_truth import _base_config  # noqa: E402
from cart.manifest.circuits import build  # noqa: E402
from cart.manifest.static_manifest import enumerate_costhet_units  # noqa: E402
from cart.oracles.quality import QualityThresholds  # noqa: E402
from obsaware.bench import reference_benchmark  # noqa: E402
from obsaware import determinism as _det  # noqa: E402
from obsaware.determinism import run_batch  # noqa: E402
from obsaware.oracles import contract_v2, fingerprint  # noqa: E402

CIRCUIT_SEED = 1234
HASHSEEDS = ("0", "1", "2")
EVENT_ORDER_SEED = 20261029
UNIT_ORDER_SEED = 20261023

_COMPILE_WORKER = r'''
import json, os, pickle, sys, warnings
warnings.filterwarnings("ignore")
import qiskit
spec = json.loads(sys.stdin.read())
assert os.path.realpath(qiskit.__file__).startswith(os.path.realpath(spec["site"])), qiskit.__file__
from cart.events.mutations import baseline_transpiler
from cart.labels.ground_truth import _base_config
from cart.manifest.circuits import build
from cart.manifest.static_manifest import enumerate_costhet_units
units = {u.test_id: u for u in enumerate_costhet_units()}
out = {}
for tid in spec["units"]:
    u = units[tid]
    qc = build(u.circuit_family, u.n_qubits, seed=spec["circuit_seed"])
    try:
        out[tid] = ("ok", baseline_transpiler(_base_config(u))(qc))
    except BaseException as exc:          # a Rust panic surfaces as PanicException (a BaseException)
        out[tid] = ("crash", f"{type(exc).__name__}: {str(exc)[:200]}")
with open(spec["pickle"], "wb") as f:
    pickle.dump(out, f)
print(json.dumps({"qiskit": qiskit.__version__, "file": qiskit.__file__}))
'''


def run_batch_limited(units, *, hashseeds, env_extra, timeout):
    """obsaware.determinism.run_batch with a time limit per launch (a re-injected fault may hang). The worker and
    the accounting are the frozen ones; only the limit is added."""
    orig = _det.subprocess.run

    def run_with_limit(*a, **k):
        k.setdefault("timeout", timeout)
        return orig(*a, **k)
    _det.subprocess.run = run_with_limit
    try:
        return run_batch(units, operator=None, hashseeds=hashseeds, env_extra=env_extra)
    finally:
        _det.subprocess.run = orig


def make_fault_site(fault_dir: Path, clean_site: Path, dest: Path) -> Path:
    """Copy the clean qiskit package and write the fault's overlay over it."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(clean_site / "qiskit", dest / "qiskit")
    overlay = fault_dir / "overlay"
    for p in overlay.rglob("*"):
        if p.is_file():
            t = dest / p.relative_to(overlay)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, t)
    return dest


def fault_env(site: Path) -> dict:
    pp = os.environ.get("PYTHONPATH", "")
    return {"PYTHONPATH": f"{site}:{pp}"}


def _run_worker(site: Path, unit_ids: list[str], pk: Path, timeout: float):
    proc = subprocess.run([sys.executable, "-c", _COMPILE_WORKER],
                          input=json.dumps(dict(site=str(site), units=unit_ids, circuit_seed=CIRCUIT_SEED,
                                                pickle=str(pk))),
                          capture_output=True, text=True, env=dict(os.environ, **fault_env(site)), timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-3000:])
    with open(pk, "rb") as f:
        cands = pickle.load(f)
    pk.unlink()
    return cands, json.loads(proc.stdout.strip().splitlines()[-1])


def compile_candidates(site: Path, unit_ids: list[str], tmp: Path, clean_compile_s: dict) -> tuple[dict, dict]:
    """All units in one fault-site interpreter. If that interpreter dies (for example an abort that is not a Python
    exception) or exceeds 3x the clean compile time plus 600 s, every unit is recompiled in its own interpreter with
    a limit of 10x its clean compile time plus 60 s: a unit whose interpreter dies or exceeds it is a crash."""
    pk = tmp / "candidates.pkl"
    total = sum(clean_compile_s[t] for t in unit_ids)
    try:
        return _run_worker(site, unit_ids, pk, 3 * total + 600)
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    cands, info = {}, {}
    for t in unit_ids:
        try:
            c, info = _run_worker(site, [t], pk, 10 * clean_compile_s[t] + 60)
            cands.update(c)
        except subprocess.TimeoutExpired:
            cands[t] = ("crash", "timeout")
        except RuntimeError as exc:
            cands[t] = ("crash", f"interpreter died: {str(exc)[-200:]}")
    info["per_unit_fallback"] = True
    return cands, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--faults", required=True, help="directory with one sub-directory per fault (fault.json, overlay/)")
    ap.add_argument("--site", required=True, help="the clean --target install of the session")
    ap.add_argument("--work", default="/kaggle/working/fault_sites")
    ap.add_argument("--max-width", type=int, default=None, help="dry runs only")
    ap.add_argument("--only-events", default=None, help="dry runs only")
    args = ap.parse_args()
    out, site, work = Path(args.out), Path(args.site), Path(args.work)
    (out / "events").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    hw = cal.hardware()
    hw["cohort"] = "R3"
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
    faults = {p.name: json.loads((p / "fault.json").read_text())
              for p in sorted(Path(args.faults).iterdir()) if (p / "fault.json").exists()}
    if args.only_events:
        faults = {k: v for k, v in faults.items() if k in args.only_events.split(",")}

    # ---- stage 2: fault import check (rule E1 for faults)
    cons_path = out / "construction_check.json"
    if not cons_path.exists():
        cons = {}
        for name in faults:
            fs = make_fault_site(Path(args.faults) / name, site, work / name)
            proc = subprocess.run([sys.executable, "-c", "import qiskit, qiskit.transpiler, qiskit._accelerate; "
                                   "print(qiskit.__version__, qiskit.__file__)"],
                                  capture_output=True, text=True, env=dict(os.environ, **fault_env(fs)))
            ok = proc.returncode == 0 and str(fs) in proc.stdout
            cons[name] = {"constructible": ok, "errors": [] if ok else [(proc.stderr or proc.stdout)[-500:]],
                          "n_errors": 0 if ok else 1}
        cons_path.write_text(json.dumps(cons, indent=1))
    cons = json.loads(cons_path.read_text())
    excluded = sorted(k for k, v in cons.items() if not v["constructible"])
    print("excluded by rule E1:", excluded, flush=True)

    # ---- stage 3: clean baseline (as K1 and label_cohort.py)
    (out / "units").mkdir(exist_ok=True)
    order = list(units)
    random.Random(UNIT_ORDER_SEED).shuffle(order)
    for i, u in enumerate(order, 1):
        p = out / "units" / f"{u.test_id}.json"
        if not p.exists():
            p.write_text(json.dumps(cal.calibrate_unit(u, th, 5), indent=1))
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
    clean = {u.test_id: json.loads((out / "units" / f"{u.test_id}.json").read_text()) for u in units}
    det_clean = json.loads(det_path.read_text())
    base = {}
    for u in units:
        cfg = _base_config(u)
        qc = build(u.circuit_family, u.n_qubits, seed=CIRCUIT_SEED)
        bo = baseline_transpiler(cfg)(qc)
        base[u.test_id] = (qc, cfg, bo, fingerprint(bo), contract_v2(qc, bo).holds)

    # ---- stage 4: events
    names = sorted(faults)
    random.Random(EVENT_ORDER_SEED).shuffle(names)
    for name in names:
        ev_path = out / "events" / f"{name}.json"
        if ev_path.exists() or name in excluded:
            continue
        t_ev = time.time()
        fs = make_fault_site(Path(args.faults) / name, site, work / name)
        cands, info = compile_candidates(fs, [u.test_id for u in units], work,
                                         {t: float(r["compile_s"]) for t, r in clean.items()})
        per_unit = {}
        for u in units:
            qc, cfg, bo, bfp, bct = base[u.test_id]
            crec = clean[u.test_id]
            appl = ["output", "quality", "contract"] + (["probe"] if crec.get("probe_applicable") else [])
            clean_cost = {c: float(crec[f"{c}_s"]) for c in appl}
            status, cand = cands[u.test_id]
            if status == "crash":
                per_unit[u.test_id] = dict(status="crash", error=cand, detects={c: True for c in appl}, cost=clean_cost)
                continue
            if fingerprint(cand) == bfp and contract_v2(qc, cand).holds == bct:
                per_unit[u.test_id] = dict(status="unchanged", detects={c: False for c in appl}, cost=clean_cost)
                continue
            alarm, cost = lc.alarms_and_costs(qc, bo, cand, cfg, th)
            passed_clean = crec["clean_verdicts_pass"]
            detects = {c: bool(alarm.get(c, False) and passed_clean.get(c, True)) for c in appl}
            per_unit[u.test_id] = dict(status="changed", detects=detects, alarms=alarm,
                                       cost={c: cost.get(c, clean_cost[c]) for c in appl})
        try:
            dres = run_batch_limited(spec, hashseeds=HASHSEEDS, env_extra=fault_env(fs),
                                     timeout=3 * sum(float(r["compile_s"]) for r in clean.values()) + 600)
            per_launch_compile = [sum(v["compile_s"][j] for v in dres.per_unit.values()) for j in range(len(HASHSEEDS))]
            det = dict(fixed_cpu_per_launch_s=[c - k for c, k in zip(dres.launch_cpu_s, per_launch_compile)],
                       per_unit={t: dict(detects=(not v["deterministic"]) and det_clean["per_unit"][t]["deterministic"],
                                         cost=sum(v["compile_s"])) for t, v in dres.per_unit.items()})
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            # the lane's interpreters died or hung: the lane observes the failure on the units whose candidate
            # compilation crashed (as every other check does); costs are the clean lane's
            det = dict(fixed_cpu_per_launch_s=det_clean["fixed_cpu_per_launch_s"], crash=str(exc)[-500:],
                       per_unit={t: dict(detects=cands[t][0] == "crash", cost=sum(v["compile_s"]))
                                 for t, v in det_clean["per_unit"].items() if t in cands})
        ev_path.write_text(json.dumps(dict(event=name, group="real", cohort="R3", fault=faults[name],
                                           imported=info, per_unit=per_unit, determinism=det,
                                           wall_s=time.time() - t_ev), indent=1))
        shutil.rmtree(fs, ignore_errors=True)
        n_det = sum(any(v["detects"].values()) for v in per_unit.values()) + \
            sum(v["detects"] for v in det["per_unit"].values())
        print(f"event {name:12s} unit-detections {n_det:3d} ({time.time() - t_ev:.0f}s)", flush=True)
        bench(f"after_{name}")
    bench("end")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
