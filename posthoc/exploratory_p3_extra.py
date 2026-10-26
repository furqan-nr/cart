#!/usr/bin/env python3
"""Paper 3, further exploratory analyses (NOT registered; nothing here changes a registered decision).

Run from the repository root:

    python posthoc/exploratory_p3_extra.py > posthoc/exploratory_p3_extra.json

For the R2 cohorts (estimate: separate calibration session; real costs and labels: labeling session) and, where
stated, the R1 cohorts:
  1. ratio-greedy budgeted coverage (coverage gain per estimated marginal price, the classical greedy for budgeted
     maximum coverage) next to OA, over the budget grid;
  2. a per-event hindsight bound: the smallest real cost of any single detecting item (unit compile + check +
     determinism-lane opening when needed); an event is detectable within budget b by some selection iff this is
     <= b, so the count of such events bounds every strategy's detection at b;
  3. equal-weight detection over the grid (mean events detected per grid budget, of 18), next to the linear AUC;
  4. hard-limit cut: each selection taken in its own order and stopped before the item whose REAL cost would exceed
     the budget; events detected;
  5. decomposition of OA's overspend (real - estimated cost of the selection) into compilation, the four
     per-unit checks, determinism per-unit compilations and the determinism lane's fixed cost;
  6. sensitivity: OA's spend when the lane's fixed cost is charged at the labeling session's CLEAN value instead of
     each event's own launches (removes fault-injection overhead from the charge).
"""
from __future__ import annotations

import importlib.util
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT / "cart" / "src"), str(ROOT / "obsaware" / "src")]
_spec = importlib.util.spec_from_file_location("analyze_p3", ROOT / "obsaware" / "scripts" / "analyze_p3.py")
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)
_spec2 = importlib.util.spec_from_file_location("expl", ROOT / "posthoc" / "exploratory_p3.py")
ex = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(ex)

from obsaware.cost_model import CostTable, cost_table, load_session, speed_factor, units_from_session  # noqa: E402
from obsaware.selection import CHANNEL_OF_CHECK, CHECKS, STRATEGIES, Ledger, real_spend  # noqa: E402

GRID = ex.GRID
REGISTERED = (0.02, 0.05, 0.10)


def ratio_greedy(units, est, budget):
    """Budgeted maximum coverage greedy: maximise (new keys covered) / (marginal price); ties and zero-gain steps by
    lowest price, then item."""
    meta = {u.id: u for u in units}
    pool = [(u.id, k) for u in units for k in CHECKS if k in est.applicable[u.id]]
    led, out, seen = Ledger(est), [], set()
    key = lambda it: (meta[it[0]].family, meta[it[0]].backend, CHANNEL_OF_CHECK[it[1]])  # noqa: E731
    while pool:
        fits = [it for it in pool if led.spent + led.marginal(it) <= budget + 1e-12]
        if not fits:
            break
        def score(it):
            gain = 0 if key(it) in seen else 1
            price = max(led.marginal(it), 1e-12)
            return (-(gain / price), price, it)
        pick = min(fits, key=score)
        led.add(pick); out.append(pick); pool.remove(pick); seen.add(key(pick))
    return out


def min_detect_cost(detects, real):
    best = math.inf
    for (u, c), d in detects.items():
        if d:
            cost = real.compile_s[u] + real.check_s.get((u, c), 0.0) + (real.det_fixed_s if c == "determinism" else 0.0)
            best = min(best, cost)
    return best


def hard_cut(sel, real, budget):
    led, kept = Ledger(real), []
    for it in sel:
        if led.spent + led.marginal(it) > budget + 1e-12:
            break
        led.add(it); kept.append(it)
    return kept


def decompose(sel, est, real):
    """Real minus estimated cost of a selection, by component."""
    comp = {"compile": 0.0, "checks": 0.0, "det_per_unit": 0.0, "det_fixed": 0.0}
    units, det_open = set(), False
    for u, c in sel:
        if u not in units:
            comp["compile"] += real.compile_s[u] - est.compile_s[u]
            units.add(u)
        d = real.check_s.get((u, c), 0.0) - est.check_s.get((u, c), 0.0)
        comp["det_per_unit" if c == "determinism" else "checks"] += d
        if c == "determinism" and not det_open:
            comp["det_fixed"] += real.det_fixed_s - est.det_fixed_s
            det_open = True
    return comp


