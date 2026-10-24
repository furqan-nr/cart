# Registration record

Filled in after each step by a commit that changes only this file. Times in UTC.

| Step | Commit | Commit time | Push time | Manifest check | Notes |
|---|---|---|---|---|---|
| Registration pushed | `40077ab4ef0ff59706c21ae2c2997a497d7cc2a1` | 2026-10-24 01:41:50 | at or before 01:43:15 (commit seen on GitHub by an independent clone) | 85/85 match (local and public clone) | First push; no cohort data existed |
| Wheelhouse built, Qiskit 2.6.1 | | | | | |
| Wheelhouse built, Qiskit 2.5.2 | | | | | |
| Cohort C261 labeled (Kaggle version, start and end) | | | | | |
| Cohort C252 labeled (Kaggle version, start and end) | | | | | |
| Registered analysis run | | | | | |

## Notes

- **Registration commit.** Commit `40077ab` constitutes the registration. `PREREGISTRATION_P3.md` was pushed unchanged with the status line written before the push ("DRAFT, not yet registered"). By its own Status paragraph, the document becomes the registration when it and the frozen files are pushed before any cohort data exist, which this push did. The frozen file is not edited, so the manifest stays valid.
- **Kaggle code dataset.** `p3-code` must be uploaded from the zip built from this commit with `obsaware/scripts/make_kaggle_zip.py`: 82 files, SHA-256 `dd75463cc246abc2ebbfddcf86b557335e8c21e47f5f6ba439d0431549955bb6`. All 82 files were checked identical to the commit.
