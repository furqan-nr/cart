#!/usr/bin/env python3
"""R3 eligibility, step 1: which Python lines of the installed Qiskit run when the 116 corpus units are compiled
with the frozen baseline transpiler (clean Qiskit, no fault, no check). Only pass-manager construction and
compilation are measured: circuit construction and module imports before the first compilation are not. Writes executed lines per Qiskit-relative
file. Uses no check, no fault and no detection label.

    PYTHONPATH=<repo>/cart/src:<repo>/obsaware/src python coverage_corpus.py --out cov_python.json
"""
from __future__ import annotations

import argparse
import json
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
for k, v in {"RAYON_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "TRUE"}.items():
    os.environ.setdefault(k, v)

import coverage  # noqa: E402

cov = coverage.Coverage(data_file=None, include=["*/qiskit/*"], branch=False)
import qiskit  # noqa: E402
from cart.events.mutations import baseline_transpiler  # noqa: E402
from cart.labels.ground_truth import _base_config  # noqa: E402
from cart.manifest.circuits import build  # noqa: E402
from cart.manifest.static_manifest import enumerate_costhet_units  # noqa: E402

CIRCUIT_SEED = 1234


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    units = enumerate_costhet_units()
    circuits = [(u, build(u.circuit_family, u.n_qubits, seed=CIRCUIT_SEED)) for u in units]   # outside coverage
    for u, qc in circuits:
        cfg = _base_config(u)
        cov.start()                         # only pass-manager construction and compilation are measured
        baseline_transpiler(cfg)(qc)
        cov.stop()
    data = cov.get_data()
    root = Path(qiskit.__file__).parent.parent
    out = {}
    for f in data.measured_files():
        rel = os.path.relpath(f, root)
        out[rel] = sorted(data.lines(f) or [])
    Path(a.out).write_text(json.dumps(dict(qiskit=qiskit.__version__, units=len(units), lines=out)))
    print(len(units), "units,", len(out), "files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
