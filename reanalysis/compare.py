#!/usr/bin/env python3
"""Compare the separate re-analysis (reanalysis/reanalysis.json) with the registered analyses
(results/registered_analysis.json, results/registered_analysis_r2.json), value by value.

    python reanalysis/compare.py > reanalysis/comparison.json
Prints a summary to stderr. Numbers are equal when they agree to 1e-9 relative (floating-point summation order).
"""
import json
import math
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
re_ = json.load(open(os.path.join(ROOT, "reanalysis", "reanalysis.json")))
reg = {"first_registration": json.load(open(os.path.join(ROOT, "results", "registered_analysis.json"))),
       "r2": json.load(open(os.path.join(ROOT, "results", "registered_analysis_r2.json")))}
STRATS = ("output_only", "all_checks", "observability", "cheapest_items")


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


report = {}
for name in ("first_registration", "r2"):
    for mine, theirs in zip(re_[name], reg[name]["cohorts"]):
        n_cmp, diffs = 0, []

        def check(label, a, b):
            global n_cmp
            n_cmp += 1
            if not close(a, b):
                diffs.append({"value": label, "reanalysis": a, "registered": b})

        check("full_estimate_s", mine["full_estimate_s"], theirs["full_suite_estimate_s"])
        check("events", mine["events"], theirs["n_events"])
        check("detectable", mine["detectable"], theirs["n_detectable"])
        for k in ("A", "B", "C"):
            check(f"claim {k}", mine[k]["supported"], theirs[f"claim_{k}"]["supported"])
        check("B p", mine["B"]["p"], theirs["claim_B"]["p"])
        theirs_events = {e["event"]: e for e in theirs["events"]}
        for row in mine["per_event"]:
            te = theirs_events[row["event"]]
            check(f"{row['event']} detectable", row["detectable"], te["detectable"])
            for f in ("0.02", "0.05", "0.1"):
                for s in STRATS:
                    key = f"{s}@{float(f)}"
                    check(f"{row['event']} {key} detected", row["detected"][key], te["budgets"][f][s]["detected"])
                    check(f"{row['event']} {key} spend", row["spend"][key], te["budgets"][f][s]["spend_ratio"])
            for s in STRATS:
                a, b = row["first"][s], te["first_cost"][s]
                check(f"{row['event']} {s} first cost", None if a is None else a, b)
        report[f"{name}/{mine['labeling']}"] = {"values_compared": n_cmp, "differences": diffs}
        print(f"{name:20s} {mine['labeling']:10s} values compared {n_cmp:5d}  differences {len(diffs)}", file=sys.stderr)
json.dump(report, sys.stdout, indent=1)
print()
