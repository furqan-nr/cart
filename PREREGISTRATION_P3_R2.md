# Pre-registration R2: the observability-aware framework with a previous-revision cost estimate (Paper 3)

**Status:** becomes a registration when this file and the files listed in `PREREGISTRATION_P3_R2.sha256` are pushed to https://github.com/furqan-nr/cart, before any data of the cohorts named in Section 4 exist. Push times are recorded in `REGISTRATION_RECORD.md` (not frozen).

**Authors:** Furqan Nasir (CUSIT; FAST-NUCES), Muhammad Arif Shah (CUSIT), Iftikhar Alam (CUSIT).

## 1. Why a second registration

The first registration (`PREREGISTRATION_P3.md`, commit `40077ab`) was run on cohorts C261 (Qiskit 2.6.1) and C252 (Qiskit 2.5.2). Results (`docs/RESULTS_P3.md`):
- Claims A (detection within budget) and B (earlier first detection) were **supported** in both cohorts.
- Claim C (real spend within budget) was **not supported**: mean spend was 1.6 to 2.2 times the budget.

A post hoc diagnosis (`posthoc/diagnose_claim_c.py`) traced the failure to the cost estimate. Its compile-based speed rule read a Qiskit 2.5/2.6 compilation speed-up (cost ratio about 0.42) as machine speed and underpriced oracle checks about 2.4-fold. Every strategy overspent.

R2 changes **only the cost estimate** and tests the same three claims, with the same thresholds, on fresh cohorts. The first registration and its results stand unchanged.

## 2. What changes, and what does not

**Changed.**
- **Estimator T2 (previous-revision costs).** A cohort's cost estimate is the per-(unit, check) cost table from a **separate calibration session N** on the same Qiskit version. N is run before the cohort's labeling session with `obsaware/scripts/calibrate_costs.py` (no fault operator). This stands for what a CI system knows from a full run of the base revision on its own runners, such as a nightly run.
- **Machine rule M1.** k = median reference benchmark of the labeling session / median reference benchmark of session N. Every estimated cost is multiplied by k only if k lies outside [0.85, 1.15]. The compile-based speed rule is not used.
- **Implementation.** `r2/analyze_r2.py` implements the changes. Everything else is imported from `obsaware/scripts/analyze_p3.py`.

**Unchanged** (all pinned by the first manifest, which R2's manifest pins):
- the corpus (116 units) and the 18 operators;
- the checks;
- labeling rules E1 and L1 to L3 and the labeling driver `obsaware/scripts/label_cohort.py`;
- the notebooks `obsaware/kaggle/nb_k1_calibration.ipynb` (used for the N sessions) and `obsaware/kaggle/nb_cohort_labeling.ipynb`;
- the strategies and budgets (2%, 5%, 10% of the estimated full observability-aware suite);
- the real-cost accounting, the first-detection cost and the sign test;
- claims A to C and their thresholds;
- the session-quality rule (benchmark drift above 15% at any reading triggers a rerun).

## 3. Disclosure: what is known before registration

1. Everything disclosed in the first registration (Section 2 there).
2. The first registration's full cohort data and results: `data/C261`, `data/C252`, `results/registered_analysis.json`, `docs/RESULTS_P3.md`, `posthoc/diagnose_claim_c.*`.
3. **The estimator preview** (`posthoc/preview_cost_estimators.py` and `.json`), run on C261 and C252 before this registration. Mean / max observability spend at the 2%, 5% and 10% budgets:

   | Estimator | C261 | C252 |
   |---|---|---|
   | first registration (failed) | 2.18 / 1.70 / 1.59 (max 2.28) | 2.15 / 1.70 / 1.60 (max 2.43) |
   | T1 (component-wise scaling) | 1.32 / 1.23 / 1.16 (max 1.37) | 1.28 / 1.21 / 1.15 (max 1.43) |
   | T2 from the same session | 1.05 / 1.01 / 1.00 (max 1.09) | 1.07 / 1.00 / 1.01 (max 1.21) |

   T2 was chosen because of this preview. The same-session T2 is **optimistic**: the same measurement served as estimate and charge for unchanged candidates. R2 therefore draws the estimate from a separate session.
4. **No contact with the R2 cohorts:** no corpus unit has been compiled and no operator built or run on Qiskit 2.6.0 or 2.3.1. The only contact with either version is observation O1's check, which compiled one plain non-corpus circuit with no operator on Qiskit 2.3.1 (`docs/OBSERVATIONS.md`).

## 4. Cohorts and sessions

| Version | Calibration session (estimate) | Labeling session (claims) |
|---|---|---|
| Qiskit 2.6.0 | N260 | C260 |
| Qiskit 2.3.1 | N231 | C231 |

- **Qiskit Aer:** the latest release installable with each Qiskit version, fixed in the wheelhouse manifest.
- **Order:** for each version, the wheelhouse is built after the registration push. Session N runs to completion (Kaggle, `nb_k1_calibration.ipynb` with only that version's wheelhouse attached; its `out_k1` output is renamed `out_N260` / `out_N231`). Only then does session C start, as a separate Kaggle session (`nb_cohort_labeling.ipynb` with `COHORT = "C260"`, `QISKIT = "2.6.0"`, or `C231` / `2.3.1`).
- **Version check:** the analysis asserts that N and C report the same Qiskit version.
- **Separate analysis:** cohorts are analysed separately and never pooled.

## 5. Claims (decided by `r2/analyze_r2.py`, frozen)

Identical to the first registration (Section 8 there), with the estimate of Section 2. Each claim is **SUPPORTED only if it holds in both R2 cohorts**:
- **A:** at the 5% budget, the number of detectable events detected satisfies:
  - observability > output-only;
  - observability ≥ all-checks;
  - observability ≥ cheapest-items.
- **B:** observability reaches its first detection at lower real cost than all-checks on more events than not, one-sided exact sign test p < 0.05.
- **C:** observability's real spend / budget has mean ≤ 1.25 and max ≤ 2.0 over all analysed events, at each of the 2%, 5% and 10% budgets.

## 6. Forecast (registered judgement)

- **P(A supported):** about 0.85.
- **P(B supported):** about 0.7.
- **P(C supported):** about 0.7.

A and B are largely predictable from the first registration's cohorts. The operators are the same, the Qiskit versions are close, and the result was identical in C261 and C252. C is the main new test: it depends on how well a separate session's costs transfer to the labeling session. On the same CPU class, oracle costs moved by 0.99 to 1.12 times between K1 and the first cohorts, and the reference benchmark moved by up to 15% between sessions. Qiskit 2.3.1 may break an operator's construction (rule E1), which reduces the event count.

## 7. Deviations

As in the first registration. A deviation is reported with its reason. No result is reported without the registered analysis.
