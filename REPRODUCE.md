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

## Registration R2

Per Qiskit version (2.6.0, 2.3.1): build the wheelhouse, run the calibration session N with `obsaware/kaggle/nb_k1_calibration.ipynb` (rename its `out_k1` output to `out_N260` / `out_N231`), then, in a later, separate session, the labeling session with `obsaware/kaggle/nb_cohort_labeling.ipynb` (`COHORT = "C260"` / `"C231"`). Then:

```bash
python r2/analyze_r2.py --pair data/N260/out_N260 data/C260/out_C260 --pair data/N231/out_N231 data/C231/out_C231 --out results/registered_analysis_r2.json
python r2/freeze_r2.py --verify
```

## Two kinds of reproduction

- **Replaying the analyses** (minutes, any machine): every result in the paper is recomputed from the raw session files in `data/` and `casestudy/data/`. Costs are read from those files, so the machine does not matter. This is the path below.
- **Rerunning the experiments** (Kaggle CPU sessions, hours): regenerates the raw session files. Costs then depend on the machine. Follow `obsaware/kaggle/KAGGLE_RUNBOOK.md`. Exact package versions of each Kaggle session are in that session's wheelhouse dataset (`requirements_p3.txt`), archived in `environment/wheelhouses/<qiskit-version>.txt`.

## Replaying every result of the paper (from the repository root)

```bash
python -m pip install qiskit==2.4.2 numpy scipy pyyaml psutil pandas matplotlib
export PYTHONPATH="$PWD/cart/src:$PWD/obsaware/src"      # Windows PowerShell: $env:PYTHONPATH="$PWD/cart/src;$PWD/obsaware/src"
python r2/freeze_r2.py --verify                           # both manifests
python obsaware/scripts/analyze_p3.py --prev data/K1/out_k1 --cohort data/C261/out_C261 --cohort data/C252/out_C252 --out results/registered_analysis.json
python r2/analyze_r2.py --pair data/N260/out_N260 data/C260/out_C260 --pair data/N231/out_N231 data/C231/out_C231 --out results/registered_analysis_r2.json
python posthoc/diagnose_claim_c.py > posthoc/diagnose_claim_c.json
python posthoc/preview_cost_estimators.py > posthoc/preview_cost_estimators.json
python posthoc/exploratory_p3.py > posthoc/exploratory_p3.json
python posthoc/exploratory_p3_extra.py > posthoc/exploratory_p3_extra.json
python posthoc/exploratory_p3_denominator.py > posthoc/exploratory_p3_denominator.json
python reanalysis/reanalyze.py > reanalysis/reanalysis.json
python reanalysis/compare.py > reanalysis/comparison.json
python reanalysis/check_labels.py > reanalysis/label_checks.json
python casestudy/analyze.py > casestudy/results/case_study.json
python manuscript/gen/make_assets.py --repo . --exploratory posthoc/exploratory_p3.json
```

The case-study snapshots (`casestudy/data/<release>/`) are regenerated by running `casestudy/snapshot.py` once in a separate environment per Qiskit release (`pip install qiskit==<release> pyyaml`), as described in `casestudy/PROTOCOL_CASESTUDY.md`.
