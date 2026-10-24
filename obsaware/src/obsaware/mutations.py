"""Paper 3 mutation operators for the three OUTPUT-INVISIBLE channels (global phase, contract/metadata,
determinism).

Design rules, carried over from Paper 2's Phase C operators (cart.events.mutations_phase_c):
  * every operator is a deterministic change INSIDE the preset pass manager (a small custom pass appended to
    or prepended to a stage), or a gate on the input decided from pre-execution facts (input width, coupling
    map topology, optimization level);
  * every operator is INPUT-SPECIFIC: only some units can reach it, so which tests are selected matters;
  * every operator leaves the output circuit equivalent to the input modulo global phase and the recorded
    layout, as far as the reference screen (exact unitary up to 12 qubits on ancilla-free units, structural
    otherwise, quality, performance) can see. The development check (scripts/dev_check_operators.py) verifies
    this on a development circuit set that is disjoint from the 116-unit corpus.

Mechanisms and their real-fault analogues (Paper 1B):
  G1 phase_drop_after_translation_wide  global phase zeroed after translation, inputs >= 14 qubits   (#14956 shape)
  G2 rz_canonicalize_without_phase      RZ angles moved to [0, 2pi) without the -1 factor, heavy-hex  (#16201 shape)
  G3 cp_rule_missing_phase              CP rewritten as RZ x RZ . RZZ without exp(i theta/4)        (#16201 shape)
  K1 input_count_includes_ancillas      recorded number of input qubits counts the ancillas (no elided
                                        permutation present, otherwise layout construction would crash) (#15024 shape)
  K2 input_registers_dropped            input register identity dropped from the recorded layout   (#15024 shape)
  K3 final_layout_record_wide           recorded final layout swaps two entries, inputs >= 13      (#14919 shape)
  D1 hash_order_rz_shift_line           hash-order choice between RZ(t) and -RZ(t+2pi) phase-compensated (#16237 shape)
  D2 hash_order_rz_4pi_heavyhex         hash-order choice between RZ(t) and RZ(t-4pi)                       (#16237 shape)

K3 is CONDITIONALLY invisible: a wrong final-layout record changes the layout-normalised operator, so the exact
check would see it, but the gate (>= 13 qubits) keeps it outside the width the dense exact check can run on.
All others are invisible to output equivalence by construction.
"""
from __future__ import annotations

import math
from typing import Any

from qiskit import QuantumCircuit
from qiskit.circuit import Qubit
from qiskit.circuit.library import RZGate, RZZGate
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit import DAGCircuit
from qiskit.transpiler import Layout, PassManager, generate_preset_pass_manager
from qiskit.transpiler.basepasses import AnalysisPass, TransformationPass

from cart.events.mutations import BaseConfig, MutationOperator, Transpiler
from cart.events.schema import FaultType

# Pre-declared input gates (fixed before any Paper 3 label exists)
G1_MIN_QUBITS = 14
K3_MIN_QUBITS = 13
D1_MIN_QUBITS = 8


def _preset(cfg: BaseConfig):
    return generate_preset_pass_manager(**cfg)


def _tasks(pm, stage: str) -> list:
    sub = getattr(pm, stage)
    if sub is None:
        return []
    return list(sub._flatten_tasks(sub._tasks))


def _append(pm, stage: str, pass_) -> None:
    setattr(pm, stage, PassManager(_tasks(pm, stage) + [pass_]))


def _prepend(pm, stage: str, pass_) -> None:
    setattr(pm, stage, PassManager([pass_] + _tasks(pm, stage)))


def _last_stage(pm) -> str:
    for st in ("scheduling", "optimization", "translation", "routing", "layout", "init"):
        if getattr(pm, st, None) is not None and _tasks(pm, st):
            return st
    raise RuntimeError("no non-empty stage")


def _is_heavy_hex(cfg: BaseConfig, n: int) -> bool:
    cm = cfg.get("coupling_map")
    return cm is not None and cm.size() != n          # corpus convention: heavy-hex maps add ancillas


def _gated(cfg: BaseConfig, build_mutant, gate) -> Transpiler:
    """Decide per input circuit (pre-execution facts only) whether the mutated pipeline applies."""
    base = _preset(cfg).run
    mutant = build_mutant(cfg)

    def fn(circuit: QuantumCircuit) -> QuantumCircuit:
        return mutant(circuit) if gate(cfg, circuit) else base(circuit)
    return fn


def _hash_choice() -> bool:
    """A tie-break decided by Python's hash-randomised set iteration order (PYTHONHASHSEED), the mechanism of
    Qiskit #14730 / #16237. Stable within one interpreter, varies across process launches."""
    return next(iter({"keep", "shift"})) == "shift"


