# Registration record

Filled in after each step by a commit that changes only this file. Times in UTC.

| Step | Commit | Commit time | Push time | Manifest check | Notes |
|---|---|---|---|---|---|
| Registration pushed | `40077ab4ef0ff59706c21ae2c2997a497d7cc2a1` | 2026-10-24 01:41:50 | at or before 01:43:15 (commit seen on GitHub by an independent clone) | 85/85 match (local and public clone) | First push; no cohort data existed |
| Wheelhouse built, Qiskit 2.6.1 | | | | | Kaggle dataset `p3-wheelhouse-qiskit-2-6-1`; Qiskit 2.6.1 confirmed by the session's hardware record |
| Wheelhouse built, Qiskit 2.5.2 | | | | | Kaggle dataset `p3-wheelhouse-qiskit-2-5-2`; Qiskit 2.5.2 confirmed by the session's hardware record |
| Cohort C261 labeled (Kaggle version, start and end) | (data commit) | | | 85/85 before analysis | Kaggle session 2026-10-24 14:32:19 to 17:47:26; Intel Xeon @ 2.20GHz; drift 4.4%; `data/C261/out_C261.zip` SHA-256 96503aceab23b8b28e71386e34bcfd272fcf0fb4022005d265567596a86a82af |
| Cohort C252 labeled (Kaggle version, start and end) | (data commit) | | | 85/85 before analysis | Kaggle session 2026-10-24 11:03:28 to 14:01:38; Intel Xeon @ 2.20GHz; drift 8.2%; `data/C252/out_C252.zip` SHA-256 4a9ddcf9bf0448467834b3d3288143094341ae821f8d7236cb4dc3532693cbbb |
| Registered analysis run | (data commit) | | | 85/85 (public clone at 40077ab) | Run 2026-10-24 about 18:10 UTC with the frozen `analyze_p3.py`, from a clone of commit 40077ab. A and B SUPPORTED, C NOT SUPPORTED. `results/registered_analysis.json`; summary in `docs/RESULTS_P3.md` |

## Notes

- **Registration commit.** Commit `40077ab` constitutes the registration. `PREREGISTRATION_P3.md` was pushed unchanged with the status line written before the push ("DRAFT, not yet registered"). By its own Status paragraph, the document becomes the registration when it and the frozen files are pushed before any cohort data exist, which this push did. The frozen file is not edited, so the manifest stays valid.
- **Kaggle code dataset.** `p3-code` must be uploaded from the zip built from this commit with `obsaware/scripts/make_kaggle_zip.py`: 82 files, SHA-256 `dd75463cc246abc2ebbfddcf86b557335e8c21e47f5f6ba439d0431549955bb6`. All 82 files were checked identical to the commit.
- **Wheelhouse build times** were not recorded; the Kaggle version history of the wheelhouse notebook holds them.
- **Cohort order:** C252 ran before C261. The registration fixes no order.
