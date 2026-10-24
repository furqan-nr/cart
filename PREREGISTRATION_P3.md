# Pre-registration: observability-aware, cost-aware regression test selection for the Qiskit transpiler (Paper 3)

**Status:** DRAFT, not yet registered. It becomes a registration only when this file and the files listed in `PREREGISTRATION_P3.sha256` are pushed to the public repository https://github.com/furqan-nr/cart, before any cohort data exist. The commit and push times are then recorded in `REGISTRATION_RECORD.md` (not part of the frozen manifest), so this file never changes after the push.

**Authors:** Furqan Nasir (CUSIT; FAST-NUCES), Muhammad Arif Shah (CUSIT), Iftikhar Alam (CUSIT).

## 1. Question

Can a regression-testing pipeline for a quantum compiler, which chooses within a CI budget both **which tests** to run and **which oracle** each test gets, detect more transpiler regressions than output-only selection and naive all-oracle selection, while staying within the budget in real seconds?

Relation to the thesis: Proposal v3.1 (RQ1 to RQ4) is answered by Papers 1A, 1B and 2. This study is additional work beyond the proposal's RQs. Its RQ4 is a feasibility check without a comparative claim, and the comparison registered here goes beyond it.

## 2. What exists before registration (disclosure)

Everything listed here was produced before registration. None of it is confirmatory.

1. **Development set:** 48 circuits disjoint from the corpus (widths 6, 10, 14, seed 7), Qiskit 2.4.2. Operator checks (`obsaware/results/dev_check_operators.json`) and a development evaluation of the strategies (`obsaware/results/dev_eval.json`). Observability-aware selection detected 6/8 invisible and 6/6 visible detectable events at a 2% budget, against 0/8 and 5/6 for output-only and 5/8 and 2/6 for all-checks.
2. **Session K1** (Kaggle, 23 Oct 2026): clean-baseline costs of every check on the 116 corpus units, Qiskit 2.4.2, **no fault operator**. It is the source of the cost estimate. Data: `data/K1/` (the Kaggle output as downloaded, `out_k1.zip`, and its extracted files). Report: `docs/K1_REPORT.md`.
3. **Probe tolerance change** after K1: the state probe's phase tolerances were widened from 1e-6/1e-7 to 1e-3 rad, because Qiskit's level-3 block resynthesis perturbs two clean 18-qubit QFT compilations by about 1e-5 rad (observation O2). This used clean data only.
4. **Driver dry runs on Qiskit 2.4.2:** `obsaware/scripts/label_cohort.py` was exercised on the corpus units of at most 8 qubits (32 units) for five operators (`wide_rz_sign_flip`, `cp_rule_missing_phase`, `input_count_includes_ancillas`, `hash_order_rz_4pi_heavyhex`, `drop_routed_swap`), and on the units of at most 5 qubits for `cp_rule_missing_phase`. Only per-event counts of detecting units were printed. These are development-version labels, not cohort labels.
5. **Observation O1:** a fixed-seed reproducibility regression in Qiskit's recorded ancilla layout (2.3.1 to 2.6.1). Checking it compiled **one plain non-corpus circuit with no fault operator** on Qiskit 2.6.1 (and 2.1.2, 2.2.3, 2.3.1).
6. **No contact with the cohorts:** no corpus unit has been compiled and no operator has been built or run on Qiskit 2.6.1 or 2.5.2.

## 3. Cohorts

| Cohort | Qiskit | Qiskit Aer | Role |
|---|---|---|---|
| C261 | 2.6.1 (latest release) | the latest release installable with Qiskit 2.6.1, fixed in its wheelhouse manifest | primary |
| C252 | 2.5.2 | likewise for 2.5.2 | second |

Each cohort is labeled in its own Kaggle CPU session(s) with `obsaware/kaggle/nb_cohort_labeling.ipynb`, from a wheelhouse built after the registration push (`obsaware/kaggle/build_wheelhouse.py`). The cohorts are analysed separately and never pooled.

## 4. Corpus, events and checks

- **Corpus:** Paper 2's 116-unit cost-heterogeneous corpus (`cart.manifest.static_manifest.enumerate_costhet_units`), circuit seed 1234, basis {cx, rz, sx, x}, `seed_transpiler` 1234, levels 1 and 3, line and heavy-hex targets.
- **Events (18 per cohort):** one event per operator.
  - 10 output-visible operators: Paper 2's Phase C set (`cart.events.mutations_phase_c`, unchanged).
  - 8 output-invisible operators (`obsaware.mutations`): `phase_drop_after_translation_wide`, `rz_canonicalize_without_phase`, `cp_rule_missing_phase` (global phase); `input_count_includes_ancillas`, `input_registers_dropped` (contract); `final_layout_record_wide` (layout record); `hash_order_rz_shift_line`, `hash_order_rz_4pi_heavyhex` (determinism).
