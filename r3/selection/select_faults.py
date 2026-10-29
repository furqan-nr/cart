#!/usr/bin/env python3
"""R3 fault selection, final step: apply the eligibility rule (r3/SELECTION.md) and write r3/faults.json and
r3/fault_selection_all.json.

    python select_faults.py --fixes fixes.json --cov cov_python.json --rust-hits rust_probe_hits.json \
        --tree261 <checkout of 2.6.1> --out-dir r3
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from exercised import changed_lines_post, exercised_py  # noqa: E402

# Qiskit fixes already contacted by this research (Paper 1B faults, operators' models, the case study)
CONTACTED = {"11399", "13094", "14603", "14621", "14622", "14623", "14730", "14734", "14919", "14920", "14939",
             "14941", "14956", "14961", "14997", "15024", "15025", "15040", "15057", "16201", "16215", "16237",
             "16238", "16285"}
COMPILATION = ("qiskit/transpiler/", "qiskit/synthesis/", "qiskit/circuit/", "qiskit/dagcircuit/",
               "qiskit/passmanager/", "qiskit/compiler/", "qiskit/converters/", "crates/transpiler/",
               "crates/synthesis/", "crates/circuit/", "crates/accelerate/", "crates/quantum_info/")
NOT_COMPILATION = ("visualization", "qpy", "qasm", "primitives", "drawer", "result")


def compilation_related(files):
    return any(f.startswith(COMPILATION) and not any(e in f for e in NOT_COMPILATION)
               for f in files if not f.startswith("test"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixes", required=True)
    ap.add_argument("--cov", required=True)
    ap.add_argument("--rust-hits", required=True)
    ap.add_argument("--tree261", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    fixes = json.loads(Path(a.fixes).read_text())
    cov = json.loads(Path(a.cov).read_text())["lines"]
    hits = set(json.loads(Path(a.rust_hits).read_text()))
    out = Path(a.out_dir)
    (out / "patches").mkdir(parents=True, exist_ok=True)
    table, sel = [], []
    for r in fixes:
        fid = r["pr"] or r["h"]
        reason, ev = None, {}
        if not r["in_261_revertible"]:
            reason = "not present in 2.6.1 or does not revert cleanly"
        elif fid in CONTACTED:
            reason = "contacted in earlier work (operators, case study)"
        elif not compilation_related(r["files"]):
            reason = "changes no compilation-related source file"
        else:
            py = len(exercised_py(changed_lines_post(Path(r["patch"]).read_text()), Path(a.tree261), cov))
            ev = dict(python_functions_run=py, rust_probe_hit=fid in hits)
            if not (py or (r["rust"] and fid in hits)):
                reason = "changed code not run when compiling the corpus"
        table.append(dict(id=fid, commit=r["h"], date=r["d"], title=r["s"], rust=bool(r["rust"]),
                          eligible=reason is None, reason=reason, evidence=ev))
        if reason is None:
            shutil.copy(r["patch"], out / "patches" / f"{fid}.diff")
            sel.append(dict(id=fid, commit=r["h"], date=r["d"], title=r["s"], rust=bool(r["rust"]), files=r["files"],
                            patch=f"patches/{fid}.diff", evidence=ev))
    (out / "faults.json").write_text(json.dumps(dict(qiskit="2.6.1", rule="r3/SELECTION.md", faults=sel), indent=1))
    (out / "fault_selection_all.json").write_text(json.dumps(table, indent=1))
    print(len(table), "mined;", len(sel), "eligible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
