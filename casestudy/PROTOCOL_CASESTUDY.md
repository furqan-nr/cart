# Historical-fault case study (Paper 3): protocol

**Status.** Exploratory, as listed in `PREREGISTRATION_P3.md` §9 ("a later case study on Paper 1B's nine historical faults"). Written and hashed (`PROTOCOL_CASESTUDY.sha256`) before any case-study run. Not a confirmatory registration; no claim is decided by it. Written 2026-10-25.

**Question.** If a real, merged Qiskit transpiler fix had been tested by the Paper 3 framework (the same 116-unit corpus, the same five checks, the same selectors), would the framework have told the buggy release apart from the fixed release, and within which budget? Where the corpus cannot reach a fault, does one test unit derived from the fix's own regression test reach it, and which check sees it?

## 1. Faults and release pairs

Scoping (before this protocol) found a buggy and a fixed PyPI release for every one of Paper 1B's nine faults (`fault_table.md`, `feasibility.md`; a read-only clone of Qiskit was used to place backports). The case study runs these five pairs:

| Pair | Fix PR | Channel | Buggy release | Fixed release | Pair type |
|---|---|---|---|---|---|
| P1 | #15024 | contract | 2.2.0rc1 | 2.2.0 | pre-release vs final |
| P2 | #14956 | global phase | 2.1.2 | 2.2.0 | different minor versions |
| P3 | #14730 | determinism | 2.1.1 | 2.1.2 | adjacent patch releases |
| P4 | #16237 | determinism | 2.4.2 | 2.5.0 | different minor versions |
| P5 | #14603 | contract | 2.0.2 | 2.0.3 | adjacent patch releases |

Not run, with the reason fixed now: #14919 (only custom pass managers that set `final_layout` twice; the release note says preset pipelines were unaffected), #16201 (needs control flow and `UnrollForLoops`, not in the preset pipelines), #16215 (`Commuting2qGateRouter`, not in the preset pipelines), #15040 (DAG edge order; none of the five checks observes it).

Releases that differ by more than one fix (P1, P2, P4, and P3, which also contains the #14919 fix) can differ for other reasons. An alarm is attributed to the fault only if the check that fires is a check that observes the fault's channel; any other difference between the builds is reported as such.

## 2. Part A: corpus replay (the framework as registered)

- Corpus: the 116 registered units, compiled with the registered baseline transpiler (preset pass manager, levels 1/3, line and heavy-hex, basis {cx, rz, sx, x}, seed 1234), under each build of each pair. No operator is involved: the build itself is the change.
- Checks: output, quality, probe, contract (K0-K3 exactly as frozen in `obsaware/oracles.py`), determinism (hash seeds 0, 1, 2; fresh interpreters).
- **Variant K3' (reported separately).** Scoping found that the frozen K3 reads registers from the original circuit's bits, while #15024 manifests in `layout.initial_layout.get_registers()`. K3' checks that every input register of the original circuit appears in `layout.initial_layout.get_registers()`. K3' is reported next to, never in place of, the frozen contract check.
- Detection rule (analogue of L1): a check detects the fault on a unit when it raises an alarm on the buggy build and not on the fixed build. Quality: the buggy compilation is a regression against the fixed one under the registered thresholds. Determinism: non-deterministic under the buggy build and deterministic under the fixed build. A compilation that raises under the buggy build only is a crash detection.
- Selection: for each pair, whether OA, AC, CH and OO select at least one detecting item at the 2%, 5% and 10% budgets, and their cost to first detection, with the registered study's estimate and costs (session N260 cost table, Qiskit 2.6.0). Costs are not measured in this case study; it runs in a cloud container, not on the registered Kaggle platform.

## 3. Part B: fault-derived trigger units

One trigger unit per pair, derived from the fix PR's regression test and fixed here before any run:

| Pair | Trigger circuit | Compilation |
|---|---|---|
| P1 | GHZ on 3 qubits | preset level 1, line coupling map of 5 qubits, `initial_layout=[0,1,2]` |
| P2 | 2 qubits: h(0), rz(pi,1), rz(pi,1), rx(pi,0), rx(pi,0), cx(0,1) | preset level 3, line of 2, basis {cx, rz, sx, x} |
| P3 | 3 qubits: rx(0.1), rx(0.2), rx(0.3) on qubits 0..2, measure_all | preset level 3, `GenericBackendV2(10, noise_info=True, seed=123)` as target |
| P4 | QFT on 5 qubits (cart corpus generator, seed 1234) | preset level 3, line of 5, basis {ecr, cx, cz, rz, sx, x} |
| P5 | 5 qubits: h on all, swap(0,1), PermutationGate([2,0,1]) on qubits 1..3 | preset level 3, line of 5, basis {cx, rz, sx, x} |

The same five checks and K3' run on each trigger under both builds (the probe and output checks only where applicable: P3 contains measurements). Detection rule as in Part A. Trigger results say whether the checks see the fault once a test reaches it. They are not part of the corpus and enter no selection result.

## 4. Expectations (written before running)

- Part A: P1 detected by K3' and not by the frozen contract check; P2 unclear (1B reported that the full preset pipeline masks #14956); P3, P4 and P5 not detected (the corpus does not reach their triggers).
- Part B: P1 by K3'; P2 by the probe's phase verdict, if the preset pipeline does not mask it; P3 and P4 by the determinism check; P5 unclear.

## 5. Environment and outputs

Container: Python 3.13, one virtual environment per Qiskit release, installed from PyPI wheels (qiskit only, with numpy 2.5.4, scipy 1.18.1; no Qiskit Aer, so the probe uses Qiskit's reference simulator). A smoke test (compile four 5-qubit GHZ units, run output, probe and contract) passed on 2.0.2, 2.1.1, 2.2.0rc1 and 2.5.0 before this protocol. Outputs: `casestudy/data/<release>/` (per-unit verdicts and fingerprints), `casestudy/results/case_study.json` and `.md`.

## 6. Disclosure added at freezing

Before hashing, `snapshot.py` was smoke-tested on Qiskit 2.1.1 with the corpus restricted to units of 5 qubits (16 units) and all five triggers, to confirm that it runs. 2.1.1 is the buggy build of P3 only. Its smoke output is not used. `analyze.py`, which applies the detection rule of Section 2 and the selection analysis, is written after this freeze and follows Sections 2 and 3 exactly.
