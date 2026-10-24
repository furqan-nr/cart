"""Paper 3 cost estimator: per-(unit, check) costs measured in an EARLIER session (K1, clean baseline, Qiskit
2.4.2), rescaled to the current machine with Paper 2's registered speed rule.

Speed rule (as cart.selectors.coast.speed_factor, Paper 2 Phase C): k = median, over units whose previous-session
baseline compile cost is at least 0.05 s, of current / previous baseline compile cost; if k lies outside
[0.8, 1.25] every estimated cost (compile, checks, determinism lane) is multiplied by k, otherwise by 1.
The current-session baseline compile costs are pre-execution information (they are measured before any event).
"""
from __future__ import annotations

import glob
import json
import os
import statistics as st
from pathlib import Path

from obsaware.selection import CostTable, Unit

SPEED_MIN_PREV_S = 0.05
SPEED_BAND = (0.8, 1.25)


def load_session(out_dir: str | Path) -> dict:
    """Read a calibration session directory (calibrate_costs.py output, or the baseline part of a cohort run)."""
    out_dir = Path(out_dir)
    recs = {}
    for p in sorted(glob.glob(str(out_dir / "units" / "*.json"))):
        r = json.loads(Path(p).read_text())
        recs[r["test_id"]] = r
    det = json.loads((out_dir / "determinism_lane.json").read_text())
    return {"units": recs, "det": det}


def applicable_checks(rec: dict) -> tuple[str, ...]:
    a = ["output", "quality", "contract", "determinism"]
    if rec.get("probe_applicable"):
        a.insert(2, "probe")
    return tuple(a)


def units_from_session(sess: dict) -> list[Unit]:
    return [Unit(r["test_id"], r["family"], r["backend"], r["n"], r["level"], r["output_tier"])
            for _, r in sorted(sess["units"].items())]


def cost_table(sess: dict, *, k: float = 1.0) -> CostTable:
    """CostTable from a session, every cost multiplied by k."""
    det = sess["det"]
    r_launch = det["r"]
    fixed = st.median(det["fixed_cpu_per_launch_s"]) * r_launch
    compile_s, check_s, appl = {}, {}, {}
    for t, r in sess["units"].items():
        appl[t] = applicable_checks(r)
        compile_s[t] = k * r["compile_s"]
        for c in ("output", "quality", "probe", "contract"):
            if c in appl[t]:
                check_s[(t, c)] = k * float(r[f"{c}_s"])
        dc = det["per_unit"][t]["compile_s"]
        check_s[(t, "determinism")] = k * sum(dc)            # R compilations of this unit, one per launch
    return CostTable(compile_s=compile_s, check_s=check_s, det_fixed_s=k * fixed, applicable=appl)


def speed_factor(current_compile_s: dict[str, float], previous_compile_s: dict[str, float]) -> tuple[float, float]:
    r = sorted(current_compile_s[t] / previous_compile_s[t] for t in current_compile_s
               if t in previous_compile_s and previous_compile_s[t] >= SPEED_MIN_PREV_S and current_compile_s[t] > 0)
    if not r:
        return 1.0, 1.0
    kr = float(st.median(r))
    return kr, (1.0 if SPEED_BAND[0] <= kr <= SPEED_BAND[1] else kr)
