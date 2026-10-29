#!/usr/bin/env python3
"""R3 eligibility, Rust part, step 2: with the probe-instrumented Qiskit installed, construct every corpus circuit,
then switch the probes on (flag file) and compile every corpus unit with the frozen baseline transpiler. Writes the
list of fault ids whose changed Rust functions ran during compilation. No check, no fault build, no label.

    PYTHONPATH=<repo>/cart/src:<repo>/obsaware/src python probe_corpus.py --out rust_probe_hits.json
"""
from __future__ import annotations

import argparse
import json
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
FLAG, HITS = Path("/tmp/qk_r3_on"), Path("/tmp/qk_r3_probes.txt")
FLAG.unlink(missing_ok=True)
HITS.unlink(missing_ok=True)

import qiskit  # noqa: E402
from cart.events.mutations import baseline_transpiler  # noqa: E402
from cart.labels.ground_truth import _base_config  # noqa: E402
from cart.manifest.circuits import build  # noqa: E402
from cart.manifest.static_manifest import enumerate_costhet_units  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    units = enumerate_costhet_units()
    circuits = [(u, build(u.circuit_family, u.n_qubits, seed=1234)) for u in units]
    FLAG.touch()
    for u, qc in circuits:
        baseline_transpiler(_base_config(u))(qc)
    FLAG.unlink()
    hits = sorted(set(HITS.read_text().split())) if HITS.exists() else []
    Path(a.out).write_text(json.dumps(hits, indent=1))
    print(len(units), "units; probes hit:", hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