- **Checks** (items are (unit, check) pairs):
  - `output`: cart's semantic oracle (exact up to 12 ancilla-free qubits, structural otherwise);
  - `quality`: cart's quality oracle;
  - `probe`: `obsaware.oracles.state_probe`, k = 2, up to 24 physical qubits;
  - `contract`: `obsaware.oracles.contract_v2`;
  - `determinism`: `obsaware.determinism.run_batch`, hash seeds 0, 1, 2.

## 5. Labeling rules (`obsaware/scripts/label_cohort.py`)

- **E1 (exclusion):** an operator whose transpiler cannot be built for every corpus unit's configuration under the cohort's Qiskit is excluded from that cohort and reported. No replacement is made.
- **L1 (detection):** a check detects an event on a unit when it raises an alarm on the candidate compilation **and** passed on that unit's clean baseline in the same session. The determinism lane detects when the candidate is non-deterministic across the hash seeds and the clean compilation was deterministic.
- **L2 (crash):** a candidate that raises during compilation is observed by every applicable check of that unit.
- **L3 (unchanged):** a candidate whose fingerprint and contract verdict equal the baseline's detects nothing and is charged the clean costs measured in the same session.
- **Costs charged:** CPU process time, single thread. The candidate's own compilation is not charged (as in Paper 2). The unit's baseline compile cost is charged once per unit, as are the measured check costs and the determinism lane's fixed and per-unit costs from the event's own launches.

## 6. Strategies (`obsaware/src/obsaware/selection.py`, frozen)

- `output_only`: Paper 2's COAST unit order. Each unit gets {output, quality}.
- `all_checks`: the same unit order. Each unit gets every applicable check.
- `observability` (**the method**): greedy over items. Items whose (family, backend, channel) is not yet covered come first, then by lowest estimated marginal cost.
- `cheapest_items`: the same without the coverage key.
- `random_items`: 20 seeds, exploratory only.

## 7. Cost estimate and budgets (`obsaware/src/obsaware/cost_model.py`)

- The estimate is session K1's per-(unit, check) costs, multiplied by k.
- k is set by Paper 2's speed rule: the median, over units with K1 compile cost of at least 0.05 s, of (cohort clean compile cost / K1 compile cost). k is applied only if it lies outside [0.8, 1.25].
- Budgets are 2%, 5% and 10% of the estimated full observability-aware suite cost. Every strategy selects within the budget by the estimate and is charged real cost.

## 8. Confirmatory claims (decided by `obsaware/scripts/analyze_p3.py`, frozen)

An event is **detectable** in a cohort if at least one item detects it. Each claim is evaluated per cohort and is **SUPPORTED only if it holds in both cohorts**.

- **A (detection within budget).** At the 5% budget, the number of detectable events detected satisfies all three conditions:
  - observability > output_only;
  - observability ≥ all_checks;
  - observability ≥ cheapest_items.
- **B (earliness).** Over detectable events, observability's real cost to its first detection (unbudgeted ranking) is lower than all_checks' on more events than it is higher, with a one-sided exact sign test p < 0.05. Ties are dropped.
- **C (budget compliance).** Observability's real spend divided by the budget has mean ≤ 1.25 and maximum ≤ 2.0 over all analysed events, at each of the 2%, 5% and 10% budgets.

## 9. Exploratory (no claim)

- Detection at every budget for every strategy.
- Per-channel results.
- Random-order comparison.
- Cost share of the added checks.
- Detection on visible versus invisible events.
- The 18-qubit probe deviation (O2) in the cohort versions.
- O1 in the cohort versions.
- A later case study on Paper 1B's nine historical faults.

## 10. Session quality and deviations

- A reference benchmark runs at the start, after the baseline, after every event and at the end. A session whose benchmark median at any reading differs from the first reading by more than **15%** is rerun from its last good event. (K1 drifted by 4.2%.)
- A session stopped by Kaggle's 12-hour limit resumes from its saved output. That is not a deviation.
- Every other departure from this plan is reported as a deviation with its reason. No result is reported without the registered analysis.

## 11. Forecast (registered, judgement from development data)

- **P(A supported):** about 0.75. On the development set the method led at tight budgets, but the corpus differs, and Phase C's wide operators reach other units.
- **P(B supported):** about 0.4. Each cohort has only about 15 detectable events and ties are likely, so the sign test has little power.
- **P(C supported):** about 0.75. This depends on the speed rule and on oracle-cost transfer, which Paper 2's RQ6 supported for a fixed unit set.

## 12. Registration record

Kept in `REGISTRATION_RECORD.md`: repository URL, commit hash, commit and push times (UTC), and the result of `python obsaware/scripts/freeze_registration.py --verify` at the time of each cohort run.
