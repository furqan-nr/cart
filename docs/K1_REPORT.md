# Session K1 report: clean-baseline cost calibration (Qiskit 2.4.2)

Run by Furqan on Kaggle, 23 Oct 2026, 18:16 to 18:48 UTC (32 min). Output: `out_k1.zip` (SHA-256 9fcdc41782ab82fa74cdd42bc3eccee8e4eb69f3fe680337b84fed88e1ba154f). Development data: no fault operator was run, so no corpus detection label exists.

## Session quality
- Hardware: Intel Xeon CPU @ 2.20GHz, 4 vCPU (pinned to one core), Python 3.13.15, Qiskit 2.4.2, image `gcr.io/kaggle-images/python@sha256:17b2fc7f...`.
- Reference benchmark: 13 readings, median 0.544 to 0.582 s, **drift 4.2%** from the first reading.
- Completeness: 116 of 116 units.
- Compile timing stability: one unit with IQR above 25% of its median among units above 5 ms (qft-n5-heavy_hex-opt3, 7.5 ms).
- Determinism lane on clean compilations: 0 of 116 units non-deterministic across 3 hash seeds.
- Clean-compilation verdicts: output, quality and contract checks passed on all 116 units. The state probe flagged 2 units (qft-n18-line-opt3, qft-n18-heavy_hex-opt3); see "Probe tolerance" below.

## Costs (CPU seconds, this machine)
| Component | Total |
|---|---|
| Baseline compilation (116 units) | 61.26 |
| Output check (cart semantic: exact on 24 ancilla-free units of at most 12 qubits, structural otherwise) | 1,144.80 |
| Quality check | 5.18 |
| State probe (64 applicable units) | 37.54 |
| Contract check | 0.011 |
| Determinism lane, fixed (3 launches x 2.05) | 6.15 |
| Determinism lane, marginal (3 compilations per unit) | 189.01 |
| **Full observability-aware suite** | **about 1,444** |
| Output-only suite (compile + output + quality) | about 1,211 |

The eight 12-qubit exact checks cost 23.5 to 264.1 s each and make up 79% of the full suite. Budgets as fractions of the full suite: 2% = 28.9 s, 5% = 72.2 s, 10% = 144.4 s. These bind (a single 12-qubit exact check exceeds the 2% budget, most exceed 5%).

## Probe tolerance (design change before registration)
On the two flagged units the probe's phase differed between probes by 3e-6 to 2.4e-5 rad, above its 1e-6 tolerance, while the overlap magnitude was 1 to within 1e-6. Disabling `ConsolidateBlocks` in the level-3 pipeline removed the deviation (phase difference at machine precision), so Qiskit's level-3 two-qubit block resynthesis changes these near-identity blocks by about 1e-5 rad. Whether that is an intended numerical tolerance or a precision weakness is not established (observation O2). The probe's two phase tolerances were widened to 1e-3 rad (about 40x the largest clean deviation). After the change: all 64 probe-applicable clean units pass (largest global-phase deviation 4e-6 rad), and the development operator check detects exactly what it detected before. This change used clean-baseline data only and is disclosed in the registration.
