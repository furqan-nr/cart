"""Post hoc diagnosis (exploratory): which transformation passes produce the global-phase difference of pi on qft-n18-line-opt3? Each pass is replaced by a no-op in turn; the probe is rerun."""
import warnings; warnings.filterwarnings("ignore")
import qiskit, sys
from cart.manifest.static_manifest import enumerate_costhet_units
from cart.labels.ground_truth import _base_config
from cart.manifest.circuits import build
from qiskit.transpiler import generate_preset_pass_manager
from qiskit.transpiler.basepasses import TransformationPass
from obsaware.oracles import state_probe
u=[u for u in enumerate_costhet_units() if u.test_id=="qft-n18-line-opt3"][0]
cfg=_base_config(u); qc=build(u.circuit_family,u.n_qubits,seed=1234)
names=[]
def cb(**kw):
    p=kw["pass_"]
    if isinstance(p,TransformationPass): names.append(type(p))
generate_preset_pass_manager(**cfg).run(qc,callback=cb)
classes=list(dict.fromkeys(names))
print(qiskit.__version__,[c.__name__ for c in classes])
for c in classes:
    if c.__name__ in ("ApplyLayout","SabreSwap","SabreLayout","BasisTranslator","FullAncillaAllocation","EnlargeWithAncilla","UnitarySynthesis","HighLevelSynthesis","GateDirection"): continue
    orig=c.run; c.run=lambda self,dag: dag
    try:
        o=generate_preset_pass_manager(**cfg).run(qc); pr=state_probe(qc,o,k=2)
        print(f"  without {c.__name__:35s} record_ok={pr.record_ok} phase_delta={pr.phase_delta}")
    except Exception as e: print("  ",c.__name__,"error",type(e).__name__)
    c.run=orig
