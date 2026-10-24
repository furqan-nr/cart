# Kaggle runbook (Paper 3)

How timing-sensitive Paper 3 runs are done on Kaggle. The rules behind it are in `PROJECT_INSTRUCTIONS.md`, section "Timing and Kaggle". Both notebooks below were dry-run end to end in a mock Kaggle layout before release.

## Datasets (made once, versioned)

| Dataset | Contents | How it is made |
|---|---|---|
| `p3-code` | `p3-code/cart/` and `p3-code/obsaware/` from this repository | From the repository root: `python obsaware/scripts/make_kaggle_zip.py --out ../p3-code.zip`, then upload the zip as a new dataset, or as a **new version** when the code changes. Record the zip's SHA-256 (printed by the tool) and the dataset version in `REGISTRATION_RECORD.md` |
| `p3-wheelhouse-qiskit-2-4-2` | Linux wheels for Qiskit 2.4.2, Qiskit Aer 0.17.2 and the other runtime packages, `requirements_p3.txt` (exact versions), `MANIFEST.json` (SHA-256 of every wheel) | Output of `nb_build_wheelhouse.ipynb` (below). One dataset per Qiskit version; the cohort wheelhouses (2.6.1, 2.5.2) are built only after the registration is pushed |

A virtual environment cannot move between machines, which is why the environment travels as a wheelhouse. Kaggle's system Python has no `ensurepip`, so notebooks do not create venvs either: they install the wheelhouse offline into a plain folder (`pip install --no-index --target /kaggle/working/site`) and put it first on `PYTHONPATH`, ahead of Kaggle's preinstalled packages.

## Notebook 1: `nb_build_wheelhouse.ipynb` (once per Qiskit version)

1. Kaggle, New Notebook, File, Import Notebook, choose `obsaware/kaggle/nb_build_wheelhouse.ipynb`.
2. Settings: Accelerator **None (CPU)**, **Internet ON**, Environment **Pin to original environment**.
3. Add Input: dataset `p3-code`.
4. Run All. It downloads the wheels, proves they install offline into a scratch folder, and writes `MANIFEST.json`. It takes a few minutes.
5. Save Version (Quick Save is enough), open the version's **Output** tab, choose **New Dataset**, name it `p3-wheelhouse-qiskit-2-4-2`.

## Notebook 2: `nb_k1_calibration.ipynb` (session K1)

Clean-baseline cost calibration of every check on the 116 corpus units under Qiskit 2.4.2. It runs **no fault operator**, so it computes no corpus detection label.

1. Import `obsaware/kaggle/nb_k1_calibration.ipynb`.
2. Settings: **CPU**, **Internet OFF** (shows the run used only the frozen inputs), **Pin to original environment**.
3. Add Inputs: `p3-code` and `p3-wheelhouse-qiskit-2-4-2`.
4. **Save Version, Save & Run All (Commit)**. You can close the browser. Expected time: 1 to 2 hours. The eight 12-qubit exact checks take minutes each.
5. When it has finished, download `out_k1.zip` from the version's Output tab and put it in `data/K1/` (done: `data/K1/out_k1.zip`).

**If it stops** (12-hour limit or a Kaggle error): add the stopped version's output as an extra input and run again. The notebook finds `out_k1/units` and skips the units already measured.

What the notebook does: installs the wheelhouse offline into `/kaggle/working/site`, pins the kernel and every child process to one core (`taskset`), sets single-thread environment variables, records the CPU model, Python and image, then runs `obsaware/scripts/calibrate_costs.py`. That script measures in a shuffled unit order (registered seed 20261023), runs the reference benchmark at the start, every 10 units and at the end, and writes one JSON file per unit.

## Notebook 3: `nb_cohort_labeling.ipynb` (cohorts C261 and C252, only after the registration push)

1. Build the cohort's wheelhouse with Notebook 1, setting `QISKIT` to `2.6.1` (or `2.5.2`) and `AER` to the latest Qiskit Aer release that installs with it, and save it as `p3-wheelhouse-qiskit-2-6-1` (or `-2-5-2`).
2. Import `obsaware/kaggle/nb_cohort_labeling.ipynb`, set `COHORT` and `QISKIT` in the first cell (`C261` / `2.6.1` or `C252` / `2.5.2`).
3. Settings: **CPU**, **Internet OFF**, **Pin to original environment**. Inputs: `p3-code` (the registered version) and the cohort's wheelhouse.
4. **Save & Run All (Commit)**. Expected time 3 to 5 hours. Resumable as for K1.
5. Download `out_<COHORT>.zip` into `data/<COHORT>/` and record the run in `REGISTRATION_RECORD.md`.
