#!/usr/bin/env python3
"""Kaggle session K1: clean-baseline cost calibration of every check on the 116-unit corpus (Qiskit 2.4.2).

Development data for Paper 3's cost estimator. It runs NO mutation operator, so it computes no detection label for
any corpus unit. It measures, per corpus unit, on the unmutated baseline compilation:
  compile_s      median CPU time of >= 5 baseline transpilations after 1 discarded warm-up
  output_s       cart's reference semantic oracle (exact <= 12 q ancilla-free, else structural)
  quality_s      cart's quality oracle
  probe_s        obsaware.state_probe (k = 2), units of at most 24 physical qubits
  contract_s     obsaware.contract_v2
and the determinism lane: R fresh interpreters over all units (fixed start-up cost and per-unit compile cost).
Clean-baseline verdicts are recorded as a specificity check (every check must pass on an unmutated compilation).

Timing rules (PROJECT_INSTRUCTIONS.md): single thread, CPU process time, warm-up discarded, shuffled unit order
(registered seed), reference benchmark at the start, after every chunk and at the end, resumable per unit.

Run from the cart source folder with cart/src and obsaware/src on PYTHONPATH:
    python ../obsaware/scripts/calibrate_costs.py --out /kaggle/working/out_k1
Options: --max-width N (smoke test on small units only), --repeats, --order-seed, --chunk, --r.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics as st
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
for _k, _v in {"RAYON_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "TRUE",
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ.setdefault(_k, _v)

import qiskit  # noqa: E402

from cart.events.mutations import baseline_transpiler  # noqa: E402
from cart.labels.ground_truth import _base_config  # noqa: E402
from cart.manifest.circuits import build  # noqa: E402
from cart.manifest.static_manifest import enumerate_costhet_units  # noqa: E402
from cart.oracles.quality import QualityThresholds, evaluate_quality  # noqa: E402
from cart.oracles.semantic import check_semantic  # noqa: E402

from obsaware.bench import drift, reference_benchmark  # noqa: E402
from obsaware.determinism import run_batch  # noqa: E402
from obsaware.oracles import PROBE_MAX_QUBITS, contract_v2, state_probe  # noqa: E402

CIRCUIT_SEED = 1234          # as cart.labels.ground_truth (Paper 2)
LONG_CHECK_S = 10.0          # a check whose first measurement exceeds this is measured once


def _timed(fn, *a, **k):
    t0 = time.process_time()
    r = fn(*a, **k)
    return r, time.process_time() - t0


def _measure(fn, reps: int):
    """Median CPU time over reps calls; one call only if the first exceeds LONG_CHECK_S."""
    r, t = _timed(fn)
    if t > LONG_CHECK_S or reps <= 1:
        return r, t, [t]
    ts = [t]
    for _ in range(reps - 1):
        r, t = _timed(fn)
        ts.append(t)
    return r, st.median(ts), ts


def hardware() -> dict:
    cpu = subprocess.run(["bash", "-lc", "grep -m1 'model name' /proc/cpuinfo"], capture_output=True,
                         text=True).stdout.strip()
    return {"python": platform.python_version(), "qiskit": qiskit.__version__, "cpu": cpu,
            "nproc": os.cpu_count(), "kaggle_image": os.environ.get("KAGGLE_DOCKER_IMAGE", ""),
            "threads_env": {k: os.environ.get(k) for k in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS")},
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def calibrate_unit(u, th, repeats: int) -> dict:
    qc = build(u.circuit_family, u.n_qubits, seed=CIRCUIT_SEED)
    cfg = _base_config(u)
    fn = baseline_transpiler(cfg)
    fn(qc)                                                     # warm-up, discarded
    times, out = [], None
    for _ in range(repeats):
        out, t = _timed(fn, qc)
        times.append(t)
    sem, out_s, out_ts = _measure(lambda: check_semantic(qc, out, coupling_map=cfg["coupling_map"],
                                                         basis_gates=cfg["basis_gates"]), 3)
    qual, q_s, _ = _measure(lambda: evaluate_quality(out, out, th), 5)
    rec = dict(test_id=u.test_id, family=u.circuit_family, n=u.n_qubits, backend=u.backend_id,
               level=cfg["optimization_level"], physical_qubits=out.num_qubits,
               compile_s=st.median(times), compile_samples=times,
               compile_iqr_s=(st.quantiles(times, n=4)[2] - st.quantiles(times, n=4)[0]) if len(times) >= 4 else None,
               output_tier=sem.strength, output_s=out_s, output_samples=out_ts, quality_s=q_s)
    clean = {"output": not ((sem.equivalent is False) or (sem.strength == "structural"
                                                         and sem.details.get("structural_ok") is False)),
             "quality": not qual.is_regression}
    if out.num_qubits <= PROBE_MAX_QUBITS:
        pr, p_s, p_ts = _measure(lambda: state_probe(qc, out, k=2), 3)
        rec.update(probe_applicable=bool(pr.assessable), probe_s=p_s, probe_samples=p_ts)
        clean["probe"] = (not pr.assessable) or (pr.record_ok is not False and pr.phase_ok is not False)
    else:
        rec.update(probe_applicable=False, probe_s=None)
    ct, c_s, _ = _measure(lambda: contract_v2(qc, out), 5)
    rec.update(contract_s=c_s)
    clean["contract"] = ct.holds is not False
    rec["clean_verdicts_pass"] = clean
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--order-seed", type=int, default=20261023)
    ap.add_argument("--chunk", type=int, default=10)
    ap.add_argument("--r", type=int, default=3, help="determinism launches (hash seeds 0..R-1)")
    ap.add_argument("--max-width", type=int, default=None, help="smoke test: only units up to this width")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "units").mkdir(parents=True, exist_ok=True)
    hw = hardware()
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
    assert len(units) == 116, len(units)
    if args.max_width:
        units = [u for u in units if u.n_qubits <= args.max_width]
    order = list(units)
    random.Random(args.order_seed).shuffle(order)
    todo = [u for u in order if not (out / "units" / f"{u.test_id}.json").exists()]
    print(f"{len(units)} units, {len(todo)} to do", flush=True)
    for i, u in enumerate(todo, 1):
        t0 = time.time()
        rec = calibrate_unit(u, th, args.repeats)
        (out / "units" / f"{u.test_id}.json").write_text(json.dumps(rec, indent=1))
        print(f"{i:3d}/{len(todo)} {u.test_id:40s} compile {rec['compile_s']:.4f}s output[{rec['output_tier']}] "
              f"{rec['output_s']:.3f}s probe {rec['probe_s']} ({time.time() - t0:.0f}s wall)", flush=True)
        if i % args.chunk == 0:
            bench(f"after_{i}")

    det_path = out / "determinism_lane.json"
    if not det_path.exists():
        spec = [dict(id=u.test_id, family=u.circuit_family, n=u.n_qubits, backend=u.backend_id,
                     level=_base_config(u)["optimization_level"], circuit_seed=CIRCUIT_SEED) for u in order]
        res = run_batch(spec, operator=None, hashseeds=tuple(str(i) for i in range(args.r)))
        per_launch_compile = [sum(v["compile_s"][j] for v in res.per_unit.values()) for j in range(args.r)]
        det = dict(r=args.r, launch_cpu_s=res.launch_cpu_s, launch_wall_s=res.launch_wall_s, import_s=res.import_s,
                   fixed_cpu_per_launch_s=[c - k for c, k in zip(res.launch_cpu_s, per_launch_compile)],
                   per_unit={k: dict(compile_s=v["compile_s"], deterministic=v["deterministic"])
                             for k, v in res.per_unit.items()},
                   clean_nondeterministic=[k for k, v in res.per_unit.items() if not v["deterministic"]])
        det_path.write_text(json.dumps(det, indent=1))
        print(f"determinism lane: fixed per launch {det['fixed_cpu_per_launch_s']}, "
              f"clean non-deterministic units: {det['clean_nondeterministic']}", flush=True)
    bench("end")

    readings = [json.loads(l) for l in bench_path.read_text().splitlines()]
    recs = [json.loads(p.read_text()) for p in sorted((out / "units").glob("*.json"))]
    summary = dict(hardware=hw, n_units=len(recs), benchmark_drift=drift(readings),
                   benchmark_readings=len(readings),
                   clean_failures=[r["test_id"] for r in recs if not all(r["clean_verdicts_pass"].values())],
                   total_compile_s=sum(r["compile_s"] for r in recs),
                   total_output_s=sum(r["output_s"] for r in recs),
                   total_probe_s=sum(r["probe_s"] or 0 for r in recs),
                   total_contract_s=sum(r["contract_s"] for r in recs),
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "hardware"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
