"""Problem 2, Steps 4-5: customer lifetime cost (TCO) of RM6 vs RM AirSeT, and
the raw-material cost-gap outlook from the Problem 1 forecast.

Run from the repo root:
    uv run python -m src.tco          # validate, print the key numbers, write report/problem2/02_tables/
    uv run python -m src.tco_plots    # charts 04-09 in plots/problem2/

Step 4 – TCO, from the customer's point of view
-----------------------------------------------
Every input comes from market_evidence/assumptions.csv (three scenarios, each
value sourced in evidence.csv), read through MarketEvidence. Only the cost
lines that DIFFER between the two products are modelled; lines that are equal
(cables, civil works, protection relays, ...) cancel out of the gap. So the
"TCO" below is a differential TCO, EUR per unit, present value at the
customer's discount rate:

    purchase       RM6 price; AirSeT = RM6 price x (1 + premium)
    installation   AirSeT - RM6 installation cost (0: same footprint, E171)
    maintenance    AirSeT - RM6 routine maintenance (0: both sealed for life, E167)
    sf6_upkeep     RM6 only: leak checks, gas readings, records (E169)
    eol_handling   RM6 only: SF6 recovery at end of life (E11, E12)
    regulation     RM6 only: cost a future rule imposes on an installed unit (0, E61)
    carbon         RM6 only: SF6 emissions x carbon price, by accounting view

Three ways the customer can count the SF6 (VIEWS):
    leaks       Scope 1 leaks over the life, discounted
    lifecycle   leaks + the gas released at end of life, discounted
                (the end-of-life release is on the fill left after the leaks)
    whole_fill  the whole SF6 fill valued at purchase, undiscounted: the unit
                is treated as a 35 t CO2e liability the day it is installed

TCO gap = TCO(AirSeT) - TCO(RM6): negative means AirSeT is cheaper over its life.

Step 5 – raw-material cost gap outlook
--------------------------------------
Reads the committed Problem 1 tables (Step 8 BOM index, Step 9 outlook) and the
local Step 2 outputs in Data/processed/ (cost breakdown, index history, prices).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

try:
    from src.market_evidence import ROOT, SCENARIOS, MarketEvidence
except ModuleNotFoundError:  # run as a script
    from market_evidence import ROOT, SCENARIOS, MarketEvidence

TABLE_DIR = ROOT / "report" / "problem2" / "02_tables"
P1_TABLES = ROOT / "report" / "problem1"
PROCESSED = ROOT / "Data" / "processed"

VIEWS = {
    "leaks": "Scope 1 leaks only",
    "lifecycle": "Leaks + end-of-life release",
    "whole_fill": "Whole fill as a liability",
}
LINES = ["purchase", "installation", "maintenance", "sf6_upkeep",
         "eol_handling", "regulation", "carbon"]

# Parameters the tornado swings (pessimistic <-> optimistic, others at base).
SENSITIVITY = [
    "price_premium_pct", "internal_carbon_price_eur_t", "sf6_kg_per_unit",
    "leak_rate_pct_per_year", "eol_release_share", "eol_recovery_cost_eur",
    "asset_life_years", "discount_rate_pct", "gwp_sf6", "sf6_admin_cost_eur_per_year",
]
LABELS = {
    "price_premium_pct": "AirSeT price premium",
    "internal_carbon_price_eur_t": "Carbon price",
    "sf6_kg_per_unit": "SF6 fill per unit",
    "leak_rate_pct_per_year": "Leak rate",
    "eol_release_share": "SF6 released at end of life",
    "eol_recovery_cost_eur": "End-of-life recovery cost",
    "asset_life_years": "Asset life",
    "discount_rate_pct": "Discount rate",
    "gwp_sf6": "GWP of SF6",
    "sf6_admin_cost_eur_per_year": "SF6 upkeep (checks, records)",
}


# ====================================================================== Step 4
@dataclass(frozen=True)
class Inputs:
    """All TCO inputs for one scenario (EUR, years, fractions)."""
    rm6_price: float
    premium_pct: float          # % of RM6 price
    sf6_kg: float
    gwp: float
    leak_pct: float             # %/yr of the initial fill
    life: float                 # years
    discount_pct: float         # %/yr
    eol_release_share: float    # share of the fill left at end of life that escapes
    eol_recovery_eur: float
    regulation_cost_eur: float
    regulation_prob: float
    install_delta_eur: float
    maintenance_delta_eur_yr: float
    sf6_admin_eur_yr: float
    carbon_price: float         # EUR / t CO2e

    @property
    def fill_t_co2e(self) -> float:
        return self.sf6_kg * self.gwp / 1000

    @property
    def premium_eur(self) -> float:
        return self.premium_pct / 100 * self.rm6_price

    def pv(self) -> tuple[float, float, float]:
        """(annuity factor over the life, discount factor at end of life, at mid-life)."""
        r, n = self.discount_pct / 100, self.life
        annuity = n if r == 0 else (1 - (1 + r) ** -n) / r
        return annuity, (1 + r) ** -n, (1 + r) ** -(n / 2)


def inputs(p2: MarketEvidence, scenario: str = "base", country_id: str | None = None,
           **overrides) -> Inputs:
    """Inputs for one scenario. With a country, the carbon price and regulation
    probability are that market's (MarketEvidence rules); otherwise the
    customer's internal carbon price and no regulation."""
    p = lambda n: p2.param(n, scenario)
    if country_id is None:
        cp, prob = p("internal_carbon_price_eur_t"), 0.0
    else:
        cp = p2.carbon_price(country_id, scenario)
        prob = p2.regulation_probability(country_id, scenario)
        prob = 0.0 if np.isnan(prob) else prob
    x = Inputs(
        rm6_price=p("rm6_price_eur"), premium_pct=p("price_premium_pct"),
        sf6_kg=p("sf6_kg_per_unit"), gwp=p("gwp_sf6"), leak_pct=p("leak_rate_pct_per_year"),
        life=p("asset_life_years"), discount_pct=p("discount_rate_pct"),
        eol_release_share=p("eol_release_share"), eol_recovery_eur=p("eol_recovery_cost_eur"),
        regulation_cost_eur=p("regulation_cost_if_hit_eur"), regulation_prob=prob,
        install_delta_eur=p("install_cost_delta_eur"),
        maintenance_delta_eur_yr=p("maintenance_cost_delta_eur_per_year"),
        sf6_admin_eur_yr=p("sf6_admin_cost_eur_per_year"), carbon_price=cp,
    )
    return replace(x, **overrides)


