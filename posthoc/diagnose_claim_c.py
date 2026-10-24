#!/usr/bin/env python3
"""POST HOC (exploratory, written after the registered analysis): why claim C failed, and whether claim A's pattern
survives real costs. Not part of the registration; nothing here changes a registered decision.

1. Cost ratios cohort / K1 on the clean baseline, per component (compile, output check, probe) and for the reference
   benchmark: separates a transpiler-version speed-up from a machine-speed difference.
2. Mean real spend / budget of every strategy at the 5% budget under the registered estimate.
3. Detection when each strategy's planned 5% selection is cut at the REAL budget (items kept while their real cost fits).

From the repository root:
    PYTHONPATH=cart/src:obsaware/src python posthoc/diagnose_claim_c.py > posthoc/diagnose_claim_c.json
"""
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

from obsaware.cost_model import cost_table, load_session, speed_factor, units_from_session
from obsaware.selection import STRATEGIES, Ledger, real_spend

spec = importlib.util.spec_from_file_location("an", "obsaware/scripts/analyze_p3.py")
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)

prev = load_session("data/K1/out_k1")
kb = st.median(json.loads(l)["median_s"] for l in open("data/K1/out_k1/benchmark.jsonl"))
out = {}
for coh in ("data/C261/out_C261", "data/C252/out_C252"):
    cur = load_session(coh)
    cb = st.median(json.loads(l)["median_s"] for l in open(coh + "/benchmark.jsonl"))

    def ratio(key, minv):
        r = [cur["units"][t][key] / prev["units"][t][key] for t in prev["units"]
             if prev["units"][t].get(key) and prev["units"][t][key] >= minv and cur["units"][t].get(key)]
        return {"median": st.median(r), "n_units": len(r)}

    k_raw, k = speed_factor({t: r["compile_s"] for t, r in cur["units"].items()},
                            {t: r["compile_s"] for t, r in prev["units"].items()})
    est = cost_table(prev, k=k)
    full = est.total()
    units = units_from_session(prev)
    b = 0.05 * full
    spend = {s: [] for s in STRATEGIES}
    cut = {s: 0 for s in STRATEGIES}
    for p in sorted(Path(coh, "events").glob("*.json")):
        ev = json.loads(p.read_text())
        det, real = an.event_tables(ev, est, cur)
        for s, fn in STRATEGIES.items():
            sel = fn(units, est, b)
            spend[s].append(real_spend(sel, real) / b)
            led, hit = Ledger(real), False
            for it in sel:
                if led.spent + led.marginal(it) > b + 1e-12:
                    break
                led.add(it)
                hit = hit or det.get(it, False)
            cut[s] += hit
    out[Path(coh).name] = {
        "speed_factor_applied": k,
        "benchmark_ratio_cohort_over_K1": cb / kb,
        "cost_ratio_cohort_over_K1": {"compile": ratio("compile_s", 0.05), "output_check": ratio("output_s", 1.0),
                                      "probe": ratio("probe_s", 0.05)},
        "mean_spend_ratio_5pct": {s: st.mean(v) for s, v in spend.items()},
        "detected_when_cut_at_real_5pct_budget": cut,
        "n_events": len(spend["observability"]),
    }
json.dump(out, sys.stdout, indent=1)
print()
