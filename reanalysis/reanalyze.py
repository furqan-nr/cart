#!/usr/bin/env python3
"""Separate re-analysis (AI-assisted) of Paper 3's registered claims A, B and C, for both registrations.

Written anew from the written definitions (PREREGISTRATION_P3.md Sections 5 to 8, PREREGISTRATION_P3_R2.md Section 2,
and the strategy descriptions in the docstring of obsaware/src/obsaware/selection.py). It reads only the raw session
files under data/ and imports nothing from obsaware, r2 or cart. Details the registrations do not spell out
(tie-breaking, whether a fixed-order walk skips an item that does not fit or stops) follow the documented behaviour of
the frozen implementation and are listed in reanalysis/README.md.

    python reanalysis/reanalyze.py > reanalysis/reanalysis.json
"""
from __future__ import annotations

import glob
import json
import math
import os
import statistics
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
FRACTIONS = (0.02, 0.05, 0.10)
ORDERED_CHECKS = ["output", "quality", "probe", "contract", "determinism"]
CHANNEL = {"output": "output", "quality": "quality", "probe": "phase_record", "contract": "contract",
           "determinism": "determinism"}


# ------------------------------------------------------------------------------------------------ reading sessions
def read_json(path):
    with open(path) as f:
        return json.load(f)


def read_session(folder):
    units = {}
    for path in glob.glob(os.path.join(folder, "units", "*.json")):
        rec = read_json(path)
        units[rec["test_id"]] = rec
    lane = read_json(os.path.join(folder, "determinism_lane.json"))
    bench = [json.loads(line)["median_s"] for line in open(os.path.join(folder, "benchmark.jsonl")) if line.strip()]
    return {"units": units, "lane": lane, "bench_median": statistics.median(bench),
            "qiskit": read_json(os.path.join(folder, "hardware.json"))["qiskit"]}


def checks_of(rec):
    """Applicable checks of a unit, from its calibration record."""
    out = ["output", "quality"]
    if rec.get("probe_applicable"):
        out.append("probe")
    return out + ["contract", "determinism"]


# ------------------------------------------------------------------------------------------------ cost tables
def table_from_session(sess, factor):
    """Estimated cost table: compile cost per unit, cost per (unit, check), determinism lane opening cost."""
    lane = sess["lane"]
    compile_cost = {u: factor * rec["compile_s"] for u, rec in sess["units"].items()}
    check_cost = {}
    for u, rec in sess["units"].items():
        for c in checks_of(rec):
            if c == "determinism":
                check_cost[(u, c)] = factor * sum(lane["per_unit"][u]["compile_s"])
            else:
                check_cost[(u, c)] = factor * rec[c + "_s"]
    opening = factor * statistics.median(lane["fixed_cpu_per_launch_s"]) * lane["r"]
    return {"compile": compile_cost, "check": check_cost, "opening": opening,
            "checks": {u: checks_of(rec) for u, rec in sess["units"].items()}}


def total_cost(t):
    return sum(t["compile"].values()) + sum(t["check"].values()) + t["opening"]


def real_table(event, labeling, est):
    """Real (charged) costs of one event: the labeling session's clean compile cost per unit, each check's cost as
    measured for this event (clean cost when the event file has none), the lane costs of this event's launches."""
    compile_cost = {u: labeling["units"][u]["compile_s"] for u in est["compile"]}
    check_cost = {}
    for (u, c) in est["check"]:
        if c == "determinism":
            check_cost[(u, c)] = event["determinism"]["per_unit"][u]["cost"]
            continue
        pu = event["per_unit"].get(u, {})
        check_cost[(u, c)] = pu.get("cost", {}).get(c, labeling["units"][u][c + "_s"])
    launches = event["determinism"]["fixed_cpu_per_launch_s"]
    return {"compile": compile_cost, "check": check_cost, "opening": statistics.median(launches) * len(launches),
            "checks": est["checks"]}


def detecting_items(event, est):
    hits = set()
    for (u, c) in est["check"]:
        if c == "determinism":
            if event["determinism"]["per_unit"][u]["detects"]:
                hits.add((u, c))
        elif event["per_unit"].get(u, {}).get("detects", {}).get(c, False):
            hits.add((u, c))
    return hits


