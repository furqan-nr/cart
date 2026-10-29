# R3 fault selection rule

The R3 faults are real Qiskit bugs: merged fixes, reverted on Qiskit 2.6.1. They were selected by the rule below, **before any of them was compiled with a corpus unit or seen by any check**. The rule uses the fixes' metadata and patches, and which Qiskit code runs when the **clean** Qiskit 2.6.1 compiles the corpus. It never uses a check result, a fault build's output or a detection label.

## Rule

A Qiskit commit is an R3 fault if all of the following hold.

1. **A fix.** It is on Qiskit's `main` branch after tag `2.0.0` (clone fetched 2026-10-29, `main` at `5f9bf19d4`), adds a release note, its subject matches `fix|bug|incorrect|wrong`, and it changes Python files under `qiskit/` or Rust files under `crates/`.
2. **Present and revertible on 2.6.1.** Its patch (restricted to `qiskit/` and `crates/`) applies in reverse to the 2.6.1 tag and does not apply forwards. Reverting it puts back the code before the fix and changes nothing else.
3. **Not contacted before.** It is not one of the Qiskit fixes this research used earlier: Paper 1B's nine faults and their backports, the fixes on which the R1 operators were modelled, and the case study's faults (list in `selection/select_faults.py`).
4. **Compilation-related.** It changes a source file under the transpiler, synthesis, circuit, DAG, pass-manager, compiler or converter code (Python or Rust), other than visualisation, QPY, QASM, primitives and results.
5. **Exercised by the corpus.** A function changed by the fix runs while the clean Qiskit 2.6.1 compiles the 116 corpus units with the frozen baseline transpiler:
   - **Python:** line coverage (`coverage.py`) of pass-manager construction and compilation only, not circuit construction (`selection/coverage_corpus.py`). A changed line counts if any line of its innermost enclosing function ran, or, outside any function, if the line itself ran (`selection/exercised.py`).
   - **Rust:** a copy of 2.6.1 with one probe at the start of every function that contains a changed line (`selection/rust_probes.py`), built once, records a fault the first time one of its functions runs after all corpus circuits have been constructed (`selection/probe_corpus.py`).

## Result

| Step | Commits |
|---|---|
| Fix commits mined (1) | 154 |
| Not present or not cleanly revertible on 2.6.1 (2) | 80 removed |
| Contacted before (3) | 6 removed |
| Not compilation-related (4) | 17 removed |
| Changed code not run on the corpus (5) | 36 removed |
| **Eligible: the R3 faults** | **15** (5 Python-only, 10 with Rust changes) |

Per-commit decisions and evidence: `fault_selection_all.json`. The 15 faults, their patches and evidence: `faults.json`, `patches/`. The rule was applied once; `selection/mine_fixes.py` and `selection/select_faults.py` reproduce it from a Qiskit clone.

Being exercised does not mean the fault changes any compiled output. Whether it does is what the labeling session measures.
