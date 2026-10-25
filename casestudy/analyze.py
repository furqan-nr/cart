#!/usr/bin/env python3
"""Historical-fault case study: compare the snapshots of each buggy/fixed release pair (PROTOCOL_CASESTUDY.md).

    PYTHONPATH=cart/src:obsaware/src python casestudy/analyze.py > casestudy/results/case_study.json

Detection rule (protocol Section 2): a check detects the fault on a unit when it raises an alarm on the buggy build
and not on the fixed build; quality when the buggy compilation is a regression against the fixed one under the
registered thresholds; determinism when the buggy build is non-deterministic and the fixed build deterministic;
a crash under the buggy build only. K3' is reported separately. Selection uses the registered study's estimate
(session N260) and the frozen strategies; costs are estimated, not measured.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT / "cart" / "src"), str(ROOT / "obsaware" / "src")]
from cart.oracles.quality import QualityThresholds  # noqa: E402
from obsaware.cost_model import cost_table, load_session, units_from_session  # noqa: E402
from obsaware.selection import STRATEGIES, Ledger  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
PAIRS = [("P1", "#15024", "contract", "2.2.0rc1", "2.2.0"),
         ("P2", "#14956", "global phase", "2.1.2", "2.2.0"),
         ("P3", "#14730", "determinism", "2.1.1", "2.1.2"),
         ("P4", "#16237", "determinism", "2.4.2", "2.5.0"),
         ("P5", "#14603", "contract", "2.0.2", "2.0.3")]
MATCH = {"contract": ("contract",), "global phase": ("probe",), "determinism": ("determinism",)}
TRIG = {"P1": "P1_15024", "P2": "P2_14956", "P3": "P3_14730", "P4": "P4_16237", "P5": "P5_14603"}
BUDGETS = (0.02, 0.05, 0.10)


def rel(b, c):
    return (0.0 if c == 0 else math.inf) if b == 0 else (c - b) / b


def quality_regression(fixed, buggy, th):
    r2, rd = rel(fixed["twoq"], buggy["twoq"]), rel(fixed["depth"], buggy["depth"])
    return (r2 >= th.tau_2q and -rd < th.tau_depth_improve) or (rd >= th.tau_depth and -r2 < th.tau_2q_improve)


def detect(b, f, th, det_b=None, det_f=None):
    """Per-check detection for one unit (b = buggy record, f = fixed record)."""
    out = {}
    if "crash" in b and "crash" not in f:
        return {"crash": True}
    if "crash" in b or "crash" in f:
        return {}
    for c in ("output", "probe", "contract", "k3prime"):
        out[c] = bool(b.get(f"{c}_alarm") is True and f.get(f"{c}_alarm") is False)
    out["quality"] = bool(quality_regression(f, b, th))
    if det_b is not None and det_f is not None:
        out["determinism"] = bool(det_b > 1 and det_f == 1)
    out["changed"] = b.get("fp") != f.get("fp")
    return out


def load(v, name):
    p = DATA / v / name
    return json.loads(p.read_text()) if p.exists() else None


def first_cost(order, detects, est):
    led = Ledger(est)
    for it in order:
        led.add(it)
        if detects.get(it):
            return led.spent
    return math.inf


def main() -> int:
    th = QualityThresholds.load()
    sess = load_session(ROOT / "data/N260/out_N260")
    units = units_from_session(sess)
    est = cost_table(sess, k=1.0)
    full = est.total()
    res = {"note": "exploratory case study; costs are the registered study's estimate (N260)", "pairs": []}
    for pid, pr, ch, bv, fv in PAIRS:
        row = dict(pair=pid, fix=pr, channel=ch, buggy=bv, fixed=fv)
        cb, cf = load(bv, "corpus.json"), load(fv, "corpus.json")
        db, dfx = load(bv, "determinism.json"), load(fv, "determinism.json")
        if cb is None or cf is None:
            row["status"] = "missing data"
            res["pairs"].append(row)
            continue
        per = {}
        for t in cb:
            per[t] = detect(cb[t], cf[t], th, db[t]["distinct"] if db else None, dfx[t]["distinct"] if dfx else None)
        row["units_changed"] = sum(1 for v in per.values() if v.get("changed"))
        row["units_detecting"] = {c: sorted(t for t, v in per.items() if v.get(c))
                                  for c in ("crash", "output", "quality", "probe", "contract", "k3prime", "determinism")}
        row["n_units_detecting"] = {c: len(v) for c, v in row["units_detecting"].items()}
        row["matched_checks"] = list(MATCH[ch]) + (["k3prime"] if ch == "contract" else [])
        # selection (registered checks; and the K3' variant counted as a contract detection)
        sel = {}
        # protocol Section 1: an alarm is attributed to the fault only if the firing check observes its channel
        for variant in ("registered", "with_k3prime"):
            detects = {}
            for t, v in per.items():
                for c in ("output", "quality", "probe", "contract", "determinism"):
                    hit = c in MATCH[ch] and (v.get(c, False) or (variant == "with_k3prime" and c == "contract"
                                                                  and v.get("k3prime", False)))
                    detects[(t, c)] = hit
            out = {}
            for s, fn in STRATEGIES.items():
                out[s] = dict({f"{int(f * 100)}%": any(detects.get(it, False) for it in fn(units, est, f * full))
                               for f in BUDGETS},
                              first_detection_est_s=first_cost(fn(units, est, math.inf), detects, est))
            sel[variant] = out
        row["selection"] = sel
        tb, tf = load(bv, "triggers.json"), load(fv, "triggers.json")
        if tb and tf:
            name = TRIG[pid]
            b, f = tb[name], tf[name]
            d = detect(b, f, th, b.get("det_distinct"), f.get("det_distinct"))
            row["trigger"] = dict(unit=name, detects={k: v for k, v in d.items() if k != "changed"},
                                  changed=d.get("changed"),
                                  buggy={k: b.get(k) for k in ("crash", "output_alarm", "probe_alarm", "probe_detail",
                                                               "contract_alarm", "contract_violations", "k3prime_alarm",
                                                               "det_distinct", "twoq", "depth")},
                                  fixed={k: f.get(k) for k in ("crash", "output_alarm", "probe_alarm", "probe_detail",
                                                               "contract_alarm", "contract_violations", "k3prime_alarm",
                                                               "det_distinct", "twoq", "depth")})
        res["pairs"].append(row)
    def clean(o):
        if isinstance(o, float) and math.isinf(o):
            return None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    print(json.dumps(clean(res), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
