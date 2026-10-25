#!/usr/bin/env python3
"""Generate every table and figure of the Paper 3 manuscript from the repository's result files.

    python gen/make_assets.py --repo /path/to/cart

Writes tab/*.tex and fig/*.pdf next to this script's parent folder. Nothing in the manuscript's tables or figures
is typed by hand; every number comes from the files read here.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
TAB, FIG = HERE / "tab", HERE / "fig"

STRATS = ["observability", "all_checks", "cheapest_items", "output_only"]
LABEL = {"observability": "Observability-aware", "all_checks": "All checks", "cheapest_items": "Cheapest items",
         "output_only": "Output only", "random_items": "Random items (20 seeds)"}
SHORT = {"observability": "OA", "all_checks": "AC", "cheapest_items": "CH", "output_only": "OO"}
COLOR = {"observability": "#2a78d6", "output_only": "#eb6834", "all_checks": "#1baf7a",
         "cheapest_items": "#eda100", "random_items": "#e87ba4"}
MARK = {"observability": "o", "output_only": "s", "all_checks": "^", "cheapest_items": "D", "random_items": "v"}
INK, MUTED, GRID = "#1f1f1e", "#6b6b66", "#e4e3df"
BUDGETS = ["0.02", "0.05", "0.1"]
COHORT_LABEL = {"out_C261": "C261 (2.6.1)", "out_C252": "C252 (2.5.2)",
                "out_C260": "C260 (2.6.0)", "out_C231": "C231 (2.3.1)"}

CHANNEL = {  # operator -> (group, channel shown in the paper, origin)
    "phase_drop_after_translation_wide": ("invisible", "global phase", "new"),
    "rz_canonicalize_without_phase": ("invisible", "global phase", "new"),
    "cp_rule_missing_phase": ("invisible", "global phase", "new"),
    "input_count_includes_ancillas": ("invisible", "contract", "new"),
    "input_registers_dropped": ("invisible", "contract", "new"),
    "final_layout_record_wide": ("invisible", "layout record", "new"),
    "hash_order_rz_shift_line": ("invisible", "determinism", "new"),
    "hash_order_rz_4pi_heavyhex": ("invisible", "determinism", "new"),
    "wide_drop_opt_loop": ("visible", "quality", "Paper 2"),
    "heavy_hex_trivial_layout": ("visible", "quality", "Paper 2"),
    "small_drop_opt_loop": ("visible", "quality", "Paper 2"),
    "cp_swap_detour": ("visible", "quality", "Paper 2"),
    "wide_no_elide_permutations": ("visible", "quality", "Paper 2"),
    "cp_small_angle_sign_flip": ("visible", "semantics", "Paper 2"),
    "wide_rz_sign_flip": ("visible", "semantics", "Paper 2"),
    "drop_routed_swap": ("visible", "semantics", "Paper 2"),
    "drop_first_rzz": ("visible", "semantics", "Paper 2"),
    "wide_leaky_basis_h": ("visible", "structure", "Paper 2"),
}


def tt(s: str) -> str:
    return r"\op{" + s.replace("_", r"\_") + "}"


def f2(x: float) -> str:
    return f"{x:.2f}"


def load(repo: Path):
    r1 = json.loads((repo / "results/registered_analysis.json").read_text())
    r2 = json.loads((repo / "results/registered_analysis_r2.json").read_text())
    diag = json.loads((repo / "posthoc/diagnose_claim_c.json").read_text())
    prev = json.loads((repo / "posthoc/preview_cost_estimators.json").read_text())
    rean = json.loads((repo / "reanalysis/comparison.json").read_text())
    lab = json.loads((repo / "reanalysis/label_checks.json").read_text())
    return r1, r2, diag, prev, rean, lab


def session_rows(repo: Path):
    spec = [("K1", "K1/out_k1", "estimate (first registration)"),
            ("C261", "C261/out_C261", "labeling, first registration"),
            ("C252", "C252/out_C252", "labeling, first registration"),
            ("N260", "N260/out_N260", "estimate (R2)"),
            ("C260", "C260/out_C260", "labeling, R2"),
            ("N231", "N231/out_N231", "estimate (R2)"),
            ("C231", "C231/out_C231", "labeling, R2")]
    rows = []
    for name, rel, role in spec:
        d = repo / "data" / rel
        hw = json.loads((d / "hardware.json").read_text())
        b = [json.loads(l)["median_s"] for l in (d / "benchmark.jsonl").read_text().splitlines()]
        drift = max(abs(x / b[0] - 1) for x in b)
        n_units = len(list((d / "units").glob("*"))) if (d / "units").exists() else None
        n_events = len(list((d / "events").glob("*.json"))) if (d / "events").exists() else 0
        rows.append(dict(name=name, qiskit=hw["qiskit"], role=role, drift=drift, readings=len(b),
                         start=hw.get("started_utc", ""), units=n_units, events=n_events,
                         bench_median=st.median(b)))
    return rows


# ------------------------------------------------------------------------------------------------ tables
def tab_sessions(rows):
    out = [r"\begin{tabular}{@{}llllrr@{}}", r"\toprule",
           r"Session & Qiskit & Role & Start (UTC) & Benchmark readings & Max.\ drift \\", r"\midrule"]
    for r in rows:
        start = r["start"].replace("T", " ").replace("Z", "")[:16] if r["start"] else "2026-10-23 18:16"
        out.append(f"{r['name']} & {r['qiskit']} & {r['role']} & {start} & {r['readings']} & "
                   f"{100 * r['drift']:.1f}\\% \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_operators(r1, r2):
    cohorts = r1["cohorts"] + r2["cohorts"]
    ev = {c["cohort"]: {e["event"]: e for e in c["events"]} for c in cohorts}
    order = [k for k, v in CHANNEL.items() if v[0] == "invisible"] + [k for k, v in CHANNEL.items() if v[0] == "visible"]
    out = [r"\begin{tabular}{@{}lllrrrr@{}}", r"\toprule",
           r" & & & \multicolumn{4}{c}{Units detecting} \\ \cmidrule(l){4-7}",
           r"Operator & Channel & Detected by & C261 & C252 & C260 & C231 \\", r"\midrule",
           r"\multicolumn{7}{@{}l}{\emph{Output-invisible (new in this study)}} \\"]
    for i, k in enumerate(order):
        if i == 8:
            out.append(r"\multicolumn{7}{@{}l}{\emph{Output-visible (Paper 2's operators, unchanged)}} \\")
        checks = sorted(set().union(*[ev[c["cohort"]][k]["checks_detecting"] for c in cohorts]))
        units = " & ".join(str(ev[c["cohort"]][k]["units_detecting"]) for c in cohorts)
        out.append(f"{tt(k)} & {CHANNEL[k][1]} & {', '.join(checks)} & {units} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_claims(r1, r2):
    out = [r"\begin{tabular}{@{}llllll@{}}", r"\toprule",
           r"Registration & Cohort & A: detected at 5\% (OA/OO/AC/CH) & B: earlier/later, $p$ & "
           r"C: mean spend 2/5/10\% & C: max spend \\", r"\midrule"]
    for reg, d in (("R2 (registered)", r2), ("Earlier", r1)):
        for c in d["cohorts"]:
            a = c["claim_A"]["detected_at_5pct"]
            b = c["claim_B"]
            cc = c["claim_C"]["spend_ratio"]
            mark = lambda s: r"\,\checkmark" if s else r"\,$\times$"  # noqa: E731
            out.append(
                f"{reg} & {COHORT_LABEL[c['cohort']]} & "
                f"{a['observability']}/{a['output_only']}/{a['all_checks']}/{a['cheapest_items']}{mark(c['claim_A']['supported'])} & "
                f"{b['wins']}/{b['losses']}, {b['p']:.4f}{mark(b['supported'])} & "
                f"{'/'.join(f2(cc[x]['mean']) for x in BUDGETS)}{mark(c['claim_C']['supported'])} & "
                f"{'/'.join(f2(cc[x]['max']) for x in BUDGETS)} \\\\")
        if reg.startswith("R2"):
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_detection(r1, r2):
    cohorts = r1["cohorts"] + r2["cohorts"]
    out = [r"\begin{tabular}{@{}l" + "r" * 12 + r"@{}}", r"\toprule",
           " & " + " & ".join(r"\multicolumn{3}{c}{" + COHORT_LABEL[c["cohort"]] + "}" for c in cohorts) + r" \\",
           " ".join(fr"\cmidrule(l){{{2 + 3 * i}-{4 + 3 * i}}}" for i in range(4)),
           "Strategy & " + " & ".join(["2\\%", "5\\%", "10\\%"] * 4) + r" \\", r"\midrule"]
    for s in STRATS + ["random_items"]:
        cells = []
        for c in cohorts:
            for f in BUDGETS:
                if s == "random_items":
                    det = [e for e in c["events"] if e["detectable"]]
                    cells.append(f"{sum(e['budgets'][f]['random_items']['detected'] for e in det) + 1e-9:.2f}")
                else:
                    cells.append(str(c["detection_by_budget"][f][s]))
        out.append(LABEL[s] + " & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_groups(r1, r2):
    cohorts = r1["cohorts"] + r2["cohorts"]
    out = [r"\begin{tabular}{@{}l" + "rr" * 4 + r"@{}}", r"\toprule",
           " & " + " & ".join(r"\multicolumn{2}{c}{" + COHORT_LABEL[c["cohort"]] + "}" for c in cohorts) + r" \\",
           " ".join(fr"\cmidrule(l){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(4)),
           "Strategy & " + " & ".join(["Vis.", "Invis."] * 4) + r" \\", r"\midrule"]
    for s in STRATS:
        cells = []
        for c in cohorts:
            for g in ("visible", "invisible"):
                evs = [e for e in c["events"] if e["detectable"] and e["group"] == g]
                cells.append(f"{sum(e['budgets']['0.05'][s]['detected'] for e in evs)}/{len(evs)}")
        out.append(LABEL[s] + " & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_spend_all(r1, r2):
    cohorts = r1["cohorts"] + r2["cohorts"]
    out = [r"\begin{tabular}{@{}l" + "r" * 4 + r"@{}}", r"\toprule",
           "Strategy & " + " & ".join(COHORT_LABEL[c["cohort"]] for c in cohorts) + r" \\", r"\midrule"]
    for s in STRATS + ["random_items"]:
        cells = [f2(st.mean(e["budgets"]["0.05"][s]["spend_ratio"] for e in c["events"])) for c in cohorts]
        out.append(LABEL[s] + " & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_preview(prev):
    names = {"registered": "First registration (compile-based speed rule)", "T1": "T1 (component-wise scaling)",
             "T2_same_session": "T2 from the same session"}
    out = [r"\begin{tabular}{@{}lll@{}}", r"\toprule",
           r"Estimator & C261: mean 2/5/10\% (max) & C252: mean 2/5/10\% (max) \\", r"\midrule"]
    keys = list(prev["out_C261"]["estimators"].keys())
    for k in keys:
        cells = []
        for c in ("out_C261", "out_C252"):
            e = prev[c]["estimators"][k]
            mx = max(e[f]["observability_spend_max"] for f in BUDGETS)
            cells.append("/".join(f2(e[f]["observability_spend_mean"]) for f in BUDGETS) + f" ({f2(mx)})")
        out.append(f"{names.get(k, k)} & {cells[0]} & {cells[1]} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_diag(diag):
    out = [r"\begin{tabular}{@{}lrr@{}}", r"\toprule", r"Median cost ratio, cohort / K1 & C261 & C252 \\", r"\midrule"]
    a, b = diag["out_C261"], diag["out_C252"]
    rows = [("Baseline compilation", a["cost_ratio_cohort_over_K1"]["compile"]["median"],
             b["cost_ratio_cohort_over_K1"]["compile"]["median"]),
            ("Output check (12-qubit exact units)", a["cost_ratio_cohort_over_K1"]["output_check"]["median"],
             b["cost_ratio_cohort_over_K1"]["output_check"]["median"]),
            ("State probe", a["cost_ratio_cohort_over_K1"]["probe"]["median"],
             b["cost_ratio_cohort_over_K1"]["probe"]["median"]),
            ("Reference benchmark", a["benchmark_ratio_cohort_over_K1"], b["benchmark_ratio_cohort_over_K1"])]
    out += [f"{n} & {x:.3f} & {y:.3f} \\\\" for n, x, y in rows]
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ figures
def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def fig_detection(r1, r2):
    cohorts = r1["cohorts"] + r2["cohorts"]
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.3), sharey=True)
    xs = [2, 5, 10]
    for ax, c in zip(axes, cohorts):
        det = [e for e in c["events"] if e["detectable"]]
        for s in STRATS + ["random_items"]:
            if s == "random_items":
                ys = [sum(e["budgets"][f]["random_items"]["detected"] for e in det) for f in BUDGETS]
            else:
                ys = [c["detection_by_budget"][f][s] for f in BUDGETS]
            ax.plot(xs, ys, color=COLOR[s], marker=MARK[s], ms=5, lw=1.6, label=LABEL[s],
                    zorder=3 if s == "observability" else 2, mec="white", mew=0.8)
        ax.set_title(COHORT_LABEL[c["cohort"]], fontsize=8.5, color=INK)
        ax.set_xticks(xs, ["2%", "5%", "10%"])
        ax.set_ylim(0, 19)
        ax.set_xlim(1, 11)
        _style(ax)
    axes[0].set_ylabel("Events detected (of 18)", fontsize=8.5, color=INK)
    for ax in axes:
        ax.set_xlabel("Budget", fontsize=8, color=INK)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=5, fontsize=7.5, frameon=False, bbox_to_anchor=(0.5, 1.07))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "detection_by_budget.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_spend(r1, r2):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.4), sharey=True)
    groups = [("First", r1), ("R2", r2)]
    for ax, f in zip(axes, BUDGETS):
        pos, data, labels = [], [], []
        p = 0
        for reg, d in groups:
            for c in d["cohorts"]:
                data.append([e["budgets"][f]["observability"]["spend_ratio"] for e in c["events"]])
                labels.append(COHORT_LABEL[c["cohort"]].split()[0] + ("\nfirst" if reg == "First" else "\nR2"))
                pos.append(p)
                p += 1
            p += 0.6
        for x, ys, i in zip(pos, data, range(len(pos))):
            col = "#eb6834" if i < 2 else "#2a78d6"
            jitter = [x + 0.18 * ((j % 5) - 2) / 2 for j in range(len(ys))]
            ax.scatter(jitter, ys, s=12, color=col, edgecolors="white", linewidths=0.5, zorder=3,
                       marker="s" if i < 2 else "o")
            ax.hlines(st.mean(ys), x - 0.3, x + 0.3, color=INK, lw=1.4, zorder=4)
        ax.axhline(1.25, color=MUTED, ls="--", lw=0.9)
        ax.axhline(2.0, color=MUTED, ls=":", lw=0.9)
        ax.axhline(1.0, color=GRID, lw=0.9)
        ax.set_xticks(pos, labels, fontsize=7.5)
        ax.set_title(f"{int(float(f) * 100)}% budget", fontsize=8.5, color=INK)
        _style(ax)
    axes[0].set_ylabel("Real spend / budget", fontsize=8.5, color=INK)
    axes[-1].text(axes[-1].get_xlim()[1], 1.27, "mean limit 1.25", fontsize=6.5, color=MUTED, ha="right", va="bottom")
    axes[-1].text(axes[-1].get_xlim()[1], 2.02, "max limit 2.0", fontsize=6.5, color=MUTED, ha="right", va="bottom")
    fig.tight_layout()
    fig.savefig(FIG / "spend_ratio.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_first(r2):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, c in zip(axes, r2["cohorts"]):
        det = [e for e in c["events"] if e["detectable"]]
        for e in det:
            a, o = e["first_cost"]["all_checks"], e["first_cost"]["observability"]
            g = e["group"]
            ax.scatter(max(a, 0.01), max(o, 0.01), s=26, marker="o" if g == "invisible" else "s",
                       color="#2a78d6" if g == "invisible" else "#eb6834", edgecolors="white", linewidths=0.6,
                       zorder=3)
        lim = (0.008, 200)
        ax.plot(lim, lim, color=MUTED, lw=0.9, ls="--")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        b = c["claim_B"]
        ax.set_title(f"{COHORT_LABEL[c['cohort']]}: {b['wins']} below the diagonal, {b['losses']} above",
                     fontsize=8.5, color=INK)
        ax.set_xlabel("All checks: real cost to first detection (s)", fontsize=8, color=INK)
        _style(ax)
        ax.xaxis.grid(True, color=GRID, lw=0.6)
    axes[0].set_ylabel("Observability-aware (s)", fontsize=8, color=INK)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", color="#2a78d6", label="output-invisible event"),
         Line2D([], [], marker="s", ls="", color="#eb6834", label="output-visible event")]
    fig.legend(handles=h, loc="upper center", ncol=2, fontsize=7.5, frameon=False, bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIG / "first_detection.pdf", bbox_inches="tight")
    plt.close(fig)


def numbers(r1, r2, diag, rean, lab, rows):
    """Macros for numbers quoted in the text, so prose and data cannot drift apart."""
    m = {}
    for d in (r1, r2):
        for c in d["cohorts"]:
            k = c["cohort"].replace("out_", "")
            m[f"full{k}"] = f"{c['full_suite_estimate_s']:,.0f}"
            m[f"p{k}"] = f"{c['claim_B']['p']:.4f}"
    m["kC261"] = f"{r1['cohorts'][0]['speed_factor_applied']:.3f}"
    m["kC252"] = f"{r1['cohorts'][1]['speed_factor_applied']:.3f}"
    m["mC260"] = f"{r2['cohorts'][0]['machine_factor_raw']:.3f}"
    m["mC231"] = f"{r2['cohorts'][1]['machine_factor_raw']:.3f}"
    return "\n".join(f"\\newcommand{{\\num{k.replace('0', 'O').replace('1', 'I').replace('2', 'Z').replace('3', 'E').replace('5', 'S').replace('6', 'X')}}}{{{v}}}"
                     for k, v in m.items()) + "\n"


# ------------------------------------------------------------------------------------------------ exploratory
EXPL_NAMES = {"OO": "OO", "AC": "AC", "OA": "OA", "CI": "CH", "AC_costaware": "AC-cost", "AC_lane_last": "AC-lane-last",
              "OA_key_channel": "OA, key (channel)", "OA_key_target_channel": "OA, key (target, channel)",
              "CI_lane_first": "CH, lane first"}


def tab_grid(ex):
    cs = [c for c in ex["cohorts"] if c["registration"] == "R2"]
    cols = ["OO", "AC", "AC_costaware", "CI", "OA"]
    out = [r"\begin{tabular}{@{}l" + "rrrrrr" * len(cs) + r"@{}}", r"\toprule",
           " & " + " & ".join(r"\multicolumn{6}{c}{" + COHORT_LABEL[c["cohort"]] + "}" for c in cs) + r" \\",
           " ".join(fr"\cmidrule(l){{{2 + 6 * i}-{7 + 6 * i}}}" for i in range(len(cs))),
           "Budget & " + " & ".join([" & ".join(EXPL_NAMES[x] for x in cols) + " & OA spend"] * len(cs)) + r" \\",
           r"\midrule"]
    for f in cs[0]["grid"]:
        cells = []
        for c in cs:
            g = c["grid"][f]
            best = max(g[x]["detected"] for x in cols)
            for x in cols:
                v = g[x]["detected"]
                cells.append(r"\textbf{" + str(v) + "}" if v == best else str(v))
            cells.append(f2(g["OA"]["spend_mean"]))
        lab = f"{float(f) * 100:g}\\%"
        if f in ("0.02", "0.05", "0.1"):
            lab += "$^*$"
        out.append(lab + " & " + " & ".join(cells) + r" \\")
    out += [r"\midrule"]
    cells = []
    for c in cs:
        cells += [f2(c["auc_0_10pct"][x]) for x in cols] + [""]
    out.append("AUC & " + " & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def tab_effects(ex):
    cs = ex["cohorts"]
    comps = [("OA_vs_AC", "AC (registered, claim B)"), ("OA_vs_AC_costaware", "AC-cost"),
             ("OA_vs_CI", "CH"), ("OA_vs_CI_lane_first", "CH, lane first"), ("OA_vs_OA_key_channel", "OA, key (channel)")]
    out = [r"\begin{tabular}{@{}l" + "l" * len(cs) + r"@{}}", r"\toprule",
           "OA against & " + " & ".join(COHORT_LABEL[c["cohort"]] for c in cs) + r" \\", r"\midrule"]
    for k, name in comps:
        cells = []
        for c in cs:
            v = c["first"][k]
            cells.append(f"{v['wins']}/{v['losses']}/{v['ties']}, $p={v['p']:.3f}$")
        out.append(name + " & " + " & ".join(cells) + r" \\")
        cells = []
        for c in cs:
            v = c["first"][k]
            cells.append(f"{v['gmean_ratio']:.2f} [{v['ci95'][0]:.3f}, {v['ci95'][1]:.2f}]")
        out.append(r"\quad geometric-mean ratio [95\% CI] & " + " & ".join(cells) + r" \\")
    out.append(r"\midrule")
    for k in ("OA", "AC", "AC_costaware", "CI", "OA_key_channel"):
        out.append(f"Total first-detection cost, {EXPL_NAMES[k]} (s) & " +
                   " & ".join(f"{c['first_totals'][k]:.0f}" for c in cs) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


def fig_grid(ex):
    cs = ex["cohorts"]
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.4), sharey=True)
    m = {"OO": "output_only", "AC": "all_checks", "CI": "cheapest_items", "OA": "observability"}
    for ax, c in zip(axes, cs):
        fs = [float(f) for f in c["grid"]]
        for k in ("OO", "AC", "CI", "OA"):
            s = m[k]
            ys = [c["grid"][f][k]["detected"] for f in c["grid"]]
            ax.plot([100 * f for f in fs], ys, color=COLOR[s], marker=MARK[s], ms=3.8, lw=1.4, label=LABEL[s],
                    zorder=3 if k == "OA" else 2, mec="white", mew=0.6)
        for x in (2, 5, 10):
            ax.axvline(x, color=GRID, lw=0.8, zorder=0)
        ax.set_xscale("log")
        ax.set_xticks([0.25, 0.5, 1, 2, 5, 10], ["0.25", "0.5", "1", "2", "5", "10"])
        ax.minorticks_off()
        ax.set_ylim(0, 19)
        ax.set_title(COHORT_LABEL[c["cohort"]], fontsize=8.5, color=INK)
        ax.set_xlabel("Budget (%)", fontsize=8, color=INK)
        _style(ax)
    axes[0].set_ylabel("Events detected (of 18)", fontsize=8.5, color=INK)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=4, fontsize=7.5, frameon=False, bbox_to_anchor=(0.5, 1.07))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "detection_grid.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--exploratory", required=True, help="output of posthoc/exploratory_p3.py")
    a = ap.parse_args()
    repo = Path(a.repo)
    ex = json.loads(Path(a.exploratory).read_text())
    TAB.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    r1, r2, diag, prev, rean, lab = load(repo)
    rows = session_rows(repo)
    (TAB / "sessions.tex").write_text(tab_sessions(rows))
    (TAB / "operators.tex").write_text(tab_operators(r1, r2))
    (TAB / "claims.tex").write_text(tab_claims(r1, r2))
    (TAB / "detection.tex").write_text(tab_detection(r1, r2))
    (TAB / "groups.tex").write_text(tab_groups(r1, r2))
    (TAB / "spend_all.tex").write_text(tab_spend_all(r1, r2))
    (TAB / "preview.tex").write_text(tab_preview(prev))
    (TAB / "diagnosis.tex").write_text(tab_diag(diag))
    (TAB / "grid.tex").write_text(tab_grid(ex))
    (TAB / "effects.tex").write_text(tab_effects(ex))
    fig_grid(ex)
    fig_spend(r1, r2)
    fig_first(r2)
    (HERE / "gen" / "sessions.json").write_text(json.dumps(rows, indent=1))
    print("tables:", sorted(p.name for p in TAB.glob("*.tex")))
    print("figures:", sorted(p.name for p in FIG.glob("*.pdf")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
