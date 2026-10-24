# obsaware (Paper 3)

Imports `cart` (`../cart/src`) and never modifies it.

- `src/obsaware/oracles.py`: state probe (global phase and layout record), contract checker v2 (K0 to K3), raw fingerprint
- `src/obsaware/mutations.py`: the eight output-invisible fault operators
- `src/obsaware/determinism.py`: batched hash-seed determinism runner
- `src/obsaware/selection.py`: budgeted selection strategies over (unit, check) items
- `src/obsaware/cost_model.py`: cost estimate from an earlier session, with Paper 2's speed rule
- `src/obsaware/registry.py`, `src/obsaware/bench.py`: operator lookup, reference benchmark
- `scripts/`: `dev_check_operators.py`, `dev_eval.py` (development), `calibrate_costs.py` (session K1), `label_cohort.py` (cohort sessions), `analyze_p3.py` (registered analysis), `freeze_registration.py`, `make_kaggle_zip.py`
- `kaggle/`: `KAGGLE_RUNBOOK.md`, `build_wheelhouse.py`, notebooks
- `results/`: development results
