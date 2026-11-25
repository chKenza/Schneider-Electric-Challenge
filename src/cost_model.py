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

# BOM source: the client's corrected BOM, `RM_Prices_XHEC_Challenge_v1.xlsx`, sheet
# BOM_Materials (received 20 Nov 2026). It replaces `bom_materials.csv`: RM6 is now fully
# labelled (310 kg) and AirSeT has copper and epoxy (547 kg). Lines the client marks as
# unknown ("Other", "Unidentified remainder") stay unpriced, as the client asked: no
# composition is invented for them (sensitivity in src/p2_cost_gap.py).
BOM_SOURCE = "BOM v1"

# Brass has no series in the BOM. Proxy: 65 % copper + 35 % zinc (cartridge-type brass),
# both LME in EUR. It moves with copper (driver D01), its main cost.
BRASS_CU_SHARE = 0.65

# material: (€/t level series, driver series). No level = unpriced (plastics, unknown lines).
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
    "Brass": ("BRASS_EUR", "D01"),
    "Unidentified": (None, None),
}

# (material, kg, where the kg comes from), from BOM v1.
RM6 = [
    ("Carbon steel FR", 144.46, BOM_SOURCE),
    ("Stainless steel", 55.80, BOM_SOURCE),
    ("Copper", 38.75, BOM_SOURCE),
    ("Galvanised steel", 21.08, BOM_SOURCE),
    ("Aluminium", 4.96, BOM_SOURCE),
    ("Epoxy", 22.32, BOM_SOURCE),
    ("Brass", 3.41, f"{BOM_SOURCE}; priced as 65 % Cu + 35 % Zn (proxy)"),
    ("Plastic", 5.58 + 4.34 + 3.72, f"{BOM_SOURCE} (PET + PP + ETP), unpriced"),
    ("Unidentified", 5.58, f"{BOM_SOURCE} 'Unidentified remainder', unpriced"),
]
AIRSET = [
    ("Carbon steel DE", 343.70, BOM_SOURCE),
    ("Stainless steel", 75.30, BOM_SOURCE),
    ("Copper", 28.46, BOM_SOURCE),
    ("Epoxy", 16.42, BOM_SOURCE),
    ("Aluminium", 4.90, BOM_SOURCE),
    (
        "Plastic",
        10.40 + 8.10 + 1.64 + 0.55 + 0.55,
        f"{BOM_SOURCE} (PBT + ETP + PE + PVC + PP), unpriced",
    ),
    ("Unidentified", 56.00, f"{BOM_SOURCE} 'Other', not priceable (client)"),
]
CASES = {"RM6": RM6, "AirSeT": AIRSET}


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
    panel = pd.read_csv(PANEL_FILE, index_col=0, parse_dates=True)
    panel["BRASS_EUR"] = (
        BRASS_CU_SHARE * panel["D01"] + (1 - BRASS_CU_SHARE) * panel["S05_EUR"]
    )
    return panel


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
        "RM6, nickel check": split_stainless(CASES["RM6"]),
        "AirSeT, nickel check": split_stainless(CASES["AirSeT"]),
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
