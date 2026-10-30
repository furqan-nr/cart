# Minimal reproducer for observation O1: no cart, no fault operators, not a corpus unit.
import warnings; warnings.filterwarnings("ignore")
import qiskit, numpy as np
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap, generate_preset_pass_manager
n = 6
qc = QuantumCircuit(n)
for j in range(n):
    qc.h(j)
    for k in range(j + 1, n):
        qc.cp(np.pi / 2 ** (k - j), k, j)
pm = generate_preset_pass_manager(optimization_level=3, coupling_map=CouplingMap.from_heavy_hex(3),
                                  basis_gates=["cx", "rz", "sx", "x"], seed_transpiler=1234)
full = {tuple(pm.run(qc).layout.initial_index_layout()) for _ in range(10)}
inputs = {tuple(pm.run(qc).layout.initial_index_layout(filter_ancillas=True)) for _ in range(10)}
print(qiskit.__version__, "distinct full initial_index_layout in 10 runs:", len(full), "| input-only:", len(inputs))
