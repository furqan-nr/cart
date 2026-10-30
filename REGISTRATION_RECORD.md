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

## Registration R2 (`PREREGISTRATION_P3_R2.md`)

| Step | Commit | Commit time | Push time | Manifest check | Notes |
|---|---|---|---|---|---|
| R2 registration pushed | `504533ecbff05cecc79a67e3862cd23918564beb` | 2026-10-24 18:43:49 | before 19:20 (seen on GitHub by an independent clone) | R2 7/7 and first 85/85 (public clone) | No R2 cohort data existed |
| Wheelhouse built, Qiskit 2.6.0 | | | | | Kaggle dataset `p3-wheelhouse-qiskit-2-6-0`; Qiskit 2.6.0 confirmed by the sessions' hardware records |
| Wheelhouse built, Qiskit 2.3.1 | | | | | Kaggle dataset `p3-wheelhouse-qiskit-2-3-1`; Qiskit 2.3.1 confirmed by the sessions' hardware records |
| Calibration session N260 (Kaggle, start and end) | (data commit) | | | | 2026-10-24 19:40:18 to 20:07:00; drift 1.8%; `data/N260/out_N260.zip` SHA-256 f4cb959b8d2e4bb54a5b1a7df8c246fb5dca395ee1ffc2116e0d68032443e088 |
| Labeling session C260 (Kaggle, start and end) | (data commit) | | | | 2026-10-24 20:25:25 to 23:36:26 (after N260 ended); drift 10.7%; `data/C260/out_C260.zip` SHA-256 90de32c3b7f59ca9651a29e9d11f053ff3eea5c9a4386295ed2d1109a2a5d1ff |
| Calibration session N231 (Kaggle, start and end) | (data commit) | | | | 2026-10-24 19:52:34 to 20:23:03; drift 3.7%; `data/N231/out_N231.zip` SHA-256 0b5e54533ef335f109643c6ef0337bc40223457ac6781db1774e46a6a0558d28 |
| Labeling session C231 (Kaggle, start and end) | (data commit) | | | | 2026-10-24 20:29:07 to 2026-10-25 00:03:23 (after N231 ended); drift 3.2%; `data/C231/out_C231.zip` SHA-256 f12739fcab9b4b1d8640d412a772af46de6ff93c89df432f668394b3a6471700 |
| R2 registered analysis run | (data commit) | | | R2 7/7, first 85/85 | Run 2026-10-25 with the frozen `r2/analyze_r2.py`, from a clean clone of 504533e and on the authors' machine (identical results). A, B and C SUPPORTED in both cohorts. `results/registered_analysis_r2.json`; summary in `docs/RESULTS_P3_R2.md` |

## Registration R3

**Where R3 is reported.** R3 asks a different question from R1 and R2 (how far a fixed corpus reveals real faults) and is reported separately, together with its post hoc diagnosis (`docs/R3_DIAGNOSIS.md`). The report of R1 and R2 refers to R3 as a separately reported follow-up. "P3" in file names and "(Paper 3)" in the frozen registration titles are internal working labels.

- Registration commit `198c867a6dc243743fe2f71d1782365263e7983e`, committed and pushed 2026-10-29 18:26:14 +0500 (13:26:14 UTC); the pushed manifest equals the frozen one.
- Kaggle datasets made from: `p3-code-r3.zip` (sha256 `96cdd564f95eb33ed32517ac751d2705f1b722c94e0f1ecb453dc08f8354d66a`), `p3-wheelhouse-r3.zip`, `p3-r3-faults.zip` (hashes of their contents in `r3/wheelhouse.sha256` and `r3/fault_overlays.sha256`).
- Calibration session N_R3: started 2026-10-29 13:41:49 UTC (hardware.json), Kaggle run time 1836 s; output `data/NR3/out_NR3.zip` (sha256 `b9dd5ce39ba0238769eecfcc526de8e38f56d91d00c2e5e27147a582df546bcf`).
- Labeling session R3: started 2026-10-29 14:50:43 UTC, after N_R3 had finished; Kaggle run time 4337 s; output `data/R3/out_R3.zip` (sha256 `696c0fb4b15b386cb4d2c30ca91082cbde28417ec5f697096606317f1d53cdfb`).
