# Results of registration R2 (Paper 3)

Registration: `PREREGISTRATION_P3_R2.md`, commit `504533e` (pushed 2026-10-24, before any R2 data existed). The only change from the first registration is the cost estimate: previous-revision costs from a separate calibration session N on the same Qiskit version, with machine rule M1. Registered analysis: `r2/analyze_r2.py`, run unchanged on 2026-10-25. Both manifests verified before the run (R2 7/7, first registration 85/85). The analysis was run twice, from a clean clone of the registered commit and on the authors' machine, and gave identical results (floating-point differences below 1e-9 relative). Full output: `results/registered_analysis_r2.json` and `.md`.

## Sessions (Kaggle, Intel Xeon @ 2.20GHz, UTC)

| Session | Qiskit | Role | Start | End | Benchmark drift (limit 15%) | Notes |
|---|---|---|---|---|---|---|
| N260 | 2.6.0 | calibration (estimate) | 2026-10-24 19:40:18 | 20:07:00 | 1.8% | 116 units, no clean false alarm, deterministic |
| C260 | 2.6.0 | labeling (claims) | 20:25:25 | 23:36:26 | 10.7% | 18/18 events, no operator excluded, no clean false alarm |
| N231 | 2.3.1 | calibration (estimate) | 19:52:34 | 20:23:03 | 3.7% | 116 units, no clean false alarm, deterministic |
| C231 | 2.3.1 | labeling (claims) | 20:29:07 | 2026-10-25 00:03:23 | 3.2% | 18/18 events, no operator excluded, no clean false alarm |

Registered order respected: each calibration session finished before its labeling session started. Machine factor (benchmark ratio C/N): 1.045 (C260) and 1.038 (C231), inside [0.85, 1.15], so not applied.

## Registered claims

| Claim | C260 (Qiskit 2.6.0) | C231 (Qiskit 2.3.1) | Decision |
|---|---|---|---|
| **A** Detection at the 5% budget: observability > output-only, and at least as many as all-checks and cheapest-items | observability 18/18, output-only 10, all-checks 18, cheapest-items 16 | observability 18/18, output-only 9, all-checks 18, cheapest-items 16 | **SUPPORTED** |
| **B** Earlier first detection than all-checks (one-sided exact sign test p < 0.05) | 14 earlier, 4 later, p = 0.0154 | 13 earlier, 5 later, p = 0.0481 | **SUPPORTED** |
| **C** Real spend / budget: mean ≤ 1.25 and max ≤ 2.0 at 2%, 5% and 10% | mean 1.14 / 1.06 / 1.07, max 1.21 / 1.12 / 1.12 | mean 1.13 / 1.07 / 1.02, max 1.20 / 1.12 / 1.07 | **SUPPORTED** |

Registered forecast: P(A) about 0.85, P(B) about 0.7, P(C) about 0.7. Claim B in C231 passed with p = 0.048, close to the threshold.

Detection within budget (events detected of 18):

| Budget | Output-only | All checks | Observability-aware | Cheapest items |
|---|---|---|---|---|
| 2% | 9 (both cohorts) | 15 (both) | **18 (both)** | 16 (both) |
| 5% | 10 (C260), 9 (C231) | 18 | **18** | 16 |
| 10% | 10 | 18 | **18** | 18 |

At 5%: output-visible events (10) were detected by every strategy except output-only in C231 (9). Output-invisible events (8): output-only 0, all-checks 8, observability-aware 8, cheapest-items 6.

Mean real spend / budget at 5% for every strategy (exploratory): output-only 1.08 / 1.03, all-checks 1.08 / 1.08, observability-aware 1.06 / 1.07, cheapest-items 1.01 / 1.00 (C260 / C231). With the previous-revision estimate, every strategy stays close to its budget.

## Paper 3 in one place

| Registration | Cost estimate | Cohorts | A | B | C |
|---|---|---|---|---|---|
| First (`40077ab`) | earlier session (K1, Qiskit 2.4.2) x compile-based speed factor | 2.6.1, 2.5.2 | supported | supported | **not supported** (spend 1.6 to 2.2x; cause: the speed rule read a Qiskit compile speed-up as machine speed) |
| R2 (`504533e`) | previous-revision costs, same Qiskit version, separate session | 2.6.0, 2.3.1 | supported | supported | **supported** (spend 1.02 to 1.14x on average, at most 1.21x) |
