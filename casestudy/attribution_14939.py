"""Post hoc attribution check (exploratory): apply the #14939 fix to TranspileLayout.initial_index_layout in the
running (buggy) Qiskit build, recompile the units on which the frozen contract check raised K0, and recheck."""
import json, sys, warnings
warnings.filterwarnings("ignore")
import qiskit
from qiskit.transpiler.layout import TranspileLayout
from cart.manifest.static_manifest import enumerate_costhet_units
from cart.labels.ground_truth import _base_config
from cart.manifest.circuits import build
from cart.events.mutations import baseline_transpiler
from obsaware.oracles import contract_v2

def fixed_initial_index_layout(self, filter_ancillas=False):
    virtual_map = self.initial_layout.get_virtual_bits()
    if filter_ancillas:
        output = [None] * self._input_qubit_count
    else:
        output = [None] * len(virtual_map)
    for virt, phys in virtual_map.items():
        pos = self.input_qubit_mapping[virt]
        if filter_ancillas and pos >= self._input_qubit_count:
            continue
        output[pos] = phys
    return output

ids = sys.argv[1].split(",")
units = {u.test_id: u for u in enumerate_costhet_units()}
res = {}
for t in ids:
    u = units[t]; cfg = _base_config(u); qc = build(u.circuit_family, u.n_qubits, seed=1234)
    out = baseline_transpiler(cfg)(qc)
    before = contract_v2(qc, out)
    orig = TranspileLayout.initial_index_layout
    TranspileLayout.initial_index_layout = fixed_initial_index_layout
    after = contract_v2(qc, out)
    TranspileLayout.initial_index_layout = orig
    res[t] = dict(before=[list(v) for v in before.violations], after_fix=[list(v) for v in after.violations])
print(json.dumps(dict(qiskit=qiskit.__version__, units=res), indent=1))
