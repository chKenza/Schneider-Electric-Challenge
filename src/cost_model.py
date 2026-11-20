"""Step 2 – raw-material cost of one RM6 / RM AirSeT unit and its BOM cost index.

Run from the repo root, after src.data_prep:
    uv run python -m src.cost_model

Cost of material i at month t:
    cost_i(t) = kg_i × level_i(origin) / 1000 × driver_i(t) / driver_i(origin)
    level  = a €/t price (MEPS, CRU, LME, epoxy file) at the origin
    driver = the forecast-target series that moves it month to month
BOM cost index = Σ cost_i(t) / Σ cost_i(origin) × 100 (origin = 100).
"""

import argparse

import numpy as np
import pandas as pd

from src.data_prep import ORIGIN_MONTH, OUT

PANEL_FILE = OUT / "panel_monthly.csv"
HORIZONS = (3, 6, 9)
SHOCK = 0.10

# Implied total masses: labelled kg ÷ share_pct in bom_materials.csv.
RM6_TOTAL_KG = 38.8 / 0.125  # ≈ 310 kg
AIRSET_TOTAL_KG = 327.2 / 0.52  # ≈ 629 kg
# RM6 PEP (ENVPEP1511010_V2, 07/2023): epoxy = 0.62 % of a 255 kg unit.
PEP_EPOXY_SHARE = 0.0062
PEP_RM6_KG = 255

# material: (€/t level series, driver series). Plastics have no €/t level (left unpriced).
PRICES = {
    "Carbon steel FR": ("MEPS_FR_CR", "S09"),
    "Carbon steel DE": ("MEPS_DE_CR", "S09"),
    "Galvanised steel": ("MEPS_DE_HDG", "S10"),
    "Stainless steel": ("CRU_SS304_DE_TOTAL", "S09"),
    "Stainless base": ("CRU_SS304_DE_BASE", "S09"),
    "Stainless alloy surcharge": ("CRU_SS304_DE_ALLOY", "S03_EUR"),
    "Copper": ("D01", "D01"),
    "Aluminium": ("D02", "D02"),
    "Plastic": (None, "S11"),
    "Epoxy": ("EPOXY_EUR", "EPOXY_EUR"),
}

# (material, kg, where the kg comes from). Unlisted slices stay unpriced.
RM6 = [
    (
        "Carbon steel FR",
        0.45 * RM6_TOTAL_KG,
        "BOM unlabelled ~45 % slice, read as carbon steel",
    ),
    ("Stainless steel", 55.8, "bom_materials.csv"),
    ("Copper", 38.8, "bom_materials.csv (PEP: ~38.7 kg)"),
    ("Galvanised steel", 21.1, "bom_materials.csv"),
    ("Plastic", 5.6, "bom_materials.csv (PET)"),
    ("Aluminium", 5.0, "bom_materials.csv"),
    ("Epoxy", PEP_EPOXY_SHARE * PEP_RM6_KG, "RM6 PEP: 0.62 % of 255 kg"),
]
AIRSET = [
    ("Carbon steel DE", 327.2, "bom_materials.csv"),
    ("Stainless steel", 102.6, "bom_materials.csv"),
    ("Plastic", 13.8 + 11.3, "bom_materials.csv (PBT + ETP)"),
    ("Aluminium", 5.0, "bom_materials.csv"),
]
CASES = {
    "RM6": RM6,
    "AirSeT epoxy low": AIRSET
    + [("Epoxy", PEP_EPOXY_SHARE * AIRSET_TOTAL_KG, "RM6 PEP share × 629 kg")],
    "AirSeT epoxy high": AIRSET + [("Epoxy", 85.6, "all of BOM 'Other'")],
}


def split_stainless(bom: list) -> list:
    """Nickel check: stainless price = base (moves with S09) + alloy surcharge (moves with nickel).

    Both rows carry the full stainless kg: each is priced at its own €/t component.
    """
    out = []
    for material, kg, source in bom:
        if material == "Stainless steel":
            out.append(("Stainless base", kg, source))
            out.append(("Stainless alloy surcharge", kg, source))
        else:
            out.append((material, kg, source))
    return out


def load_panel() -> pd.DataFrame:
    return pd.read_csv(PANEL_FILE, index_col=0, parse_dates=True)


def last_value(series: pd.Series, origin: str = ORIGIN_MONTH) -> float:
    """Latest observed value at or before the origin month."""
    return series.loc[:origin].dropna().iloc[-1]


