"""Problem 2, Step 7: how to price RM AirSeT in each target segment.

For each segment and pricing option, two checks:
  customer   - is AirSeT's lifetime cost (TCO) lower than RM6's?            (src/tco.py)
  Schneider  - is the margin kept, once raw-material risk is covered?         (Problem 1 Step 9)

Price window per segment:
  floor   = lowest premium that keeps Schneider's margin
  ceiling = highest premium at which the customer still saves over the life

All amounts are EUR per unit; "points" = % of the RM6 selling price (EUR 8,740).

Run from the repo root:
    uv run python -m src.value_pricing
"""
from __future__ import annotations

import pandas as pd

from src import tco
from src.market_evidence import ROOT, MarketEvidence

TABLE_DIR = ROOT / "report" / "problem2" / "03_tables"
QUOTE_RULE = ROOT / "report" / "problem1" / "step9_tables" / "quote_rule.csv"

# Target segments from Step 3 (01_market_and_regulation.md 3.4).
SEGMENTS = {
    "Johor-Singapore data centres": dict(country="MY", view="whole_fill", sf6_rules=False),
    "Gulf data centres":            dict(country="SA", view="lifecycle",  sf6_rules=False),
    "Australia colocation":         dict(country="AU", view="whole_fill", sf6_rules=True),
    "Australia utilities":          dict(country="AU", view="lifecycle",  sf6_rules=True),
}

# Problem 1 Step 9 settings for the raw-material risk on the offer
HORIZON_M = 9            
TOLERATED_PTS = 0.5
CONFIDENCE = 0.9
STEEL = "PPI"
AIRSET_CASE = "AirSeT epoxy low, nickel check"
P1_PRICE = {"RM6": 8740.0, "AirSeT": 8740.0 * 1.2}   # same prices as src/pricing.py

# Schneider-side assumptions:
EXTRA_COST_PCT = [0, 5, 10, 15, 20]   # AirSeT's extra unit cost vs RM6, % of RM6 price
EXTRA_COST_BASE = 10                  # placeholder until the organisers' cost overview
MARGIN_GIVE_PTS = 0.0                 # margin points Schneider accepts to give up vs RM6


def raw_material_risk_eur() -> dict:
    """Uplift the Step 9 quote rule charges to cover raw-material risk, EUR per unit."""
    q = pd.read_csv(QUOTE_RULE)
    q = q[(q.steel == STEEL) & (q.horizon_m == HORIZON_M)
          & (q.tolerated_erosion_pts == TOLERATED_PTS)
          & (q.confidence == CONFIDENCE)].set_index("case")
    return {"RM6": q.loc["RM6", "uplift_charged_pts"] / 100 * P1_PRICE["RM6"],
            "AirSeT": q.loc[AIRSET_CASE, "uplift_charged_pts"] / 100 * P1_PRICE["AirSeT"]}


def segment_inputs(p2: MarketEvidence, segment: str, scenario: str = "base") -> tco.Inputs:
    """TCO inputs for one segment: the market's carbon price, plus SF6 upkeep where rules apply."""
    s = SEGMENTS[segment]
    extra = {}
    if s["sf6_rules"]:
        extra["sf6_admin_eur_yr"] = p2.param("sf6_admin_cost_eur_per_year", "optimistic")
    return tco.inputs(p2, scenario, country_id=s["country"], **extra)


def risk_gap_pts(rm6_price: float) -> float:
    """AirSeT's raw-material risk minus RM6's, in points. Negative = AirSeT is less risky."""
    r = raw_material_risk_eur()
    return (r["AirSeT"] - r["RM6"]) / rm6_price * 100


def margin_vs_rm6_pts(premium_pct: float, extra_cost_pct: float, rm6_price: float) -> float:
    """Schneider's margin on AirSeT minus its margin on RM6, in points of the RM6 price."""
    return premium_pct - extra_cost_pct - risk_gap_pts(rm6_price)


def price_floor_pct(extra_cost_pct: float, rm6_price: float) -> float:
    """Lowest premium that keeps AirSeT's margin within MARGIN_GIVE_PTS of RM6's."""
    return extra_cost_pct + risk_gap_pts(rm6_price) - MARGIN_GIVE_PTS


def price_ceiling_pct(x: tco.Inputs, view: str) -> float:
    """Highest premium at which the customer's lifetime cost is still lower with AirSeT."""
    return max(0.0, tco.max_premium_pct(x, view))


def pricing_options(p2: MarketEvidence, extra_cost_pct: float = EXTRA_COST_BASE) -> pd.DataFrame:
    """Each pricing option in each segment: customer check and Schneider check."""
    rows = []
    for seg, s in SEGMENTS.items():
        x = segment_inputs(p2, seg)
        options = {
            "price parity": 0.0,
            "TCO-based price": price_ceiling_pct(x, s["view"]),
            "green premium (EU stated WTP, E173)": 20.0,
            "today's list premium": p2.param("price_premium_pct", "base"),
        }
        for name, prem in options.items():
            gap = tco.tco_gap(tco.replace(x, premium_pct=prem), s["view"])
            margin = margin_vs_rm6_pts(prem, extra_cost_pct, x.rm6_price)
            rows.append({
                "segment": seg, "option": name, "premium_pct": prem,
                "premium_eur": prem / 100 * x.rm6_price,
                "customer_tco_gap_eur": gap,          # negative = customer saves
                "customer_saves": gap <= 0,
                "margin_vs_rm6_pts": margin,
                "margin_kept": margin >= -MARGIN_GIVE_PTS,
            })
    return pd.DataFrame(rows)


def price_window(p2: MarketEvidence) -> pd.DataFrame:
    """Floor and ceiling of the premium per segment, for each extra-cost assumption."""
    rows = []
    for seg, s in SEGMENTS.items():
        x = segment_inputs(p2, seg)
        ceiling = price_ceiling_pct(x, s["view"])
        for c in EXTRA_COST_PCT:
            floor = price_floor_pct(c, x.rm6_price)
            rows.append({
                "segment": seg, "carbon_view": s["view"], "carbon_price_eur_t": x.carbon_price,
                "extra_cost_pct": c, "floor_pct": floor, "ceiling_pct": ceiling,
                "window_open": ceiling >= floor,
                "recommendation": recommend(floor, ceiling),
            })
    return pd.DataFrame(rows)


def recommend(floor: float, ceiling: float) -> str:
    if ceiling >= floor:
        return f"TCO-based price: premium {max(floor, 0):.1f}-{ceiling:.1f} %"
    return f"no price works on cost alone: {floor - ceiling:.1f} pts short -> bundle / volume / ESG"


def main() -> None:
    p2 = MarketEvidence.load()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    risk = raw_material_risk_eur()
    print(f"Raw-material risk at {HORIZON_M} m (EUR per unit): "
          f"RM6 {risk['RM6']:.0f}, AirSeT {risk['AirSeT']:.0f}")
    tables = {"pricing_options.csv": pricing_options(p2),
              "price_window.csv": price_window(p2)}
    for name, df in tables.items():
        df.round(2).to_csv(TABLE_DIR / name, index=False)
        print(f"\n=== {name} ===\n{df.round(1).to_string(index=False)}")
    print(f"\nTables written to {TABLE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()