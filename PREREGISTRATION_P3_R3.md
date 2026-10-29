# Pre-registration R3: real Qiskit faults with measured costs (Paper 3)

**Status:** approved by the authors on 2026-10-29. Becomes a registration when this file and the files listed in `PREREGISTRATION_P3_R3.sha256` are pushed to https://github.com/furqan-nr/cart, before any R3 session has run. Push times are recorded in `REGISTRATION_RECORD.md` (not frozen).

**Authors:** Furqan Nasir (CUSIT; FAST-NUCES), Muhammad Arif Shah (CUSIT), Iftikhar Alam (CUSIT).

## 1. Why a third registration

R1 and R2 (`PREREGISTRATION_P3.md`, `PREREGISTRATION_P3_R2.md`) tested the framework on 18 injected fault operators that we wrote. Two limits remain, raised in internal and external review:
1. **The faults were ours.** The operators were written for this study, several were gated on facts of the corpus, and the coverage key's channels are the channels for which operators were written.
2. **The strongest simple alternatives were not registered comparators.** These are cost-aware all-checks (AC-cost) and cheapest-items with the determinism lane opened first (CH-lane-first). Both were only compared in exploratory analyses.

R3 keeps every check, the corpus, the strategies, the cost estimate (R2's) and the accounting. It changes the events and adds the two comparators:
- **Real faults.** Each event is a real Qiskit bug. A merged fix is reverted on Qiskit 2.6.1, so the faulty Qiskit differs from the clean one by exactly that bug (the idea of the Defects4J benchmark).
- **Selection rule.** The faults were selected by a rule that uses only the fixes and clean-Qiskit coverage, never a check result (`r3/SELECTION.md`).
- **Comparators.** AC-cost and CH-lane-first are registered comparators (`r3/strategies_r3.py`).

## 2. What changes, and what does not

**Changed.**
- **Events: 15 real faults** (`r3/faults.json`): 5 with Python changes only and 10 with Rust changes.
  - **Python-only faults:** the reverted Python files.
  - **Faults with Rust changes:** a wheel built from the reverted source. The fault's overlay is every file of that wheel that differs from the clean wheel (`r3/make_faults.py`).
  - Overlay hashes: `r3/fault_overlays.sha256`.
- **Qiskit build.** All R3 sessions use our build of the Qiskit 2.6.1 source (`r3/BUILD.md`), not the PyPI wheel, so that clean and faulty Qiskit differ only by the fault. Before registration, this build compiled the 116 corpus units to the same fingerprints as the PyPI 2.6.1 wheel (116 of 116). The wheelhouse's hashes are in `r3/wheelhouse.sha256`.
- **Labeling driver `r3/label_faults.py`.** It follows `obsaware/scripts/label_cohort.py` (rules L1 and L2, costs, determinism lane) with four differences:
  - **Separate interpreter.** Candidate compilations run in an interpreter with the fault's Qiskit first on the path, and are returned pickled. Every check runs in the clean interpreter.
  - **Rule E1 becomes an import check.** A fault whose Qiskit does not import is excluded and reported.
  - **Crash and hang rule.** If the fault's interpreter dies, or the batch exceeds 3 times the clean compile time plus 600 s, every unit is recompiled in its own interpreter with a limit of 10 times its clean compile time plus 60 s. A unit whose interpreter dies or exceeds the limit is a crash, which every check of that unit observes. A determinism launch exceeding 3 times the clean compile time plus 600 s, or dying, makes the lane observe the failure on the units whose candidate crashed.
  - **Event order:** seed 20261029.
- **Comparators added:** AC-cost and CH-lane-first (Section 5).
- **Claims:** A3 to D3 (Section 5).

**Unchanged** (pinned through R2's manifest, which this manifest pins):
- the corpus (116 units);
- the checks: output, quality, probe, contract, and the determinism lane with hash seeds 0, 1, 2;
- the strategies output-only (OO), all-checks (AC), observability-aware (OA), cheapest-items (CH) and random items;
- R2's cost estimate (a separate calibration session of the same Qiskit) and machine rule M1;
- the budgets (fractions of the estimated full suite), the real-cost accounting, the first-detection cost and the one-sided exact sign test;
- the session-quality rule (benchmark drift above 15% at any reading triggers a rerun).

## 3. Disclosure: what is known before registration

1. Everything disclosed in R1 and R2, and all their data and results. This includes the exploratory analyses (`posthoc/exploratory_p3*.py`), which showed:
   - OA selects the same items as CH-lane-first at budgets of 1% and more in all four earlier cohorts;
   - OA's detection lead over AC lies within a band of budgets.
2. **The case study** (`casestudy/`) on six historical Qiskit faults, all excluded from R3 (rule 3 of `r3/SELECTION.md`).
3. **Fault selection.**
   - **What was read:** the subjects of all 154 mined fix commits. We read the patches of the 15 selected faults only to revert and build them.
   - **What was not done:** no fault build has compiled a corpus unit, no check has run on a fault, and no fault's effect on any circuit has been observed.
   - **Exercise coverage:** the selection measured which changed functions the clean Qiskit runs on the corpus (Python line coverage, Rust probes). It says nothing about whether a fault changes an output.
4. **Builds.** All 15 faults were built and pass an import check. Building does not compile any circuit.
5. **Dry runs of `r3/label_faults.py`** used only a null fault (an empty overlay) and an artificial crashing fault, on units of at most five qubits. Their outputs are not used.

## 4. Sessions

| Session | What | Qiskit |
|---|---|---|
| N_R3 | calibration (estimate): `obsaware/kaggle/nb_k1_calibration.ipynb`, unchanged, with the R3 wheelhouse; output `out_k1` renamed `out_NR3` | our 2.6.1 build |
| R3 | labeling: `r3/kaggle/nb_r3_labeling.ipynb` with the R3 code, wheelhouse and fault datasets | our 2.6.1 build plus each fault |

Order:
- N_R3 runs to completion before R3 starts, as a separate Kaggle session on the same CPU class.
- Both sessions use the code dataset made by `r3/make_kaggle_zip_r3.py` from the registered commit. Its SHA-256 is recorded in `REGISTRATION_RECORD.md`.

## 5. Strategies and claims (decided by `r3/analyze_r3.py`, frozen)

**Strategies.**
- **Observability-aware (OA), the framework's selector:** unchanged.
- **Observability-blind comparators** (they do not use which channel a check observes):
  - output-only (OO);
  - all-checks (AC);
  - **AC-cost**: all-checks with units in order of their full estimated cost;
  - cheapest-items (CH).
- **Reported only:** CH-lane-first and random items. CH-lane-first uses one piece of observability knowledge, namely that the determinism channel needs its own lane, so it is not an observability-blind comparator.

**Terms.**
- **Events:** the 15 faults, minus any excluded by E1.
- **Detectable:** an event is detectable if some item of the full suite detects it under rule L1.

**Claims.** Each is decided on the single R3 cohort.
- **A3 (detection at the registered budget):** at the 5% budget, the number of detectable events OA detects is at least the number detected by each of OO, AC, AC-cost and CH.
- **B3 (earlier detection):** OA reaches its first detection at lower real cost than AC on more detectable events than not, with a one-sided exact sign test p < 0.05. With fewer than 5 detectable events, B3 is **inconclusive** and counted as not supported.
- **C3 (budget compliance):** OA's real spend divided by the budget has mean ≤ 1.25 and maximum ≤ 2.0 over all events, at each of 2%, 5% and 10%.
- **D3 (detection across budgets):** over the grid 0.25%, 0.5%, 0.75%, 1%, 1.5%, 2%, 3%, 5%, 7.5% and 10%, with each budget weighted equally, OA's mean number of detectable events detected is at least that of each of OO, AC, AC-cost and CH.

**Reported without decision:**
- first-detection sign tests of OA against AC-cost, CH, CH-lane-first and OO;
- detection of every strategy at every grid budget;
- per-fault detail: the checks and units that detect it, and crashes.

## 6. Forecast (registered judgement)

- **Detectable events: about 5 to 9 of the 15.** Being exercised does not imply a changed output. Some fixes concern conditions the corpus may not meet, such as Python-defined gates or a routing pass with explicit trial counts. One concerns performance only (#16476).
- **P(A3 supported):** about 0.7. At 5%, the earlier cohorts' observability-blind strategies other than OO detected most events, and ties satisfy A3.
- **P(B3 supported):** about 0.4. The direction is expected from AC's early lane cost, but with 5 to 9 events the test has low power.
- **P(C3 supported):** about 0.75, as in R2.
- **P(D3 supported):** about 0.5. In the R2 cohorts the equal-weight margins over AC-cost and CH were 0.1 to 0.6 events.

## 7. Deviations

As in R1 and R2. A deviation is reported with its reason. No result is reported without the registered analysis.
