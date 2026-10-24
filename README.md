# cart: observability-aware, cost-aware regression testing for the Qiskit transpiler (Paper 3)

Code, registration, data and reproduction recipes for Paper 3 of Furqan Nasir's doctoral research (CUSIT): a pre-registered study of whether a regression-testing pipeline for a quantum compiler, which chooses within a CI budget both **which tests** to run and **which oracle** each test gets, detects more transpiler regressions than output-only and naive all-oracle selection.

**Status:** registered (commit `40077ab`, 2026-10-24) and run. Both cohorts labeled; registered analysis complete: claims A and B SUPPORTED, claim C NOT SUPPORTED. See `docs/RESULTS_P3.md` (with a post hoc diagnosis of claim C, clearly separated). A second registration, `PREREGISTRATION_P3_R2.md` (files in `r2/`), changes only the cost estimate (previous-revision costs from a separate calibration session) and re-tests claims A to C on fresh cohorts (Qiskit 2.6.0 and 2.3.1).

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
| `results/` | Registered analysis output |
| `posthoc/` | Post hoc (exploratory) diagnosis of claim C, script and output |
| `docs/` | `RESULTS_P3.md`, `K1_REPORT.md`, `OBSERVATIONS.md` (development observations O1 and O2), `o1_repro.py` |
| `REPRODUCE.md` | How to reproduce every result in this repository |

## Use of AI tools

Claude (Anthropic), a large language model, was used through the Claude desktop application in October 2026. It wrote most of the `obsaware` code, the Kaggle notebooks and drivers, the analysis and packaging scripts, and drafted the registration and documentation. The authors made the study-design decisions, ran every Kaggle session, approve and push the registration themselves, and review the code, results and text. They take full responsibility for the content.

## License and citation

MIT (see `LICENSE`). Citation metadata: `CITATION.cff`.
