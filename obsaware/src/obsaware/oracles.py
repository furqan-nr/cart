"""Paper 3 oracle portfolio: cheap matched oracles for the output-invisible channels.

These complement, and do not replace, cart's oracles (02_baseline_cart/src/cart/oracles). Nothing in cart is
modified. Three mechanisms:

  * state_probe      A layout-aware statevector probe. Prepares k random product states on the physical wires
                     chosen by the recorded initial layout, runs the compiled circuit, undoes the recorded final
                     permutation and compares with the original circuit's output state, INCLUDING its phase.
                     One probe gives two verdicts:
                       - phase:     whether the compiled circuit preserved the global phase (the global-phase
                                    channel, invisible to output equivalence by construction);
                       - record:    whether the compiled circuit, read through its recorded layout, implements
                                    the original (sampled, so a negative verdict is exact but a positive one is
                                    probabilistic). This is what exposes a wrong final-layout record on circuits
                                    too wide for the dense exact check.
                     Cost is a 2^N statevector (N = physical width), not a 2^n x 2^n operator, so it is usable up
                     to PROBE_MAX_QUBITS physical qubits, ancillas included.
  * contract_v2      cart's contract checker (K0 getter raised, K1 not a permutation, K2 composition) generalised
                     to circuits with ancillas, plus K3 input-register preservation. K3 is the register-set
                     invariant behind Paper 1B's #15024 adapter, so it is reported separately as of known origin.
  * fingerprint      A raw fingerprint of a compiled circuit for the determinism runner (obsaware.determinism).

Verdict convention, as in cart: True = property holds (good), False = violated (fault detected), None = not
assessable for this unit.
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from qiskit import QuantumCircuit

PROBE_MAX_QUBITS = 24          # physical width ceiling for the statevector probe (2^24 complex = 256 MiB)
# Tolerances. MAG_TOL bounds 1 - |overlap| (clean compilations: about 1e-10). The two phase tolerances are in
# radians and were widened from 1e-7 / 1e-6 to 1e-3 after session K1 (clean baseline, Qiskit 2.4.2, no labels):
# Qiskit's level-3 two-qubit block resynthesis (ConsolidateBlocks) changes 18-qubit QFT compilations by up to about
# 2.4e-5 rad (phase spread between probes), which the stricter values flagged on correct compilations. 1e-3 is
# about 40x the largest clean deviation on the 116 corpus units; injected phase faults are multiples of pi or sums
# of rotation angles. See docs/OBSERVATIONS.md (O2).
PHASE_TOL = 1e-3
MAG_TOL = 1e-6
CONSISTENCY_TOL = 1e-3
NONUNITARY_OPS = {"measure", "reset"}


# --------------------------------------------------------------------------------------------- helpers
def is_unitary_pure(circuit: QuantumCircuit) -> bool:
    for instr in circuit.data:
        op = instr.operation
        if op.name in NONUNITARY_OPS or op.name in ("if_else", "while_loop", "switch_case", "for_loop"):
            return False
    return True


def _wrap(phi: float) -> float:
    return (phi + math.pi) % (2 * math.pi) - math.pi


def _index_layouts(transpiled: QuantumCircuit, n: int) -> tuple[list[int], list[int]]:
    """(initial, final) index layouts over ALL physical qubits: position = virtual index (inputs first, then
    ancillas), value = physical qubit. Identity when the circuit carries no layout."""
    N = transpiled.num_qubits
    layout = getattr(transpiled, "layout", None)
    if layout is None:
        return list(range(N)), list(range(N))
    return list(layout.initial_index_layout(filter_ancillas=False)), list(layout.final_index_layout(filter_ancillas=False))


def _haar_1q(rng: np.random.Generator) -> tuple[float, float, float]:
    theta = 2 * math.acos(math.sqrt(rng.random()))
    return theta, 2 * math.pi * rng.random(), 2 * math.pi * rng.random()


def _simulate(circ: QuantumCircuit) -> np.ndarray:
    """Statevector including the global phase. Single-threaded Aer when available, else qiskit's reference."""
    try:
        from qiskit_aer import AerSimulator
        sim = AerSimulator(method="statevector", max_parallel_threads=1, max_parallel_experiments=1,
                           max_parallel_shots=1, fusion_enable=True)
        c = circ.copy()
        c.save_statevector()
        res = sim.run(c, shots=1).result()
        return np.asarray(res.get_statevector(), dtype=complex)
    except ImportError:
        from qiskit.quantum_info import Statevector
        return Statevector(circ).data


