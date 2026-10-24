"""Build the Paper 3 wheelhouse INSIDE a Kaggle CPU notebook (Internet ON), then save the output as a Dataset.

Usage in a notebook cell:
    QISKIT = "2.4.2"; AER = "0.17.2"
    exec(open("<p3-code>/obsaware/kaggle/build_wheelhouse.py").read())

Writes /kaggle/working/wheelhouse/ with all wheels, requirements_p3.txt (the exact versions) and MANIFEST.json.

Kaggle's system Python has no ensurepip, so no virtual environment is created. Completeness is proved by an
OFFLINE install into a plain target folder (pip install --no-index --target), which is also how every experiment
notebook installs the environment.
"""
import hashlib
import importlib.metadata as md
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

QISKIT = globals().get("QISKIT", "2.4.2")
AER = globals().get("AER", "0.17.2")
OUT = globals().get("WHEELHOUSE_OUT", "/kaggle/working/wheelhouse")

TOP_LEVEL = [f"qiskit=={QISKIT}", f"qiskit-aer=={AER}", "numpy", "scipy", "pyyaml", "psutil", "pandas"]

os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "download", "--dest", OUT, "--only-binary=:all:", *TOP_LEVEL],
               check=True)

# Offline install into a scratch target folder to prove the wheelhouse is complete, then record exact versions.
tmp = tempfile.mkdtemp()
site = os.path.join(tmp, "site")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--find-links", OUT,
                "--target", site, *TOP_LEVEL], check=True)
pins = sorted(f"{d.metadata['Name']}=={d.version}" for d in md.distributions(path=[site]))
open(os.path.join(OUT, "requirements_p3.txt"), "w").write("\n".join(pins) + "\n")
check = subprocess.run([sys.executable, "-c", "import qiskit, qiskit_aer; print(qiskit.__version__, qiskit_aer.__version__)"],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=site), check=True).stdout.strip()

manifest = {
    "qiskit_requested": QISKIT, "aer_requested": AER, "import_check": check,
    "python": platform.python_version(), "platform": platform.platform(),
    "cpu": subprocess.run(["bash", "-lc", "grep -m1 'model name' /proc/cpuinfo"], capture_output=True,
                          text=True).stdout.strip(),
    "install_method": "pip install --no-index --find-links <wheelhouse> --target <site>; PYTHONPATH=<site>",
    "files": {f: hashlib.sha256(open(os.path.join(OUT, f), "rb").read()).hexdigest()
              for f in sorted(os.listdir(OUT)) if f.endswith(".whl")},
}
json.dump(manifest, open(os.path.join(OUT, "MANIFEST.json"), "w"), indent=1)
shutil.rmtree(tmp, ignore_errors=True)
assert check.split()[0] == QISKIT, f"import check returned {check!r}, expected Qiskit {QISKIT}"
print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=1), len(manifest["files"]), "wheels")
print("pins:", ", ".join(pins))
