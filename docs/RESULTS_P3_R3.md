# Registration R3: results

Registration: `PREREGISTRATION_P3_R3.md`, commit `198c867` (pushed 2026-10-29 13:26:14 UTC). Sessions: calibration N_R3 started 13:41:49 UTC and finished about 14:10 UTC (Kaggle: 1836 s); labeling R3 started 14:50:43 UTC (Kaggle: 4337 s). Both on Intel Xeon 2.20 GHz, Python 3.13.15, our Qiskit 2.6.1 build. Benchmark drift: at most 3.8% (N_R3) and 10.9% (R3), inside the registered 15% limit. Registered analysis: `r3/analyze_r3.py` -> `results/registered_analysis_r3.json`, run unchanged.

## Registered claims

| Claim | Decision | Detail |
|---|---|---|
| A3 | SUPPORTED by the script, **vacuously** | no event was detectable, so every strategy detected 0 of 0 |
| B3 | NOT SUPPORTED (**inconclusive**, 0 detectable events, fewer than the registered minimum of 5) | |
| C3 | **SUPPORTED** | OA mean real spend / budget 0.96 (2%), 0.98 (5%), 0.96 (10%); max 1.005 |
| D3 | NOT SUPPORTED | every strategy's equal-weight mean is 0 (OA's mean equals the others', but the script requires at least one detectable event) |

Full-suite estimate 1420.6 s; machine factor 1.005 (not applied). Faults 15, none excluded by E1, **0 detectable**.

**Main finding.** None of the 15 real faults changed the compiled output of any corpus unit. Every unit's candidate had the clean fingerprint and contract verdict, no candidate crashed or hung, and the determinism lane saw no new non-determinism. The faults were exercised (their changed functions run on the corpus, `r3/SELECTION.md`) but never revealed.

## Post hoc check that the faults were active (not registered)

`posthoc/r3_injection_check.py` ran each fix's own regression tests (added by the fix commit) with the clean build and with the fault overlay, outside Kaggle.

| Fault | Fix | Corpus units changed | Its own regression tests |
|---|---|---|---|
| #13945 | Fix composing virtual permutation layouts for `ElidePermutations` and  | 0 of 116 | 2/2 fail or hang on the fault |
| #14943 | Fix passmanager to preserve falsy pass outputs instead of reverting to | 0 of 116 | not collected |
| #15623 | Fix QPY bug with user-defined register named 'ancilla' (#15623) | 0 of 116 | 1/1 fail or hang on the fault |
| #16153 | Fix `InverseCancellation` for symmetric pairs (#16153) | 0 of 116 | 1/1 fail or hang on the fault |
| #16283 | Parameter expression bugfixes (#16283) | 0 of 116 | 9/9 fail or hang on the fault |
| #16402 | Fix incorrect global phase shift for P and U1 gates in CommutativeCanc | 0 of 116 | 1/1 fail or hang on the fault |
| #16476 | Fix cache and prediction misses in `Target::qargs` (#16476) | 0 of 116 | no regression test |
| #16599 | Fix `sx` resynthesis of negative angles in `CommutativeCancellation` ( | 0 of 116 | 1/1 fail or hang on the fault |
| #16637 | Fix transpiler error message with routing_pass when layout_trials or s | 0 of 116 | no regression test |
| #16656 | Fix non-determinism in `DAGCircuit::remove_qubits` (#16656) | 0 of 116 | 2/2 fail or hang on the fault |
| #16752 | Fix add/sub optimizations including the same symbols (#16752) | 0 of 116 | 1/1 fail or hang on the fault |
| #16884 | Fix non-identity removal in ConsolidateBlocks for gates wider than 2 q | 0 of 116 | 1/1 fail or hang on the fault |
| #16963 | Fix GIL deadlock in `CommutationAnalysis` with Python-defined gates (# | 0 of 116 | 1/2 fail or hang on the fault (the deadlock reproduces as a hang) |
| #16988 | Fix: `CouplingMap` storing parallel edges (#16988) | 0 of 116 | 3/3 fail or hang on the fault |
| #17163 | Fix correctness bugs `TwoQubitBasisDecomposer`  (#17163) | 0 of 116 | 2/5 fail or hang on the fault |

Every one of the 12 faults with a collectable regression test fails or hangs at least one of its own tests on the fault and passes all of them on the clean build (#14943's test was not collected by the runner; #16637 and #16476 have none). The injection therefore worked: the bugs were present but the corpus inputs do not reach the conditions that reveal them.