# ------------------------------------------------------------------------------------------------ cost accounting
class Account:
    def __init__(self, table):
        self.t, self.paid_units, self.lane_open, self.total = table, set(), False, 0.0

    def price(self, item):
        u, c = item
        p = self.t["check"][item]
        if u not in self.paid_units:
            p += self.t["compile"][u]
        if c == "determinism" and not self.lane_open:
            p += self.t["opening"]
        return p

    def buy(self, item):
        self.total += self.price(item)
        self.paid_units.add(item[0])
        if item[1] == "determinism":
            self.lane_open = True


# ------------------------------------------------------------------------------------------------ strategies
def unit_order(meta, est):
    """Paper 2's COAST order: an unused (family, backend, output tier) first, then cheaper (compile + output check),
    then unit id."""
    left = sorted(meta)
    used, order = set(), []
    while left:
        def rank(u):
            m = meta[u]
            return ((m["family"], m["backend"], m["tier"]) in used, est["compile"][u] + est["check"][(u, "output")], u)
        best = min(left, key=rank)
        order.append(best)
        used.add((meta[best]["family"], meta[best]["backend"], meta[best]["tier"]))
        left.remove(best)
    return order


def walk_fixed_order(items, est, budget):
    """Keep each item whose estimated price still fits; an item that does not fit is skipped, the walk continues."""
    acct, chosen = Account(est), []
    for it in items:
        if acct.total + acct.price(it) <= budget + 1e-12:
            acct.buy(it)
            chosen.append(it)
    return chosen


def strategy_output_only(meta, est, budget):
    order = unit_order(meta, est)
    return walk_fixed_order([(u, c) for u in order for c in ("output", "quality")], est, budget)


def strategy_all_checks(meta, est, budget):
    order = unit_order(meta, est)
    return walk_fixed_order([(u, c) for u in order for c in ORDERED_CHECKS if c in est["checks"][u]], est, budget)


def greedy(meta, est, budget, coverage):
    """Repeatedly take the best remaining item that still fits: uncovered (family, backend, channel) first when
    coverage is on, then lowest current estimated price, then (unit, check). Stops when no remaining item fits."""
    remaining = [(u, c) for u in sorted(meta) for c in ORDERED_CHECKS if c in est["checks"][u]]
    acct, chosen, covered = Account(est), [], set()
    while remaining:
        def rank(it):
            key = (meta[it[0]]["family"], meta[it[0]]["backend"], CHANNEL[it[1]])
            return ((key in covered) if coverage else False, acct.price(it), it)
        candidates = sorted(remaining, key=rank)
        pick = next((it for it in candidates if acct.total + acct.price(it) <= budget + 1e-12), None)
        if pick is None:
            break
        acct.buy(pick)
        chosen.append(pick)
        covered.add((meta[pick[0]]["family"], meta[pick[0]]["backend"], CHANNEL[pick[1]]))
        remaining.remove(pick)
    return chosen


STRATEGIES = {
    "output_only": strategy_output_only,
    "all_checks": strategy_all_checks,
    "observability": lambda m, e, b: greedy(m, e, b, True),
    "cheapest_items": lambda m, e, b: greedy(m, e, b, False),
}


def spend(items, table):
    acct = Account(table)
    for it in items:
        acct.buy(it)
    return acct.total


def cost_to_first_hit(items, hits, table):
    acct = Account(table)
    for it in items:
        acct.buy(it)
        if it in hits:
            return acct.total
    return math.inf


def one_sided_sign_p(wins, losses):
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


