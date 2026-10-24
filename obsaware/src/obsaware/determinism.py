"""Determinism runner (Paper 1B mechanism, batched for CI).

PYTHONHASHSEED is fixed for the lifetime of an interpreter, so non-determinism of the #14730 / #16237 kind is
only observable across process launches. The runner starts R fresh interpreters, each with a different
PYTHONHASHSEED, and in each one compiles a BATCH of units with a fixed seed_transpiler and returns the raw
fingerprint (obsaware.oracles.fingerprint) of every unit. A unit is non-deterministic when its fingerprints
are not all equal.

Cost model (what a selector must price): R process launches, each paying a fixed start-up cost (interpreter,
qiskit import) plus the sum of the batch's compile times. The start-up cost is shared by every unit in the
batch, which is why the determinism check is priced as a lane with a fixed cost plus per-unit marginal costs
(obsaware.selection).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_HASHSEEDS = ("0", "1", "2")

_WORKER = r'''
import json, sys, time, warnings
warnings.filterwarnings("ignore")
t_import0 = time.process_time()
from cart.events.mutations import baseline_transpiler
from cart.manifest.backends import coupling_map_for
from cart.manifest.circuits import build
from obsaware.oracles import fingerprint
spec = json.loads(sys.stdin.read())
op = None
if spec.get("operator"):
    from obsaware.registry import get_any_operator
    op = get_any_operator(spec["operator"])
t_import = time.process_time() - t_import0
out = {}
for u in spec["units"]:
    cfg = dict(optimization_level=u["level"], coupling_map=coupling_map_for(u["backend"], u["n"]),
               basis_gates=["cx", "rz", "sx", "x"], seed_transpiler=1234)
    qc = build(u["family"], u["n"], seed=u.get("circuit_seed", 1234))
    fn = op.transpiler(cfg) if op is not None else baseline_transpiler(cfg)
    t0 = time.process_time()
    tq = fn(qc)
    out[u["id"]] = {"fp": fingerprint(tq), "compile_s": time.process_time() - t0}
print(json.dumps({"import_s": t_import, "units": out}))
'''


@dataclass
class DeterminismResult:
    per_unit: dict[str, dict[str, Any]]      # id -> {"distinct": k, "deterministic": bool, "compile_s": [..]}
    launches: int
    wall_s: float
    cpu_s_children: float
    import_s: list[float]
    launch_wall_s: list[float]
    launch_cpu_s: list[float]


def run_batch(units: list[dict[str, Any]], *, operator: str | None = None,
              hashseeds: tuple[str, ...] = DEFAULT_HASHSEEDS, python: str | None = None,
              env_extra: dict[str, str] | None = None) -> DeterminismResult:
    """units: dicts with id, family, n, backend, level (and optional circuit_seed)."""
    python = python or sys.executable
    fps: dict[str, set] = {u["id"]: set() for u in units}
    ctimes: dict[str, list] = {u["id"]: [] for u in units}
    imports, lwall, lcpu = [], [], []
    t0 = time.perf_counter()
    c0 = os.times()
    for hs in hashseeds:
        env = dict(os.environ, PYTHONHASHSEED=hs, RAYON_NUM_THREADS="1", OMP_NUM_THREADS="1",
                   QISKIT_IN_PARALLEL="TRUE", **(env_extra or {}))
        w0, k0 = time.perf_counter(), os.times()
        proc = subprocess.run([python, "-c", _WORKER], input=json.dumps({"units": units, "operator": operator}),
                              capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise RuntimeError(f"determinism worker failed (PYTHONHASHSEED={hs}):\n{proc.stderr[-3000:]}")
        k1 = os.times()
        lwall.append(time.perf_counter() - w0)
        lcpu.append((k1.children_user - k0.children_user) + (k1.children_system - k0.children_system))
        res = json.loads(proc.stdout.strip().splitlines()[-1])
        imports.append(res["import_s"])
        for uid, r in res["units"].items():
            fps[uid].add(r["fp"])
            ctimes[uid].append(r["compile_s"])
    c1 = os.times()
    per = {uid: {"distinct": len(s), "deterministic": len(s) == 1, "compile_s": ctimes[uid]}
           for uid, s in fps.items()}
    return DeterminismResult(per, len(hashseeds), time.perf_counter() - t0,
                             (c1.children_user - c0.children_user) + (c1.children_system - c0.children_system),
                             imports, lwall, lcpu)
