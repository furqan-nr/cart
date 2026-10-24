# Registration R2

Files of the second registration (`../PREREGISTRATION_P3_R2.md`): the frozen analysis `analyze_r2.py` and the manifest tool `freeze_r2.py`. Labeling and calibration reuse the first registration's frozen driver and notebooks unchanged.

Analysis, once the four sessions exist:

```bash
python r2/analyze_r2.py --pair data/N260/out_N260 data/C260/out_C260 --pair data/N231/out_N231 data/C231/out_C231 \
    --out results/registered_analysis_r2.json
```
