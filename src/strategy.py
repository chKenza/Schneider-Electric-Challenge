"""Problem 2, Step 9: roadmap, win conditions, triggers and KPIs.

Turns the Step 4 TCO model (src/tco.py) and the Step 7 price window
(src/value_pricing.py) into the numbers the roadmap rests on. It reuses their
functions and changes none of their settings.

  win_conditions   per segment: the AirSeT extra unit cost below which a price
                   works for both sides, and the carbon price that would open
                   the window if the extra cost stays at the placeholder
  window_opening   the year each segment's window opens if AirSeT's extra cost
                   falls with volume (illustrative paths, see COST_PATHS)
  triggers         thresholds to watch, from Problem 1 (raw-material outlook)
                   and from the TCO model (carbon price, premium)
  co2_avoided      t CO2e avoided per AirSeT unit sold, by accounting view (KPI)

All prices in EUR; "points" and "%" are of the RM6 selling price (EUR 8,740).

Run from the repo root:
    uv run python -m src.strategy
    uv run python -m src.strategy_plots
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from src import tco
from src import value_pricing as vp
from src.market_evidence import ROOT, MarketEvidence

TABLE_DIR = ROOT / "report" / "problem2" / "04_tables"
P1_OUTLOOK = ROOT / "report" / "problem1" / "step9_tables" / "outlook_2027.csv"
P1_BOM = ROOT / "report" / "problem1" / "step8_tables" / "bom_index_and_margin_points.csv"

YEARS = [2027, 2028, 2029, 2030]
ENTRY_GIVE_PTS = 1.0     # margin Schneider might give up with a lead customer (Step 7 7.6)

# AirSeT's extra unit cost vs RM6 (% of RM6 price), 2027 -> 2030, linear in between.
# Start = the Step 7 placeholder (10 %). End points: the UK review expects the
# SF6-free premium to fall from 15-30 % to 5-10 % at scale (E166); we assume the
# extra cost falls in the same proportion. Illustrative, not a forecast.
COST_PATHS = {
    "no volume gain": (10.0, 10.0),
    "slow (UK review, top of range)": (10.0, 7.5),
    "at scale (UK review, bottom of range)": (10.0, 5.0),
}
BASE_PATH = "at scale (UK review, bottom of range)"

# Step 7 segments plus the two "what if" variants the Step 7 report discusses.
VARIANTS = {
    "Gulf data centres, if they count the whole fill": ("Gulf data centres", {"view": "whole_fill"}),
    "Australia colocation, without SF6 upkeep": ("Australia colocation", {"sf6_admin_eur_yr": 0.0}),
}


def segments(p2: MarketEvidence) -> dict[str, tuple[tco.Inputs, str]]:
    """Segment -> (TCO inputs, carbon view): the Step 7 segments and their variants."""
    out = {seg: (vp.segment_inputs(p2, seg), s["view"]) for seg, s in vp.SEGMENTS.items()}
    for name, (base, change) in VARIANTS.items():
        x, view = out[base]
        view = change.get("view", view)
        x = replace(x, **{k: v for k, v in change.items() if k != "view"})
        out[name] = (x, view)
    return out


def max_extra_cost_pct(x: tco.Inputs, view: str, give_pts: float = vp.MARGIN_GIVE_PTS) -> float:
    """AirSeT extra unit cost (% of RM6 price) below which a premium works for both sides.
    Window open <=> ceiling >= floor = extra cost + risk gap - give."""
    return vp.price_ceiling_pct(x, view) - vp.risk_gap_pts(x.rm6_price) + give_pts


def carbon_to_open(x: tco.Inputs, view: str, extra_cost_pct: float) -> float:
    """Carbon price (EUR/t) at which the customer accepts the Schneider floor premium."""
    floor = vp.price_floor_pct(extra_cost_pct, x.rm6_price)
    return tco.break_even_carbon(replace(x, premium_pct=max(floor, 0.0)), view)


def win_conditions(p2: MarketEvidence) -> pd.DataFrame:
    today = p2.param("price_premium_pct", "base")
    rows = []
    for seg, (x, view) in segments(p2).items():
        rows.append({
            "segment": seg, "carbon_view": view, "carbon_price_eur_t": x.carbon_price,
            "ceiling_pct": vp.price_ceiling_pct(x, view),
            "max_extra_cost_pct": max_extra_cost_pct(x, view),
            "max_extra_cost_pct_with_entry_give": max_extra_cost_pct(x, view, ENTRY_GIVE_PTS),
            "window_open_at_placeholder": max_extra_cost_pct(x, view) >= vp.EXTRA_COST_BASE,
            "carbon_to_open_at_placeholder_eur_t": carbon_to_open(x, view, vp.EXTRA_COST_BASE),
            "carbon_for_todays_premium_eur_t":
                tco.break_even_carbon(replace(x, premium_pct=today), view),
        })
    return pd.DataFrame(rows)


def cost_path(name: str) -> pd.Series:
    start, end = COST_PATHS[name]
    return pd.Series(np.linspace(start, end, len(YEARS)), index=YEARS)


def window_opening(p2: MarketEvidence) -> pd.DataFrame:
    """First year the window opens per segment and cost path (None = not by 2030)."""
    w = win_conditions(p2).set_index("segment")
    rows = []
    for path in COST_PATHS:
        c = cost_path(path)
        for seg, r in w.iterrows():
            opens = c[c <= r.max_extra_cost_pct + 1e-9]
            opens_give = c[c <= r.max_extra_cost_pct_with_entry_give + 1e-9]
            rows.append({
                "segment": seg, "cost_path": path,
                "max_extra_cost_pct": r.max_extra_cost_pct,
                "opens": int(opens.index[0]) if len(opens) else None,
                "opens_with_entry_give": int(opens_give.index[0]) if len(opens_give) else None,
            })
    df = pd.DataFrame(rows)
    return df.astype({"opens": "Int64", "opens_with_entry_give": "Int64"})


def triggers(p2: MarketEvidence) -> pd.DataFrame:
    """Quantified accelerate / pause triggers. Each row says what to watch,
    the threshold, where it comes from, and what to do."""
    o = pd.read_csv(P1_OUTLOOK)
    gap9 = o[(o.case == "RM6 − AirSeT gap change") & (o.horizon_m == 9)].iloc[0]
    air9 = o[(o.case == vp.AIRSET_CASE) & (o.horizon_m == 9)].iloc[0]
    rm6_9 = o[(o.case == "RM6") & (o.horizon_m == 9)].iloc[0]
    w = win_conditions(p2).set_index("segment")
    js = w.loc["Johor-Singapore data centres"]
    x0 = tco.inputs(p2, "base")
    rows = [
        ("AirSeT raw-material cost (Problem 1 monthly run)",
         f"> EUR {air9.cost_p90_eur:.0f} by Jun 2027 (9-month P90)",
         "P1 Step 9 outlook_2027.csv",
         "Copper/steel/stainless clause triggers; re-quote fixed-price offers; check the price floor"),
        ("RM6 raw-material cost",
         f"> EUR {rm6_9.cost_p90_eur:.0f} by Jun 2027 (9-month P90; a floor, copper tail)",
         "P1 Step 9 outlook_2027.csv",
         "Copper clause on RM6 quotes; the RM6 - AirSeT gap narrows: use it in tenders"),
        ("RM6 - AirSeT raw-material gap",
         f"change > +EUR {gap9.cost_p90_eur:.0f} (P90) or < EUR {gap9.cost_p10_eur:.0f} (P10)",
         "P1 Step 9 outlook_2027.csv",
         "Above: mention convergence (still < 3 % of the premium). Below: AirSeT relatively "
         "dearer, re-check the floor"),
        ("AirSeT extra unit cost vs RM6 (Schneider internal)",
         f"< {js.max_extra_cost_pct:.1f} % (< {js.max_extra_cost_pct_with_entry_give:.1f} % "
         f"with a {ENTRY_GIVE_PTS:.0f}-point entry give)",
         "win_conditions.csv",
         "Open Johor-Singapore at the TCO-based price (Phase 2)"),
        ("Carbon price a target customer applies to SF6",
         f">= EUR {js.carbon_to_open_at_placeholder_eur_t:.0f}/t (whole fill)",
         "win_conditions.csv",
         "Johor-Singapore window opens at today's cost; scale the ESG pitch"),
        ("Carbon price that justifies today's 22 % premium",
         f">= EUR {tco.break_even_carbon(x0, 'whole_fill'):.0f}/t (whole fill), "
         f"{tco.break_even_carbon(x0, 'lifecycle'):.0f}/t (lifecycle)",
         "src/tco.py, 02 4.4",
         "Move ESG-led segments from TCO-based price to list price"),
        ("SF6 rule in a target market", "status 0/1 -> 2 or 3 (phase-out adopted or ban)",
         "market_evidence/regulation.csv", "Accelerate: future-proof pitch, list price, more sales capacity"),
        ("SF6-free rival price (Eaton, Chinese dry-air RMUs)",
         "below AirSeT's TCO-based price in a target market", "competitors.csv",
         "Defend with bundle (take-back, monitoring) before cutting price; pause if below floor"),
    ]
    return pd.DataFrame(rows, columns=["watch", "threshold", "source", "action"])


def co2_avoided(p2: MarketEvidence) -> pd.DataFrame:
    """t CO2e avoided per AirSeT unit sold instead of an RM6, by accounting view."""
    rows = []
    for sc in ["pessimistic", "base", "optimistic"]:
        x = tco.inputs(p2, sc)
        for view in ["leaks", "lifecycle", "whole_fill"]:
            rows.append({"scenario": sc, "view": view, "t_co2e_per_unit": tco.carbon_t(x, view)[0]})
    return pd.DataFrame(rows)


def main() -> None:
    p2 = MarketEvidence.load()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    tables = {"win_conditions.csv": win_conditions(p2),
              "window_opening.csv": window_opening(p2),
              "triggers.csv": triggers(p2),
              "co2_avoided.csv": co2_avoided(p2)}
    for name, df in tables.items():
        df.round(2).to_csv(TABLE_DIR / name, index=False)
        with pd.option_context("display.width", 200, "display.max_colwidth", 70):
            print(f"\n=== {name} ===\n{df.round(1).to_string(index=False)}")
    print(f"\nTables written to {TABLE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
