# Feasibility: running the CI selection framework on real Qiskit regressions (Kaggle, Python 3.13)

The evidence and citations are in `fault_table.md`, which sits next to this file. The constraints are:

- Kaggle gives `pip install` of PyPI wheels. Building Qiskit from source needs a Rust toolchain and 15–30 min per build, which is possible on Kaggle but fragile.
- The corpus is fixed: 116 units, preset pass managers, opt 1/3, line/heavy_hex, basis {cx, rz, sx, x}, no control flow, no measurements, no `initial_layout`.

## 1. Classification

| Fault | Release-wheel pair (py3.13 abi3 wheels exist for both) | Pair quality | Corpus reaches trigger? | Runnable as an *unmodified-corpus* case study? |
|---|---|---|---|---|
| #14603 ElidePermutations | 2.0.2 → 2.0.3 (also 1.4.3 → 1.4.4) | adjacent patch (good) | No (needs `PermutationGate`; pass is off at opt 1) | No: expected null result |
| #14919 final_layout composition | 2.1.1 → 2.1.2 | adjacent patch (good) | No (preset pipelines never set `final_layout` twice, per the release note) | No: expected null result |
| #14730 VF2Layout 1q determinism | 2.1.1 → 2.1.2 | adjacent patch (good) | No (no idle/1q-only qubits; no target error data) | No: expected null result |
| #15040 DAG edge order | 2.2.0 → 2.2.1 | adjacent patch (good) | No (no barriers/clbits); the five checks are likely blind even with a trigger | No |
| #16201 UnrollForLoops phase | 2.4.1 → 2.4.2 | adjacent patch (good) | No (no control flow; pass not in presets) | No |
| #15024 TranspileLayout registers | 2.2.0rc1 (or 2.2.0b1) → 2.2.0 | pre-release vs final (acceptable; rc1 → final is a small diff) | **Yes, likely** (every unit builds a `TranspileLayout`) | **Yes**, but K3 as implemented is probably blind (see §3) |
| #14956 CommutativeCancellation phase | 2.1.2 → 2.2.0 | cross-minor (confounded) | Unclear (CC runs at opt 3; 1B reports masking in the full preset pipeline) | Possible; outcome unknown |
| #16215 Commuting2qGateRouter phase | 2.4.2 → 2.5.0 (or 2.5.0rc1) | cross-minor (confounded) | No (pass not in presets) | No |
| #16237 ConsolidateBlocks determinism | 2.4.2 → 2.5.0 (or 2.5.0rc1) | cross-minor (confounded) | No (single 2q basis gate) | No |

**Source builds needed:** none is strictly required. Every fault has a buggy and a fixed build on PyPI as wheels, which is the reverse of what the companion paper's §6.6 claims (see the note in `fault_table.md`). Source builds of the exact fix commit and its parent would only be needed in two cases:

