#!/usr/bin/env python3
"""R3 eligibility, step 2: is a fix's code exercised by clean compilation of the corpus?

A fault is EXERCISED if some function (or method) of Qiskit 2.6.1 that contains a line changed by the fix executes at
least one line while the corpus is compiled. A changed line outside any function counts if that line itself executes.
Python: from coverage_corpus.py. Rust: from probe hits of an instrumented build (rust_probes.py). Uses no check
result and no fault build.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


def changed_lines_post(patch: str) -> dict[str, set[int]]:
    """Lines in the post-fix file (2.6.1) added or adjacent to removals, per file."""
    out, cur, ln = {}, None, 0
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]; out.setdefault(cur, set())
        elif line.startswith("@@"):
            ln = int(re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line).group(1))
        elif cur is None or line.startswith("---"):
            continue
        elif line.startswith("+"):
            out[cur].add(ln); ln += 1
        elif line.startswith("-"):
            out[cur].add(ln)          # removal: attribute to the following post-fix line
        elif line.startswith(" "):
            ln += 1
    return out


def py_functions(src: str):
    tree = ast.parse(src)
    fns = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fns.append((node.lineno, node.end_lineno))
    return fns


def exercised_py(changed: dict[str, set[int]], tree_root: Path, cov: dict[str, list[int]]):
    hits = []
    for f, lines in changed.items():
        if not f.endswith(".py") or not f.startswith("qiskit/"):
            continue
        p = tree_root / f
        if not p.exists():
            continue
        ran = set(cov.get(f, []))
        fns = py_functions(p.read_text())
        for l in lines:
            enc = [(a, b) for a, b in fns if a <= l <= b]
            if enc:
                a, b = min(enc, key=lambda x: x[1] - x[0])      # innermost
                if any(a <= r <= b for r in ran):
                    hits.append((f, l))
            elif l in ran:
                hits.append((f, l))
    return hits


if __name__ == "__main__":
    fixes = json.load(open(sys.argv[1]))
    cov = json.load(open(sys.argv[2]))["lines"]
    root = Path(sys.argv[3])
    probes = set(json.load(open(sys.argv[4]))) if len(sys.argv) > 4 else None
    for r in fixes:
        ch = changed_lines_post(Path(r["patch"]).read_text())
        r["py_hits"] = len(exercised_py(ch, root, cov))
        if probes is not None and r.get("rust"):
            r["rust_hit"] = (r["pr"] or r["h"]) in probes
    json.dump(fixes, sys.stdout, indent=1)
