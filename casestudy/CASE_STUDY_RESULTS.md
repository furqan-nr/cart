# Historical-fault case study: results (exploratory)

Protocol: `PROTOCOL_CASESTUDY.md` (hashed 2026-10-25 15:16 UTC before any run; pushed in commit `9789ee3` at 16:10 UTC, after three of the eight builds had been compiled and before any comparison was run or read). Snapshots: `data/<release>/` from `snapshot.py`. Comparison: `analyze.py` -> `results/case_study.json`. Selection for the unplanned findings: `results/posthoc_selection.json`. Run in a cloud container (Python 3.13, Qiskit from PyPI wheels, numpy 2.5.4, scipy 1.18.1, no Qiskit Aer), so no cost was measured.

## Planned pairs

| Pair | Fix | Releases | Corpus: matched-check detections | Trigger | Expected |
|---|---|---|---|---|---|
| P1 | #15024 contract | 2.2.0rc1 -> 2.2.0 | frozen contract check: 0; K3' variant: 68 units. With K3', OA, CH and AC select a detecting item at 2%, 5% and 10%; OO never | K3' only | as expected |
| P2 | #14956 global phase | 2.1.2 -> 2.2.0 | none attributable (the one probe alarm is a different fault, see U2) | probe: phase -pi on the buggy release, 0 on the fixed | trigger as expected; corpus unclear beforehand |
| P3 | #14730 determinism | 2.1.1 -> 2.1.2 | none | determinism: 3 distinct compilations vs 1 | as expected |
| P4 | #16237 determinism | 2.4.2 -> 2.5.0 | none | none (hash seeds 0, 1, 2 gave one compilation on the buggy release); depth 57 vs 49 differs | trigger NOT as expected |
| P5 | #14603 contract | 2.0.2 -> 2.0.3 | none | none (no change in the full preset pipeline) | as expected (unclear beforehand) |

Differences between releases seen by checks that do not observe a pair's channel (quality on 4, 15 and 30 units in P1, P2 and P4; contract on 3 units in P2) are not attributed to the planned fault.

## Unplanned findings (post hoc attribution)

- **U1: #14939 (contract).** Under Qiskit 2.0.2, 2.0.3, 2.1.1 and 2.1.2 the frozen contract check raised K0 on 2 or 3 heavy-hex units: `TranspileLayout.initial_index_layout(filter_ancillas=True)` raised `IndexError`. None under 2.2.0rc1, 2.2.0, 2.4.2, 2.5.0. Qiskit fixed this in PR #14939 (first released in 2.2.0b1; the 2.1 backport #14941 was never released). `attribution_14939.py` applies the fix's code change to the buggy release and rechecks: every K0 alarm disappears (`results/attribution_14939_2.0.2.json`, `_2.1.2.json`). Selection with the registered estimate: OA and CH select a detecting item at every budget from 0.5%, AC from 2%, OO never. Paper 1B's generic trigger had missed #14939.
- **U2: global phase of pi on qft-n18-line-opt3.** Under 2.0.2 to 2.1.2 the probe finds the compiled circuit equal to the input times -1 (phase delta -3.14159, record verdict OK); from 2.2.0rc1 on, the deviation is below 1e-5. `diagnose_qft18_phase.py` (2.1.2): disabling ElidePermutations or ConsolidateBlocks removes it, disabling CommutativeCancellation does not, so it is not #14956. The fixing change is not identified. Selection: OA, AC and CH from 5%, OO never.
