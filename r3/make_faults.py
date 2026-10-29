#!/usr/bin/env python3
"""R3: build the fault overlays from the frozen fault list (r3/faults.json).

For each fault: start from a pristine copy of Qiskit 2.6.1's source, apply the fix's patch in REVERSE (the fault
is the code before the fix), and
  * Python-only fault: the overlay is the reverted Python files;
  * fault with Rust changes: build a wheel exactly as the clean wheel was built (same source path, toolchain,
    profile and target directory) and the overlay is every file of that wheel that differs from the clean wheel
    (the compiled extension and any reverted Python file).
Writes <out>/<fault id>/fault.json and <out>/<fault id>/overlay/qiskit/... No corpus unit is compiled and no check
is run here.

    python r3/make_faults.py --faults r3/faults.json --src <qiskit 2.6.1 tree> --clean-wheel <wheel> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def wheel_files(whl: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(whl) as z:
        return {n: z.read(n) for n in z.namelist() if n.startswith("qiskit/")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--faults", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--clean-wheel", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="/home/claude/r3/srcwork")
    ap.add_argument("--target", default="/home/claude/r3/target")
    a = ap.parse_args()
    faults = json.loads(Path(a.faults).read_text())["faults"]
    out, work, src = Path(a.out), Path(a.work), Path(a.src)
    clean = wheel_files(Path(a.clean_wheel))
    env = dict(os.environ, RUSTUP_TOOLCHAIN="stable", CARGO_TARGET_DIR=a.target,
               PATH=f"{Path.home() / '.cargo' / 'bin'}:{os.environ['PATH']}")
    for f in faults:
        fid = f["id"]
        dest = out / fid
        if (dest / "fault.json").exists():
            continue
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(src, work, ignore=shutil.ignore_patterns(".git", "build", "*.egg-info"))
        patch = Path(a.faults).parent / f["patch"]
        r = subprocess.run(["git", "apply", "-R", str(patch.resolve())], cwd=work, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"{fid}: reverse patch failed: {r.stderr}")
        overlay = {}
        if f["rust"]:
            wdir = out / "_wheels" / fid
            shutil.rmtree(wdir, ignore_errors=True)
            r = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w",
                                str(wdir), "."], cwd=work, env=env, capture_output=True, text=True)
            if r.returncode:
                (out / f"{fid}.build_error.log").write_text(r.stdout[-20000:] + r.stderr[-20000:])
                print(f"{fid}: BUILD FAILED", flush=True)
                continue
            fw = wheel_files(next(wdir.glob("*.whl")))
            overlay = {n: b for n, b in fw.items() if clean.get(n) != b}
            shutil.rmtree(wdir)
        else:
            for p in f["files"]:
                if p.startswith("qiskit/") and p.endswith(".py"):
                    overlay[p] = (work / p).read_bytes()
        for n, b in overlay.items():
            t = dest / "overlay" / n
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(b)
        meta = dict(f, patch_sha256=sha(patch.read_bytes()),
                    overlay={n: sha(b) for n, b in sorted(overlay.items())})
        (dest / "fault.json").write_text(json.dumps(meta, indent=1))
        print(f"{fid}: overlay {len(overlay)} files", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
