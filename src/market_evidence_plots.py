"""Problem 2 charts built from the market evidence data.

    uv run python src/market_evidence_plots.py     # writes plots/problem2/

01_carbon_prices_vs_break_even.png
    Every sourced carbon price on one log axis (compliance schemes, company
    internal prices, the social cost of carbon) against the carbon prices at
    which AirSeT's upfront premium pays back. The key TCO chart.
02_regulation_and_market.png
    Step 2 landscape: data-centre capacity of every jurisdiction (log scale),
    coloured by how SF6 is regulated there, with inventory growth.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

try:
    from src.market_evidence import ROOT, MarketEvidence
except ModuleNotFoundError:  # run as a script
    from market_evidence import ROOT, MarketEvidence

OUT = ROOT / "plots" / "problem2"
# validated default categorical palette, slots 1-3 in fixed order (dataviz skill)
COLORS = {"Compliance scheme": "#2a78d6", "Company internal price": "#eb6834",
          "Social cost of carbon": "#1baf7a"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#6b6a64", "#e6e5e0", "#fcfcfb"
SCHEME = {"EU": "EU ETS", "GB": "UK ETS", "US-CA": "California cap-and-invest",
          "CA": "Canada OBPS", "CN": "China national ETS", "KR": "Korea ETS",
          "SG": "Singapore carbon tax", "JP": "Japan carbon tax", "AU": "Australia Safeguard",
          "CL": "Chile carbon tax", "MX": "Mexico carbon tax", "US-NY": "RGGI (incl. New York)",
          "US-MA": "Massachusetts ETS"}


def carbon_prices(p2: MarketEvidence) -> pd.DataFrame:
    """All sourced carbon prices (EUR / t CO2e), with whether each one reaches
    the SF6 in a data centre's switchgear."""
    rows = []
    reg = p2.regulation.dropna(subset=["compliance_carbon_price_eur_t"])
    for cid, r in reg.iterrows():
        rows.append((SCHEME.get(cid, cid), float(r.compliance_carbon_price_eur_t),
                     "Compliance scheme", r.sf6_pricing == "priced"))
    cus = p2.customers.dropna(subset=["internal_carbon_price_eur_t"])
    for _, c in cus.iterrows():
        rows.append((f"{c.company} internal fee", float(c.internal_carbon_price_eur_t),
                     "Company internal price", True))       # applies to its own Scope 1
    rows.append(("CDP median internal price", p2.param("internal_carbon_price_eur_t", "base"),
                 "Company internal price", True))
    rows.append(("US EPA social cost of CO2", p2.param("internal_carbon_price_eur_t", "optimistic"),
                 "Social cost of carbon", False))
    return pd.DataFrame(rows, columns=["name", "eur_t", "group", "reaches_dc"]).sort_values("eur_t")


def break_evens(p2: MarketEvidence, scenario: str = "base") -> dict[str, float]:
    """Carbon price at which the upfront premium pays back, three ways."""
    fill_t = p2.param("sf6_kg_per_unit", scenario) * p2.param("gwp_sf6", scenario) / 1000
    leaked = (fill_t * p2.param("leak_rate_pct_per_year", scenario) / 100
              * p2.param("asset_life_years", scenario))
    premium = p2.price_premium_eur(scenario)
    return {
        "Whole SF6 fill valued": premium / fill_t,
        "Lifetime model\n(leaks + end of life, discounted)": p2.break_even_carbon_price("JP", scenario),
        "Leaks only": premium / leaked,
    }


