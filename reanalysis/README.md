# Separate re-analysis (AI-assisted)

A second computation of Paper 3's registered claims A, B and C, for both registrations (`PREREGISTRATION_P3.md` and `PREREGISTRATION_P3_R2.md`), done on 2026-10-25 after both registered analyses.

**Independence and its limits.** `reanalyze.py` was written anew from the written definitions:
- the two registrations;
- the strategy descriptions in the docstring of `obsaware/src/obsaware/selection.py`.

It reads only the raw session files under `data/` and imports nothing from `obsaware/`, `r2/` or `cart/`. It was written by the same AI tool (Claude) that wrote the registered analysis code, so it is **not** an independent re-implementation by another team. Like Paper 2's checks, it is a separate re-analysis (AI-assisted).

**Details the registrations leave open.** The re-analysis follows the documented behaviour of the frozen implementation for these:
- **Unit order (output-only, all-checks):** an unused (family, backend, output tier) comes first, then lower estimated compile plus output-check cost, then unit id.
- **Fixed-order walk (output-only, all-checks):** an item whose estimated price does not fit is skipped, and the walk continues.
- **Greedy (observability, cheapest-items):** at each step, the remaining item that fits with the best rank is taken. Rank is an uncovered (family, backend, channel) first (observability only), then the lowest current estimated price, then (unit, check). The walk stops when no remaining item fits.
- **Item price:** the check's cost, plus the unit's compile cost if the unit is not yet paid, plus the determinism lane's opening cost if the lane is not yet open.
- **First-detection cost:** the unbudgeted ranking walked with real costs, up to and including the first detecting item.

## Files

| File | What it is |
|---|---|
| `reanalyze.py` → `reanalysis.json` | The separate computation of claims A to C, per event and per cohort, for both registrations |
| `compare.py` → `comparison.json` | Value-by-value comparison with `results/registered_analysis.json` and `results/registered_analysis_r2.json` |
| `check_labels.py` → `label_checks.json` | Consistency of the raw labeling data with the registered labeling rules E1 and L1 to L3, plus coverage of all 116 units, and no output-invisible event detected by the output check |

From the repository root (standard-library Python only):

```bash
python reanalysis/reanalyze.py > reanalysis/reanalysis.json
python reanalysis/compare.py > reanalysis/comparison.json
python reanalysis/check_labels.py > reanalysis/label_checks.json
```

## Result

| Registration | Cohort | Values compared | Differences | Claims (re-analysis) |
|---|---|---|---|---|
| First | C261 (Qiskit 2.6.1) | 529 | 0 | A yes, B yes, C no |
| First | C252 (Qiskit 2.5.2) | 529 | 0 | A yes, B yes, C no |
| R2 | C260 (Qiskit 2.6.0) | 529 | 0 | A yes, B yes, C yes |
| R2 | C231 (Qiskit 2.3.1) | 529 | 0 | A yes, B yes, C yes |

**What was compared.** Per cohort:
- the estimated full-suite cost;
- the number of events and of detectable events;
- the three claim decisions and the sign-test p-value;
- every event's detectability;
- detection and real spend ratio for each of 4 strategies at 3 budgets;
- every first-detection cost.

Equality means agreement to 1e-9 relative. Every value agreed.

Label consistency (`label_checks.json`): 4,212 checks per cohort, 16,848 in all, with 0 problems.

**Conclusion.** The separate computation reproduces both registered analyses exactly:
- **First registration:** A and B supported, C not supported.
- **R2:** A, B and C supported in both cohorts.
