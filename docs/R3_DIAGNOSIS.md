# Why R3 revealed none of the 15 real faults (post hoc, not registered)

Sources: `docs/RESULTS_P3_R3.md` (registered result), `posthoc/r3_injection_check.*` (each fault fails its own regression test), `posthoc/r3_triggers.*` (trigger units built from each fix's regression test, run through the frozen checks at pass level and through the full preset compiler at optimisation levels 1 to 3).

## 1. What the corpus contains

All 116 units are built from four families (GHZ, QFT, QAOA-linear, random Clifford). Together they use ten gate types: h, cx, rzz, rx, cp, swap, s, x, y and z. There are no parameters, no gates on three or more qubits, no custom or unitary gates. Every unit is compiled with plain `transpile` settings: levels 1 and 3, basis cx/rz/sx/x, two topologies, one thread.

## 2. Fault by fault

| Fault | What the bug needs | In the corpus? | Checks catch it once the input is given (pass level / full compiler) |
|---|---|---|---|
| #16402 phase gates in CommutativeCancellation | P or U1 gates in a basis that keeps them, summing to 2π | no (basis has rz only) | **probe** / **probe** (levels 2, 3) |
| #16599 negative X-rotation runs | sxdg runs with sx in the target | no | **output, probe** / not reached (earlier passes rewrite sxdg) |
| #16884 ConsolidateBlocks on 3-qubit gates | Toffoli in a 3-qubit block consolidation | no (no 3-qubit gates, preset collects 2-qubit blocks) | **output, probe** / not reached |
| #16153 CS/CSdg cancellation | reversed CS/CSdg pairs | no | **quality** / **quality** (level 1) |
| #17163 two-qubit synthesis near the 2-CX/3-CX boundary | a two-qubit unitary near that boundary | no (no unitary gates) | **output, probe** / **output, probe** (all levels) |
| #13945 permutation layouts | permutation gates with Split2QUnitaries or StarPreRouting | no | missed: the error is in the virtual permutation bookkeeping, which no check reads |
| #16656 DAG edge-id non-determinism | repeated `remove_qubits` builds | not observable | missed: internal edge ids, identical outputs |
| #16963 deadlock with Python-defined gates | multithreaded commutation of custom gates | no (no custom gates, one thread) | hang reproduced by its pytest test but not under our harness |
| #16283, #16752 expression arithmetic | symbolic parameter expressions | no (no parameters) | outside the checks' scope (no compilation) |
| #16988 CouplingMap duplicates | a coupling list with repeated edges | no | outside scope (container behaviour) |
| #15623 QPY ancilla register | QPY round trip | no | outside scope |
| #14943 falsy pass outputs | a custom pass returning a falsy value | no | outside scope |
| #16637 error message | specific SabreLayout arguments | no | outside scope (message text) |
| #16476 Target cache | very high-degree coupling maps | no | performance only |

## 3. The reasons, in order of size

1. **Input conditions, not code reach.** The selection rule asked whether the fixed code runs on the corpus. It does, but each bug also needs a specific input: a gate kind, parameter, matrix, option or thread count the corpus never supplies. None of the 15 conditions occurs in the corpus.
2. **Seven of the 15 are not output faults of compilation** (expression arithmetic, containers, QPY, pass-manager API, an error message, performance). No output oracle, ours or another, can see them.
3. **End-to-end compilation masks some faults.** Of the five faults the checks catch at pass level, two (#16599, #16884) are never reached through the full preset compiler, because earlier passes rewrite the triggering gates or the buggy pass is not in the preset pipeline.
4. **The checks themselves work on real faults.** Given the triggering input, the frozen checks caught 5 of the 8 faults with a compilation test at pass level, and 3 through the full compiler. Two of the five were caught by a single, non-output channel: #16402 only by the probe (a global-phase bug) and #16153 only by the quality check. Output-only checking would have missed both. This is real-fault evidence for the observability argument.

## 4. What follows

- The corpus needs **input-feature coverage**: gate kinds (phase, controlled-S, multi-qubit, unitary blocks), symbolic parameters, non-default bases and options. Coverage of the code is not enough.
- Testing needs **pass-level units** next to end-to-end compilation, because some faults are invisible end to end.
- Testing either change fairly needs faults not used to design it.