# ------------------------------------------------------------------------------------------------ passes
class _ZeroGlobalPhase(TransformationPass):
    def run(self, dag: DAGCircuit) -> DAGCircuit:
        dag.global_phase = 0.0
        return dag


class _RZToPositiveNoPhase(TransformationPass):
    """RZ(t) with t < 0 -> RZ(t + 2pi). RZ has period 4pi, RZ(t + 2pi) = -RZ(t): the -1 is dropped."""
    def run(self, dag: DAGCircuit) -> DAGCircuit:
        for node in dag.op_nodes():
            if node.op.name == "rz":
                t = float(node.op.params[0])
                if t < -1e-12:
                    dag.substitute_node(node, RZGate(t + 2 * math.pi))
        return dag


class _CPRuleMissingPhase(TransformationPass):
    """CP(t) = exp(i t/4) . RZ(t/2) x RZ(t/2) . RZZ(-t/2). The rewrite omits exp(i t/4)."""
    def run(self, dag: DAGCircuit) -> DAGCircuit:
        for node in list(dag.op_nodes()):
            if node.op.name == "cp":
                t = float(node.op.params[0])
                sub = QuantumCircuit(2)
                sub.rz(t / 2, 0)
                sub.rz(t / 2, 1)
                sub.append(RZZGate(-t / 2), [0, 1])
                dag.substitute_node_with_dag(node, circuit_to_dag(sub))
        return dag


class _InputCountIncludesAncillas(AnalysisPass):
    def run(self, dag: DAGCircuit) -> None:
        n_in = self.property_set["num_input_qubits"]
        # Only on the "happy path" of TranspileLayout.from_property_set (no elided virtual permutation): with a
        # virtual_permutation_layout present, the miscount makes layout construction raise, which would turn the
        # fault into a visible crash rather than a silent metadata error.
        if self.property_set["virtual_permutation_layout"] is not None:
            return
        if n_in is not None and dag.num_qubits() > n_in:
            self.property_set["num_input_qubits"] = dag.num_qubits()


class _DropInputRegisters(AnalysisPass):
    """Replace the input virtual qubits with register-less Qubit objects, consistently in the initial layout
    and the input-index map, so the recorded layout still composes but has lost the input registers."""
    def run(self, dag: DAGCircuit) -> None:
        layout: Layout | None = self.property_set["layout"]
        idx: dict | None = self.property_set["original_qubit_indices"]
        n_in = self.property_set["num_input_qubits"]
        if layout is None or idx is None or n_in is None:
            return
        repl = {q: Qubit() for q, i in idx.items() if i < n_in}
        new_idx = {repl.get(q, q): i for q, i in idx.items()}
        v2p = layout.get_virtual_bits()
        new_layout = Layout({repl.get(v, v): p for v, p in v2p.items()})
        for reg in layout.get_registers():
            if not any(q in repl for q in reg):
                new_layout.add_register(reg)
        self.property_set["layout"] = new_layout
        self.property_set["original_qubit_indices"] = new_idx
        vpl: Layout | None = self.property_set["virtual_permutation_layout"]
        if vpl is not None:          # keep the elided-permutation record consistent with the new qubit objects
            self.property_set["virtual_permutation_layout"] = Layout(
                {repl.get(v, v): p for v, p in vpl.get_virtual_bits().items()})


class _SwapFinalLayoutRecord(AnalysisPass):
    """Record a final layout in which the end positions of the first two input qubits are exchanged."""
    def run(self, dag: DAGCircuit) -> None:
        layout: Layout | None = self.property_set["layout"]
        idx = self.property_set["original_qubit_indices"]
        if layout is None or idx is None:
            return
        fl: Layout | None = self.property_set["final_layout"]
        if fl is None:
            fl = Layout({q: i for i, q in enumerate(dag.qubits)})
        # physical qubits where input virtual 0 and 1 start
        inputs = sorted((i, q) for q, i in idx.items())
        p0, p1 = layout[inputs[0][1]], layout[inputs[1][1]]
        m = dict(fl.get_physical_bits())            # physical index -> qubit in the dag
        m[p0], m[p1] = m[p1], m[p0]
        self.property_set["final_layout"] = Layout(m)


class _HashOrderRZShift(TransformationPass):
    """Where the hash-order tie-break says so: RZ(t), t < 0  ->  RZ(t + 2pi) with global phase + pi.
    Exactly equal operators (phase included), different compiled representation."""
    def run(self, dag: DAGCircuit) -> DAGCircuit:
        if not _hash_choice():
            return dag
        for node in dag.op_nodes():
            if node.op.name == "rz" and float(node.op.params[0]) < -1e-12:
                dag.substitute_node(node, RZGate(float(node.op.params[0]) + 2 * math.pi))
                dag.global_phase += math.pi
        return dag


