#!/usr/bin/env python3
"""Development check of the Paper 3 invisible-channel operators (EXPLORATORY, development data only).

Runs on a DEVELOPMENT circuit set disjoint from the 116-unit corpus (widths 6, 10, 14; circuit seed 7; the
corpus uses widths 5, 8, 12, 18, ... and seed 1234), so no corpus label is computed here.

For every (operator, development unit) it records:
  fires      the candidate compilation differs from the baseline in a way the operator intends;
  ref        the reference screen's verdict (cart's semantic oracle: exact <= 12q ancilla-free, else structural;
             cart's quality oracle), which must stay blind for an output-invisible operator;
  probe      obsaware.state_probe (record and phase verdicts);
  contract   obsaware.contract_v2.
Determinism operators are checked separately with fresh interpreters (PYTHONHASHSEED varies), see
scripts/dev_check_determinism.py.

Writes results/dev_check_operators.json and prints a per-operator summary.
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]

from cart.events.mutations import baseline_transpiler
from cart.manifest.backends import coupling_map_for
from cart.manifest.circuits import build
from cart.oracles.quality import QualityThresholds, evaluate_quality
from cart.oracles.semantic import check_semantic

from obsaware.mutations import CHANNEL, MUTATION_OPERATORS_P3
from obsaware.oracles import contract_v2, fingerprint, state_probe

DEV_FAMILIES = ("ghz", "qft", "qaoa_linear", "random_clifford")
DEV_BACKENDS = ("line", "heavy_hex")
DEV_WIDTHS = (6, 10, 14)
DEV_LEVELS = (1, 3)
DEV_SEED = 7
BASIS = ["cx", "rz", "sx", "x"]


def cfg_for(backend, n, level):
    return dict(optimization_level=level, coupling_map=coupling_map_for(backend, n), basis_gates=list(BASIS),
                seed_transpiler=1234)


def main() -> int:
    th = QualityThresholds.load()
    rows = []
    for fam in DEV_FAMILIES:
        for be in DEV_BACKENDS:
            for n in DEV_WIDTHS:
                for lvl in DEV_LEVELS:
                    qc = build(fam, n, seed=DEV_SEED)
                    cfg = cfg_for(be, n, lvl)
                    base_out = baseline_transpiler(cfg)(qc)
                    base_fps = {fingerprint(base_out), fingerprint(baseline_transpiler(cfg)(qc))}
                    if len(base_fps) > 1:
                        print("WARNING baseline not reproducible:", fam, n, be, lvl)
                    for name, op in MUTATION_OPERATORS_P3.items():
                        if CHANNEL[name] == "determinism":
                            continue
                        t0 = time.process_time()
                        try:
                            cand = op.transpiler(cfg)(qc)
                        except Exception as exc:
                            rows.append(dict(op=name, unit=f"{fam}-{n}-{be}-opt{lvl}", error=repr(exc)))
                            continue
                        tt = time.process_time() - t0
                        sem = check_semantic(qc, cand, coupling_map=cfg["coupling_map"], basis_gates=BASIS)
                        qual = evaluate_quality(base_out, cand, th)
                        pr = state_probe(qc, cand)
                        ct = contract_v2(qc, cand)
                        ref_detect = (sem.equivalent is False) or (sem.strength == "structural" and
                                                                   sem.details.get("structural_ok") is False) \
                            or qual.is_regression
                        matched = (pr.record_ok is False) or (pr.phase_ok is False) or (ct.holds is False)
                        rows.append(dict(
                            op=name, channel=CHANNEL[name], unit=f"{fam}-{n}-{be}-opt{lvl}", family=fam, backend=be,
                            n=n, level=lvl, fires=fingerprint(cand) not in base_fps or ct.holds is False,
                            ref_strength=sem.strength, ref_equiv=sem.equivalent, ref_quality=qual.is_regression,
                            ref_detect=bool(ref_detect), probe_record=pr.record_ok, probe_phase=pr.phase_ok,
                            probe_delta=pr.phase_delta, contract=ct.holds,
                            contract_clauses=sorted({k for k, _ in ct.violations}), matched_detect=bool(matched),
                            transpile_s=tt, probe_s=pr.cost_s, contract_s=ct.cost_s))
    out = ROOT / "results" / "dev_check_operators.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    agg = defaultdict(lambda: defaultdict(int))
    for r in rows:
        a = agg[r["op"]]
        a["units"] += 1
        if "error" in r:
            a["errors"] += 1
            continue
        a["fires"] += r["fires"]
        a["ref_detect"] += r["ref_detect"]
        a["matched"] += r["matched_detect"]
        a["fires_ref_blind_matched"] += r["fires"] and not r["ref_detect"] and r["matched_detect"]
        a["fires_both_blind"] += r["fires"] and not r["ref_detect"] and not r["matched_detect"]
    print(f"{'operator':36s} units fires ref_detect matched invisible+matched fired_but_missed errors")
    for k, a in agg.items():
        print(f"{k:36s} {a['units']:5d} {a['fires']:5d} {a['ref_detect']:10d} {a['matched']:7d} "
              f"{a['fires_ref_blind_matched']:17d} {a['fires_both_blind']:16d} {a['errors']:6d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