def _to_virtual_order(sv: np.ndarray, fin: list[int]) -> np.ndarray:
    """Reorder an N-qubit little-endian statevector so that qubit i holds the state of virtual qubit i,
    where fin[i] is the physical qubit that carries virtual qubit i at the end of the circuit."""
    N = len(fin)
    t = sv.reshape([2] * N)                       # axis a <-> qubit N-1-a
    axes = [N - 1 - fin[N - 1 - a] for a in range(N)]
    return t.transpose(axes).reshape(-1)


# --------------------------------------------------------------------------------------------- state probe
@dataclass
class ProbeResult:
    assessable: bool
    record_ok: bool | None          # sampled equivalence through the recorded layout
    phase_ok: bool | None           # global phase preserved (only meaningful when record_ok is True)
    phase_delta: float | None
    cost_s: float
    details: dict[str, Any] = field(default_factory=dict)


def state_probe(original: QuantumCircuit, transpiled: QuantumCircuit, *, k: int = 2, seed: int = 0) -> ProbeResult:
    t0 = time.process_time()
    n, N = original.num_qubits, transpiled.num_qubits
    if not is_unitary_pure(original) or not is_unitary_pure(transpiled):
        return ProbeResult(False, None, None, None, time.process_time() - t0, {"reason": "non_unitary"})
    if N > PROBE_MAX_QUBITS:
        return ProbeResult(False, None, None, None, time.process_time() - t0, {"reason": "too_wide", "N": N})
    try:
        init, fin = _index_layouts(transpiled, n)
    except Exception as exc:       # a layout getter that raises is the contract oracle's signal, not ours
        return ProbeResult(False, None, None, None, time.process_time() - t0,
                           {"reason": f"layout_getter_raised:{type(exc).__name__}"})
    if len(init) != N or len(fin) != N or sorted(fin) != list(range(N)) or sorted(init) != list(range(N)):
        return ProbeResult(True, False, None, None, time.process_time() - t0,
                           {"reason": "recorded layout is not a permutation of the physical qubits"})
    rng = np.random.default_rng(seed)
    overlaps = []
    for _ in range(k):
        angles = [_haar_1q(rng) for _ in range(n)]
        po = QuantumCircuit(n)
        for i, (a, b, c) in enumerate(angles):
            po.u(a, b, c, i)
        so = _simulate(po.compose(original))
        pt = QuantumCircuit(N)
        for i, (a, b, c) in enumerate(angles):
            pt.u(a, b, c, init[i])
        st = _to_virtual_order(_simulate(pt.compose(transpiled)), fin)
        overlaps.append(complex(np.vdot(so, st[: 2 ** n])))
    mags = np.abs(overlaps)
    if np.any(np.abs(mags - 1.0) > MAG_TOL):
        return ProbeResult(True, False, None, None, time.process_time() - t0,
                           {"min_overlap": float(mags.min()), "k": k})
    phis = np.angle(overlaps)
    spread = float(np.max(np.abs((phis - phis[0] + math.pi) % (2 * math.pi) - math.pi)))
    if spread > CONSISTENCY_TOL:
        return ProbeResult(True, False, None, None, time.process_time() - t0,
                           {"reason": "phase differs between probes (not a global phase)", "spread": spread})
    delta = _wrap(float(np.angle(np.mean(np.exp(1j * phis)))))
    return ProbeResult(True, True, abs(delta) <= PHASE_TOL, delta, time.process_time() - t0, {"k": k})


# --------------------------------------------------------------------------------------------- contract v2
@dataclass
class ContractResult:
    holds: bool | None
    violations: list[tuple[str, str]]
    cost_s: float


def _getter(layout, name, **kw):
    fn = getattr(layout, name, None)
    if not callable(fn):
        return None
    try:
        return list(fn(**kw))
    except Exception as exc:
        return f"__error__:{type(exc).__name__}"


