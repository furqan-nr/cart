#!/usr/bin/env python3
"""Registration R2, frozen analysis: claims A, B and C with the PREVIOUS-REVISION cost estimate (estimator T2).

Differences from the first registration's analysis (obsaware/scripts/analyze_p3.py), and nothing else:
  * the cost ESTIMATE for a cohort comes from a separate calibration session N (obsaware/scripts/calibrate_costs.py,
    no fault operator) run on the SAME Qiskit version as the cohort, before the cohort's labeling session: the costs a
    CI system knows from a full run of the base revision on its own runners (a nightly run);
  * no compile-based speed rule. Machine-speed rule M1: k = median reference benchmark of the labeling session /
    median reference benchmark of session N; every estimated cost is multiplied by k only if k lies outside
    [0.85, 1.15], otherwise k = 1.
Everything else is imported unchanged from analyze_p3.py: the strategies, the budgets (2%, 5%, 10% of the estimated
full observability-aware suite), detection (rule L1 of label_cohort.py), real costs (the labeling session), the
first-detection cost and the sign test. Claims A, B and C and their thresholds are identical.

    python r2/analyze_r2.py --pair data/N260/out_N260 data/C260/out_C260 --pair data/N231/out_N231 data/C231/out_C231 \
        --out results/registered_analysis_r2.json
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
sys.path[:0] = [str(ROOT / "cart" / "src"), str(ROOT / "obsaware" / "src")]
_spec = importlib.util.spec_from_file_location("analyze_p3", ROOT / "obsaware" / "scripts" / "analyze_p3.py")
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)

from obsaware.cost_model import cost_table, load_session, units_from_session  # noqa: E402
from obsaware.selection import STRATEGIES, random_items, real_spend  # noqa: E402

BENCH_BAND = (0.85, 1.15)


def bench_median(d: Path) -> float:
    return st.median(json.loads(l)["median_s"] for l in (d / "benchmark.jsonl").read_text().splitlines())


def analyse_pair(n_dir: Path, c_dir: Path) -> dict:
    prev, cur = load_session(n_dir), load_session(c_dir)
    qv_n = json.loads((n_dir / "hardware.json").read_text())["qiskit"]
    qv_c = json.loads((c_dir / "hardware.json").read_text())["qiskit"]
    assert qv_n == qv_c, f"calibration session is Qiskit {qv_n}, labeling session is Qiskit {qv_c}"
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
        row = dict(event=ev["event"], group=ev["group"], detectable=any(detects.values()),
                   units_detecting=len({t for (t, c), d in detects.items() if d}),
                   checks_detecting=sorted({c for (t, c), d in detects.items() if d}), budgets={}, first_cost={})
        for f in an.BUDGETS:
            b = f * full
            res = {}
            for s, fn in STRATEGIES.items():
                sel = fn(units, est, b)
                res[s] = dict(detected=any(detects.get(it, False) for it in sel), spend_ratio=real_spend(sel, real) / b)
            rnd = [random_items(units, est, b, seed=i) for i in range(an.RANDOM_SEEDS)]
            res["random_items"] = dict(detected=st.mean(any(detects.get(it, False) for it in s) for s in rnd),
                                       spend_ratio=st.mean(real_spend(s, real) / b for s in rnd))
            row["budgets"][str(f)] = res
        for s, fn in STRATEGIES.items():
            row["first_cost"][s] = an.first_cost(fn(units, est, math.inf), detects, real)
        rows.append(row)
    det_rows = [r for r in rows if r["detectable"]]

    def count(s, f):
        return sum(1 for r in det_rows if r["budgets"][str(f)][s]["detected"])

    a = {s: count(s, 0.05) for s in (an.PRIMARY,) + an.COMPARATORS}
    claim_a = a[an.PRIMARY] > a["output_only"] and a[an.PRIMARY] >= a["all_checks"] and a[an.PRIMARY] >= a["cheapest_items"]
    wins = sum(1 for r in det_rows if r["first_cost"][an.PRIMARY] < r["first_cost"]["all_checks"] - 1e-9)
    losses = sum(1 for r in det_rows if r["first_cost"][an.PRIMARY] > r["first_cost"]["all_checks"] + 1e-9)
    p_b = an.sign_test_p(wins, losses)
    c_detail, claim_c = {}, True
    for f in an.BUDGETS:
        ratios = [r["budgets"][str(f)][an.PRIMARY]["spend_ratio"] for r in rows]
        c_detail[str(f)] = dict(mean=st.mean(ratios) if ratios else None, max=max(ratios) if ratios else None)
        claim_c = claim_c and bool(ratios) and st.mean(ratios) <= 1.25 and max(ratios) <= 2.0
    return dict(cohort=c_dir.name, calibration_session=n_dir.name, qiskit=qv_c, machine_factor_raw=k_raw,
                machine_factor_applied=k, full_suite_estimate_s=full, budgets_s={str(f): f * full for f in an.BUDGETS},
                excluded_operators=excluded, n_events=len(rows), n_detectable=len(det_rows),
                claim_A=dict(supported=claim_a, detected_at_5pct=a),
                claim_B=dict(supported=wins > losses and p_b < 0.05, wins=wins, losses=losses,
                             ties=len(det_rows) - wins - losses, p=p_b),
                claim_C=dict(supported=claim_c, spend_ratio=c_detail),
                detection_by_budget={str(f): {s: count(s, f) for s in STRATEGIES} for f in an.BUDGETS},
                events=rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", nargs=2, action="append", required=True, metavar=("CALIBRATION_DIR", "COHORT_DIR"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cohorts = [analyse_pair(Path(n), Path(c)) for n, c in a.pair]
    overall = {c: all(r[c]["supported"] for r in cohorts) for c in ("claim_A", "claim_B", "claim_C")}
    Path(a.out).write_text(json.dumps(dict(overall=overall, cohorts=cohorts), indent=1,
                                      default=lambda x: None if x == math.inf else x))
    lines = ["# Registration R2: registered claims", ""]
    for c in cohorts:
        lines += [f"## Cohort {c['cohort']} (Qiskit {c['qiskit']}, estimate from {c['calibration_session']})",
                  f"machine factor {c['machine_factor_raw']:.3f} (applied {c['machine_factor_applied']:.3f}); full suite "
                  f"estimate {c['full_suite_estimate_s']:.1f} s; events {c['n_events']}, detectable {c['n_detectable']}; "
                  f"excluded {c['excluded_operators']}",
                  f"- A: {'SUPPORTED' if c['claim_A']['supported'] else 'NOT SUPPORTED'} {c['claim_A']['detected_at_5pct']}",
                  f"- B: {'SUPPORTED' if c['claim_B']['supported'] else 'NOT SUPPORTED'} wins {c['claim_B']['wins']}, "
                  f"losses {c['claim_B']['losses']}, ties {c['claim_B']['ties']}, p = {c['claim_B']['p']:.4f}",
                  f"- C: {'SUPPORTED' if c['claim_C']['supported'] else 'NOT SUPPORTED'} {c['claim_C']['spend_ratio']}", ""]
    lines += ["## Overall (every cohort)"] + [f"- {k}: {'SUPPORTED' if v else 'NOT SUPPORTED'}" for k, v in overall.items()]
    Path(a.out).with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
