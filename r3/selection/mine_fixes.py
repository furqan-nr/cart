#!/usr/bin/env python3
"""R3 fault selection, step 0: mine Qiskit bug fixes and test which revert cleanly on Qiskit 2.6.1.

Candidates: commits on Qiskit's main branch after tag 2.0.0 that add a release note, whose subject matches
fix|bug|incorrect|wrong, and that change Python files under qiskit/ or Rust files under crates/. For each, the
patch restricted to qiskit/ and crates/ is written to patches_all/<PR>.diff. A candidate is PRESENT AND REVERTIBLE
on 2.6.1 if the patch applies in reverse to the 2.6.1 tag and does not apply forwards.

    python mine_fixes.py --repo <qiskit clone with tags> --tree261 <checkout of tag 2.6.1> --out fixes.json
(the clone was fetched on 2026-10-29; main was at 5f9bf19d4)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def sh(*a, cwd=None):
    return subprocess.run(a, capture_output=True, text=True, cwd=cwd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--tree261", required=True)
    ap.add_argument("--head", default="5f9bf19d4")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    log = sh("git", "log", "--format=@@%h|%ad|%s", "--date=short", "--name-only", f"2.0.0..{a.head}", cwd=a.repo).stdout
    pdir = Path(a.out).parent / "patches_all"
    pdir.mkdir(exist_ok=True)
    res = []
    for blk in log.split("@@")[1:]:
        lines = blk.strip().split("\n")
        h, d, s = lines[0].split("|", 2)
        f = lines[1:]
        if not any(x.startswith("releasenotes/notes/") for x in f) or not re.search(r"fix|bug|incorrect|wrong", s, re.I):
            continue
        py = [x for x in f if x.startswith("qiskit/") and x.endswith(".py")]
        rs = [x for x in f if x.startswith("crates/")]
        if not (py or rs):
            continue
        pr = (re.findall(r"#(\d+)\)?$", s) or [""])[-1]
        diff = sh("git", "diff", f"{h}^", h, "--", "qiskit/", "crates/", cwd=a.repo).stdout
        p = pdir / f"{pr or h}.diff"
        p.write_text(diff)
        rv = sh("git", "apply", "-R", "--check", str(p.resolve()), cwd=a.tree261).returncode == 0
        fw = sh("git", "apply", "--check", str(p.resolve()), cwd=a.tree261).returncode == 0
        res.append(dict(h=h, d=d, s=s, pr=pr, py=len(py), rust=len(rs), in_261_revertible=rv and not fw,
                        files=[l[6:] for l in diff.splitlines() if l.startswith("+++ b/")], patch=str(p)))
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(len(res), "candidates;", sum(r["in_261_revertible"] for r in res), "present and revertible on 2.6.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