def contract_v2(original: QuantumCircuit, transpiled: QuantumCircuit, *, include_k3: bool = True) -> ContractResult:
    """K0-K2 as in cart.oracles.contract_differ, generalised to ancillas; K3 input-register preservation."""
    t0 = time.process_time()
    n, N = original.num_qubits, transpiled.num_qubits
    layout = getattr(transpiled, "layout", None)
    if layout is None:
        return ContractResult(None, [], time.process_time() - t0)
    v: list[tuple[str, str]] = []
    init = _getter(layout, "initial_index_layout", filter_ancillas=True)
    fin = _getter(layout, "final_index_layout", filter_ancillas=True)
    rperm = _getter(layout, "routing_permutation")
    for name, lst in (("initial_index_layout", init), ("final_index_layout", fin), ("routing_permutation", rperm)):
        if isinstance(lst, str):
            v.append(("K0", f"{name} raised {lst}"))
    # K1: the recorded input layouts place exactly the n input qubits on distinct physical qubits
    for name, lst in (("initial_index_layout", init), ("final_index_layout", fin)):
        if isinstance(lst, list):
            ok = (len(lst) == n and all(isinstance(x, (int, np.integer)) for x in lst)
                  and len(set(lst)) == n and all(0 <= x < N for x in lst))
            if not ok:
                v.append(("K1", f"{name} (inputs only) = {lst[:12]}{'...' if len(lst) > 12 else ''} "
                                f"is not an injective map of {n} inputs into {N} physical qubits"))
    if isinstance(rperm, list) and sorted(rperm) != list(range(N)):
        v.append(("K1", "routing_permutation is not a permutation of the physical qubits"))
    # K2: composition, ancilla-free case (as in cart)
    if (N == n and isinstance(init, list) and isinstance(fin, list) and isinstance(rperm, list)
            and sorted(init) == sorted(fin) == sorted(rperm) == list(range(n))):
        if fin != [init[rperm[i]] for i in range(n)] and fin != [rperm[init[i]] for i in range(n)]:
            v.append(("K2", "final layout is neither composition of initial layout and routing permutation"))
    # K3: input registers preserved (register-set invariant behind the #15024 adapter of Paper 1B)
    if include_k3:
        try:
            mapping = layout.input_qubit_mapping
            regs = set()
            for q, idx in mapping.items():
                if idx < n:
                    loc = None
                    try:
                        loc = original.find_bit(q)
                    except Exception:
                        pass
                    if loc is None or not loc.registers:
                        regs.add(("<missing>", -1))
                    else:
                        for r, _ in loc.registers:
                            regs.add((r.name, r.size))
            want = {(r.name, r.size) for r in original.qregs}
            if regs != want:
                v.append(("K3", f"input registers recorded {sorted(regs)} != original {sorted(want)}"))
        except Exception as exc:
            v.append(("K0", f"input_qubit_mapping raised {type(exc).__name__}"))
    return ContractResult(len(v) == 0, v, time.process_time() - t0)


# --------------------------------------------------------------------------------------------- fingerprint
def fingerprint(transpiled: QuantumCircuit) -> str:
    """Raw fingerprint: instruction sequence (name, rounded params, physical qubits), global phase and the
    recorded layout. Two compilations with equal fingerprints are the same compiled object."""
    parts = [f"gp={round(float(transpiled.global_phase) % (2 * math.pi), 10)}"]
    for ins in transpiled.data:
        ps = []
        for p in ins.operation.params:
            try:
                ps.append(f"{float(p):.10f}")
            except (TypeError, ValueError):
                ps.append(str(p))
        qs = [transpiled.find_bit(q).index for q in ins.qubits]
        parts.append(f"{ins.operation.name}({','.join(ps)}){qs}")
    layout = getattr(transpiled, "layout", None)
    if layout is not None:
        # Input qubits only. On Qiskit 2.4.2 the ANCILLA entries of the recorded initial layout vary between
        # repeated fixed-seed runs in one process (development observation O1, docs/OBSERVATIONS.md), while the
        # instructions and the input layouts do not; including ancillas would make every heavy-hex unit look
        # non-deterministic.
        for name in ("initial_index_layout", "final_index_layout"):
            parts.append(f"{name}={_getter(layout, name, filter_ancillas=True)}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
