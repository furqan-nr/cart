# Reproducing the results

All commands run from the repository root with Python 3.11 or later.

## Environment

```bash
python -m pip install qiskit==2.4.2 qiskit-aer==0.17.2 numpy scipy pyyaml psutil pandas
export PYTHONPATH="$PWD/cart/src:$PWD/obsaware/src"
export RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 QISKIT_IN_PARALLEL=TRUE
```

`cart` reads its configuration files relative to its own folder, so run scripts with the working directory set to `cart/` (as below) or from the repository root with `PYTHONPATH` as above. Exact versions of the Paper 2 environment: `cart/environment/requirements.lock`. Exact versions of each Kaggle session: the `requirements_p3.txt` in that session's wheelhouse dataset.

## Development results (`obsaware/results/`, exploratory)

```bash
cd cart
python ../obsaware/scripts/dev_check_operators.py    # operator checks on the 48-circuit development set
python ../obsaware/scripts/dev_eval.py               # development evaluation of the strategies
```

Both write to `obsaware/results/`. They contain no timing claim. Their costs are those of the machine they run on.

**Note:** these two files were produced before the probe tolerance change described in `docs/K1_REPORT.md`. `dev_check_operators.py` was rerun with the current code on 24 Oct 2026 and gave the same detections. `dev_eval.py` has not been rerun since the change. Costs differ by machine.

## Session K1: clean-baseline cost calibration (`data/K1/`)

On Kaggle, following `obsaware/kaggle/KAGGLE_RUNBOOK.md`: build the code dataset (`python obsaware/scripts/make_kaggle_zip.py --out ../p3-code.zip`), then the Qiskit 2.4.2 wheelhouse (`obsaware/kaggle/nb_build_wheelhouse.ipynb`), then run `obsaware/kaggle/nb_k1_calibration.ipynb`. Costs are machine-dependent. Clean verdicts and determinism are not. Locally:

```bash
cd cart && python ../obsaware/scripts/calibrate_costs.py --out /tmp/out_k1
```

## Confirmatory cohorts (after registration)

For each cohort (C261: Qiskit 2.6.1, C252: Qiskit 2.5.2): build its wheelhouse, then run `obsaware/kaggle/nb_cohort_labeling.ipynb` with `COHORT` and `QISKIT` set. Outputs go to `data/C261/` and `data/C252/`.

## Registered analysis

```bash
python obsaware/scripts/analyze_p3.py --prev data/K1/out_k1 --cohort data/C261/out_C261 --cohort data/C252/out_C252 --out results/registered_analysis.json
```

## Verifying the frozen files

```bash
python obsaware/scripts/freeze_registration.py --verify
```

## Post hoc diagnosis of claim C (exploratory)

```bash
PYTHONPATH=cart/src:obsaware/src python posthoc/diagnose_claim_c.py > posthoc/diagnose_claim_c.json
```
