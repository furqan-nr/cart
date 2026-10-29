#!/usr/bin/env python3
"""Build the R3 Kaggle code dataset (p3-code-r3.zip): cart/, obsaware/ and r3/ under p3-code/ (the layout the
notebooks look for). Fault overlays are NOT included (they are the separate dataset p3-r3-faults).

From the repository root:   python r3/make_kaggle_zip_r3.py --out ../p3-code-r3.zip
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for top in ("cart", "obsaware", "r3"):
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
