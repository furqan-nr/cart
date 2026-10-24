#!/usr/bin/env python3
"""POST HOC preview (exploratory, run on 2026-10-24 BEFORE registration R2, on the first registration's cohorts
C261 and C252): mean / max real spend per budget and detections at each budget for the observability-aware order,
under three cost estimates:
  registered  the first registration's estimate (K1 costs x compile-based speed factor), which failed claim C;
  T1          K1 compile costs x compile ratio, K1 check costs x reference-benchmark ratio;
  T2          previous-revision costs taken from the SAME labeling session's clean baseline. This is optimistic: the
              same measurement is both estimate and charge for unchanged candidates (rule L3). Registration R2 therefore
              takes the estimate from a SEPARATE calibration session.
Disclosed in PREREGISTRATION_P3_R2.md. Output: posthoc/preview_cost_estimators.json.

    PYTHONPATH=cart/src:obsaware/src python posthoc/preview_cost_estimators.py > posthoc/preview_cost_estimators.json
"""
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

from obsaware.cost_model import cost_table, load_session, speed_factor, units_from_session
from obsaware.selection import STRATEGIES, CostTable, real_spend

spec = importlib.util.spec_from_file_location("an", "obsaware/scripts/analyze_p3.py")
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)
prev = load_session("data/K1/out_k1")
kb = st.median(json.loads(l)["median_s"] for l in open("data/K1/out_k1/benchmark.jsonl"))


def componentwise(sess, kc, km):
    ct = cost_table(sess, k=1.0)
    return CostTable(compile_s={t: v * kc for t, v in ct.compile_s.items()},
                     check_s={(t, c): (v * kc if c == "determinism" else v * km) for (t, c), v in ct.check_s.items()},
                     det_fixed_s=ct.det_fixed_s * km, applicable=ct.applicable)


out = {}
for coh in ("data/C261/out_C261", "data/C252/out_C252"):
    cur = load_session(coh)
    units = units_from_session(prev)
    kc = speed_factor({t: r["compile_s"] for t, r in cur["units"].items()},
                      {t: r["compile_s"] for t, r in prev["units"].items()})[0]
    km = st.median(json.loads(l)["median_s"] for l in open(coh + "/benchmark.jsonl")) / kb
    ests = {"registered": cost_table(prev, k=kc), "T1": componentwise(prev, kc, km), "T2_same_session": cost_table(cur, k=1.0)}
    events = [json.loads(p.read_text()) for p in sorted(Path(coh, "events").glob("*.json"))]
    out[Path(coh).name] = {"k_compile": kc, "k_benchmark": km, "estimators": {}}
    for name, est in ests.items():
        full, res = est.total(), {}
        for f in (0.02, 0.05, 0.10):
            b = f * full
            ratios, det = [], {s: 0 for s in STRATEGIES}
            for ev in events:
                d, real = an.event_tables(ev, est, cur)
                for s, fn in STRATEGIES.items():
                    sel = fn(units, est, b)
                    det[s] += any(d.get(i, False) for i in sel)
                    if s == "observability":
                        ratios.append(real_spend(sel, real) / b)
            res[str(f)] = {"observability_spend_mean": st.mean(ratios), "observability_spend_max": max(ratios),
                           "detected": det}
        out[Path(coh).name]["estimators"][name] = res
json.dump(out, sys.stdout, indent=1)
print()