def carbon_t(x: Inputs, view: str) -> tuple[float, float]:
    """(t CO2e counted for one RM6, the PV factor applied to its carbon cost)."""
    annuity, df_end, _ = x.pv()
    fill = x.fill_t_co2e
    leak_t_yr = fill * x.leak_pct / 100
    left_at_eol = fill * max(0.0, 1 - x.leak_pct / 100 * x.life)
    if view == "leaks":
        return leak_t_yr * x.life, annuity / x.life
    if view == "lifecycle":
        t = leak_t_yr * x.life + left_at_eol * x.eol_release_share
        pv_t = leak_t_yr * annuity + left_at_eol * x.eol_release_share * df_end
        return t, (pv_t / t if t else 0.0)
    if view == "whole_fill":
        return fill, 1.0
    raise ValueError(f"view must be one of {list(VIEWS)}")


def tco_lines(x: Inputs, view: str = "lifecycle") -> pd.DataFrame:
    """PV of each differential cost line, EUR per unit: columns RM6, AirSeT, gap."""
    annuity, df_end, df_mid = x.pv()
    t, factor = carbon_t(x, view)
    rm6 = {
        "purchase": x.rm6_price,
        "installation": 0.0,
        "maintenance": 0.0,
        "sf6_upkeep": x.sf6_admin_eur_yr * annuity,
        "eol_handling": x.eol_recovery_eur * df_end,
        "regulation": x.regulation_prob * x.regulation_cost_eur * df_mid,
        "carbon": t * factor * x.carbon_price,
    }
    airset = {
        "purchase": x.rm6_price + x.premium_eur,
        "installation": x.install_delta_eur,
        "maintenance": x.maintenance_delta_eur_yr * annuity,
        "sf6_upkeep": 0.0, "eol_handling": 0.0, "regulation": 0.0, "carbon": 0.0,
    }
    df = pd.DataFrame({"RM6": rm6, "AirSeT": airset}).loc[LINES]
    df.loc["total"] = df.sum()
    df["gap"] = df["AirSeT"] - df["RM6"]
    return df


