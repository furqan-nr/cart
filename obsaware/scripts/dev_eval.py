#!/usr/bin/env python3
"""Development evaluation of observability-aware selection (EXPLORATORY, development data only).

Development units: 4 families x {line, heavy_hex} x widths {6, 10, 14} x levels {1, 3} = 48 units, circuit seed 7
(disjoint from the 116-unit corpus). Events: Paper 2's ten Phase C operators (output-visible faults, imported
unchanged from cart) and Paper 3's eight invisible-channel operators (obsaware.mutations).

Cost ESTIMATE = costs measured on the clean baseline (what a CI system knows from earlier runs).
Cost CHARGED  = costs measured on the event (real seconds, CPU process time).
Budgets are fractions of the estimated cost of the full observability-aware suite (every applicable check on
every unit).

Writes results/dev_eval.json and prints detection within budget per strategy, split into visible and invisible
events, plus mean real spend / budget.
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]

from cart.events.mutations import baseline_transpiler
from cart.events.mutations_phase_c import MUTATION_OPERATORS_PHASE_C
from cart.manifest.backends import coupling_map_for
from cart.manifest.circuits import build
from cart.oracles.quality import QualityThresholds, evaluate_quality
from cart.oracles.semantic import check_semantic

from obsaware.determinism import run_batch
from obsaware.mutations import CHANNEL, MUTATION_OPERATORS_P3
from obsaware.oracles import PROBE_MAX_QUBITS, contract_v2, fingerprint, state_probe
from obsaware.selection import CHECKS, CostTable, STRATEGIES, Unit, random_items, real_spend

FAMILIES = ("ghz", "qft", "qaoa_linear", "random_clifford")
BACKENDS = ("line", "heavy_hex")
WIDTHS = (6, 10, 14)
LEVELS = (1, 3)
SEED = 7
BASIS = ["cx", "rz", "sx", "x"]
R = 3
BUDGETS = (0.02, 0.05, 0.10, 0.25, 0.50)


def cfg_for(be, n, lvl):
    return dict(optimization_level=lvl, coupling_map=coupling_map_for(be, n), basis_gates=list(BASIS),
                seed_transpiler=1234)


def timed(fn, *a, **k):
    t0 = time.process_time()
    r = fn(*a, **k)
    return r, time.process_time() - t0


def run_checks(qc, base_out, cand, cfg, th):
    sem, c_out = timed(check_semantic, qc, cand, coupling_map=cfg["coupling_map"], basis_gates=BASIS)
    qual, c_q = timed(evaluate_quality, base_out, cand, th)
    pr = state_probe(qc, cand) if cand.num_qubits <= PROBE_MAX_QUBITS else None
    ct = contract_v2(qc, cand)
    det = {
        "output": (sem.equivalent is False) or (sem.strength == "structural" and sem.details.get("structural_ok") is False),
        "quality": bool(qual.is_regression),
        "probe": bool(pr is not None and pr.assessable and (pr.record_ok is False or pr.phase_ok is False)),
        "contract": ct.holds is False,
    }
    cost = {"output": c_out, "quality": c_q, "probe": (pr.cost_s if pr is not None else 0.0), "contract": ct.cost_s}
    return det, cost, sem.strength, pr is not None and pr.assessable


def main() -> int:
    th = QualityThresholds.load()
    units, base = [], {}
    t_start = time.time()
    for fam in FAMILIES:
        for be in BACKENDS:
            for n in WIDTHS:
                for lvl in LEVELS:
                    uid = f"{fam}-{n}-{be}-opt{lvl}"
                    qc = build(fam, n, seed=SEED)
                    cfg = cfg_for(be, n, lvl)
                    fn = baseline_transpiler(cfg)
                    fn(qc)                                            # warm-up
                    times = []
                    for _ in range(3):
                        out, t = timed(fn, qc)
                        times.append(t)
                    det, cost, tier, probe_ok = run_checks(qc, out, out, cfg, th)
                    assert not any(det.values()), f"baseline alarm on {uid}: {det}"
                    base[uid] = dict(qc=qc, cfg=cfg, out=out, fp=fingerprint(out), compile_s=st.median(times),
                                     cost=cost, probe_ok=probe_ok)
                    units.append(Unit(uid, fam, be, n, lvl, tier))
    print(f"baseline done in {time.time() - t_start:.0f}s")

    spec = [dict(id=u.id, family=u.family, n=u.n, backend=u.backend, level=u.level, circuit_seed=SEED) for u in units]
    det_base = run_batch(spec, operator=None)
    assert all(v["deterministic"] for v in det_base.per_unit.values()), "baseline non-deterministic"
    det_fixed = R * st.median(det_base.import_s) + R * 0.05          # interpreter start-up beyond import, rough

    def applicable(uid):
        a = ["output", "quality", "contract", "determinism"]
        if base[uid]["probe_ok"]:
            a.insert(2, "probe")
        return tuple(a)

    est = CostTable(compile_s={u: base[u]["compile_s"] for u in base},
                    check_s={**{(u, k): base[u]["cost"][k] for u in base for k in ("output", "quality", "probe", "contract")
                                if k in applicable(u)},
                             **{(u, "determinism"): R * base[u]["compile_s"] for u in base}},
                    det_fixed_s=det_fixed, applicable={u: applicable(u) for u in base})
    full = est.total()
    print(f"estimated full observability-aware suite cost: {full:.2f}s "
          f"(output checks {sum(v for (u, k), v in est.check_s.items() if k == 'output'):.2f}s)")

    ops = {**{k: ("visible", v) for k, v in MUTATION_OPERATORS_PHASE_C.items()},
           **{k: ("invisible:" + CHANNEL[k], v) for k, v in MUTATION_OPERATORS_P3.items()}}
    events = []
    for name, (group, op) in ops.items():
        t_ev = time.time()
        detects, real_check = {}, {}
        for u in units:
            b = base[u.id]
            try:
                cand = op.transpiler(b["cfg"])(b["qc"])
            except Exception:
                detects[(u.id, "output")] = True                # crash: any check that runs sees it
                for k in ("quality", "probe", "contract"):
                    detects[(u.id, k)] = False
                real_check.update({(u.id, k): b["cost"][k] for k in ("output", "quality", "probe", "contract")})
                continue
            if fingerprint(cand) == b["fp"] and contract_v2(b["qc"], cand).holds is not False:
                for k in ("output", "quality", "probe", "contract"):
                    detects[(u.id, k)] = False
                    real_check[(u.id, k)] = b["cost"][k]
                continue
            det, cost, _, _ = run_checks(b["qc"], b["out"], cand, b["cfg"], th)
            for k in ("output", "quality", "probe", "contract"):
                detects[(u.id, k)] = det[k]
                real_check[(u.id, k)] = cost[k]
        dres = run_batch(spec, operator=name)
        for u in units:
            detects[(u.id, "determinism")] = not dres.per_unit[u.id]["deterministic"]
            real_check[(u.id, "determinism")] = R * base[u.id]["compile_s"]
        real = CostTable(compile_s=est.compile_s, check_s={k: v for k, v in real_check.items() if k in est.check_s},
                         det_fixed_s=det_fixed, applicable=est.applicable)
        reachable = sorted({u for (u, k), d in detects.items() if d})
        ev = dict(event=name, group=group, units_detecting=len(reachable),
                  checks_detecting=sorted({k for (u, k), d in detects.items() if d}), results={})
        for frac in BUDGETS:
            budget = frac * full
            res = {}
            for sname, fn in STRATEGIES.items():
                sel = fn(units, est, budget)
                res[sname] = dict(detected=any(detects.get(it, False) for it in sel),
                                  spend_ratio=real_spend(sel, real) / budget, items=len(sel))
            rnd = [random_items(units, est, budget, seed=s) for s in range(20)]
            res["random_items"] = dict(detected=st.mean(any(detects.get(it, False) for it in sel) for sel in rnd),
                                       spend_ratio=st.mean(real_spend(sel, real) / budget for sel in rnd))
            ev["results"][str(frac)] = res
        events.append(ev)
        print(f"{name:40s} {group:28s} units={len(reachable):2d} checks={ev['checks_detecting']} ({time.time() - t_ev:.0f}s)")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "dev_eval.json").write_text(json.dumps(dict(full_cost_s=full, det_fixed_s=det_fixed,
                                                                    units=len(units), events=events), indent=1))
    strategies = list(STRATEGIES) + ["random_items"]
    for grp in ("visible", "invisible"):
        evs = [e for e in events if e["group"].startswith(grp) and e["units_detecting"] > 0]
        print(f"\n== {grp} events detectable by some check: {len(evs)}")
        print("budget   " + "".join(f"{s:>16s}" for s in strategies))
        for frac in BUDGETS:
            row = [sum(e["results"][str(frac)][s]["detected"] for e in evs) for s in strategies]
            spend = [st.mean(e["results"][str(frac)][s]["spend_ratio"] for e in evs) for s in strategies]
            print(f"{frac:<8} " + "".join(f"{d:>9.1f} ({sp:.2f})" for d, sp in zip(row, spend)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