- **Cross-minor pairs (#14956, #16215, #16237).** Use a source build for a clean, single-change attribution. The alternative is to accept 2.1.2 → 2.2.0 or 2.4.2 → 2.5.0 and argue attribution from the fact that the firing check matches the fixed code path.
- **#15024 attribution.** Use a source build if you want commit-exact attribution rather than rc1 → final. The rc1 → 2.2.0 diff is small, so this is optional.

**Unreachable by the fixed corpus:** #14603, #14919, #14730, #15040, #16201, #16215 and #16237 are all unreachable. #14956 is unclear. Only #15024 is plausibly reached unchanged. This matches the companion paper's own finding (§4.7) that each of these faults needed a trigger rebuilt from the fix's regression test.

## 2. Two designs

**A. Pure corpus replay (strict "would CI have caught it?").** Install buggy and fixed wheels, run all 116 units × 5 checks in each, and diff the verdicts.

- Expected outcome: mostly null. Only #15024 (if K3 reads `initial_layout.get_registers()`) and maybe #14956 could fire.
- This is an honest *negative* case study. It shows that the corpus, not the checks, limits sensitivity, which is the 1B trigger-matching lesson.

**B. Corpus + fault-derived trigger units (recommended for a positive demonstration).** Add one trigger unit per fault, built from the fix PR's own regression test, as a pre-declared "case-study extension". Then run the unchanged five checks on buggy and fixed wheels. Note:

- #14603 needs opt ≥ 2 and a `PermutationGate`. 1B suggests the full pipeline masks it, so it may stay null even then.
- #14919, #16201 and #16215 need custom pass managers, which goes beyond the preset framework. Report them as out of scope rather than force them.
- #14730 needs a `Target` with error data (`GenericBackendV2(noise_info=True)`).
- #16237 needs a multi-2q-gate basis.
- #15040 has no detecting check among the five.

## 3. Recommended minimal plan

1. **Primary pair: #15024 (2.2.0rc1 buggy → 2.2.0 fixed).**
   - Run all 116 units unchanged.
   - Before running, decide and pre-register whether K3 uses `layout.initial_layout.get_registers()` vs `{r for r in original.qregs}`. The current `obsaware/oracles.py` K3 derives registers from `original.find_bit(...)`, which probably cannot see this bug because the Qubit objects still belong to the original's registers.
   - If K3 is left as is and returns no violation, report that as a finding about the check.
2. **#14956 (2.1.2 → 2.2.0):**
   - Run all 116 units. SP phase is the expected detector, mostly at opt 3.
   - Then add the fix-test trigger (`rz(π)+rz(π)` and `rx(π)+rx(π)`) as one extra unit compiled at opt 3.
   - State the cross-minor confound explicitly.
3. **Adjacent-patch determinism pair #14730 (2.1.1 → 2.1.2), with one trigger unit:**
   - Trigger: 3 × `rx` + `measure_all` compiled against `GenericBackendV2(10, noise_info=True, seed=123)` at opt 1/3, `seed_transpiler=1234`.
   - The DET check (3 fresh interpreters) should separate the builds. The randomness comes from a Rust hash set, so fresh processes matter more than the PYTHONHASHSEED value.
   - Note that this departs from the corpus target (basis + coupling map). Treat it as an extension unit.
4. Optional:
   - #16237 (2.4.2 → 2.5.0) with a trigger unit using basis `["ecr","cx","cz","rz","sx","x"]`. The DET check with PYTHONHASHSEED 0/1/2 is the natural detector here because the fault is in Python `set` order.
   - #14603 (2.0.2 → 2.0.3) with a `PermutationGate` trigger at opt 3, as a likely-null control.
5. Skip:
   - #14919, #16201 and #16215: unreachable through preset pipelines.
   - #15040: not observable by the five checks.
   - Mention all four in the paper as out of scope, with these reasons.

## 4. Kaggle practicalities

- One `pip install qiskit==<v>` per build in a separate venv or `--target` dir.
- Wheels confirmed resolvable for CPython 3.13 / manylinux x86_64: 1.4.3, 1.4.4, 2.0.2, 2.0.3, 2.1.1, 2.1.2, 2.2.0b1, 2.2.0rc1, 2.2.0, 2.2.1, 2.4.1, 2.4.2, 2.5.0rc1, 2.5.0.
- **Unknown risk:** whether 2.0.x, 2.1.x and 2.2.x behave correctly with the newest numpy (pip resolved 2.5.4) and scipy (1.18.1) on 3.13. Pin numpy and scipy to versions contemporaneous with each release, and run a smoke test (`transpile` of GHZ-5, `Operator` equality) before the main run.
- Check that the cart/obsaware code paths work on each build:
  - `cart/events/mutations.py` notes a reliance on the private `_flatten_tasks` API, which is "pin within the 2.1–2.4 band". This matters only for mutation operators, not for `baseline_transpiler`.
  - The layout getters `routing_permutation`, `initial_index_layout` and `final_index_layout` are defined in `qiskit/transpiler/layout.py` at 1.4.3, 2.0.2 and 2.1.1 (checked with git), so K0 should not fire spuriously on the older builds.
- The DET check spawns 3 fresh interpreters per unit per build, so budget about 3× the compile time.
