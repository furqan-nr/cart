# Development observations (Paper 3)

Things noticed during development that are not results. Each needs checking before it is used anywhere.

## O1 (2026-10-23): fixed-seed non-determinism of the ANCILLA part of the recorded initial layout, Qiskit 2.4.2

- **What:** compiling the same circuit with the same pass manager and `seed_transpiler=1234`, in one Python
  process, gives different `layout.initial_index_layout(filter_ancillas=False)` results from run to run. The
  ancilla entries are assigned to different physical qubits. Instructions, global phase and the input-qubit layouts
  (`filter_ancillas=True`) are identical.
- **Where seen:** heavy-hex targets (ancillas added), QFT and random-Clifford circuits, levels 1 and 3, widths 6 and
  10 (development set). Line targets (no ancillas) and GHZ were stable. Up to 4 distinct records in 4 runs.
- **Likely cause (unverified):** ancilla `Qubit` objects created fresh in each run and ordered by object identity or
  hash somewhere in ancilla allocation.
- **Why it may be harmless:** Qiskit's `TranspileLayout.from_property_set` docstring says ancilla indices "don't mean
  much". Public API `initial_index_layout()` still returns run-dependent values.
- **Action taken:** the Paper 3 determinism fingerprint compares input-qubit layouts only, so this does not raise
  false alarms.
- **Checked 2026-10-23:**
  - *Where it starts:* tracing the pass manager with a callback, two runs first diverge at `ApplyLayout` when it applies
    the `VF2PostLayout` result. That path calls `update_layout` from `qiskit._accelerate.apply_layout`, compiled Rust
    code from the Rust port of `ApplyLayout`. Rust's standard `HashMap` gives every new map its own random iteration
    order, which would explain variation inside one process (not confirmed by reading the Rust source).
  - *Which versions:* minimal reproducer `docs/o1_repro.py` (plain Qiskit, a 6-qubit QFT, heavy-hex distance 3, level 3,
    seed 1234, 10 runs in one process). Distinct full initial layouts: **2.1.2: 1, 2.2.3: 1, 2.3.1: 7, 2.4.2: 6, 2.6.1
    (latest): 7**. Input-only layouts: 1 in every version. So it is a regression introduced between 2.2.3 and 2.3.1 and
    still present in the current release.
  - *Known already?* No matching report found by web search. GitHub's issue search could not be queried from the
    workspace (blocked to automated access), so the tracker itself is not yet checked: search
    https://github.com/Qiskit/qiskit/issues for "ancilla" "initial_index_layout" "deterministic" "update_layout".
  - *Severity (assessment, not tested):* likely low. Only the ancilla part of the record varies, and ancillas carry no
    input state, so layout-normalised results should not change. It still breaks the run-to-run reproducibility of a
    public API return value under a fixed seed, the same class of property as the determinism faults #14730 and #16237
    that Qiskit fixed.
  - *Disclosure for Paper 3's registration:* this check compiled one plain non-corpus circuit with no Paper 3 operator on
    Qiskit 2.6.1 (and 2.1.2, 2.2.3, 2.3.1). No corpus unit and no operator has been compiled on 2.6.1 or 2.5.2.
- **Tracker search by Furqan (2026-10-23):** "ancilla initial_index_layout deterministic" in Qiskit/qiskit issues: 0 results. Two broader searches still to run before filing ("update_layout ancilla", "VF2PostLayout ancilla layout run"). An issue text has been drafted for filing. Search "VF2PostLayout ancilla layout run": 1 result, #14997 (VF2PostLayout crash during layout finalisation with 1q wires, closed for 2.2.0). Not a duplicate (a crash, fixed before 2.3; no mention of determinism or ancilla ordering), cited in the draft as a possibly related code path. Search "update_layout ancilla": 0 results. Tracker check complete: no existing report found; ready to file.
- **Next:** search the tracker by hand; if nothing exists, Furqan may file an issue with the reproducer. In Paper 3 it can
  be reported as an incidental real finding of the determinism oracle (found during development, not by the
  confirmatory study).

## O2 (2026-10-24): level-3 two-qubit block resynthesis perturbs near-identity blocks by about 1e-5 rad, Qiskit 2.4.2

- **What:** on 18-qubit QFT compiled at level 3 (line and heavy-hex), the compiled circuit read through its layout implements the input only up to a non-global phase of about 3e-6 to 2.4e-5 rad (the phase of the probe overlap differs between random input states); |overlap| is 1 to within 1e-6.
- **Cause located:** disabling `ConsolidateBlocks` removes it (deviation at machine precision). QFT-18 contains CP rotations as small as pi/2^17 (2.4e-5 rad); resynthesis of the near-identity two-qubit blocks appears to drop or approximate them.
- **Status:** not established whether this is an intended tolerance (default `approximation_degree` is 1.0) or a precision weakness. Not investigated further; possible follow-up: compare against `Operator.equiv` tolerances and check whether the two-qubit decomposer treats near-identity blocks as identity when the basis fidelity is 1.0.
- **Effect on Paper 3:** the state probe's phase tolerances were widened from 1e-6 / 1e-7 to 1e-3 rad before any corpus label exists (docs/K1_REPORT.md).
