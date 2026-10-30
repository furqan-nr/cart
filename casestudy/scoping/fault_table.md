# Real-fault case study: release provenance of the nine faults of our earlier fault study

Compiled 2026-10-25. Evidence sources, in order of weight:

1. **Qiskit git history** (full-history blobless clone of https://github.com/Qiskit/qiskit at `/home/claude/qiskit/qiskit`, main at `73aa14d2b`). Fix commits and backports were found with `git log --all --grep "#<N>"`, and release membership with `git tag --contains`. Whether the buggy code shipped in a given release was checked by comparing the affected file's blob at the release tag with the blob at the backport's parent (identical blob = the release ships exactly the code the backport fixed). Where no backport exists, I grepped the release tag for the removed lines.
2. **PyPI JSON** (`https://pypi.org/pypi/qiskit/<v>/json`) for wheel file lists and upload dates. `pip download --only-binary=:all: --python-version 3.13 --implementation cp --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 qiskit==<v>` resolved for every version listed below.
3. **Companion paper (1B)**, `body_raw.tex`, Table 4 (lines ~434–583), Table 2 (lines ~250–300) and §6.6 (lines 1044–1050).
4. **Study corpus/checks** at `/home/claude/furqan-nr/cart`: `cart/src/cart/manifest/circuits.py`, `manifest/static_manifest.py`, `manifest/instrumentation.py`, `events/mutations.py`, and `obsaware/src/obsaware/oracles.py`.

Not available this session: the GitHub REST API and web pages. `gh api` was refused because the repo is not attached with credentials, and WebFetch hit a session limit. As a result, **PR labels, milestones and issue text were not read directly**. Backports were identified from mergify/backport commits on the `stable/*` branches instead, which is the authoritative record of what shipped. "Merge date" below is the committer date of the squash commit on `main`.

## Corpus facts used for reachability

- 4 families, built by hand in `circuits.py`:
  - `ghz`: h + cx chain.
  - `qft`: h + cp + `swap` gates (no `PermutationGate`).
  - `qaoa_linear`: h, rzz, rx.
  - `random_clifford`: `random_clifford(n).to_circuit()`.
- `measured=False` by default, so there are no measurements or barriers.
- No control flow and no `initial_layout`.
- Every qubit takes part in at least one 2-qubit gate.
- Compiled with `generate_preset_pass_manager(optimization_level ∈ {1,3}, coupling_map ∈ {line, heavy_hex}, basis_gates=["cx","rz","sx","x"], seed_transpiler=1234)`. This gives exactly one 2-qubit basis gate. No `Target` error data is supplied.
- Preset pipelines (checked in `builtin_plugins.py` at 2.1.2 and 2.4.2):
  - `ElidePermutations` runs only at opt 2/3, in the init stage.
  - `CommutativeCancellation` runs at opt 2/3 init and in the opt 2/3 optimization loop.
  - `ConsolidateBlocks` runs at opt 2/3 init (no basis passed) and in the opt 2/3 optimization stage (with `basis_gates`).
  - `UnrollForLoops` and `Commuting2qGateRouter` do **not** appear in `qiskit/transpiler/preset_passmanagers` at 2.4.2.
- K3 as implemented (`oracles.py` l.200–220) reads register membership by calling `original.find_bit(q)` on the qubits in `layout.input_qubit_mapping`. It does **not** read `layout.initial_layout.get_registers()`.

## Table

Abbreviations:
- **Checks:** EQ = output equivalence, Q = quality, SP = state probe, K0–K3 = contract checks, DET = determinism.
- **Channel:** GP = global phase, CM = contract/metadata, D = determinism.
- **Wheels:** "py3.13 wheel" means an abi3 Linux x86_64 wheel exists and pip resolves it for CPython 3.13.

| PR | Title (fix commit on main, merge date) | Ch. | First release with bug | First release with fix (incl. backports) | Release-wheel pair? | Trigger needed | Corpus reaches it? | Checks that should see it | py3.13 / x86_64 wheels |
|---|---|---|---|---|---|---|---|---|---|
| #14603 | Fix `ElidePermutations` pass in the presence of `PermutationGate`s. `96fda18888de4492f37ccdb93faf15dc014c99eb`, 2025-06-16 | CM | 1.3.0. The buggy Rust port came in #13094 `cbb4d5d5`, first tag 1.3.0. The buggy `remapped_qindices` code is present in 1.3.0, 1.4.0, 1.4.3, 2.0.0 and 2.0.2 (`crates/accelerate/src/elide_permutations.rs`). | 2.0.3 (backport `cdc292d1`, #14621), 2.1.0 (backport `54889177`, #14623; merged before the 2.1.0 tag), 1.4.4 (backport `c2a84dcc`, #14622), 2.2.0 (main) | **Yes**: 2.0.2 → 2.0.3. The `elide_permutations.rs` blob at 2.0.2 equals the backport parent. Also 1.4.3 → 1.4.4. | A `PermutationGate` in the input (the fix touches only the `PermutationGate` branch). `ElidePermutations` needs opt 2/3 and `routing_method != "none"`. Fix test: 5q circuit with h, swaps and `PermutationGate(perm)` on [1,2,3], run under `PassManager([ElidePermutations()])`. | **No.** The corpus has no `PermutationGate` (qft uses `swap`). Also, `ElidePermutations` does not run at opt 1. | In the full pipeline, probably **none**: 1B reports that a downstream pass recomputes the corrupted permutation, so full-pipeline checks stay blind (body_raw.tex l.77, l.129). 1B detected it only with an isolated-pass exception differential. The fix's release note says it led to "incorrect circuits and updates to the pass manager's property set", so EQ/SP on an isolated-pass run is unknown. | 2.0.2: yes (`cp39-abi3-manylinux_2_17`). 2.0.3: yes. |
| #14919 | Fix composition of `final_layout`. `dfcc5c6ce87fa424c8fd7abf22baba9e8750fa66`, 2025-08-15 | CM | 1.1.0. Introduced by #11399 `df59ab0c`, first tag 1.1.0, per 1B Table 2. | 2.1.2 (backport `5a2a9c4e`, #14920), 2.2.0 (main) | **Yes**: 2.1.1 → 2.1.2. The `sabre_swap.py` blob at 2.1.1 equals the backport parent. | More than one routing pass setting `final_layout` in a custom `PassManager` (fix test: `SetLayout`+`ApplyLayout` followed by 5 `SabreSwap`/`LookaheadSwap`/`BasicSwap` passes on different line maps). Release note: "This did not affect any normal calls to `transpile` or `generate_preset_pass_manager` using Qiskit's built-in plugins." | **No.** The corpus uses preset pass managers only. | K2 (composition) and SP (record verdict). EQ only when it is layout-normalised and exact (n ≤ 12). 1B: MR-1 detected it. | 2.1.1: yes. 2.1.2: yes. |
| #14956 | Fix global phase handling in `CommutativeCancellation`. `1064921158bbb6457d43c72c4d1f0502537d1ca3`, 2025-08-28 | GP | At least 2.1.0–2.1.2: the `commutation_cancellation.rs` blob at 2.1.2 equals the parent of the stable/2.1 backport. The introducing commit was not traced, so earlier releases are **unknown**. | 2.2.0 (main fix is in 2.2.0b1/rc1/2.2.0). The backport `d16e6c91` (#14961) was merged to stable/2.1 on 2025-09-03, **after** 2.1.2, and no 2.1.3 tag exists, so the backport never shipped. | **Cross-minor only**: 2.1.2 → 2.2.0. Many unrelated changes, so attribution is confounded. | `CommutativeCancellation` merging rotations to an angle of (2+4k)π (wrong −1 phase), merging X with RX, or accumulating T/S into P/U1 (fix tests: `rz(π)+rz(π)`, `rx(π)+rx(π)`, etc.). Runs at opt 2/3. | **Unclear.** CC runs at opt 3, and Clifford/QFT angles could sum to 2π. However, 1B §6.6 (l.1044) reports the fault is "masked by the full preset pipeline … invisible unless CommutativeCancellation runs alone". | SP (phase verdict). EQ, K and DET are blind. | 2.1.2: yes. 2.2.0: yes. |
| #14730 | Fix non-determinism VF2Layout with only 1q gates. `d33ef5335e05523e35a29530dbc389c52c8e7bc7`, 2025-07-15 | D | At least 2.1.1: the `vf2_layout.rs` blob at 2.1.1 equals the backport parent. Earliest release is **unknown**. | 2.1.2 (backport `f93fbcc7`, #14734), 2.2.0 (main) | **Yes**: 2.1.1 → 2.1.2. | Circuit qubits with no 2-qubit interactions (`map_free_qubits`), plus a `Target` with per-qubit error rates whose scores tie (fix tests: 3 × `rx` + `measure_all` on `GenericBackendV2(10, noise_info=True)`). The unstable order comes from a Rust hash set, which per the fix message is not controlled by PYTHONHASHSEED. | **No.** Every corpus qubit takes part in a 2q gate, and no target error data is given. | DET (raw fingerprint, via layout). EQ is blind. | 2.1.1: yes. 2.1.2: yes. |
| #16237 | Fix determinism in `ConsolidateBlocks`. `3b9a64fdd4353834d83a6e393a76a2ee657800f2`, 2026-06-03 | D | 2.4.0. The `next(iter(kak_gates))` set-iteration code is present in 2.4.0 and 2.4.2 and absent in 2.0.0 and 2.3.0. Whether 2.3.0 had a different non-deterministic form is **unknown**. | 2.5.0rc1 / 2.5.0 (main only; no backport commit found) | **Cross-minor only**: 2.4.2 → 2.5.0 (or 2.5.0rc1). | A basis with **several** 2q KAK gates (e.g. `["ecr","cx","cz"]` or `["ryy","rzz"]`). The choice then depends on Python `set` iteration order, which is PYTHONHASHSEED-dependent. Reached through `ConsolidateBlocks(basis_gates=…)` in the opt 2/3 optimization stage. | **No.** The corpus basis has only one 2q gate (`cx`). | DET (raw fingerprint differs across hash seeds). Possibly Q (different 2q gate counts). EQ is blind. | 2.4.2: yes (`cp310-abi3-manylinux_2_28`). 2.5.0: yes. |
| #16201 | Fix UnrollForLoops global phase accumulation. `2b4c81d4a8de182376eca71195474d86af7e7b33`, 2026-05-21 | GP | At least 2.4.1: the `unroll_forloops.py` blob at 2.4.1 equals the backport parent. The fix line is also absent at 2.0.0 and 2.4.0, but whether those releases show the bug is **unknown**. | 2.4.2 (backport `d549bba2`, #16238), 2.5.0 (main) | **Yes**: 2.4.1 → 2.4.2. | A `for_loop` whose body has a nonzero `global_phase` (fix tests: body `QuantumCircuit(1, global_phase=π/7)`, `range(3)`), run through `UnrollForLoops`. That pass is not in the 2.4.2 presets. | **No.** The corpus has no control flow, and the pass is not in the preset pipelines. | SP (phase). EQ is blind. | 2.4.1: yes. 2.4.2: yes. |
| #16215 | Fix Commuting2qGateRouter global phase handling. `be4c248ef729f4ae6721a7ca44238bd0f80a4a75`, 2026-05-21 | GP | ≤ 2.0.0. The buggy `return new_dag.copy_empty_like()` is present in 2.0.0, 2.3.0, 2.4.0 and 2.4.2 (first introduction not traced). | 2.5.0rc1 / 2.5.0 (main only; no backport found) | **Cross-minor only**: 2.4.2 → 2.5.0 (or 2.5.0rc1). | `Commuting2qGateRouter(SwapStrategy…)` run on a circuit with nonzero `global_phase` (fix test: 4q, `global_phase=0.3`, h+cx, line swap strategy). The pass is not in the presets. | **No.** The pass is not in the preset pipelines, and corpus circuits have global_phase 0 on input. | SP (phase). EQ is blind. | 2.4.2: yes. 2.5.0: yes. |
| #15024 | Preserve registers in output TranspileLayout. `bb100f83c76eaecccb9c2888799ea0b2895980a7`, 2025-09-17 | CM | **Never in a final release.** It was introduced in the 2.2 cycle (Rust `ApplyLayout`/`TranspileLayout` round-trip). The fix message says "the bug wasn't included in a full release … difference between 2.2.0rc1 and 2.2.0". Pre-releases on PyPI with the bug: 2.2.0rc1 (`input_registers` absent; fix not in rc1 tag) and very likely 2.2.0b1 (same check). | 2.2.0 (backport `cad44743`, #15025, on stable/2.2 before the tag); 2.3.0 (main) | **Pre-release only**: 2.2.0rc1 → 2.2.0. | Any transpile producing a layout. Fix tests: `initial_layout=[0,1,2]` at opt 0–3, and also a `Target` with a coupling map and no initial layout. Visible as `tqc.layout.initial_layout.get_registers()` missing the input registers. | **Yes, likely**: every corpus unit has a coupling map, so `TranspileLayout` is built. Not run, though. | K3 **as currently implemented: unclear, likely blind**. It derives registers from `original.find_bit` rather than from `initial_layout.get_registers()`. A one-line K3 variant comparing `layout.initial_layout.get_registers()` to `original.qregs` matches 1B's adapter. EQ, SP and DET are blind. | 2.2.0rc1: yes. 2.2.0b1: yes. 2.2.0: yes. |
| #15040 | Fix edge-order non-determinism when adding DAG nodes. `25c3206f0b94c3e1a55e334a050a0d1fd144f996`, 2025-09-23 | D | At least 2.2.0: the `dag_circuit.rs` blob at 2.2.0 equals the backport parent. Earliest release is **unknown**. | 2.2.1 (backport `33fef5fc`, #15057), 2.3.0 (main) | **Yes**: 2.2.0 → 2.2.1. | High-degree quantum nodes (barriers) or nodes with several classical in-edges added through `DAGCircuit.push_back`/`push_front`. Fix tests involve `BarrierBeforeFinalMeasurements` and DAG construction. Observable via `DAGCircuit.structurally_equal` across fresh processes (Rust `HashSet` order). | **No.** The corpus has no barriers, measurements or classical bits. | Of the five, likely **none**. The compiled instruction sequence and layout are not expected to change, so the raw fingerprint is stable. 1B needed a DAG edge-order adapter. | 2.2.0: yes. 2.2.1: yes. |

## Notes

- Backport parents equal to the release blob were verified for: #14603 (2.0.2), #14919 (2.1.1), #14956 (2.1.2), #14730 (2.1.1), #16201 (2.4.1) and #15040 (2.2.0).
- For #16237 and #16215, the release blob differs from the main-branch fix parent because the file has other changes. Presence of the buggy lines was confirmed by grep instead.
- Release tag dates (committer date of the tag commit):
  - 2.0.2: 2025-05-27
  - 2.0.3: 2025-06-17
  - 2.1.0: 2025-06-18
  - 2.1.1: 2025-07-10
  - 2.1.2: 2025-08-19
  - 2.2.0b1: 2025-08-28
  - 2.2.0rc1: 2025-09-04
  - 2.2.0: 2025-09-18
  - 2.2.1: 2025-09-26
  - 2.4.1: 2026-04-24
  - 2.4.2: 2026-06-12 (PyPI upload 2026-06-14)
  - 2.5.0rc1: 2026-06-18
  - 2.5.0: 2026-07-02
- **This contradicts the companion paper §6.6 (body_raw.tex l.1046).** That section states that for #14956, #15040, #15024, #16215, #16201 and #16237 "the fix commit and its buggy parent are tagged to the SAME Qiskit release" and that "No pair of released wheels therefore brackets the bug". The git record shows backports to stable branches that create adjacent-patch release pairs for #15040 (2.2.0 → 2.2.1) and #16201 (2.4.1 → 2.4.2). It shows cross-minor pairs for #14956 (2.1.2 → 2.2.0), #16215 and #16237 (2.4.2 → 2.5.0), and a pre-release pair for #15024 (2.2.0rc1 → 2.2.0). The §6.6 claim looks at main-branch tags only and should be revised.
- Wheel tags:
  - 1.4.x, 2.0.x, 2.1.x and 2.2.x: `cp39-abi3-manylinux_2_17_x86_64`.
  - 2.4.x and 2.5.x: `cp310-abi3-manylinux_2_28_x86_64` (requires_python ≥ 3.10).
  - abi3 wheels install on CPython 3.13.
  - Unverified: whether 2.0.x/2.1.x run correctly against the newest numpy (2.5.x) and scipy (1.18.x) that pip resolves for 3.13. **Unknown; pin conservatively** (e.g. numpy<2.3) and smoke-test.

## Source URLs

- PRs (not fetched this session; identifiers verified from commit subjects):
  - https://github.com/Qiskit/qiskit/pull/14603, /pull/14919, /pull/14956, /pull/14730, /pull/16237, /pull/16201, /pull/16215, /pull/15024, /pull/15040
  - Backports: /pull/14621, /pull/14622, /pull/14623, /pull/14920, /pull/14961, /pull/14734, /pull/16238, /pull/15025, /pull/15057
- Issues named in fix messages: https://github.com/Qiskit/qiskit/issues/14729 (#14730), https://github.com/Qiskit/qiskit/issues/15014 (#15024), https://github.com/Qiskit/qiskit/issues/16205 (#16215).
- Commits: `https://github.com/Qiskit/qiskit/commit/<sha>` for each SHA above.
- Release tags: `https://github.com/Qiskit/qiskit/releases/tag/<v>` for 2.0.2, 2.0.3, 2.1.1, 2.1.2, 2.2.0rc1, 2.2.0, 2.2.1, 2.4.1, 2.4.2, 2.5.0.
- PyPI: `https://pypi.org/pypi/qiskit/<v>/json` for 1.4.3, 1.4.4, 2.0.2, 2.0.3, 2.1.0, 2.1.1, 2.1.2, 2.2.0b1, 2.2.0rc1, 2.2.0, 2.2.1, 2.4.1, 2.4.2, 2.5.0rc1, 2.5.0 (all fetched).
- Companion paper: the manuscript of our earlier fault study (tables of the nine faults).
