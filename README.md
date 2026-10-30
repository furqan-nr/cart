# cart: observability-aware, cost-aware regression testing for the Qiskit transpiler (Paper 3)

Code, registration, data and reproduction recipes for Paper 3 of Furqan Nasir's doctoral research (CUSIT): a pre-registered study of whether a regression-testing pipeline for a quantum compiler, which chooses within a CI budget both **which tests** to run and **which oracle** each test gets, detects more transpiler regressions than output-only and naive all-oracle selection.

**Status:** registered (commit `40077ab`, 2026-10-24) and run. Both cohorts labeled; registered analysis complete: claims A and B SUPPORTED, claim C NOT SUPPORTED. See `docs/RESULTS_P3.md` (with a post hoc diagnosis of claim C, clearly separated). A second registration, `PREREGISTRATION_P3_R2.md` (files in `r2/`), changes only the cost estimate (previous-revision costs from a separate calibration session) and re-tests claims A to C on fresh cohorts (Qiskit 2.6.0 and 2.3.1). **R2 result: claims A, B and C all SUPPORTED in both cohorts** (`docs/RESULTS_P3_R2.md`).

**Registration R3** (`PREREGISTRATION_P3_R3.md`, files in `r3/`): real Qiskit faults re-injected into Qiskit 2.6.1, with measured costs. None of the 15 faults changed any corpus compilation (`docs/RESULTS_P3_R3.md`; diagnosis in `docs/R3_DIAGNOSIS.md`). R3 is reported in Paper 4 (in preparation), not in Paper 3.

## Layout

| Path | Contents |
|---|---|
| `PREREGISTRATION_P3.md` | The registration: question, disclosures, cohorts, rules, strategies, claims A to C, forecast |
| `PREREGISTRATION_P3.sha256` | SHA-256 of every frozen file (`obsaware/scripts/freeze_registration.py`) |
| `PREREGISTRATION_P3_R2.md`, `PREREGISTRATION_P3_R2.sha256`, `r2/` | Registration R2: the repaired cost estimate, its frozen analysis and manifest (`r2/freeze_r2.py --verify` also checks the first manifest) |
| `REGISTRATION_RECORD.md` | Commit and push times of the registration and of every later run (not frozen) |
| `cart/` | The `cart` prototype from the Paper 2 replication package ([Quantum-Selection](https://github.com/furqan-nr/Quantum-Selection), DOI [10.5281/zenodo.23475857](https://doi.org/10.5281/zenodo.23475857)), copied unchanged: `src/cart`, `configs`, `pyproject.toml`, `environment/requirements.lock` |
| `obsaware/` | Paper 3 code: `src/obsaware` (state probe, contract checker v2, determinism runner, invisible-channel fault operators, selection strategies, cost model, reference benchmark), `scripts/` (development checks, Kaggle calibration and labeling drivers, frozen analysis, manifest and packaging tools), `kaggle/` (notebooks and runbook), `results/` (development results) |
| `data/K1/` | Kaggle session K1 output as downloaded (`out_k1.zip`) and extracted (`out_k1/`): clean-baseline costs of every check on the 116 corpus units, Qiskit 2.4.2 |
| `data/C261/`, `data/C252/` | Cohort labeling sessions (Qiskit 2.6.1 and 2.5.2), zip as downloaded and extracted |
| `data/N260/`, `data/N231/`, `data/C260/`, `data/C231/` | Registration R2: calibration sessions (estimate) and labeling sessions (claims), Qiskit 2.6.0 and 2.3.1 |
| `results/` | Registered analysis output |
| `reanalysis/` | Separate re-analysis (AI-assisted) of both registrations from the raw data, value-by-value comparison (0 differences) and label-rule checks |
| `posthoc/` | Post hoc (exploratory): diagnosis of R1's claim C, estimator preview, exploratory analyses of the paper (`exploratory_p3.py`, `exploratory_p3_extra.py`, `exploratory_p3_denominator.py`) |
| `casestudy/` | Historical-fault case study: hashed protocol, snapshot and analysis scripts, per-release data, results (`CASE_STUDY_RESULTS.md`), scoping notes |
| `manuscript/gen/` | Script that generates every table and figure of the paper from this repository |
| `docs/` | `RESULTS_P3.md`, `RESULTS_P3_R2.md`, `K1_REPORT.md`, `OBSERVATIONS.md` (development observations O1 and O2), `o1_repro.py` |
| `REPRODUCE.md` | The single authoritative path to reproduce every result in this repository |

## Use of AI tools

Claude (Anthropic), a large language model, was used through the Claude desktop application in October 2026. It wrote most of the `obsaware` code, the Kaggle notebooks and drivers, the analysis and packaging scripts, and drafted the registration and documentation. The authors made the study-design decisions, ran every Kaggle session, approve and push the registration themselves, and review the code, results and text. They take full responsibility for the content.

## License and citation

MIT (see `LICENSE`). Citation metadata: `CITATION.cff`.