def tco_gap(x: Inputs, view: str = "lifecycle") -> float:
    """TCO(AirSeT) - TCO(RM6), EUR per unit. Negative: AirSeT is cheaper."""
    return float(tco_lines(x, view).loc["total", "gap"])


def break_even_carbon(x: Inputs, view: str = "lifecycle") -> float:
    """Carbon price (EUR/t) at which the two TCOs are equal. The gap is linear
    in the carbon price, so it is solved directly. inf if carbon can't close it."""
    g0 = tco_gap(replace(x, carbon_price=0.0), view)
    slope = tco_gap(replace(x, carbon_price=1.0), view) - g0
    if g0 <= 0:
        return 0.0
    return -g0 / slope if slope < 0 else np.inf


def max_premium_pct(x: Inputs, view: str = "lifecycle") -> float:
    """Largest premium (% of RM6 price) at which AirSeT still has the lower TCO."""
    return (x.premium_pct - tco_gap(x, view) / x.rm6_price * 100)


def view_table(p2: MarketEvidence, discounted: bool = True) -> pd.DataFrame:
    """Break-even carbon price and TCO gap for each view x scenario."""
    rows = []
    for s in SCENARIOS:
        x = inputs(p2, s)
        if not discounted:
            x = replace(x, discount_pct=0.0)
        for v, label in VIEWS.items():
            t, factor = carbon_t(x, v)
            rows.append({
                "scenario": s, "view": v, "view_label": label,
                "discounted": discounted, "carbon_price_eur_t": x.carbon_price,
                "t_co2e_counted": t, "pv_factor_on_carbon": factor,
                "premium_eur": x.premium_eur,
                "airset_saving_pv_eur": x.premium_eur + x.install_delta_eur - tco_gap(x, v),
                "tco_gap_eur": tco_gap(x, v),
                "break_even_carbon_eur_t": break_even_carbon(x, v),
                "max_premium_pct": max_premium_pct(x, v),
            })
    return pd.DataFrame(rows)


def carbon_sweep(p2: MarketEvidence, prices=None, scenario: str = "base") -> pd.DataFrame:
    """TCO gap vs carbon price, one column per view (break-even chart)."""
    prices = np.linspace(0, 250, 251) if prices is None else np.asarray(prices, float)
    x = inputs(p2, scenario)
    return pd.DataFrame({v: [tco_gap(replace(x, carbon_price=c), v) for c in prices]
                         for v in VIEWS}, index=pd.Index(prices, name="carbon_price_eur_t"))


def premium_carbon_grid(p2: MarketEvidence, view: str, premiums=None, prices=None,
                        scenario: str = "base") -> pd.DataFrame:
    """TCO gap over (premium %, carbon price): where the switch pays for itself."""
    premiums = np.arange(0, 32.5, 2.5) if premiums is None else premiums
    prices = np.arange(0, 210, 10) if prices is None else prices
    x = inputs(p2, scenario)
    return pd.DataFrame(
        [[tco_gap(replace(x, premium_pct=pm, carbon_price=c), view) for c in prices]
         for pm in premiums],
        index=pd.Index(premiums, name="premium_pct"),
        columns=pd.Index(prices, name="carbon_price_eur_t"))


