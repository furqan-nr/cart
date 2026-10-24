#!/usr/bin/env python3
"""Build the Kaggle code dataset (p3-code.zip) from this repository: the cart/ and obsaware/ folders under a top
folder p3-code/, which is the layout the Kaggle notebooks look for.

From the repository root:   python obsaware/scripts/make_kaggle_zip.py --out ../p3-code.zip
Prints the SHA-256 of the zip; record it with every Kaggle run.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for top in ("cart", "obsaware"):
            for p in sorted((ROOT / top).rglob("*")):
                rel = p.relative_to(ROOT)
                if p.is_file() and not (set(rel.parts) & SKIP) and not p.name.endswith(".pyc") \
                        and ".egg-info" not in rel.as_posix():
                    z.write(p, f"p3-code/{rel.as_posix()}")
                    n += 1
    print(f"{out.name}: {n} files, sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
