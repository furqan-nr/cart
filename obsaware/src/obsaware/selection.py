"""Budgeted selection over (unit, check) items: output-only, all-checks, observability-aware, and controls.

An ITEM is (unit, check). Checks:
  output       cart's reference semantic oracle (exact <= 12 q ancilla-free, else structural validity)
  quality      cart's quality oracle (two-qubit count and depth against the baseline)
  probe        obsaware.state_probe (record + global-phase verdicts)
  contract     obsaware.contract_v2 (K0-K3)
  determinism  obsaware.determinism, a LANE: opening it costs R process launches (fixed), each unit added costs
               R further compilations (marginal)

Cost of a selection = sum over selected units of the unit's compile cost (paid once per unit, as in Paper 2:
baseline transpilation) + the selected checks' oracle costs + the determinism lane's fixed cost if opened.

Strategies (all budget with the same cost ESTIMATE and are charged the REAL cost):
  output_only    Paper 2's COAST order over units (diversity over family x backend x tier, cheapest first);
                 each unit gets {output, quality}. This is the best deployable configuration of Paper 2.
  all_checks     the same unit order; each unit gets every applicable check (naive observability).
  observability  OA-COAST: greedy over ITEMS; an item whose (family, backend, channel) is not yet covered comes
                 first, cheapest marginal cost first; then the remaining items cheapest-marginal first.
  cheapest_items channel-blind control: items by marginal cost only.
  random_items   seeded random item order.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

CHECKS = ("output", "quality", "probe", "contract", "determinism")
CHANNEL_OF_CHECK = {"output": "output", "quality": "quality", "probe": "phase_record", "contract": "contract",
                    "determinism": "determinism"}


@dataclass(frozen=True)
class Unit:
    id: str
    family: str
    backend: str
    n: int
    level: int
    tier: str                 # exact / structural (reference semantic oracle tier)


@dataclass
class CostTable:
    compile_s: dict[str, float]                       # unit -> compile cost
    check_s: dict[tuple[str, str], float]             # (unit, check) -> oracle cost (det: marginal per unit)
    det_fixed_s: float                                # lane opening cost
    applicable: dict[str, tuple[str, ...]]            # unit -> applicable checks

    def total(self) -> float:
        tot = sum(self.compile_s.values()) + sum(self.check_s.values())
        if any("determinism" in a for a in self.applicable.values()):
            tot += self.det_fixed_s
        return tot


class Ledger:
    """Tracks marginal cost of adding items under a cost table."""
    def __init__(self, ct: CostTable):
        self.ct = ct
        self.units: set[str] = set()
        self.det_open = False
        self.spent = 0.0

    def marginal(self, item: tuple[str, str]) -> float:
        u, k = item
        c = self.ct.check_s.get(item, 0.0)
        if u not in self.units:
            c += self.ct.compile_s[u]
        if k == "determinism" and not self.det_open:
            c += self.ct.det_fixed_s
        return c

    def add(self, item: tuple[str, str]) -> float:
        c = self.marginal(item)
        self.units.add(item[0])
        if item[1] == "determinism":
            self.det_open = True
        self.spent += c
        return c


def coast_unit_order(units: list[Unit], est: CostTable) -> list[str]:
    """Paper 2 COAST ordering over units: uncovered (family, backend, tier) first, then cheaper (compile + output
    oracle estimate), then id."""
    seen, out = set(), []
    remaining = list(units)
    cost = {u.id: est.compile_s[u.id] + est.check_s.get((u.id, "output"), 0.0) for u in units}
    while remaining:
        remaining.sort(key=lambda u: ((u.family, u.backend, u.tier) in seen, cost[u.id], u.id))
        u = remaining.pop(0)
        out.append(u.id)
        seen.add((u.family, u.backend, u.tier))
    return out


def _take(items: list[tuple[str, str]], est: CostTable, budget: float) -> list[tuple[str, str]]:
    """Walk a fixed item order, keeping each item whose ESTIMATED marginal cost still fits (skip otherwise)."""
    led, out = Ledger(est), []
    for it in items:
        if led.spent + led.marginal(it) <= budget + 1e-12:
            led.add(it)
            out.append(it)
    return out


def output_only(units, est, budget):
    order = coast_unit_order(units, est)
    items = [(u, k) for u in order for k in ("output", "quality") if k in est.applicable[u]]
    return _take(items, est, budget)


def all_checks(units, est, budget):
    order = coast_unit_order(units, est)
    items = [(u, k) for u in order for k in CHECKS if k in est.applicable[u]]
    return _take(items, est, budget)


def observability(units, est, budget, *, coverage: bool = True):
    meta = {u.id: u for u in units}
    pool = [(u.id, k) for u in units for k in CHECKS if k in est.applicable[u.id]]
    led, out, seen = Ledger(est), [], set()

    def key(it):
        u = meta[it[0]]
        return (u.family, u.backend, CHANNEL_OF_CHECK[it[1]])

    while pool:
        pool.sort(key=lambda it: ((key(it) in seen) if coverage else False, led.marginal(it), it))
        pick = next((it for it in pool if led.spent + led.marginal(it) <= budget + 1e-12), None)
        if pick is None:
            break
        led.add(pick)
        out.append(pick)
        seen.add(key(pick))
        pool.remove(pick)
    return out


def cheapest_items(units, est, budget):
    return observability(units, est, budget, coverage=False)


def random_items(units, est, budget, *, seed: int = 0):
    pool = [(u.id, k) for u in units for k in CHECKS if k in est.applicable[u.id]]
    random.Random(seed).shuffle(pool)
    return _take(pool, est, budget)


STRATEGIES: dict[str, Callable] = {
    "output_only": output_only,
    "all_checks": all_checks,
    "observability": observability,
    "cheapest_items": cheapest_items,
}


def real_spend(selection: list[tuple[str, str]], real: CostTable) -> float:
    led = Ledger(real)
    for it in selection:
        led.add(it)
    return led.spent
