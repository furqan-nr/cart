#!/usr/bin/env python3
"""Paper 3 frozen analysis: decides the registered claims A, B and C for each cohort from the labeling sessions.

Inputs:  --prev  the earlier calibration session (K1, Qiskit 2.4.2), the source of every cost ESTIMATE
         --cohort DIR (repeatable), one label_cohort.py output directory per cohort
Output:  --out results JSON and a markdown summary.

Definitions (as registered):
  estimate      obsaware.cost_model.cost_table(K1) x k, k from the speed rule on clean baseline compile costs
  budget        f x estimated full observability-aware suite cost, f in {0.02, 0.05, 0.10}
  selection     each strategy selects items within the budget by the ESTIMATE
  detected      the selection contains an item that detects the event (rule L1 in label_cohort.py)
  spend ratio   REAL cost of the selection (measured in the cohort session) / budget
  first cost    walking the strategy's unbudgeted ranking, cumulative REAL cost up to and including the first
                detecting item (infinite if none)
  detectable    at least one item of the cohort detects the event

Claims, per cohort; a claim is SUPPORTED only if it holds in every cohort analysed:
  A  at the 5% budget, detectable events detected: observability > output_only, observability >= all_checks,
     observability >= cheapest_items
  B  over detectable events, observability's first cost is lower than all_checks' on more events than it is
     higher, with a one-sided exact sign test p < 0.05 (ties dropped)
  C  observability's spend ratio: mean <= 1.25 and max <= 2.0 over all analysed events, at each of the three budgets
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

from obsaware.cost_model import cost_table, load_session, speed_factor, units_from_session
from obsaware.selection import CHECKS, CostTable, Ledger, STRATEGIES, random_items, real_spend

BUDGETS = (0.02, 0.05, 0.10)
PRIMARY = "observability"
COMPARATORS = ("output_only", "all_checks", "cheapest_items")
RANDOM_SEEDS = 20


def sign_test_p(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n


def event_tables(ev: dict, est: CostTable, cur: dict) -> tuple[dict, CostTable]:
    detects, check_s = {}, {}
    for t in est.compile_s:
        pu = ev["per_unit"].get(t)
        for c in est.applicable[t]:
            if c == "determinism":
                d = ev["determinism"]["per_unit"][t]
                detects[(t, c)] = bool(d["detects"])
                check_s[(t, c)] = float(d["cost"])
                continue
            detects[(t, c)] = bool(pu and pu["detects"].get(c, False))
            check_s[(t, c)] = float(pu["cost"][c]) if pu and c in pu["cost"] else float(cur["units"][t][f"{c}_s"])
    fixed = st.median(ev["determinism"]["fixed_cpu_per_launch_s"]) * len(ev["determinism"]["fixed_cpu_per_launch_s"])
    real = CostTable(compile_s={t: float(cur["units"][t]["compile_s"]) for t in est.compile_s}, check_s=check_s,
                     det_fixed_s=fixed, applicable=est.applicable)
    return detects, real


def first_cost(order: list, detects: dict, real: CostTable) -> float:
    led = Ledger(real)
    for it in order:
        led.add(it)
        if detects.get(it):
            return led.spent
    return math.inf


def analyse_cohort(prev: dict, cohort_dir: Path) -> dict:
    cur = load_session(cohort_dir)
    units = units_from_session(prev)
    prev_c = {t: r["compile_s"] for t, r in prev["units"].items()}
    cur_c = {t: r["compile_s"] for t, r in cur["units"].items()}
    k_raw, k = speed_factor(cur_c, prev_c)
    est = cost_table(prev, k=k)
    full = est.total()
    cons = json.loads((cohort_dir / "construction_check.json").read_text())
    excluded = sorted(n for n, v in cons.items() if not v["constructible"])
    events = [json.loads(p.read_text()) for p in sorted((cohort_dir / "events").glob("*.json"))]
    rows = []
    for ev in events:
        detects, real = event_tables(ev, est, cur)
        row = dict(event=ev["event"], group=ev["group"], detectable=any(detects.values()),
                   units_detecting=len({t for (t, c), d in detects.items() if d}),
                   checks_detecting=sorted({c for (t, c), d in detects.items() if d}), budgets={}, first_cost={})
        for f in BUDGETS:
            b = f * full
            res = {}
            for s, fn in STRATEGIES.items():
                sel = fn(units, est, b)
                res[s] = dict(detected=any(detects.get(it, False) for it in sel), spend_ratio=real_spend(sel, real) / b)
            rnd = [random_items(units, est, b, seed=i) for i in range(RANDOM_SEEDS)]
            res["random_items"] = dict(detected=st.mean(any(detects.get(it, False) for it in s) for s in rnd),
                                       spend_ratio=st.mean(real_spend(s, real) / b for s in rnd))
            row["budgets"][str(f)] = res
        for s, fn in STRATEGIES.items():
            row["first_cost"][s] = first_cost(fn(units, est, math.inf), detects, real)
        rows.append(row)
    det_rows = [r for r in rows if r["detectable"]]

    def count(s, f):
        return sum(1 for r in det_rows if r["budgets"][str(f)][s]["detected"])

    a_counts = {s: count(s, 0.05) for s in (PRIMARY,) + COMPARATORS}
    claim_a = (a_counts[PRIMARY] > a_counts["output_only"] and a_counts[PRIMARY] >= a_counts["all_checks"]
               and a_counts[PRIMARY] >= a_counts["cheapest_items"])
    wins = sum(1 for r in det_rows if r["first_cost"][PRIMARY] < r["first_cost"]["all_checks"] - 1e-9)
    losses = sum(1 for r in det_rows if r["first_cost"][PRIMARY] > r["first_cost"]["all_checks"] + 1e-9)
    p_b = sign_test_p(wins, losses)
    claim_b = wins > losses and p_b < 0.05
    c_detail = {}
    claim_c = True
    for f in BUDGETS:
        ratios = [r["budgets"][str(f)][PRIMARY]["spend_ratio"] for r in rows]
        c_detail[str(f)] = dict(mean=st.mean(ratios) if ratios else None, max=max(ratios) if ratios else None)
        claim_c = claim_c and bool(ratios) and st.mean(ratios) <= 1.25 and max(ratios) <= 2.0
    return dict(cohort=cohort_dir.name, speed_factor_raw=k_raw, speed_factor_applied=k, full_suite_estimate_s=full,
                budgets_s={str(f): f * full for f in BUDGETS}, excluded_operators=excluded,
                n_events=len(rows), n_detectable=len(det_rows),
                claim_A=dict(supported=claim_a, detected_at_5pct=a_counts),
                claim_B=dict(supported=claim_b, wins=wins, losses=losses, ties=len(det_rows) - wins - losses, p=p_b),
                claim_C=dict(supported=claim_c, spend_ratio=c_detail),
                detection_by_budget={str(f): {s: count(s, f) for s in list(STRATEGIES)} for f in BUDGETS},
                events=rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", required=True)
    ap.add_argument("--cohort", action="append", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    prev = load_session(args.prev)
    cohorts = [analyse_cohort(prev, Path(c)) for c in args.cohort]
    overall = {c: all(r[c]["supported"] for r in cohorts) for c in ("claim_A", "claim_B", "claim_C")}
    res = dict(overall=overall, cohorts=cohorts)
    Path(args.out).write_text(json.dumps(res, indent=1, default=lambda x: None if x == math.inf else x))
    lines = ["# Paper 3 registered claims", ""]
    for c in cohorts:
        lines += [f"## Cohort {c['cohort']}",
                  f"speed factor {c['speed_factor_raw']:.3f} (applied {c['speed_factor_applied']:.3f}); full suite "
                  f"estimate {c['full_suite_estimate_s']:.1f} s; events {c['n_events']}, detectable {c['n_detectable']}; "
                  f"excluded {c['excluded_operators']}",
                  f"- A: {'SUPPORTED' if c['claim_A']['supported'] else 'NOT SUPPORTED'} {c['claim_A']['detected_at_5pct']}",
                  f"- B: {'SUPPORTED' if c['claim_B']['supported'] else 'NOT SUPPORTED'} wins {c['claim_B']['wins']}, "
                  f"losses {c['claim_B']['losses']}, ties {c['claim_B']['ties']}, p = {c['claim_B']['p']:.4f}",
                  f"- C: {'SUPPORTED' if c['claim_C']['supported'] else 'NOT SUPPORTED'} {c['claim_C']['spend_ratio']}", ""]
    lines += ["## Overall (every cohort)"] + [f"- {k}: {'SUPPORTED' if v else 'NOT SUPPORTED'}" for k, v in overall.items()]
    Path(args.out).with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
