# Results of the registered study (Paper 3)

Registration: `PREREGISTRATION_P3.md`, commit `40077ab` (pushed 2026-10-24, before any cohort data existed). Registered analysis: `obsaware/scripts/analyze_p3.py`, run unchanged on 2026-10-24. The manifest verified 85/85 frozen files before the run. Full output: `results/registered_analysis.json` and `.md`.

## Sessions

| Cohort | Qiskit | Kaggle session (UTC) | CPU | Benchmark drift (limit 15%) | Excluded operators (rule E1) | Clean false alarms | Clean non-determinism |
|---|---|---|---|---|---|---|---|
| C261 | 2.6.1 | 2026-10-24 14:32 to 17:47 | Intel Xeon @ 2.20GHz | 4.4% | none | none | none |
| C252 | 2.5.2 | 2026-10-24 11:03 to 14:01 | Intel Xeon @ 2.20GHz | 8.2% | none | none | none |

Both sessions labeled all 18 events on all 116 units. All 18 events were detectable in both cohorts.

## Registered claims

| Claim | C261 | C252 | Decision |
|---|---|---|---|
| **A** Detection at the 5% budget: observability > output-only, and at least as many as all-checks and cheapest-items | observability 18/18, output-only 9/18, all-checks 18/18, cheapest-items 16/18 | identical | **SUPPORTED** |
| **B** Earlier first detection (real cost) than all-checks, one-sided exact sign test p < 0.05 | 14 earlier, 4 later, 0 ties, p = 0.0154 | 14 earlier, 4 later, 0 ties, p = 0.0154 | **SUPPORTED** |
| **C** Real spend / budget: mean ≤ 1.25 and max ≤ 2.0 at the 2%, 5% and 10% budgets | mean 2.18 / 1.70 / 1.59, max 2.28 / 1.77 / 1.65 | mean 2.15 / 1.70 / 1.60, max 2.43 / 1.84 / 1.68 | **NOT SUPPORTED** |

Registered forecast for comparison: P(A) about 0.75, P(B) about 0.4, P(C) about 0.75.

Detection within budget, all strategies (events detected of 18, identical in both cohorts):

| Budget | Output-only | All checks | Observability-aware | Cheapest items |
|---|---|---|---|---|
| 2% | 9 | 15 | **18** | 16 |
| 5% | 9 | 18 | **18** | 16 |
| 10% | 10 | 18 | **18** | 18 |

At 5%, by event group: output-visible events (10): output-only 9, all others 10. Output-invisible events (8): output-only 0, all-checks 8, observability-aware 8, cheapest-items 6.

## Post hoc diagnosis of claim C (exploratory, not registered)

Script: `posthoc/diagnose_claim_c.py`; output: `posthoc/diagnose_claim_c.json`. Written after the registered analysis. Nothing here changes a registered decision.

- **Cause.** The registered speed rule estimates machine speed from baseline compile costs. Compilation in the cohorts cost 0.415 (C261) and 0.419 (C252) times its K1 cost, on the same CPU model. Oracle checks did not get cheaper: the median cohort/K1 ratio was 1.12 and 1.07 for the output check (12-qubit exact units) and 0.99 and 1.03 for the state probe. The reference benchmark ratio was 0.85 and 0.87. The drop in compile cost therefore reflects faster compilation in Qiskit 2.5 and 2.6, not a faster machine. The rule scaled every estimated cost, oracle costs included, by about 0.42, so the oracle checks were underpriced about 2.4-fold.
- **All strategies overspent**, not only the method. Mean spend / budget at 5%: output-only 1.45 (C261) and 1.44 (C252), all-checks 1.96 and 1.99, observability-aware 1.70 and 1.70, cheapest-items 1.66 and 1.69.
- **Claim A's pattern under real costs.** Each planned 5% selection was cut at the point where its real cost would exceed the budget. Events detected, the same in both cohorts: observability-aware 18, cheapest-items 16, all-checks 15, output-only 9.
- **Implication.** As in Paper 2, the estimate that failed is the cost model, not the ordering. Estimates must not transfer a transpiler-version speed-up to oracle costs. A speed rule based on the reference benchmark, or one that scales compile and oracle costs separately, is the obvious repair. Like any repair, it needs confirmation on fresh data.

## Not yet done

- An independent re-analysis that does not reuse `analyze_p3.py`.
- The case study on Paper 1B's nine historical faults.