# ------------------------------------------------------------------------------------------------ one cohort
def analyse(estimate_session, labeling_dir, factor):
    labeling = read_session(labeling_dir)
    est = table_from_session(estimate_session, factor)
    meta = {u: {"family": r["family"], "backend": r["backend"], "tier": r["output_tier"]}
            for u, r in estimate_session["units"].items()}
    full = total_cost(est)
    excluded = sorted(k for k, v in read_json(os.path.join(labeling_dir, "construction_check.json")).items()
                      if not v["constructible"])
    per_event = []
    for path in sorted(glob.glob(os.path.join(labeling_dir, "events", "*.json"))):
        ev = read_json(path)
        hits = detecting_items(ev, est)
        real = real_table(ev, labeling, est)
        row = {"event": ev["event"], "group": ev["group"], "detectable": bool(hits), "detected": {}, "spend": {},
               "first": {}}
        for f in FRACTIONS:
            b = f * full
            for name, fn in STRATEGIES.items():
                sel = fn(meta, est, b)
                row["detected"][f"{name}@{f}"] = any(it in hits for it in sel)
                row["spend"][f"{name}@{f}"] = spend(sel, real) / b
        for name, fn in STRATEGIES.items():
            row["first"][name] = cost_to_first_hit(fn(meta, est, math.inf), hits, real)
        per_event.append(row)
    detectable = [r for r in per_event if r["detectable"]]
    at5 = {s: sum(r["detected"][f"{s}@0.05"] for r in detectable) for s in STRATEGIES}
    a = at5["observability"] > at5["output_only"] and at5["observability"] >= at5["all_checks"] \
        and at5["observability"] >= at5["cheapest_items"]
    wins = sum(r["first"]["observability"] < r["first"]["all_checks"] - 1e-9 for r in detectable)
    losses = sum(r["first"]["observability"] > r["first"]["all_checks"] + 1e-9 for r in detectable)
    p = one_sided_sign_p(wins, losses)
    c_rows, c = {}, True
    for f in FRACTIONS:
        vals = [r["spend"][f"observability@{f}"] for r in per_event]
        c_rows[str(f)] = {"mean": statistics.mean(vals), "max": max(vals)}
        c = c and statistics.mean(vals) <= 1.25 and max(vals) <= 2.0
    return {"labeling": os.path.basename(os.path.normpath(labeling_dir)), "factor": factor, "full_estimate_s": full,
            "excluded": excluded, "events": len(per_event), "detectable": len(detectable),
            "A": {"supported": a, "detected_at_5pct": at5},
            "B": {"supported": wins > losses and p < 0.05, "wins": wins, "losses": losses, "p": p},
            "C": {"supported": c, "spend": c_rows},
            "detected_by_budget": {str(f): {s: sum(r["detected"][f"{s}@{f}"] for r in detectable) for s in STRATEGIES}
                                   for f in FRACTIONS},
            "per_event": per_event}


def first_registration_factor(prev, cur):
    ratios = sorted(cur["units"][u]["compile_s"] / rec["compile_s"] for u, rec in prev["units"].items()
                    if rec["compile_s"] >= 0.05 and cur["units"][u]["compile_s"] > 0)
    k = statistics.median(ratios)
    return k if (k < 0.8 or k > 1.25) else 1.0


def r2_factor(n_sess, c_sess):
    k = c_sess["bench_median"] / n_sess["bench_median"]
    return k if (k < 0.85 or k > 1.15) else 1.0


def main():
    out = {"first_registration": [], "r2": []}
    k1 = read_session(os.path.join(DATA, "K1", "out_k1"))
    for c in ("C261", "C252"):
        d = os.path.join(DATA, c, f"out_{c}")
        out["first_registration"].append(analyse(k1, d, first_registration_factor(k1, read_session(d))))
    for n, c in (("N260", "C260"), ("N231", "C231")):
        ns, cd = read_session(os.path.join(DATA, n, f"out_{n}")), os.path.join(DATA, c, f"out_{c}")
        cs = read_session(cd)
        assert ns["qiskit"] == cs["qiskit"]
        out["r2"].append(analyse(ns, cd, r2_factor(ns, cs)))
    for reg in ("first_registration", "r2"):
        out[f"{reg}_overall"] = {k: all(r[k]["supported"] for r in out[reg]) for k in ("A", "B", "C")}
    json.dump(out, sys.stdout, indent=1, default=lambda x: None if x == math.inf else x)
    print()


if __name__ == "__main__":
    main()
