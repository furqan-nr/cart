"""R3: the strategies compared in registration R3.

The five registered strategies of obsaware.selection (output-only, all-checks, observability-aware, cheapest-items,
random items) are imported unchanged. R3 adds two NAMED COMPARATORS, frozen here, that review of the earlier results
identified as the strongest simple alternatives (both were exploratory in R1/R2, posthoc/exploratory_p3.py):

  * AC-cost (all checks, cost-aware): all-checks with its units ordered by their FULL estimated cost (compile plus
    every applicable check), uncovered (family, backend, tier) first; every applicable check of a unit is taken;
  * CH-lane-first (cheapest items, determinism lane first): cheapest-items selection that first opens the
    determinism lane with its cheapest determinism item, if it fits.

AC-cost and cheapest-items do not use which channel a check observes. CH-lane-first uses one piece of observability
knowledge (that one channel, determinism, needs its own lane). Their code is identical to posthoc/exploratory_p3.py.
"""
from __future__ import annotations

from obsaware.selection import CHECKS, STRATEGIES, Ledger, _take


def ac_costaware(units, est, budget):
    seen, order, rem = set(), [], list(units)
    full = {u.id: est.compile_s[u.id] + sum(est.check_s.get((u.id, k), 0.0) for k in est.applicable[u.id]) for u in units}
    while rem:
        rem.sort(key=lambda u: ((u.family, u.backend, u.tier) in seen, full[u.id], u.id))
        u = rem.pop(0); order.append(u.id); seen.add((u.family, u.backend, u.tier))
    items = [(u, k) for u in order for k in CHECKS if k in est.applicable[u]]
    return _take(items, est, budget)


def ch_lane_first(units, est, budget):
    pool = [(u.id, k) for u in units for k in CHECKS if k in est.applicable[u.id]]
    led, out = Ledger(est), []
    det = sorted((it for it in pool if it[1] == "determinism"), key=lambda it: (led.marginal(it), it))
    if det and led.marginal(det[0]) <= budget + 1e-12:
        led.add(det[0]); out.append(det[0]); pool.remove(det[0])
    while pool:
        pool.sort(key=lambda it: (led.marginal(it), it))
        pick = next((it for it in pool if led.spent + led.marginal(it) <= budget + 1e-12), None)
        if pick is None:
            break
        led.add(pick); out.append(pick); pool.remove(pick)
    return out


R3_STRATEGIES = dict(STRATEGIES)
R3_STRATEGIES["ac_costaware"] = ac_costaware
R3_STRATEGIES["ch_lane_first"] = ch_lane_first
OBSERVABILITY_BLIND = ("output_only", "all_checks", "ac_costaware", "cheapest_items")
