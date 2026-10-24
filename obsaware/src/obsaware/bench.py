"""Fixed reference benchmark for timing sessions.

Run at the start, at chunk boundaries and at the end of every timed session. Its median CPU time tracks the
speed of the machine the session is on: the drift between readings detects a session that slowed down part-way
(noisy neighbours, throttling), and its ratio between sessions is the machine-speed factor.

The workload mirrors what Paper 3 times (single-threaded transpilation plus a small dense operator and a
statevector probe), with fixed inputs, so it exercises the same code paths as the measurements it guards.
"""
from __future__ import annotations

import statistics as st
import time


def reference_benchmark(repeats: int = 5) -> dict:
    import warnings
    warnings.filterwarnings("ignore")
    from qiskit.quantum_info import Operator
    from qiskit.transpiler import CouplingMap, generate_preset_pass_manager

    from cart.manifest.circuits import build
    from obsaware.oracles import state_probe

    qc_t = build("qft", 10, seed=0)
    pm = generate_preset_pass_manager(optimization_level=3, coupling_map=CouplingMap.from_heavy_hex(3),
                                      basis_gates=["cx", "rz", "sx", "x"], seed_transpiler=99)
    qc_o = build("random_clifford", 8, seed=0)
    out = pm.run(qc_t)
    pm.run(qc_t)                                    # warm-up
    times = []
    for _ in range(repeats):
        t0 = time.process_time()
        pm.run(qc_t)
        Operator(qc_o)
        state_probe(qc_t, out, k=1)
        times.append(time.process_time() - t0)
    return {"median_s": st.median(times), "min_s": min(times), "max_s": max(times), "repeats": repeats,
            "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def drift(readings: list[dict]) -> float:
    """Largest relative deviation of any reading's median from the first reading's median."""
    if not readings:
        return 0.0
    ref = readings[0]["median_s"]
    return max(abs(r["median_s"] - ref) / ref for r in readings)
