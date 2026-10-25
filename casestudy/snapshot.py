#!/usr/bin/env python3
"""Historical-fault case study: verdict snapshot of ONE Qiskit build (run inside that build's environment).

    PYTHONPATH=cart/src:obsaware/src python casestudy/snapshot.py --out casestudy/data/<release>

Part A: every registered corpus unit, compiled with the registered baseline transpiler; per unit the output,
probe and contract verdicts (frozen code), the K3' variant, the quality metrics, the raw fingerprint, and the
determinism lane (hash seeds 0, 1, 2, fresh interpreters). Part B: the five trigger units of PROTOCOL_CASESTUDY.md.
Nothing here is compared; casestudy/analyze.py compares two snapshots.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
for _k, _v in {"RAYON_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "TRUE"}.items():
    os.environ.setdefault(_k, _v)

import qiskit  # noqa: E402
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.transpiler import CouplingMap, generate_preset_pass_manager  # noqa: E402

from cart.events.mutations import baseline_transpiler  # noqa: E402
from cart.labels.ground_truth import _base_config  # noqa: E402
from cart.manifest.circuits import build  # noqa: E402
from cart.manifest.static_manifest import enumerate_costhet_units  # noqa: E402
from cart.oracles.quality import count_2q  # noqa: E402
from cart.oracles.semantic import check_semantic  # noqa: E402
from obsaware.determinism import run_batch  # noqa: E402
from obsaware.oracles import PROBE_MAX_QUBITS, contract_v2, fingerprint, is_unitary_pure, state_probe  # noqa: E402

HASHSEEDS = ("0", "1", "2")


# ------------------------------------------------------------------------------------------------ K3' variant
def k3_prime(original: QuantumCircuit, transpiled: QuantumCircuit):
    """True if every input register of the original appears in layout.initial_layout.get_registers()."""
    layout = getattr(transpiled, "layout", None)
    if layout is None or getattr(layout, "initial_layout", None) is None:
        return None
    try:
        got = {(r.name, r.size) for r in layout.initial_layout.get_registers()}
    except Exception as exc:  # a getter that raises is a violation
        return False
    want = {(r.name, r.size) for r in original.qregs}
    return want <= got


# ------------------------------------------------------------------------------------------------ triggers
def trigger(name: str):
    """(circuit, pass-manager kwargs, basis for the structural check, coupling map or None)."""
    if name == "P1_15024":
        qc = QuantumCircuit(3)
        qc.h(0); qc.cx(0, 1); qc.cx(1, 2)
        cm = CouplingMap.from_line(5)
        return qc, dict(optimization_level=1, coupling_map=cm, basis_gates=["cx", "rz", "sx", "x"],
                        initial_layout=[0, 1, 2], seed_transpiler=1234), ["cx", "rz", "sx", "x"], cm
    if name == "P2_14956":
        qc = QuantumCircuit(2)
        qc.h(0); qc.rz(math.pi, 1); qc.rz(math.pi, 1); qc.rx(math.pi, 0); qc.rx(math.pi, 0); qc.cx(0, 1)
        cm = CouplingMap.from_line(2)
        return qc, dict(optimization_level=3, coupling_map=cm, basis_gates=["cx", "rz", "sx", "x"],
                        seed_transpiler=1234), ["cx", "rz", "sx", "x"], cm
    if name == "P3_14730":
        from qiskit.providers.fake_provider import GenericBackendV2
        qc = QuantumCircuit(3)
        qc.rx(0.1, 0); qc.rx(0.2, 1); qc.rx(0.3, 2)
        qc.measure_all()
        be = GenericBackendV2(10, noise_info=True, seed=123)
        return qc, dict(optimization_level=3, target=be.target, seed_transpiler=1234), None, None
    if name == "P4_16237":
        qc = build("qft", 5, seed=1234)
        cm = CouplingMap.from_line(5)
        basis = ["ecr", "cx", "cz", "rz", "sx", "x"]
        return qc, dict(optimization_level=3, coupling_map=cm, basis_gates=basis, seed_transpiler=1234), basis, cm
    if name == "P5_14603":
        from qiskit.circuit.library import PermutationGate
        qc = QuantumCircuit(5)
        for q in range(5):
            qc.h(q)
        qc.swap(0, 1)
        qc.append(PermutationGate([2, 0, 1]), [1, 2, 3])
        cm = CouplingMap.from_line(5)
        return qc, dict(optimization_level=3, coupling_map=cm, basis_gates=["cx", "rz", "sx", "x"],
                        seed_transpiler=1234), ["cx", "rz", "sx", "x"], cm
    raise KeyError(name)


TRIGGERS = ("P1_15024", "P2_14956", "P3_14730", "P4_16237", "P5_14603")


# ------------------------------------------------------------------------------------------------ verdicts
def verdicts(qc, out, cmap, basis) -> dict:
    rec = dict(physical_qubits=out.num_qubits, twoq=count_2q(out), depth=out.depth(), fp=fingerprint(out))
    try:
        if basis is None:
            raise ValueError("no basis/coupling map (target-based compilation)")
        sem = check_semantic(qc, out, coupling_map=cmap, basis_gates=basis)
        rec["output_alarm"] = bool((sem.equivalent is False) or (sem.strength == "structural"
                                                                 and sem.details.get("structural_ok") is False))
        rec["output_tier"] = sem.strength
    except Exception as exc:
        rec["output_alarm"] = None
        rec["output_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    if out.num_qubits <= PROBE_MAX_QUBITS and is_unitary_pure(qc):
        pr = state_probe(qc, out, k=2)
        rec["probe_assessable"] = bool(pr.assessable)
        rec["probe_alarm"] = bool(pr.assessable and (pr.record_ok is False or pr.phase_ok is False))
        rec["probe_detail"] = dict(record_ok=pr.record_ok, phase_ok=pr.phase_ok,
                                   phase_delta=None if pr.phase_delta is None else float(pr.phase_delta))
    else:
        rec["probe_alarm"] = None
    ct = contract_v2(qc, out)
    rec["contract_alarm"] = None if ct.holds is None else (ct.holds is False)
    rec["contract_violations"] = [list(v) for v in ct.violations]
    k3p = k3_prime(qc, out)
    rec["k3prime_alarm"] = None if k3p is None else (k3p is False)
    return rec


def trigger_fp(name: str) -> None:
    qc, kw, _, _ = trigger(name)
    out = generate_preset_pass_manager(**kw).run(qc)
    print(json.dumps({"fp": fingerprint(out)}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--trigger-fp", help="internal: print the fingerprint of one trigger compilation")
    ap.add_argument("--max-width", type=int, default=None, help="smoke test only")
    a = ap.parse_args()
    if a.trigger_fp:
        trigger_fp(a.trigger_fp)
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "build.json").write_text(json.dumps(dict(qiskit=qiskit.__version__, python=sys.version.split()[0]),
                                               indent=1))
    # ---- Part A: corpus
    units = enumerate_costhet_units()
    assert len(units) == 116
    if a.max_width:
        units = [u for u in units if u.n_qubits <= a.max_width]
    pa = out / "corpus.json"
    if not pa.exists():
        res = {}
        for i, u in enumerate(units, 1):
            cfg = _base_config(u)
            qc = build(u.circuit_family, u.n_qubits, seed=1234)
            try:
                o = baseline_transpiler(cfg)(qc)
            except Exception as exc:
                res[u.test_id] = dict(crash=f"{type(exc).__name__}: {str(exc)[:200]}")
                continue
            res[u.test_id] = verdicts(qc, o, cfg["coupling_map"], cfg["basis_gates"])
            print(f"{qiskit.__version__} corpus {i:3d}/{len(units)} {u.test_id}", flush=True)
        pa.write_text(json.dumps(res, indent=1))
    pd = out / "determinism.json"
    if not pd.exists():
        spec = [dict(id=u.test_id, family=u.circuit_family, n=u.n_qubits, backend=u.backend_id,
                     level=_base_config(u)["optimization_level"], circuit_seed=1234) for u in units]
        r = run_batch(spec, operator=None, hashseeds=HASHSEEDS)
        pd.write_text(json.dumps({k: dict(distinct=v["distinct"], deterministic=v["deterministic"])
                                  for k, v in r.per_unit.items()}, indent=1))
    # ---- Part B: triggers
    pt = out / "triggers.json"
    if not pt.exists():
        res = {}
        for name in TRIGGERS:
            try:
                qc, kw, basis, cmap = trigger(name)
                o = generate_preset_pass_manager(**kw).run(qc)
                rec = verdicts(qc, o, cmap, basis)
            except Exception as exc:
                res[name] = dict(crash=f"{type(exc).__name__}: {str(exc)[:200]}",
                                 trace=traceback.format_exc()[-600:])
                continue
            fps = set()
            for hs in HASHSEEDS:
                env = dict(os.environ, PYTHONHASHSEED=hs)
                p = subprocess.run([sys.executable, __file__, "--trigger-fp", name], capture_output=True, text=True,
                                   env=env)
                fps.add(json.loads(p.stdout.strip().splitlines()[-1])["fp"] if p.returncode == 0 else f"ERR:{hs}")
            rec["det_distinct"] = len(fps)
            res[name] = rec
            print(f"{qiskit.__version__} trigger {name} done", flush=True)
        pt.write_text(json.dumps(res, indent=1))
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
