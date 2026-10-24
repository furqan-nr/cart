#!/usr/bin/env python3
"""Write or verify PREREGISTRATION_P3.sha256: SHA-256 of every file the registration freezes.

Frozen: PREREGISTRATION_P3.md, LICENSE, every file under cart/ and obsaware/ (caches excluded), and the K1 session
output data/K1/out_k1.zip. Not frozen: README.md, REPRODUCE.md, CITATION.cff, docs/, REGISTRATION_RECORD.md, the
extracted copy data/K1/out_k1/ (the zip is frozen) and cohort outputs added after registration.

From the repository root:
    python obsaware/scripts/freeze_registration.py            # write the manifest
    python obsaware/scripts/freeze_registration.py --verify   # check every frozen file against it
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "PREREGISTRATION_P3.sha256"
SINGLE = ["PREREGISTRATION_P3.md", "LICENSE", "data/K1/out_k1.zip"]
TREES = ["cart", "obsaware"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}


def frozen_files() -> list[str]:
    files = list(SINGLE)
    for t in TREES:
        for p in sorted((ROOT / t).rglob("*")):
            if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_PARTS) and not p.name.endswith(".pyc") \
                    and ".egg-info" not in p.as_posix():
                files.append(p.relative_to(ROOT).as_posix())
    return files


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        listed = {}
        for line in MANIFEST.read_text().splitlines():
            h, name = line.split("  ", 1)
            listed[name] = h
        bad = [n for n, h in listed.items() if not (ROOT / n).exists() or sha(ROOT / n) != h]
        new = [f for f in frozen_files() if f not in listed]
        for n in bad:
            print("CHANGED OR MISSING:", n)
        for n in new:
            print("NOT IN MANIFEST:", n)
        print(f"{len(listed) - len(bad)}/{len(listed)} frozen files match" + ("" if not new else f"; {len(new)} new files"))
        return 1 if (bad or new) else 0
    lines = [f"{sha(ROOT / f)}  {f}" for f in frozen_files()]
    MANIFEST.write_text("\n".join(lines) + "\n")
    print(f"wrote {MANIFEST.name}: {len(lines)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
