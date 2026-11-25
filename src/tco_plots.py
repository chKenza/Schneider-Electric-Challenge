"""Problem 2, Steps 4-5 charts (plots/problem2/04-09).

    uv run python -m src.tco_plots

04_upfront_gap.png          AirSeT price premium by rival vs the raw-material cost difference
05_tco_gap_vs_carbon.png    TCO gap vs carbon price, one line per accounting view (break-even chart)
06_tco_tornado.png          Which input moves the TCO gap most (lifecycle and whole-fill views)
07_premium_carbon_map.png   Whole-fill view: TCO gap over price premium x carbon price
08_rm_gap_outlook.png       Problem 1 forecast: RM6 vs AirSeT raw-material cost to Jun 2027
09_price_vs_rm_gap.png      2017-2026: the price premium fell, the raw-material gap barely moved
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from src import tco
from src.market_evidence import MarketEvidence
from src.plotting import DIVERGING, GRID, INK, INK2, MUTED, SERIES, _save, set_style

OUT = tco.ROOT / "plots" / "problem2"
VIEW_COLORS = dict(zip(tco.VIEWS, SERIES))                  # fixed order: leaks, lifecycle, whole fill
PRODUCT_COLORS = {"RM6": SERIES[0], "AirSeT": SERIES[1]}


def _markers(p2: MarketEvidence) -> list[tuple[str, float]]:
    eu = float(p2.regulation.loc["EU", "compliance_carbon_price_eur_t"])
    return [("Microsoft", p2.param("internal_carbon_price_eur_t", "pessimistic")),
            ("CDP median", p2.param("internal_carbon_price_eur_t", "base")),
            ("EU ETS*", eu),
            ("US EPA SCC", p2.param("internal_carbon_price_eur_t", "optimistic"))]


def upfront_gap(p2: MarketEvidence):
    u = tco.upfront_gap(p2)
    prem = u.drop_duplicates("scenario").set_index("rival")["premium_eur"]
    gap = float(u.rm_cost_gap_eur.iloc[0])
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    labels = [f"Premium vs {r}" for r in prem.index] + ["Raw-material cost difference\n(AirSeT − RM6)"]
    y = np.arange(len(labels))[::-1]
    ax.barh(y[:3], prem.values, height=0.5, color=SERIES[1])
    for yi, v in zip(y[:3], prem.values):
        ax.text(v + 40, yi, f"€{v:,.0f}", va="center", color=INK, fontsize=8)
    ax.barh(y[3], gap, height=0.5, color=SERIES[0])
    ax.text(max(gap, 0) + 40, y[3], f"{gap:+,.0f} € (BOM v1)", va="center", color=INK, fontsize=8)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(y, labels)
    ax.set_xlim(-400, 3100)
    ax.set_xlabel("€ per unit (2025 price benchmark P50; raw materials at Sep 2026)")
    ax.set_title("Against RM6, raw materials explain about a tenth of AirSeT's premium", loc="left")
    ax.grid(axis="y", visible=False)
    return _save(fig, OUT, "04_upfront_gap")


def tco_vs_carbon(p2: MarketEvidence):
    sweep = tco.carbon_sweep(p2)
    base = tco.inputs(p2, "base")
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    for v, label in tco.VIEWS.items():
        be = tco.break_even_carbon(base, v)
        ax.plot(sweep.index, sweep[v], color=VIEW_COLORS[v], lw=2,
                label=f"{label}: break-even €{be:,.0f}/t")
    ax.axhline(0, color=INK, lw=0.9)
    ax.text(100, -150, "below 0: AirSeT cheaper over its life", fontsize=8, color=INK2, va="top")
    for name, c in _markers(p2):
        ax.axvline(c, color=MUTED, lw=0.8, ls=(0, (3, 3)))
        ax.text(c + 2, -6100, name, rotation=90, fontsize=7, color=INK2, va="bottom", ha="left")
    ax.set_ylim(-6200, 2200)
    ax.set_xlim(0, 250)
    ax.set_xlabel("Carbon price the customer applies to SF6 (€ / t CO₂e)")
    ax.set_ylabel("TCO(AirSeT) − TCO(RM6), € per unit")
    ax.set_title("AirSeT wins on lifetime cost only if the customer values the whole SF6 fill", loc="left")
    ax.legend(loc="center right", title="How the SF6 is counted", title_fontsize=8)
    fig.text(0.0, -0.03, "Base scenario: premium €1,921 (+22 %), 1.5 kg SF6, 0.2 %/yr leaks, 40-year life, 7 % discount rate. "
             "Leaks and end-of-life lines are discounted; the whole fill is valued at purchase.\n*EU ETS shown for reference: it does not apply to a data centre outside the EU.",
             fontsize=7, color=MUTED)
    return _save(fig, OUT, "05_tco_gap_vs_carbon")


def tornado(p2: MarketEvidence):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=False)
    for ax, view in zip(axes, ("lifecycle", "whole_fill")):
        t = tco.tornado(p2, view).iloc[::-1]
        base = t.gap_base.iloc[0]
        y = np.arange(len(t))
        for yi, (_, r) in zip(y, t.iterrows()):
            for s, col in (("pessimistic", SERIES[1]), ("optimistic", SERIES[0])):
                ax.barh(yi, r[f"gap_{s}"] - base, left=base, height=0.6, color=col,
                        label={"pessimistic": "Input at its pessimistic value",
                               "optimistic": "Input at its optimistic value"}[s] if yi == y[-1] else None)
        ax.axvline(base, color=INK, lw=0.9)
        ax.axvline(0, color=MUTED, lw=0.8, ls=(0, (3, 3)))
        ax.set_yticks(y, t.label)
        ax.set_title(f"{tco.VIEWS[view]}: base gap €{base:,.0f}", loc="left")
        ax.set_xlabel("TCO(AirSeT) − TCO(RM6), € per unit")
        ax.grid(axis="y", visible=False)
    axes[0].legend(loc="lower right", fontsize=7)
    fig.suptitle("The premium and the carbon price decide the gap; leak and life assumptions barely matter", x=0.0, ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    fig.text(0.0, -0.04, "One input at a time from its pessimistic to its optimistic value (assumptions.csv), the others at base; "
             "carbon at the €22/t CDP median. Dashed line: TCO parity.", fontsize=7, color=MUTED)
    fig.tight_layout()
    return _save(fig, OUT, "06_tco_tornado")


def premium_carbon_map(p2: MarketEvidence):
    g = tco.premium_carbon_grid(p2, "whole_fill", premiums=np.arange(0, 31, 1),
                                prices=np.arange(0, 205, 5))
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    lim = np.abs(g.values).max()
    m = ax.pcolormesh(g.columns, g.index, g.values, cmap=DIVERGING,
                      norm=TwoSlopeNorm(0, -lim, lim), shading="nearest")
    cs = ax.contour(g.columns, g.index, g.values, levels=[0], colors=INK, linewidths=1.4)
    ax.clabel(cs, fmt={0: "TCO parity"}, fontsize=8)
    for name, c in _markers(p2):
        ax.axvline(c, color=INK2, lw=0.7, ls=(0, (3, 3)))
        ax.text(c + 1.5, 8, name, rotation=90, fontsize=7, color=INK, va="bottom")
    for pm, lab in ((3, "premium vs Siemens"), (21.98, "vs RM6"), (27, "vs SF6 brand average")):
        ax.axhline(pm, color=INK2, lw=0.7)
        ax.text(198, pm + 0.3, lab, fontsize=7, color=INK, va="bottom", ha="right")
    ax.grid(False)
    cb = fig.colorbar(m, ax=ax, pad=0.12)
    cb.set_label("TCO(AirSeT) − TCO(RM6), €  (blue: AirSeT cheaper)", fontsize=8)
    ax.set_xlabel("Carbon price on the whole SF6 fill (€ / t CO₂e)")
    ax.set_ylabel("AirSeT price premium (% of RM6 price)")
    ax.set_title("Whole-fill view: at €22/t AirSeT pays back only below a ~9 % premium", loc="left")
    return _save(fig, OUT, "07_premium_carbon_map")


def rm_gap_outlook(p2: MarketEvidence):
    o = tco.bom_outlook()
    g = tco.gap_outlook(p2)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [1.3, 1]})
    for case, col, ls in (("RM6", PRODUCT_COLORS["RM6"], "-"),
                          ("AirSeT, nickel check", PRODUCT_COLORS["AirSeT"], "-")):
        d = o[o.case == case].sort_values("horizon_m")
        h = np.r_[0, d.horizon_m]
        t0 = d.cost_today_eur.iloc[0]
        a1.fill_between(h, np.r_[t0, d.cost_p10_eur], np.r_[t0, d.cost_p90_eur], color=col, alpha=0.15, lw=0)
        a1.plot(h, np.r_[t0, d.cost_p50_eur], color=col, lw=2, ls=ls)
        a1.text(9.2, d.cost_p50_eur.iloc[-1], case.replace(", nickel check", ""), fontsize=8, color=INK, va="center")
    a1.set_xticks([0, 3, 6, 9], ["Sep 2026", "Dec 2026", "Mar 2027", "Jun 2027"])
    a1.set_xlim(0, 13.5)
    a1.set_ylabel("Raw-material cost, € per unit")
    a1.set_title("Forecast P50 and P10–P90 band (Problem 1, Step 8)", loc="left")

    x = np.arange(len(g))
    a2.bar(x, g.share_of_premium_p50_pct, width=0.45, color=SERIES[2], label="P50")
    a2.errorbar(x, g.share_of_premium_p50_pct,
                yerr=[g.share_of_premium_p50_pct - g.share_of_premium_p10_pct,
                      g.share_of_premium_p90_pct - g.share_of_premium_p50_pct],
                fmt="none", ecolor=INK2, capsize=4, lw=1, label="P10–P90")
    a2.axhline(0, color=INK, lw=0.8)
    a2.set_xticks(x, [f"{h} months\nP(RM6 rises more)\n{p:.0%}" for h, p in zip(g.horizon_m, g.p_rm6_rises_more)])
    a2.set_ylabel("Gap closed, % of the €1,921 premium")
    a2.set_title("How much of the premium the RM forecast closes", loc="left")
    a2.legend(loc="upper left", fontsize=7)
    a2.grid(axis="x", visible=False)
    fig.suptitle("The raw-material forecast barely moves the cost gap to mid-2027", x=0.0, ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    fig.text(0.0, -0.04, "Right: change in RM6 − AirSeT raw-material cost from the joint simulation "
             "(RM6 vs AirSeT, BOM v1, stainless priced through nickel). Positive = the gap narrows for AirSeT.",
             fontsize=7, color=MUTED)
    fig.tight_layout()
    return _save(fig, OUT, "08_rm_gap_outlook")


def price_vs_rm_gap():
    d = tco.price_vs_rm_gap()
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    ax.plot(d.year, d.premium_eur, color=SERIES[1], lw=2, marker="o", ms=5,
            label="Selling-price premium (Eaton SF6-free − Schneider RM6, P50)")
    r = d.dropna(subset=["rm_gap_eur"])
    ax.plot(r.year, -r.rm_gap_eur, color=SERIES[0], lw=2, marker="o", ms=5,
            label="Raw-material cost difference (AirSeT − RM6, BOM v1)")
    ax.axhline(0, color=INK, lw=0.8)
    ax.axvspan(2025.5, 2026.5, color=GRID, lw=0, zorder=0)
    ax.text(2025.6, 2600, "EU ban on\nnew SF6 ≤ 24 kV", fontsize=7, color=INK2, va="top")
    ax.set_ylabel("€ per unit")
    ax.set_xticks(d.year)
    ax.set_title("The price gap closed through regulation, not raw materials", loc="left")
    ax.legend(loc="lower left", fontsize=7)
    fig.text(0.0, -0.03, "Price benchmark is synthetic and EU-only; raw-material cost = fixed Sep 2026 recipe at "
             "each year's average prices (Problem 1, Step 2).", fontsize=7, color=MUTED)
    return _save(fig, OUT, "09_price_vs_rm_gap")


def main() -> None:
    set_style()
    p2 = MarketEvidence.load()
    for f in (lambda: upfront_gap(p2), lambda: tco_vs_carbon(p2), lambda: tornado(p2),
              lambda: premium_carbon_map(p2), lambda: rm_gap_outlook(p2), price_vs_rm_gap):
        fig = f()
        plt.close(fig)
    print(f"Wrote charts 04-09 to {OUT.relative_to(tco.ROOT)}")


if __name__ == "__main__":
    main()
