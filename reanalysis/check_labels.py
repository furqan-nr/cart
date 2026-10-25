#!/usr/bin/env python3
"""Consistency of the raw labeling data with the registered labeling rules (PREREGISTRATION_P3.md, Section 5),
for every cohort. Independent of any selection or cost logic.

  L1  a check counts as detecting on a unit only if it raised an alarm on the candidate and passed on that unit's
      clean baseline; determinism counts only if the clean compilation was deterministic
  L2  a crashed candidate is observed by every applicable check of that unit
  L3  an unchanged candidate detects nothing
  E1  excluded operators have no event file
  plus: every event file covers all 116 units; no output-invisible event is detected by the output check.

    python reanalysis/check_labels.py > reanalysis/label_checks.json
"""
import glob
import json
import os
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
res = {}
for c in ("C261", "C252", "C260", "C231"):
    d = os.path.join(DATA, c, f"out_{c}")
    clean = {}
    for p in glob.glob(os.path.join(d, "units", "*.json")):
        r = json.load(open(p))
        clean[r["test_id"]] = r
    lane = json.load(open(os.path.join(d, "determinism_lane.json")))
    cons = json.load(open(os.path.join(d, "construction_check.json")))
    problems, n = [], 0
    events = sorted(glob.glob(os.path.join(d, "events", "*.json")))
    names = {json.load(open(p))["event"] for p in events}
    for k, v in cons.items():
        n += 1
        if not v["constructible"] and k in names:
            problems.append(f"E1: excluded operator {k} has an event file")
    for p in events:
        ev = json.load(open(p))
        n += 1
        if set(ev["per_unit"]) != set(clean):
            problems.append(f"{ev['event']}: per_unit does not cover the 116 units")
        for u, pu in ev["per_unit"].items():
            n += 1
            if pu["status"] == "unchanged" and any(pu["detects"].values()):
                problems.append(f"L3 {ev['event']} {u}")
            if pu["status"] == "crash" and not all(pu["detects"].values()):
                problems.append(f"L2 {ev['event']} {u}")
            if pu["status"] == "changed":
                for chk, det in pu["detects"].items():
                    if det and not (pu["alarms"].get(chk) and clean[u]["clean_verdicts_pass"].get(chk, True)):
                        problems.append(f"L1 {ev['event']} {u} {chk}")
            if ev["group"] == "invisible" and pu["detects"].get("output"):
                problems.append(f"invisible event detected by output check: {ev['event']} {u}")
        for u, dd in ev["determinism"]["per_unit"].items():
            n += 1
            if dd["detects"] and not lane["per_unit"][u]["deterministic"]:
                problems.append(f"L1 determinism {ev['event']} {u}")
    res[c] = {"checks": n, "problems": problems}
    print(f"{c}: {n} checks, {len(problems)} problems", file=sys.stderr)
json.dump(res, sys.stdout, indent=1)
print()