_FIELD = {"price_premium_pct": "premium_pct", "internal_carbon_price_eur_t": "carbon_price",
          "sf6_kg_per_unit": "sf6_kg", "leak_rate_pct_per_year": "leak_pct",
          "eol_release_share": "eol_release_share", "eol_recovery_cost_eur": "eol_recovery_eur",
          "asset_life_years": "life", "discount_rate_pct": "discount_pct", "gwp_sf6": "gwp",
          "sf6_admin_cost_eur_per_year": "sf6_admin_eur_yr"}


def tornado(p2: MarketEvidence, view: str = "lifecycle") -> pd.DataFrame:
    """One input at a time from its pessimistic to its optimistic value, the
    others at base: TCO gap and break-even carbon price at each end."""
    base = inputs(p2, "base")
    rows = []
    for name in SENSITIVITY:
        row = {"param": name, "label": LABELS[name], "unit": p2.assumptions.loc[name, "unit"]}
        for s in ("pessimistic", "optimistic"):
            x = replace(base, **{_FIELD[name]: p2.param(name, s)})
            row[f"value_{s}"] = p2.param(name, s)
            row[f"gap_{s}"] = tco_gap(x, view)
            row[f"break_even_{s}"] = break_even_carbon(x, view)
        row["swing_eur"] = abs(row["gap_optimistic"] - row["gap_pessimistic"])
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("swing_eur", ascending=False)
    out.insert(3, "value_base", [p2.param(n, "base") for n in out.param])
    out["gap_base"] = tco_gap(base, view)
    out["view"] = view
    return out.reset_index(drop=True)


def upfront_gap(p2: MarketEvidence) -> pd.DataFrame:
    """Price premium vs raw-material cost difference: how much of the upfront
    gap raw materials can explain (Step 2 cost breakdown, Sep 2026)."""
    rm = rm_cost_today()
    rows = []
    for s in SCENARIOS:
        prem = inputs(p2, s).premium_eur
        for case in ("AirSeT",):
            d = rm[case] - rm["RM6"]
            rows.append({"scenario": s, "rival": {"pessimistic": "SF6 brand average",
                                                  "base": "Schneider RM6",
                                                  "optimistic": "Siemens"}[s],
                         "premium_eur": prem, "airset_case": case,
                         "rm_cost_gap_eur": d, "rm_share_of_premium_pct": d / prem * 100,
                         "non_rm_gap_eur": prem - d})
    return pd.DataFrame(rows)


# ====================================================================== Step 5
COPPER_CASES = {          # kg of copper per unit, with the evidence row behind it
    "RM6, BOM v1 (38.75 kg)": (38.75, "RM6", "BOM v1"),
    "RM6, teardown (8.6 kg)": (8.62, "RM6", "E174"),
    "AirSeT, BOM v1 (28.46 kg)": (28.46, "AirSeT", "BOM v1"),
    "AirSeT like Eaton Xiria (26.4 kg)": (26.4, "AirSeT", "E174"),
}


def rm_cost_today() -> pd.Series:
    """Raw-material cost per unit at the origin (Sep 2026), EUR, per Step 2 case."""
    b = pd.read_csv(PROCESSED / "cost_breakdown.csv")
    return b.groupby("case")["cost_eur"].sum()


def copper_eur_per_t() -> float:
    b = pd.read_csv(PROCESSED / "cost_breakdown.csv")
    return float(b.loc[b.material == "Copper", "eur_per_t"].iloc[0])


