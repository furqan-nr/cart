#!/usr/bin/env python3
"""Exploratory analyses requested in review (NOT registered; nothing here changes a registered decision).

Run from the repository root (it imports the frozen code and reads only data/):

    python posthoc/exploratory_p3.py > posthoc/exploratory_p3.json

Analyses, for the four cohorts with the estimate each registration used (first: K1 x compile speed factor;
R2: separate calibration session of the same Qiskit version):
  1. budget grid 0.25% .. 10%: events detected, OA real spend / budget, items, units, real seconds, per strategy;
     normalised area under the detection-versus-budget curve on [0, 10%];
  2. suite composition: share of the estimated full suite taken by the eight 12-qubit exact output checks;
  3. baseline variants: AC with the determinism lane deferred to the end (AC-lane-last), and AC with units ordered
     by their full estimated cost (AC-costaware);
  4. coverage-key ablation: OA with key (channel), (target, channel), (family, target, channel) = the method, and
     CI with the determinism lane opened first (CI+lane);
  5. effect sizes for first detection: OA vs AC, OA vs CI, OA vs the variants: wins/losses/ties, one-sided exact
     sign test, geometric-mean cost ratio with a bootstrap 95% interval, total cost;
  6. over-budget counts: events x registered budgets with OA spend > budget;
  7. power of the one-sided exact sign test at n = 18 for true win probabilities 0.65 .. 0.85.
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import statistics as st
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT / "cart" / "src"), str(ROOT / "obsaware" / "src")]
_spec = importlib.util.spec_from_file_location("analyze_p3", ROOT / "obsaware" / "scripts" / "analyze_p3.py")
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)

from obsaware.cost_model import cost_table, load_session, speed_factor, units_from_session  # noqa: E402
from obsaware.selection import (CHANNEL_OF_CHECK, CHECKS, STRATEGIES, Ledger, _take,  # noqa: E402
                                coast_unit_order, real_spend)

GRID = (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05, 0.075, 0.10)
REGISTERED = ("0.02", "0.05", "0.1")


# ------------------------------------------------------------------------------------------------ strategies
def greedy(units, est, budget, key=None, lane_first=False):
    """The frozen observability() walk with a configurable coverage key (None = cheapest items)."""
    meta = {u.id: u for u in units}
    pool = [(u.id, k) for u in units for k in CHECKS if k in est.applicable[u.id]]
    led, out, seen = Ledger(est), [], set()
    if lane_first:
        det = sorted((it for it in pool if it[1] == "determinism"), key=lambda it: (led.marginal(it), it))
        if det and led.marginal(det[0]) <= budget + 1e-12:
            led.add(det[0]); out.append(det[0]); pool.remove(det[0])
    kf = (lambda it: key(meta[it[0]], CHANNEL_OF_CHECK[it[1]])) if key else None
    if kf:
        seen.update(kf(it) for it in out)
    while pool:
        pool.sort(key=lambda it: ((kf(it) in seen) if kf else False, led.marginal(it), it))
        pick = next((it for it in pool if led.spent + led.marginal(it) <= budget + 1e-12), None)
        if pick is None:
            break
        led.add(pick); out.append(pick); pool.remove(pick)
        if kf:
            seen.add(kf(pick))
    return out


def ac_lane_last(units, est, budget):
    order = coast_unit_order(units, est)
    items = [(u, k) for u in order for k in CHECKS if k in est.applicable[u] and k != "determinism"]
    items += [(u, "determinism") for u in order if "determinism" in est.applicable[u]]
    return _take(items, est, budget)


def ac_costaware(units, est, budget):
    seen, order, rem = set(), [], list(units)
    full = {u.id: est.compile_s[u.id] + sum(est.check_s.get((u.id, k), 0.0) for k in est.applicable[u.id]) for u in units}
    while rem:
        rem.sort(key=lambda u: ((u.family, u.backend, u.tier) in seen, full[u.id], u.id))
        u = rem.pop(0); order.append(u.id); seen.add((u.family, u.backend, u.tier))
    items = [(u, k) for u in order for k in CHECKS if k in est.applicable[u]]
    return _take(items, est, budget)


VARIANTS = {
    "OO": STRATEGIES["output_only"],
    "AC": STRATEGIES["all_checks"],
    "OA": STRATEGIES["observability"],
    "CI": STRATEGIES["cheapest_items"],
    "AC_lane_last": ac_lane_last,
    "AC_costaware": ac_costaware,
    "OA_key_channel": lambda u, e, b: greedy(u, e, b, key=lambda m, ch: ch),
    "OA_key_target_channel": lambda u, e, b: greedy(u, e, b, key=lambda m, ch: (m.backend, ch)),
    "CI_lane_first": lambda u, e, b: greedy(u, e, b, key=None, lane_first=True),
}


# ------------------------------------------------------------------------------------------------ helpers
def sign_p(w, l):
    return an.sign_test_p(w, l)


def boot_gmean_ratio(a, b, reps=10000, seed=0):
    """Geometric mean of the per-event cost ratios a/b, with a percentile bootstrap 95% interval over events."""
    r = [math.log(max(x, 1e-6) / max(y, 1e-6)) for x, y in zip(a, b)]
    rng = random.Random(seed)
    ms = sorted(st.mean(rng.choices(r, k=len(r))) for _ in range(reps))
    return math.exp(st.mean(r)), math.exp(ms[int(0.025 * reps)]), math.exp(ms[int(0.975 * reps) - 1])


def power(n, p_true, alpha=0.05):
    crit = next(k for k in range(n + 1) if an.sign_test_p(k, n - k) < alpha)
    return crit, sum(math.comb(n, k) * p_true ** k * (1 - p_true) ** (n - k) for k in range(crit, n + 1))


def cohort(est_sess, cohort_dir, k):
    cur = load_session(cohort_dir)
    units = units_from_session(est_sess)
    est = cost_table(est_sess, k=k)
    full = est.total()
    events = [json.loads(p.read_text()) for p in sorted((cohort_dir / "events").glob("*.json"))]
    tables = [(ev["event"], ev["group"], *an.event_tables(ev, est, cur)) for ev in events]
    exact = sorted((c for (u, ch), c in est.check_s.items() if ch == "output"), reverse=True)[:8]
    out = dict(cohort=cohort_dir.name, full_suite_estimate_s=full, items=sum(len(v) for v in est.applicable.values()),
               exact8_share=sum(exact) / full, grid={}, first={}, over_budget={})
    for f in GRID:
        b = f * full
        row = {}
        for name, fn in VARIANTS.items():
            sel = fn(units, est, b)
            det = sum(any(d.get(it, False) for it in sel) for _, _, d, _ in tables)
            sp = [real_spend(sel, real) / b for _, _, _, real in tables]
            row[name] = dict(detected=det, spend_mean=st.mean(sp), spend_max=max(sp), items=len(sel),
                             units=len({u for u, _ in sel}), real_s_mean=st.mean(s * b for s in sp))
        out["grid"][f"{f:g}"] = row
    xs = [0.0] + list(GRID)
    for name in VARIANTS:
        ys = [0.0] + [out["grid"][f"{f:g}"][name]["detected"] for f in GRID]
        area = sum((xs[i + 1] - xs[i]) * (ys[i] + ys[i + 1]) / 2 for i in range(len(xs) - 1))
        out.setdefault("auc_0_10pct", {})[name] = area / (0.10 * len(tables))
    fc = {name: [an.first_cost(fn(units, est, math.inf), d, real) for _, _, d, real in tables]
          for name, fn in VARIANTS.items()}
    for other in ("AC", "CI", "AC_lane_last", "AC_costaware", "CI_lane_first", "OA_key_channel"):
        a, b = fc["OA"], fc[other]
        w = sum(x < y - 1e-9 for x, y in zip(a, b)); l = sum(x > y + 1e-9 for x, y in zip(a, b))
        gm, lo, hi = boot_gmean_ratio(a, b)
        out["first"][f"OA_vs_{other}"] = dict(wins=w, losses=l, ties=len(a) - w - l, p=sign_p(w, l),
                                              gmean_ratio=gm, ci95=[lo, hi], total_OA=sum(a), total_other=sum(b))
    out["first_totals"] = {n: sum(v) for n, v in fc.items()}
    for f in REGISTERED:
        b = float(f) * full
        sel = STRATEGIES["observability"](units, est, b)
        sp = [real_spend(sel, real) / b for _, _, _, real in tables]
        out["over_budget"][f] = dict(over=sum(s > 1 for s in sp), n=len(sp), over_1_25=sum(s > 1.25 for s in sp))
    return out


def composition(est_sess, cohort_dir, k):
    """Coverable keys, per-check ratio of real clean cost (labeling session) to estimated cost, budgets in seconds."""
    cur = load_session(cohort_dir)
    units = units_from_session(est_sess)
    est = cost_table(est_sess, k=k)
    keys = {(u.family, u.backend, CHANNEL_OF_CHECK[c]) for u in units for c in est.applicable[u.id]}
    ratios = {}
    comp = [cur["units"][t]["compile_s"] / est.compile_s[t] for t in est.compile_s if est.compile_s[t] >= 0.05]
    ratios["compile (units >= 0.05 s)"] = st.median(comp)
    for c in ("output", "quality", "probe", "contract"):
        r = [cur["units"][t][f"{c}_s"] / est.check_s[(t, c)] for t in est.compile_s
             if (t, c) in est.check_s and est.check_s[(t, c)] >= 0.01 and cur["units"][t].get(f"{c}_s")]
        if r:
            ratios[c] = st.median(r)
    full = est.total()
    return dict(coverable_keys=len(keys), median_real_over_estimate=ratios,
                budgets_s={f: f * full for f in (0.02, 0.05, 0.10)})


def main() -> int:
    k1 = load_session(ROOT / "data/K1/out_k1")
    res = {"note": "exploratory, not registered", "cohorts": []}
    for c in ("C261", "C252"):
        cdir = ROOT / f"data/{c}/out_{c}"
        cur = load_session(cdir)
        _, k = speed_factor({t: r["compile_s"] for t, r in cur["units"].items()},
                            {t: r["compile_s"] for t, r in k1["units"].items()})
        r = cohort(k1, cdir, k); r["registration"] = "first"; r["composition"] = composition(k1, cdir, k)
        res["cohorts"].append(r)
    for n, c in (("N260", "C260"), ("N231", "C231")):
        es = load_session(ROOT / f"data/{n}/out_{n}")
        r = cohort(es, ROOT / f"data/{c}/out_{c}", 1.0); r["composition"] = composition(es, ROOT / f"data/{c}/out_{c}", 1.0)
        r["registration"] = "R2"; res["cohorts"].append(r)
    res["sign_test_power_n18"] = {f"{p:.2f}": dict(zip(("critical_wins", "power"), power(18, p)))
                                  for p in (0.65, 0.70, 0.75, 0.80, 0.85)}
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