class _HashOrderRZ4Pi(TransformationPass):
    """Where the hash-order tie-break says so: RZ(t), t > 0  ->  RZ(t - 4pi). RZ has period 4pi: identical
    operator, different compiled representation."""
    def run(self, dag: DAGCircuit) -> DAGCircuit:
        if not _hash_choice():
            return dag
        for node in dag.op_nodes():
            if node.op.name == "rz" and float(node.op.params[0]) > 1e-12:
                dag.substitute_node(node, RZGate(float(node.op.params[0]) - 4 * math.pi))
        return dag


# ------------------------------------------------------------------------------------------------ builders
def _m_append(stage: str, pass_cls):
    def b(cfg):
        pm = _preset(cfg)
        _append(pm, stage, pass_cls())
        return pm.run
    return b


def _m_append_last(pass_cls):
    def b(cfg):
        pm = _preset(cfg)
        _append(pm, _last_stage(pm), pass_cls())
        return pm.run
    return b


def _m_prepend(stage: str, pass_cls):
    def b(cfg):
        pm = _preset(cfg)
        _prepend(pm, stage, pass_cls())
        return pm.run
    return b


def g1(cfg):
    return _gated(cfg, _m_append("translation", _ZeroGlobalPhase), lambda c, qc: qc.num_qubits >= G1_MIN_QUBITS)


def g2(cfg):
    return _gated(cfg, _m_append("optimization", _RZToPositiveNoPhase), lambda c, qc: _is_heavy_hex(c, qc.num_qubits))


def g3(cfg):
    return _m_prepend("translation", _CPRuleMissingPhase)(cfg)


def k1(cfg):
    return _m_append_last(_InputCountIncludesAncillas)(cfg)        # fires only when ancillas exist


def k2(cfg):
    return _gated(cfg, _m_append_last(_DropInputRegisters), lambda c, qc: not _is_heavy_hex(c, qc.num_qubits))


def k3(cfg):
    return _gated(cfg, _m_append_last(_SwapFinalLayoutRecord), lambda c, qc: qc.num_qubits >= K3_MIN_QUBITS)


def d1(cfg):
    return _gated(cfg, _m_append("optimization", _HashOrderRZShift),
                  lambda c, qc: (not _is_heavy_hex(c, qc.num_qubits)) and qc.num_qubits >= D1_MIN_QUBITS
                  and c.get("optimization_level") == 3)


def d2(cfg):
    return _gated(cfg, _m_append("optimization", _HashOrderRZ4Pi),
                  lambda c, qc: _is_heavy_hex(c, qc.num_qubits) and c.get("optimization_level") == 1)


# Channel of each operator (the matched oracle that should see it) and the FaultType used in the ledger.
CHANNEL = {}


def _op(family, fault_type, stage, desc, builder, channel):
    CHANNEL[family] = channel
    return MutationOperator(family, fault_type, stage, desc, builder)


MUTATION_OPERATORS_P3: dict[str, MutationOperator] = {op.family: op for op in [
    _op("phase_drop_after_translation_wide", FaultType.semantic, "translation",
        f"Global phase zeroed after translation for inputs >= {G1_MIN_QUBITS} qubits.", g1, "global_phase"),
    _op("rz_canonicalize_without_phase", FaultType.semantic, "optimization",
        "RZ angles moved to [0, 2pi) without the -1 factor, heavy-hex targets only.", g2, "global_phase"),
    _op("cp_rule_missing_phase", FaultType.semantic, "translation",
        "CP rewritten as RZ x RZ . RZZ without the exp(i theta/4) factor.", g3, "global_phase"),
    _op("input_count_includes_ancillas", FaultType.contract_metadata, "scheduling",
        "Recorded number of input qubits counts the ancillas (only when ancillas are added).", k1, "contract"),
    _op("input_registers_dropped", FaultType.contract_metadata, "scheduling",
        "Input register identity dropped from the recorded layout, ancilla-free targets.", k2, "contract"),
    _op("final_layout_record_wide", FaultType.contract_metadata, "routing",
        f"Recorded final layout exchanges two inputs' end positions, inputs >= {K3_MIN_QUBITS} qubits.", k3,
        "layout_record"),
    _op("hash_order_rz_shift_line", FaultType.determinism, "optimization",
        f"Hash-order choice RZ(t) vs -RZ(t+2pi), line targets, level 3, >= {D1_MIN_QUBITS} qubits.", d1,
        "determinism"),
    _op("hash_order_rz_4pi_heavyhex", FaultType.determinism, "optimization",
        "Hash-order choice RZ(t) vs RZ(t-4pi), heavy-hex targets, level 1.", d2, "determinism"),
]}


def get_operator_p3(family: str) -> MutationOperator:
    return MUTATION_OPERATORS_P3[family]