def carbon_price_chart(p2: MarketEvidence, out: Path = OUT) -> Path:
    prices, be = carbon_prices(p2), break_evens(p2)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(10, 7.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    n = len(prices)
    for i, (_, r) in enumerate(prices.iterrows()):
        c = COLORS[r.group]
        ax.axhline(i, color=GRID, lw=0.8, zorder=1)
        ax.scatter(r.eur_t, i, s=58, zorder=3, color=c if r.reaches_dc else SURFACE,
                   edgecolor=c, linewidth=2)
    fmt = lambda v: f"€{v:,.0f}" if v >= 10 else f"€{v:.1f}"
    ax.set_yticks(range(n), [f"{nm}   {fmt(v)}" for nm, v in zip(prices.name, prices.eur_t, strict=True)],
                  color=INK)
    # break-even lines; short labels stacked above the dots, the last one to the right
    ordered = sorted(be.items(), key=lambda kv: kv[1])
    for k, (label, v) in enumerate(ordered):
        ax.axvline(v, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=2)
        right = k == len(ordered) - 1
        ax.text(v * (1.08 if right else 1 / 1.08), n + 0.7 + 1.4 * k, f"{label}\n€{v:,.0f}/t",
                ha="left" if right else "right", va="center", fontsize=8, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(1, 30000)
    ax.set_ylim(-0.7, n + 0.6 + 1.4 * len(be))
    ax.set_xlabel("Carbon price, € per tonne CO₂e (log scale)", color=INK)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"€{v:,.0f}"))
    ax.grid(False)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    handles = [Line2D([], [], marker="o", ls="", color=c, markersize=7, label=g)
               for g, c in COLORS.items()]
    handles += [Line2D([], [], marker="o", ls="", markerfacecolor=SURFACE, markeredgecolor=MUTED,
                       markeredgewidth=2, markersize=7, label="Hollow: does not reach a data centre's SF6"),
                Line2D([], [], color=INK, lw=1.2, ls=(0, (4, 3)), label="Price at which AirSeT's premium pays back")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.09), ncol=3,
              frameon=False, fontsize=8)
    premium = p2.price_premium_eur("base")
    fig.suptitle("Real carbon prices reach AirSeT's pay-back point only if the whole SF6 fill is valued;\n"
                 "on leaks alone, none comes close", x=0.02, ha="left", fontsize=12, color=INK)
    fig.text(0.02, 0.885, f"Base case: €{premium:,.0f} premium (+{p2.param('price_premium_pct', 'base'):.0f} % on RM6, the 2025 gap), "
             "1.5 kg SF6, GWP 23,500, 0.2 %/yr leaks over 40 years. Compliance prices: World Bank, Apr 2024\n"
             "(EU, Korea, Singapore: 2026). Filled dot = the price applies to SF6 in a data centre's switchgear.",
             fontsize=8, color=MUTED, va="top")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "01_carbon_prices_vs_break_even.png"
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


# regulation groups in fixed order (validated categorical slots 1-5)
GROUP_STYLE = {
    "nothing_forces": ("Nothing forces it (status 0)", "#2a78d6"),
    "leaks_cost_money": ("SF6 priced for large operators", "#eb6834"),
    "sf6_rules_apply": ("SF6 rules short of a ban apply", "#1baf7a"),
    "regulation_coming": ("Phase-out adopted or under discussion", "#eda100"),
    "reference": ("Ban in force: reference, not voluntary", "#e87ba4"),
}


def regulation_market_chart(p2: MarketEvidence, out: Path = OUT) -> Path:
    land = p2.landscape().drop(index="US-FED")          # US-FED overlaps the state rows
    land = land.dropna(subset=["dc_mw"])
    order = list(GROUP_STYLE)
    land["g"] = land.group.map(order.index)
    land = land.sort_values(["g", "dc_mw"], ascending=[False, True])
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(10, 8.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for i, (_, r) in enumerate(land.iterrows()):
        color = GROUP_STYLE[r.group][1]
        ax.axhline(i, color=GRID, lw=0.8, zorder=1)
        ax.scatter(r.dc_mw, i, s=62, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        g = "" if pd.isna(r.dc_growth_pct) else f"  +{r.dc_growth_pct:.0f} %/yr"
        ax.text(r.dc_mw * 1.15, i, f"{r.dc_mw:,.0f} MW{g}", va="center", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(land)), [f"{c} ({rg})" for c, rg in zip(land.country, land.region, strict=True)],
                  color=INK)
    ax.set_xscale("log")
    ax.set_xlim(150, 120000)
    ax.set_ylim(-0.7, len(land) - 0.3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Data-centre capacity, operational + under construction, MW (log scale)", color=INK)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    handles = [Line2D([], [], marker="o", ls="", color=c, markersize=8, label=lab)
               for lab, c in GROUP_STYLE.values()]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.42, -0.08), ncol=2, frameon=False, fontsize=8)
    fig.suptitle("The largest data-centre markets have no SF6 rule: the switch there has to be won, not forced",
                 x=0.02, ha="left", fontsize=12, color=INK)
    fig.text(0.02, 0.945, "Capacity: datacentres.com Nov 2026 (CBRE, Cushman & Wakefield); China: SemiAnalysis; Saudi Arabia: MCIT.\n"
             "Growth: CBRE inventory growth (regional figure where no country figure). US states shown separately "
             "(the US total, 30,500 MW,\nis not repeated); Massachusetts has no tracked market.", fontsize=8, color=MUTED, va="top")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "02_regulation_and_market.png"
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


if __name__ == "__main__":
    p2 = MarketEvidence.load()
    print(carbon_price_chart(p2))
    print(regulation_market_chart(p2))