def cost_breakdown(
    bom: list, panel: pd.DataFrame, origin: str = ORIGIN_MONTH
) -> pd.DataFrame:
    """€ per material at the origin, one row per BOM line."""
    rows = []
    for material, kg, source in bom:
        level_id, driver_id = PRICES[material]
        level = last_value(panel[level_id], origin) if level_id else float("nan")
        level_month = (
            panel[level_id].loc[:origin].dropna().index[-1].strftime("%Y-%m")
            if level_id
            else ""
        )
        rows.append((material, kg, source, level_id, level_month, level, driver_id))
    out = pd.DataFrame(
        rows,
        columns=[
            "material",
            "kg",
            "kg_source",
            "level_series",
            "level_month",
            "eur_per_t",
            "driver",
        ],
    )
    out["cost_eur"] = out["kg"] * out["eur_per_t"] / 1000
    out["cost_share"] = out["cost_eur"] / out["cost_eur"].sum()
    return out


def driver_ratios(
    breakdown: pd.DataFrame, panel: pd.DataFrame, origin: str = ORIGIN_MONTH
) -> pd.DataFrame:
    """driver(t) / driver(origin), one column per priced material."""
    priced = breakdown.dropna(subset=["cost_eur"])
    return pd.DataFrame(
        {
            row.material: panel[row.driver] / last_value(panel[row.driver], origin)
            for row in priced.itertuples()
        }
    )


def bom_index(breakdown: pd.DataFrame, ratios: pd.DataFrame) -> pd.Series:
    """BOM cost index (origin = 100) for any set of driver ratios.

    `ratios` has one column per priced material (driver / driver at origin) and one row
    per month, scenario or simulated path. Rows with a missing driver give NaN.
    Reuse this in Steps 6–7 on simulated paths: never add up material P90s.
    """
    cost0 = breakdown.dropna(subset=["cost_eur"]).set_index("material")["cost_eur"]
    weights = cost0 / cost0.sum()
    return (
        ratios[weights.index].mul(weights, axis=1).sum(axis=1, min_count=len(weights))
        * 100
    )


def shock_table(breakdown: pd.DataFrame) -> pd.DataFrame:
    """BOM index change when one material's price rises by SHOCK, others flat."""
    priced = breakdown.dropna(subset=["cost_eur"])
    ones = pd.DataFrame(1.0, index=priced["material"], columns=priced["material"])
    shocked = ones + SHOCK * np.eye(len(priced))
    change = bom_index(breakdown, shocked) - 100
    return pd.DataFrame(
        {
            "material": change.index,
            "price_change_pct": SHOCK * 100,
            "bom_index_change_pts": change.values,
            "eur_per_unit": (priced.set_index("material")["cost_eur"] * SHOCK).values,
        }
    )


def historical_changes(index: pd.Series) -> pd.DataFrame:
    """Distribution of past H-month % changes of the BOM index (all months with full data)."""
    rows = []
    for h in HORIZONS:
        change = (index / index.shift(h) - 1).dropna() * 100
        rows.append(
            (
                h,
                change.index[0].strftime("%Y-%m"),
                len(change),
                change.quantile(0.1),
                change.quantile(0.5),
                change.quantile(0.9),
                change.max(),
            )
        )
    return pd.DataFrame(
        rows,
        columns=["horizon_m", "from", "n", "p10_pct", "p50_pct", "p90_pct", "max_pct"],
    )


def _tag(df: pd.DataFrame, case: str) -> pd.DataFrame:
    return df.assign(case=case)[["case", *df.columns]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--origin", default=ORIGIN_MONTH, help="forecast origin, YYYY-MM"
    )
    args = parser.parse_args()

    panel = load_panel()
    cases = CASES | {
        "AirSeT epoxy low, nickel check": split_stainless(CASES["AirSeT epoxy low"]),
        "AirSeT epoxy high, nickel check": split_stainless(CASES["AirSeT epoxy high"]),
    }
    breakdowns, indices, shocks, history = [], {}, [], []
    for case, bom in cases.items():
        bd = cost_breakdown(bom, panel, args.origin)
        idx = bom_index(bd, driver_ratios(bd, panel, args.origin)).dropna()
        breakdowns.append(bd.pipe(_tag, case))
        indices[case] = idx
        shocks.append(shock_table(bd).pipe(_tag, case))
        history.append(historical_changes(idx).pipe(_tag, case))
        print(f"{case}: €{bd['cost_eur'].sum():,.0f} raw material at {args.origin}")

    pd.concat(breakdowns).to_csv(
        OUT / "cost_breakdown.csv", index=False, float_format="%.4g"
    )
    pd.DataFrame(indices).to_csv(OUT / "bom_index_history.csv", float_format="%.3f")
    pd.concat(shocks).to_csv(OUT / "cost_shocks.csv", index=False, float_format="%.3g")
    pd.concat(history).to_csv(
        OUT / "bom_index_changes.csv", index=False, float_format="%.3g"
    )
    print(f"wrote 4 files to {OUT}/")


if __name__ == "__main__":
    main()
