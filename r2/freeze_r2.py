#!/usr/bin/env python3
"""Write or verify PREREGISTRATION_P3_R2.sha256 (registration R2).

Frozen by R2: PREREGISTRATION_P3_R2.md, every file under r2/, the disclosed preview (posthoc/preview_cost_estimators.py
and .json), and the first registration's manifest PREREGISTRATION_P3.sha256, which in turn pins every reused file
(labeling driver, notebooks, oracles, operators, strategies, analyze_p3.py, K1 data). --verify checks both manifests.

From the repository root:
    python r2/freeze_r2.py            # write
    python r2/freeze_r2.py --verify   # check R2 and the first registration
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "PREREGISTRATION_P3_R2.sha256"
SINGLE = ["PREREGISTRATION_P3_R2.md", "PREREGISTRATION_P3.sha256",
          "posthoc/preview_cost_estimators.py", "posthoc/preview_cost_estimators.json"]


def files() -> list[str]:
    fs = list(SINGLE)
    fs += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "r2").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"))
    return fs


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if not a.verify:
        lines = [f"{sha(ROOT / f)}  {f}" for f in files()]
        MANIFEST.write_text("\n".join(lines) + "\n")
        print(f"wrote {MANIFEST.name}: {len(lines)} files")
        return 0
    listed = dict(reversed(l.split("  ", 1)) for l in MANIFEST.read_text().splitlines())
    bad = [n for n, h in listed.items() if not (ROOT / n).exists() or sha(ROOT / n) != h]
    new = [f for f in files() if f not in listed]
    for n in bad:
        print("CHANGED OR MISSING:", n)
    for n in new:
        print("NOT IN MANIFEST:", n)
    print(f"R2: {len(listed) - len(bad)}/{len(listed)} frozen files match")
    first = subprocess.run([sys.executable, str(ROOT / "obsaware" / "scripts" / "freeze_registration.py"), "--verify"],
                           capture_output=True, text=True)
    print("First registration:", first.stdout.strip().splitlines()[-1] if first.stdout.strip() else first.stderr[-300:])
    return 1 if (bad or new or first.returncode) else 0


if __name__ == "__main__":
    sys.exit(main())
