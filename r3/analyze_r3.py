#!/usr/bin/env python3
"""Registration R3, frozen analysis: real Qiskit faults re-injected into Qiskit 2.6.1, measured costs.

Estimate: the per-(unit, check) cost table of the separate calibration session N_R3 (same Qiskit build), with the
machine rule M1 of R2 (k = median reference benchmark of the labeling session / that of N_R3; applied only outside
[0.85, 1.15]). Detection (rule L1), real costs, budgets (fractions of the estimated full suite), the first-detection
cost and the one-sided exact sign test are imported unchanged from obsaware/scripts/analyze_p3.py.

Claims (each decided on the single R3 cohort; events = faults not excluded by rule E1; detectable = some item of
the full suite detects it):
  A3  at the 5% budget, detectable events detected by OA >= those detected by each of OO, AC, AC-cost and CH;
  B3  OA reaches its first detection at lower real cost than AC on more detectable events than not, one-sided
      exact sign test p < 0.05. With fewer than 5 detectable events B3 is INCONCLUSIVE (not supported);
  C3  OA's real spend / budget has mean <= 1.25 and max <= 2.0 over all events, at each of 2%, 5% and 10%;
  D3  over the budget grid 0.25%, 0.5%, 0.75%, 1%, 1.5%, 2%, 3%, 5%, 7.5%, 10%, each budget weighted equally,
      OA's mean number of detectable events detected >= that of each of OO, AC, AC-cost and CH.
Reported, not claims: first-detection sign tests of OA against AC-cost, CH, CH-lane-first and OO; detection at
every grid budget for every strategy; per-fault detail.

    python r3/analyze_r3.py --calibration data/NR3/out_NR3 --labeling data/R3/out_R3 \
        --out results/registered_analysis_r3.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cart" / "src"), str(ROOT / "obsaware" / "src"), str(ROOT / "r3")]
_spec = importlib.util.spec_from_file_location("analyze_p3", ROOT / "obsaware" / "scripts" / "analyze_p3.py")
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)

from obsaware.cost_model import cost_table, load_session, units_from_session  # noqa: E402
from obsaware.selection import random_items, real_spend  # noqa: E402
from strategies_r3 import OBSERVABILITY_BLIND, R3_STRATEGIES  # noqa: E402

BENCH_BAND = (0.85, 1.15)
GRID = (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05, 0.075, 0.10)
BUDGETS = sorted(set(GRID) | set(an.BUDGETS))
PRIMARY = "observability"
MIN_EVENTS_B3 = 5


def bench_median(d: Path) -> float:
    return st.median(json.loads(l)["median_s"] for l in (d / "benchmark.jsonl").read_text().splitlines())


def sign(a, b, rows):
    w = sum(1 for r in rows if r["first_cost"][a] < r["first_cost"][b] - 1e-9)
    l = sum(1 for r in rows if r["first_cost"][a] > r["first_cost"][b] + 1e-9)
    return dict(wins=w, losses=l, ties=len(rows) - w - l, p=an.sign_test_p(w, l))


def analyse(n_dir: Path, c_dir: Path) -> dict:
    prev, cur = load_session(n_dir), load_session(c_dir)
    qv_n = json.loads((n_dir / "hardware.json").read_text())["qiskit"]
    qv_c = json.loads((c_dir / "hardware.json").read_text())["qiskit"]
    assert qv_n == qv_c == "2.6.1", (qv_n, qv_c)
    k_raw = bench_median(c_dir) / bench_median(n_dir)
    k = 1.0 if BENCH_BAND[0] <= k_raw <= BENCH_BAND[1] else k_raw
    units = units_from_session(prev)
    est = cost_table(prev, k=k)
    full = est.total()
    cons = json.loads((c_dir / "construction_check.json").read_text())
    excluded = sorted(n for n, v in cons.items() if not v["constructible"])
    rows = []
    for p in sorted((c_dir / "events").glob("*.json")):
        ev = json.loads(p.read_text())
        detects, real = an.event_tables(ev, est, cur)
        row = dict(event=ev["event"], title=ev["fault"]["title"], detectable=any(detects.values()),
                   units_detecting=len({t for (t, c), d in detects.items() if d}),
                   checks_detecting=sorted({c for (t, c), d in detects.items() if d}),
                   crashes=sum(1 for v in ev["per_unit"].values() if v["status"] == "crash"), budgets={},
                   first_cost={})
        for f in BUDGETS:
            b = f * full
            res = {}
            for s, fn in R3_STRATEGIES.items():
                sel = fn(units, est, b)
                res[s] = dict(detected=any(detects.get(it, False) for it in sel), spend_ratio=real_spend(sel, real) / b)
            if f in an.BUDGETS:
                rnd = [random_items(units, est, b, seed=i) for i in range(an.RANDOM_SEEDS)]
                res["random_items"] = dict(detected=st.mean(any(detects.get(it, False) for it in s) for s in rnd),
                                           spend_ratio=st.mean(real_spend(s, real) / b for s in rnd))
            row["budgets"][str(f)] = res
        for s, fn in R3_STRATEGIES.items():
            row["first_cost"][s] = an.first_cost(fn(units, est, math.inf), detects, real)
        rows.append(row)
    det = [r for r in rows if r["detectable"]]

    def count(s, f):
        return sum(1 for r in det if r["budgets"][str(f)][s]["detected"])

    a = {s: count(s, 0.05) for s in R3_STRATEGIES}
    claim_a = all(a[PRIMARY] >= a[s] for s in OBSERVABILITY_BLIND)
    b3 = sign(PRIMARY, "all_checks", det)
    b_inconclusive = len(det) < MIN_EVENTS_B3
    claim_b = (not b_inconclusive) and b3["wins"] > b3["losses"] and b3["p"] < 0.05
    c_detail, claim_c = {}, True
    for f in an.BUDGETS:
        ratios = [r["budgets"][str(f)][PRIMARY]["spend_ratio"] for r in rows]
        c_detail[str(f)] = dict(mean=st.mean(ratios) if ratios else None, max=max(ratios) if ratios else None)
        claim_c = claim_c and bool(ratios) and st.mean(ratios) <= 1.25 and max(ratios) <= 2.0
    ew = {s: st.mean(count(s, f) for f in GRID) for s in R3_STRATEGIES}
    claim_d = bool(det) and all(ew[PRIMARY] >= ew[s] for s in OBSERVABILITY_BLIND)
    return dict(cohort=c_dir.name, calibration_session=n_dir.name, qiskit=qv_c, machine_factor_raw=k_raw,
                machine_factor_applied=k, full_suite_estimate_s=full, excluded_faults=excluded,
                n_events=len(rows), n_detectable=len(det),
                claim_A3=dict(supported=claim_a, detected_at_5pct=a),
                claim_B3=dict(supported=claim_b, inconclusive=b_inconclusive, **b3),
                claim_C3=dict(supported=claim_c, spend_ratio=c_detail),
                claim_D3=dict(supported=claim_d, equal_weight_mean_detected=ew),
                reported_first_detection={f"OA_vs_{s}": sign(PRIMARY, s, det)
                                          for s in R3_STRATEGIES if s != PRIMARY},
                detection_by_budget={str(f): {s: count(s, f) for s in R3_STRATEGIES} for f in BUDGETS},
                events=rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--labeling", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = analyse(Path(a.calibration), Path(a.labeling))
    Path(a.out).write_text(json.dumps(r, indent=1, default=lambda x: None if x == math.inf else x))
    lines = [f"# Registration R3: registered claims (Qiskit {r['qiskit']}, estimate from {r['calibration_session']})", "",
             f"machine factor {r['machine_factor_raw']:.3f} (applied {r['machine_factor_applied']:.3f}); full suite "
             f"estimate {r['full_suite_estimate_s']:.1f} s; faults {r['n_events']}, detectable {r['n_detectable']}; "
             f"excluded {r['excluded_faults']}", ""]
    for c in ("claim_A3", "claim_B3", "claim_C3", "claim_D3"):
        d = {k: v for k, v in r[c].items() if k != "supported"}
        lines.append(f"- {c[6:]}: {'SUPPORTED' if r[c]['supported'] else 'NOT SUPPORTED'} {d}")
    Path(a.out).with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