def bom_outlook(steel: str = "PPI") -> pd.DataFrame:
    """Step 8 BOM cost outlook per product and horizon (EUR and index)."""
    t = pd.read_csv(P1_TABLES / "step8_tables" / "bom_index_and_margin_points.csv")
    t = t[t.steel == steel].copy()
    for q in ("p10", "p50", "p90"):
        t[f"cost_{q}_eur"] = t.cost_today_eur * t[f"index_{q}"] / 100
    return t[["case", "horizon_m", "cost_today_eur", "index_p10", "index_p50", "index_p90",
              "cost_p10_eur", "cost_p50_eur", "cost_p90_eur"]]


def gap_outlook(p2: MarketEvidence) -> pd.DataFrame:
    """Change in the RM6 - AirSeT raw-material gap to mid-2027 (Step 9 joint
    paths, RM6 vs AirSeT with nickel-driven stainless), in EUR, as a
    share of the AirSeT price premium and in points of the RM6 price.
    Positive = RM6's raw materials rose more = the gap narrows for AirSeT."""
    o = pd.read_csv(P1_TABLES / "step9_tables" / "outlook_2027.csv")
    g = o[o.case.str.contains("gap")].copy()
    prem, price = inputs(p2, "base").premium_eur, p2.param("rm6_price_eur", "base")
    out = g[["horizon_m", "month", "p_rm6_rises_more"]].copy()
    for q in ("p10", "p50", "p90"):
        out[f"gap_change_{q}_eur"] = g[f"cost_{q}_eur"].values
        out[f"share_of_premium_{q}_pct"] = g[f"cost_{q}_eur"].values / prem * 100
        out[f"rm6_price_pts_{q}"] = g[f"cost_{q}_eur"].values / price * 100
    return out.reset_index(drop=True)


def copper_scenarios(p2: MarketEvidence, moves=(0.10, 0.30, 0.50, 1.00)) -> pd.DataFrame:
    """How a copper move changes the RM6 - AirSeT raw-material gap, for each
    pairing of copper contents (BOM vs teardown). Other materials held flat."""
    eur_t, prem = copper_eur_per_t(), inputs(p2, "base").premium_eur
    rows = []
    for rm6_name, (rm6_kg, _, rm6_src) in COPPER_CASES.items():
        if not rm6_name.startswith("RM6"):
            continue
        for air_name, (air_kg, _, air_src) in COPPER_CASES.items():
            if not air_name.startswith("AirSeT"):
                continue
            net = (rm6_kg - air_kg) * eur_t / 1000       # EUR of copper RM6 carries in excess
            row = {"rm6_copper": rm6_name, "airset_copper": air_name,
                   "net_copper_kg": rm6_kg - air_kg, "net_copper_eur": net,
                   "sources": f"{rm6_src}; {air_src}"}
            for m in moves:
                row[f"gap_change_cu_+{int(m * 100)}pct_eur"] = net * m
            row["copper_rise_to_close_premium_pct"] = (prem / net * 100) if net > 0 else np.inf
            rows.append(row)
    return pd.DataFrame(rows)


def gap_history() -> pd.DataFrame:
    """Monthly raw-material cost per unit (EUR, fixed Sep 2026 recipe and
    weights) and the RM6 - AirSeT gap, from the Step 2 BOM index history."""
    h = pd.read_csv(PROCESSED / "bom_index_history.csv", parse_dates=["month"]).set_index("month")
    today = rm_cost_today()
    eur = pd.DataFrame({c: h[c] / 100 * today[c] for c in ("RM6", "AirSeT")})
    eur["gap"] = eur["RM6"] - eur["AirSeT"]
    return eur