def cohort(est_sess, cdir, k):
    cur = load_session(cdir)
    units = units_from_session(est_sess)
    est = cost_table(est_sess, k=k)
    full = est.total()
    clean_fixed = st.median(cur["det"]["fixed_cpu_per_launch_s"]) * cur["det"]["r"]
    events = [json.loads(p.read_text()) for p in sorted((cdir / "events").glob("*.json"))]
    tabs = [(ev["event"], *an.event_tables(ev, est, cur)) for ev in events]
    strategies = dict(STRATEGIES)
    strategies["ratio_greedy"] = ratio_greedy
    strategies["AC_costaware"] = ex.ac_costaware
    out = dict(cohort=cdir.name, grid={}, hindsight={}, hard_cut={}, decomposition={}, clean_lane_sensitivity={})
    for f in GRID:
        b = f * full
        row = {}
        for s, fn in strategies.items():
            sel = fn(units, est, b)
            row[s] = dict(detected=sum(any(d.get(it, False) for it in sel) for _, d, _ in tabs), items=len(sel))
        row["hindsight_bound"] = sum(1 for _, d, r in tabs if min_detect_cost(d, r) <= b)
        out["grid"][f"{f:g}"] = row
    names = list(strategies) + ["hindsight_bound"]
    out["equal_weight_mean_detected"] = {
        s: st.mean((out["grid"][f"{f:g}"][s] if s == "hindsight_bound" else out["grid"][f"{f:g}"][s]["detected"])
                   for f in GRID) for s in names}
    out["ratio_greedy_equals_OA_items"] = {f"{f:g}": ratio_greedy(units, est, f * full) ==
                                           STRATEGIES["observability"](units, est, f * full) for f in GRID}
    for f in REGISTERED:
        b = f * full
        out["hard_cut"][f"{f:g}"] = {s: sum(any(d.get(it, False) for it in hard_cut(fn(units, est, b), r, b))
                                            for _, d, r in tabs) for s, fn in STRATEGIES.items()}
        sel = STRATEGIES["observability"](units, est, b)
        comps = [decompose(sel, est, r) for _, _, r in tabs]
        mean = {k2: st.mean(c[k2] for c in comps) for k2 in comps[0]}
        tot = sum(mean.values())
        out["decomposition"][f"{f:g}"] = dict(mean_overspend_s=tot, components_s=mean,
                                              share={k2: (v / tot if tot else None) for k2, v in mean.items()})
        spends, spends_clean = [], []
        for _, _, r in tabs:
            spends.append(real_spend(sel, r) / b)
            rc = CostTable(compile_s=r.compile_s, check_s=r.check_s, det_fixed_s=clean_fixed, applicable=r.applicable)
            spends_clean.append(real_spend(sel, rc) / b)
        out["clean_lane_sensitivity"][f"{f:g}"] = dict(mean_registered=st.mean(spends), max_registered=max(spends),
                                                       mean_clean_lane=st.mean(spends_clean),
                                                       max_clean_lane=max(spends_clean))
    return out


def main() -> int:
    res = {"note": "exploratory, not registered", "cohorts": []}
    for n, c in (("N260", "C260"), ("N231", "C231")):
        res["cohorts"].append(cohort(load_session(ROOT / f"data/{n}/out_{n}"), ROOT / f"data/{c}/out_{c}", 1.0))
    k1 = load_session(ROOT / "data/K1/out_k1")
    for c in ("C261", "C252"):
        cdir = ROOT / f"data/{c}/out_{c}"
        cur = load_session(cdir)
        _, k = speed_factor({t: r["compile_s"] for t, r in cur["units"].items()},
                            {t: r["compile_s"] for t, r in k1["units"].items()})
        res["cohorts"].append(cohort(k1, cdir, k))
    print(json.dumps(res, indent=1, default=lambda x: None if isinstance(x, float) and math.isinf(x) else x))
    return 0


if __name__ == "__main__":
    sys.exit(main())
