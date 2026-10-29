#!/usr/bin/env python3
"""R3: the wheelhouse for the R3 Kaggle sessions, built OFFLINE-COMPLETE outside Kaggle.

Qiskit is our own build of the 2.6.1 source (r3/BUILD.md: same toolchain, profile and features as every fault
build), not the PyPI wheel, so that clean and faulty Qiskit differ only by the fault. Every other package is
downloaded from PyPI for CPython 3.13 on manylinux x86_64. Writes requirements_p3.txt and MANIFEST.json in the
format of obsaware/kaggle/build_wheelhouse.py, so the frozen notebooks accept it.

    python r3/make_wheelhouse_r3.py --qiskit-wheel <our qiskit wheel> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AER = "0.18.0"
OTHERS = [f"qiskit-aer=={AER}", "numpy==2.5.4", "scipy==1.18.1", "pyyaml==6.0.3", "psutil==7.2.2", "pandas==3.1.0"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qiskit-wheel", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    qw = Path(a.qiskit_wheel)
    shutil.copy2(qw, out / qw.name)
    subprocess.run([sys.executable, "-m", "pip", "download", "--dest", str(out), "--only-binary=:all:",
                    "--python-version", "3.13", "--platform", "manylinux_2_28_x86_64", "--platform",
                    "manylinux2014_x86_64", "--platform", "manylinux_2_17_x86_64", "--platform", "manylinux_2_27_x86_64",
                    "--platform", "manylinux_2_24_x86_64", "--platform", "manylinux_2_12_x86_64",
                    "--platform", "manylinux2010_x86_64", "--platform", "linux_x86_64",
                    str(out / qw.name), *OTHERS], check=True)
    tmp = tempfile.mkdtemp()
    site = os.path.join(tmp, "site")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--find-links", str(out), "--target",
                    site, "qiskit==2.6.1", *OTHERS], check=True)
    pins = sorted(f"{d.metadata['Name']}=={d.version}" for d in md.distributions(path=[site]))
    (out / "requirements_p3.txt").write_text("\n".join(pins) + "\n")
    check = subprocess.run([sys.executable, "-c", "import qiskit, qiskit_aer; print(qiskit.__version__, qiskit_aer.__version__)"],
                           capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=site), check=True).stdout.strip()
    manifest = {
        "qiskit_requested": "2.6.1", "aer_requested": AER, "import_check": check,
        "qiskit_source": "built from the Qiskit 2.6.1 source tag (r3/BUILD.md), not the PyPI wheel",
        "python": platform.python_version(), "platform": platform.platform(),
        "install_method": "pip install --no-index --find-links <wheelhouse> --target <site>; PYTHONPATH=<site>",
        "files": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.glob("*.whl"))},
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=1), len(manifest["files"]), "wheels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
