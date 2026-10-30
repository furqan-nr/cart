#!/usr/bin/env python3
"""R3 post hoc (NOT registered): do the frozen checks see the real faults once an input reaches them, and at
which level of testing?

For every R3 fault, trigger units mirror the fix's own regression test, at two levels:
  * PASS level: exactly what the test does (the pass or synthesis call it makes, on its input), giving an input
    circuit and an output circuit;
  * PIPELINE level: the same input circuit (a matrix input becomes a UnitaryGate) compiled with Qiskit's standard
    preset pass manager at optimisation levels 1, 2 and 3, with the basis gates the test uses (else cx, rz, sx, x),
    seed_transpiler 1234.
Each unit runs with the clean build and with the fault build (fault overlay first on PYTHONPATH, as in
r3/label_faults.py), in fresh interpreters with PYTHONHASHSEED 0, 1 and 2. The frozen checks are applied as in the
R3 labeling session (obsaware/scripts/label_cohort.py alarms_and_costs; rule L1 against the clean output), plus
crash or hang (a 120 s limit; #16963's units run with 4 Rust threads, its bug's condition) and determinism (outputs differing across the three hash seeds when the clean build's
do not). A fault is DETECTED at a level if some unit of that level is detected.

Units are FAULT-INFORMED by construction (they come from the fix's test): they show what the checks can see once
an input reaches the fault, not how often a corpus would. Faults whose test exercises no circuit-producing call
(an expression-arithmetic test, a coupling-map container, an error message, a performance fix, a QPY round trip)
have no unit at that level and are reported as outside the checks' scope.

    python posthoc/r3_triggers.py --clean-site <site> --faults <r3 faults dir> --out posthoc/r3_triggers.json
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]

PRELUDE = r'''
import itertools, numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter, Gate, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import (U1Gate, PhaseGate, RZGate, UnitaryGate, PermutationGate, CXGate, CSGate,
                                    CSdgGate, XGate, Measure)
from qiskit.quantum_info import Operator
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import (CommutativeCancellation, CommutationAnalysis, ConsolidateBlocks,
                                      CollectMultiQBlocks, InverseCancellation, ElidePermutations, StarPreRouting,
                                      Split2QUnitaries)
from qiskit.synthesis import TwoQubitBasisDecomposer
from qiskit.converters import dag_to_circuit, circuit_to_dag
from qiskit.dagcircuit import DAGCircuit
UNITS = []   # (unit id, input circuit, callable returning output circuit or None for pipeline, basis)
'''

# fault -> code appending PASS-level units (input circuit, function) and PIPELINE inputs (circuit, basis)
SPECS = {
    "16402": r'''
for gate in (PhaseGate(np.pi/4), U1Gate(np.pi/4)):
    basis = [gate.name, "t", "rz", "cx"]
    for rep in (7, 15, 23, 31):
        qc = QuantumCircuit(1); qc.append(gate, [0])
        for _ in range(rep): qc.t(0)
        UNITS.append((f"{gate.name}_{rep}", qc, lambda c, b=basis: CommutativeCancellation(basis_gates=b)(c), basis))
''',
    "16599": r'''
for n in (2, 3, 4):
    qc = QuantumCircuit(1)
    for _ in range(n): qc.sxdg(0)
    UNITS.append((f"sxdg{n}", qc, lambda c: CommutativeCancellation(["sx", "rz"])(c), ["sx", "rz"]))
''',
    "16884": r'''
qc = QuantumCircuit(3); qc.ccx(0, 1, 2)
UNITS.append(("ccx", qc, lambda c: PassManager([CollectMultiQBlocks(max_block_size=3), ConsolidateBlocks()]).run(c), None))
''',
    "16153": r'''
for qargs in itertools.product([(0, 1), (1, 0)], repeat=2):
    for gates in itertools.permutations([CSGate(), CSdgGate()]):
        qc = QuantumCircuit(2); qc.append(gates[0], qargs[0]); qc.append(gates[1], qargs[1])
        UNITS.append((f"{gates[0].name}{qargs[0]}_{gates[1].name}{qargs[1]}", qc, lambda c: InverseCancellation()(c),
                      ["cs", "csdg", "cx", "rz", "sx", "x"]))
''',
    "17163": r'''
for eps in (1e-6, 1e-7, 1e-8):
    for a in (-1.2, 0.3, 0.4):
        for b in (-0.6, 0.1, 1.5):
            t = QuantumCircuit(2); t.rxx(a, 0, 1); t.ryy(b, 0, 1); t.rzz(-2.0 * eps, 0, 1)
            qc = QuantumCircuit(2); qc.append(UnitaryGate(Operator(t)), [0, 1])
            UNITS.append((f"eps{eps}_a{a}_b{b}", qc,
                          lambda c: TwoQubitBasisDecomposer(CXGate(), euler_basis="ZSX")(Operator(c).data), None))
for eps in (1e-4, 1e-5):
    t = QuantumCircuit(2); t.rzz(eps, 0, 1)
    qc = QuantumCircuit(2); qc.append(UnitaryGate(Operator(t)), [0, 1])
    UNITS.append((f"rzz{eps}", qc, lambda c: TwoQubitBasisDecomposer(CXGate(), euler_basis="ZSX")(Operator(c).data), None))
''',
    "13945": r'''
u = QuantumCircuit(2); u.swap(0, 1); u.global_phase += 1.2345; ug = UnitaryGate(Operator(u))
qc = QuantumCircuit(5); qc.h(0); qc.append(PermutationGate([0, 2, 1]), [0, 2, 3]); qc.swap(0, 2); qc.cx(0, 1)
qc.swap(1, 0); qc.cx(0, 1); qc.cx(0, 2); qc.append(ug, [1, 2]); qc.cx(0, 3); qc.cx(0, 4)
qc.append(PermutationGate([0, 2, 1]), [0, 1, 2]); qc.h(1)
passes = [ElidePermutations, StarPreRouting, lambda: Split2QUnitaries(split_swap=True)]
for r in range(1, 4):
    for comb in itertools.permutations(range(3), r):
        UNITS.append(("order" + "".join(map(str, comb)), qc,
                      lambda c, comb=comb: PassManager([passes[i]() for i in comb]).run(c), None))
''',
    "16656": r'''
def build_dag(c):
    in_reg = QuantumRegister(4, "f"); in_dag = DAGCircuit(); in_dag.add_qreg(in_reg)
    out_reg = QuantumRegister(4, "q"); out_dag = in_dag.copy_empty_like(); out_dag.add_qreg(out_reg)
    out_dag.remove_qregs(in_reg); out_dag.remove_qubits(*in_reg)
    out_dag.apply_operation_back(XGate(), (out_dag.qubits[0],), ()); out_dag.apply_operation_back(XGate(), (out_dag.qubits[1],), ())
    return dag_to_circuit(out_dag)
UNITS.append(("remove_qubits", QuantumCircuit(4), build_dag, None))
''',
    "16963": r'''
qc = QuantumCircuit(2); qc.append(Gate("foo", 1, []), [1]); qc.append(Gate("bar", 2, []), [0, 1])
UNITS.append(("custom_gates_cancellation", qc, lambda c: CommutativeCancellation()(c), None))
UNITS.append(("custom_gates_analysis", qc, lambda c: (CommutationAnalysis()(c), c)[1], None))
''',
}
# the condition of #16963's bug is multithreaded execution (its test runs with default threads)
THREADS = {"16963": {"RAYON_NUM_THREADS": "4"}}
NO_UNIT = {
    "16283": "the test checks ParameterExpression arithmetic; no circuit is compiled",
    "16752": "the test checks ParameterExpression arithmetic; no circuit is compiled",
    "16988": "the test checks the CouplingMap container; no circuit is compiled",
    "15623": "the test checks a QPY save and load round trip; no compilation",
    "14943": "the test checks a generic pass manager returning a falsy value; no circuit",
    "16637": "an error-message fix; no regression test",
    "16476": "a performance fix; no regression test and no output change by design",
}

WORKER = r'''
import json, pickle, sys, warnings
warnings.filterwarnings("ignore")
spec = json.loads(sys.stdin.read())
ns = {}
exec(spec["prelude"] + spec["code"], ns)
from qiskit.transpiler import generate_preset_pass_manager
from obsaware.oracles import fingerprint
out = {}
for uid, qc, fn, basis in ns["UNITS"]:
    for level in spec["levels"]:
        key = f"{uid}|{level}"
        try:
            if level == "pass":
                res = fn(qc)
            else:
                res = generate_preset_pass_manager(optimization_level=int(level), basis_gates=basis or ["cx", "rz", "sx", "x"],
                                                   seed_transpiler=1234).run(qc)
            out[key] = ("ok", qc, res, fingerprint(res))
        except BaseException as exc:
            out[key] = ("crash", qc, f"{type(exc).__name__}: {str(exc)[:160]}", None)
with open(spec["pickle"], "wb") as f:
    pickle.dump(out, f)
'''


def run(site, fault, levels, tmp, hashseed, timeout=120):
    pk = Path(tmp) / f"{fault}_{hashseed}_{abs(hash(site)) % 10**6}.pkl"
    env = dict(os.environ, PYTHONPATH=f"{site}:{os.environ.get('PYTHONPATH', '')}", PYTHONHASHSEED=hashseed)
    env.update(THREADS.get(fault, {}))
    try:
        p = subprocess.run([sys.executable, "-c", WORKER], input=json.dumps(dict(prelude=PRELUDE, code=SPECS[fault],
                           levels=levels, pickle=str(pk))), capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "hang"
    if p.returncode != 0:
        return "died: " + p.stderr[-300:]
    with open(pk, "rb") as f:
        return pickle.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-site", required=True)
    ap.add_argument("--faults", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.path[:0] = [str(ROOT / "cart" / "src"), str(ROOT / "obsaware" / "src")]
    import importlib.util
    spec = importlib.util.spec_from_file_location("label_cohort", ROOT / "obsaware" / "scripts" / "label_cohort.py")
    lc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lc)
    from cart.oracles.quality import QualityThresholds
    th = QualityThresholds.load()
    tmp = tempfile.mkdtemp()
    levels = ["pass", "1", "2", "3"]
    summary, units = {}, []
    for fault, code in SPECS.items():
        fs = Path(tmp) / f"site_{fault}"
        shutil.copytree(Path(a.clean_site) / "qiskit", fs / "qiskit")
        ov = Path(a.faults) / fault / "overlay"
        for p in ov.rglob("*"):
            if p.is_file():
                t = fs / p.relative_to(ov)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, t)
        clean = [run(a.clean_site, fault, levels, tmp, hs) for hs in ("0", "1", "2")]
        faulty = [run(str(fs), fault, levels, tmp, hs) for hs in ("0", "1", "2")]
        det = {lv: [] for lv in levels}
        if any(isinstance(f, str) for f in faulty):
            for lv in levels:
                det[lv].append(("all units", "crash/hang: " + next(f for f in faulty if isinstance(f, str))[:120]))
        else:
            for key, (st, qc, res, fp) in clean[0].items():
                uid, lv = key.rsplit("|", 1)
                fst, _, fres, ffp = faulty[0][key]
                rec = dict(fault=fault, unit=uid, level=lv, clean_status=st, fault_status=fst)
                checks = []
                if st != "ok":
                    rec["note"] = "clean call failed: " + res
                elif fst != "ok":
                    checks = ["crash (every check)"]
                else:
                    clean_fps = {c[key][3] for c in clean}
                    fault_fps = {f[key][3] for f in faulty}
                    if len(fault_fps) > 1 and len(clean_fps) == 1:
                        checks.append("determinism")
                    if ffp != fp:
                        q, b, c = qc, res, fres
                        if q.num_qubits == 0 or (q.size() == 0 and b.size() == 0):
                            q = b
                        cfg = dict(coupling_map=None, basis_gates=None)
                        try:
                            alarm, _ = lc.alarms_and_costs(q, b, c, cfg, th)
                            alarm0, _ = lc.alarms_and_costs(q, b, b, cfg, th)
                        except Exception:
                            # a check cannot read a gate (e.g. the simulator lacks cs): decompose all three circuits
                            # to u/cx with the clean build (semantics and global phase preserved), then check
                            from qiskit import transpile
                            q, b, c = [transpile(x, basis_gates=["u", "cx"], optimization_level=0) for x in (q, b, c)]
                            rec["decomposed_for_checks"] = True
                            alarm, _ = lc.alarms_and_costs(q, b, c, cfg, th)
                            alarm0, _ = lc.alarms_and_costs(q, b, b, cfg, th)
                        checks += [k for k, v in alarm.items() if v and not alarm0.get(k)]
                        rec["changed"] = True
                rec["detected_by"] = checks
                units.append(rec)
                if checks:
                    det[lv].append((uid, checks))
        summary[fault] = {lv: dict(units_detected=len(v), checks=sorted({c for _, cs in v for c in (cs if isinstance(cs, list) else [cs])}))
                          for lv, v in det.items()}
        print(fault, {lv: (s["units_detected"], s["checks"]) for lv, s in summary[fault].items()}, flush=True)
        shutil.rmtree(fs, ignore_errors=True)
    for f, why in NO_UNIT.items():
        summary[f] = dict(no_unit=why)
    Path(a.out).write_text(json.dumps(dict(note="post hoc, fault-informed trigger units; not registered",
                                           summary=summary, units=units), indent=1, default=str))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
