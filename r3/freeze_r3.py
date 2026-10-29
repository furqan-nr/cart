#!/usr/bin/env python3
"""Write or verify PREREGISTRATION_P3_R3.sha256 (registration R3).

Frozen by R3: PREREGISTRATION_P3_R3.md, every file under r3/ (code, fault list, fault patches, the selection
evidence, the overlay and wheelhouse hash lists, the notebook), and R2's manifest PREREGISTRATION_P3_R2.sha256,
which pins R2 and, through it, the first registration. --verify checks all three manifests.

From the repository root:
    python r3/freeze_r3.py            # write
    python r3/freeze_r3.py --verify   # check R3, R2 and the first registration
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "PREREGISTRATION_P3_R3.sha256"
SINGLE = ["PREREGISTRATION_P3_R3.md", "PREREGISTRATION_P3_R2.sha256"]


def files() -> list[str]:
    fs = list(SINGLE)
    fs += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "r3").rglob("*")
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
    print(f"R3: {len(listed) - len(bad)}/{len(listed)} frozen files match")
    r2 = subprocess.run([sys.executable, str(ROOT / "r2" / "freeze_r2.py"), "--verify"], capture_output=True, text=True)
    print(r2.stdout.strip())
    return 1 if (bad or new or r2.returncode) else 0


if __name__ == "__main__":
    sys.exit(main())