def price_vs_rm_gap() -> pd.DataFrame:
    """Yearly SF6-free price premium (Eaton - Schneider P50, price benchmark)
    next to the yearly average RM6 - AirSeT raw-material gap: did the price
    convergence follow raw materials?"""
    p = pd.read_csv(PROCESSED / "rmu_prices_yearly.csv")
    p = p.pivot(index="year", columns="brand_id", values="p50")
    h = gap_history()
    rm = h.groupby(h.index.year)[["RM6", "AirSeT", "gap"]].mean()
    out = pd.DataFrame({"schneider_p50": p["SE"], "eaton_p50": p["ETN"]})
    out["premium_eur"] = out.eaton_p50 - out.schneider_p50
    out["premium_pct"] = out.premium_eur / out.schneider_p50 * 100
    out = out.join(rm.rename(columns={"RM6": "rm6_rm_cost_eur", "AirSeT": "airset_rm_cost_eur",
                                      "gap": "rm_gap_eur"}))
    return out.reset_index().rename(columns={"index": "year"})


# ====================================================================== output
def _sanity_check(p2: MarketEvidence) -> None:
    """Reproduce the framing note's EUR 54.5/t: whole fill, undiscounted, the
    EUR 1,921 premium, no other cost line."""
    x = inputs(p2, "base", gwp=23500, premium_pct=1921 / 8740 * 100, eol_recovery_eur=0.0,
               sf6_admin_eur_yr=0.0, discount_pct=0.0)
    be = break_even_carbon(x, "whole_fill")
    assert abs(be - 54.5) < 0.5, be


def write_tables(p2: MarketEvidence) -> list:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "tco_lines_base.csv": pd.concat({v: tco_lines(inputs(p2, "base"), v) for v in VIEWS},
                                        names=["view", "line"]),
        "tco_views.csv": pd.concat([view_table(p2, True), view_table(p2, False)]),
        "tornado_lifecycle.csv": tornado(p2, "lifecycle"),
        "tornado_whole_fill.csv": tornado(p2, "whole_fill"),
        "upfront_gap.csv": upfront_gap(p2),
        "carbon_sweep.csv": carbon_sweep(p2, np.arange(0, 260, 10)),
        "gap_outlook_2027.csv": gap_outlook(p2),
        "copper_scenarios.csv": copper_scenarios(p2),
        "price_vs_rm_gap.csv": price_vs_rm_gap(),
    }
    paths = []
    for name, df in tables.items():
        path = TABLE_DIR / name
        keep_index = name in ("tco_lines_base.csv", "carbon_sweep.csv")
        df.round(4).to_csv(path, index=keep_index)
        paths.append(path)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-write", action="store_true", help="print only")
    args = ap.parse_args()
    p2 = MarketEvidence.load()
    _sanity_check(p2)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print("=== TCO lines, base scenario (EUR PV per unit) ===")
    for v, label in VIEWS.items():
        print(f"\n-- {label} --\n{tco_lines(inputs(p2, 'base'), v).round(0)}")
    cols = ["scenario", "view", "carbon_price_eur_t", "premium_eur", "airset_saving_pv_eur",
            "tco_gap_eur", "break_even_carbon_eur_t", "max_premium_pct"]
    print("\n=== Views x scenarios, discounted ===")
    print(view_table(p2, True)[cols].round(1).to_string(index=False))
    print("\n=== Views x scenarios, undiscounted ===")
    print(view_table(p2, False)[cols].round(1).to_string(index=False))
    print("\n=== Tornado, lifecycle view ===")
    print(tornado(p2, "lifecycle")[["label", "gap_pessimistic", "gap_base", "gap_optimistic",
                                     "break_even_pessimistic", "break_even_optimistic"]].round(0))
    print("\n=== Upfront gap ===")
    print(upfront_gap(p2).round(1).to_string(index=False))
    print("\n=== Step 5: gap outlook to mid-2027 ===")
    print(gap_outlook(p2).round(2).to_string(index=False))
    print("\n=== Step 5: copper scenarios ===")
    print(copper_scenarios(p2).drop(columns="sources").round(1).to_string(index=False))
    print("\n=== Step 5: price premium vs raw-material gap ===")
    print(price_vs_rm_gap().round(1).to_string(index=False))
    if not args.no_write:
        for p in write_tables(p2):
            print(f"Wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
