#!/usr/bin/env python3
"""Paper 3, denominator sensitivity (exploratory, NOT registered; nothing here changes a registered decision).

Run from the repository root:

    python posthoc/exploratory_p3_denominator.py > posthoc/exploratory_p3_denominator.json

Question: how much do the budget results depend on the eight exact output checks on 12-qubit units, which make up
79% to 86% of the estimated full suite? We remove those eight items from the suite (as if they ran only nightly,
outside the per-change budget), so they leave both the selectable pool and the denominator. Budgets are then
fractions of the reduced suite. Everything else (estimate, real costs, labels, strategies) is as in
exploratory_p3.py. Reported per cohort:
  - the reduced suite's estimated cost and the share of the full suite it represents;
  - events detectable at all by the reduced suite (any item detects);
  - detection and real spend of every strategy over a grid of reduced-suite fractions from 0.25% to 100%;
  - equal-weight mean detection over the grid 0.25% to 10% and over 0.25% to 50%;
  - first-detection comparisons of OA with every other strategy (budget-free orders), as in exploratory_p3.py.
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


an = _load("analyze_p3", ROOT / "obsaware" / "scripts" / "analyze_p3.py")
ex = _load("expl", ROOT / "posthoc" / "exploratory_p3.py")

from obsaware.cost_model import CostTable, cost_table, load_session, speed_factor, units_from_session  # noqa: E402
from obsaware.selection import real_spend  # noqa: E402

GRID = (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0)
LOW = tuple(f for f in GRID if f <= 0.10)
MID = tuple(f for f in GRID if f <= 0.50)
VARIANTS = {k: ex.VARIANTS[k] for k in ("OO", "AC", "OA", "CI", "AC_costaware", "AC_lane_last", "CI_lane_first")}


def reduce(est: CostTable):
    """Remove the eight most expensive output checks (the exact 12-qubit checks) from a cost table."""
    eight = sorted(((c, it) for it, c in est.check_s.items() if it[1] == "output"), reverse=True)[:8]
    drop = {it for _, it in eight}
    appl = {u: tuple(k for k in a if (u, k) not in drop) for u, a in est.applicable.items()}
    check_s = {it: c for it, c in est.check_s.items() if it not in drop}
    return CostTable(compile_s=est.compile_s, check_s=check_s, det_fixed_s=est.det_fixed_s, applicable=appl), \
        sorted(drop), sum(c for c, _ in eight)


def cohort(est_sess, cdir, k):
    cur = load_session(cdir)
    units = units_from_session(est_sess)
    est_full = cost_table(est_sess, k=k)
    est, dropped, dropped_s = reduce(est_full)
    full, red = est_full.total(), est.total()
    events = [json.loads(p.read_text()) for p in sorted((cdir / "events").glob("*.json"))]
    tabs = [(ev["event"], ev["group"], *an.event_tables(ev, est, cur)) for ev in events]
    tabs_full = [(ev["event"], *an.event_tables(ev, est_full, cur)) for ev in events]
    only_exact = [name for (name, d, _), (_, _, d2, _) in zip(tabs_full, tabs)
                  if any(d.values()) and not any(d2.values())]
    out = dict(cohort=cdir.name, full_suite_estimate_s=full, reduced_suite_estimate_s=red,
               reduced_share_of_full=red / full, dropped_items=[list(i) for i in dropped], dropped_s=dropped_s,
               events=len(tabs), detectable_by_reduced_suite=sum(any(d.values()) for _, _, d, _ in tabs),
               events_detected_only_by_the_eight=only_exact,
               registered_budgets_as_reduced_fractions={f"{f:g}": f * full / red for f in (0.02, 0.05, 0.10)},
               grid={}, first={})
    for f in GRID:
        b = f * red
        row = {}
        for name, fn in VARIANTS.items():
            sel = fn(units, est, b)
            sp = [real_spend(sel, real) / b for _, _, _, real in tabs]
            row[name] = dict(detected=sum(any(d.get(it, False) for it in sel) for _, _, d, _ in tabs),
                             items=len(sel), spend_mean=st.mean(sp), spend_max=max(sp))
        out["grid"][f"{f:g}"] = row
    for label, g in (("0.25-10pct", LOW), ("0.25-50pct", MID)):
        out[f"equal_weight_mean_detected_{label}"] = {
            n: st.mean(out["grid"][f"{f:g}"][n]["detected"] for f in g) for n in VARIANTS}
    out["band_OA_strictly_ahead_of"] = {
        n: [f"{f:g}" for f in GRID if out["grid"][f"{f:g}"]["OA"]["detected"] > out["grid"][f"{f:g}"][n]["detected"]]
        for n in VARIANTS if n != "OA"}
    out["band_OA_behind"] = {
        n: [f"{f:g}" for f in GRID if out["grid"][f"{f:g}"]["OA"]["detected"] < out["grid"][f"{f:g}"][n]["detected"]]
        for n in VARIANTS if n != "OA"}
    fc = {n: [an.first_cost(fn(units, est, math.inf), d, real) for _, _, d, real in tabs] for n, fn in VARIANTS.items()}
    for other in VARIANTS:
        if other == "OA":
            continue
        a, b = fc["OA"], fc[other]
        fin = [(x, y) for x, y in zip(a, b) if math.isfinite(x) and math.isfinite(y)]
        w = sum(x < y - 1e-9 for x, y in zip(a, b)); l = sum(x > y + 1e-9 for x, y in zip(a, b))
        gm, lo, hi = ex.boot_gmean_ratio([x for x, _ in fin], [y for _, y in fin]) if fin else (None,) * 3
        out["first"][f"OA_vs_{other}"] = dict(wins=w, losses=l, ties=len(a) - w - l, p=an.sign_test_p(w, l),
                                              gmean_ratio=gm, ci95=[lo, hi])
    return out


def main() -> int:
    res = {"note": "exploratory, not registered: suite without the eight exact 12-qubit output checks",
           "cohorts": []}
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
