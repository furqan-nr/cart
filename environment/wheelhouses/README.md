# Environment provenance of the Kaggle sessions

The session scripts recorded Python and Qiskit versions (`data/*/out_*/hardware.json`) but not the Qiskit Aer version. The information below was **recovered after the sessions**, and each row says from what.

Every session installed offline (Internet off) with `pip install --no-index --find-links <wheelhouse>` from the attached wheelhouse dataset, so it could only load the wheels in that wheelhouse.

| Qiskit | Wheelhouse dataset | Sessions | Qiskit Aer | Source of the Aer version |
|---|---|---|---|---|
| 2.4.2 | `p3-wheelhouse-qiskit-2-4-2` | K1 | 0.17.2 | runbook pin (`obsaware/kaggle/KAGGLE_RUNBOOK.md`) and authors' record |
| 2.6.1 | `p3-wheelhouse-qiskit-2-6-1` | C261 | 0.18.0 | authors' record |
| 2.5.2 | `p3-wheelhouse-qiskit-2-5-2` | C252 | 0.18.0 | authors' record |
| 2.6.0 | `p3-wheelhouse-qiskit-2-6-0` | N260, C260 | 0.18.0 | authors' record |
| 2.3.1 | `p3-wheelhouse-qiskit-2-3-2` (dataset name typo; contents are Qiskit 2.3.1) | N231, C231 | 0.18.0 | **verified**: `build_wheelhouse_2.3.1.log` (pins line and import check) and the session log line `3.13.15 2.3.1 /kaggle/working/site/qiskit/__init__.py 0.18.0` |

Other pinned packages in the 2.3.1 wheelhouse (from its build log): numpy 2.5.4, scipy 1.18.1, pandas 3.1.0, PyYAML 6.0.3, psutil 7.2.2, rustworkx 0.18.1, dill 0.4.1, stevedore 5.9.1, python-dateutil 3.0.0, six 1.17.0, typing_extensions 4.16.0, tzdata 2026.5. Python 3.13.15 in all sessions.

The dataset name `p3-wheelhouse-qiskit-2-3-2` is a naming slip. The labeling notebook asserts that the attached wheelhouse's `qiskit_requested` equals the cohort's version (2.3.1) before running, and the session log confirms Qiskit 2.3.1 was imported.
