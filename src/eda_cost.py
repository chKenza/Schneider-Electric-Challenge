"""Business EDA on top of the Step 2 cost model (src/cost_model.py, Karin).

Nothing here changes the cost model. It only reshapes its output for the EDA:
  * € per material per month for a case (the BOM index split by material);
  * a "market price" variant, where each material moves with its own €/t series
    (MEPS / CRU / LME / epoxy) instead of the forecast-target driver (e.g. S09);
  * a constant non-raw-material cost, so the margin simulation has a full unit cost.
"""

from __future__ import annotations

import pandas as pd

from src import cost_model as cm


def all_cases() -> dict:
    """The Step 2 cases, including the two nickel-check variants built in cost_model.main()."""
    return cm.CASES | {
        "RM6, nickel check": cm.split_stainless(cm.CASES["RM6"]),
        "AirSeT, nickel check": cm.split_stainless(cm.CASES["AirSeT"]),
    }


def material_paths(case: str, panel: pd.DataFrame, origin: str, drive: str = "driver") -> pd.DataFrame:
    """€ per unit for each priced material, month by month, plus rm_cost and bom_index.

    drive = "driver": the Step 2 definition. cost_i(t) = cost_i(origin) × driver_i(t) / driver_i(origin)
    drive = "market": same, but each material moves with its own €/t level series.
    Months where any material is missing are dropped (as in cm.bom_index).
    Plastics have no €/t level in Step 2 and are left out, as there.
    """
    bd = cm.cost_breakdown(all_cases()[case], panel, origin)
    priced = bd.dropna(subset=["cost_eur"]).copy()
    if drive == "market":
        priced["driver"] = priced["level_series"]
    elif drive != "driver":
        raise ValueError("drive must be 'driver' or 'market'")
    ratios = cm.driver_ratios(priced, panel, origin)
    cost0 = priced.set_index("material")["cost_eur"]
    paths = ratios[cost0.index].mul(cost0, axis=1).dropna()
    paths["rm_cost"] = paths[cost0.index].sum(axis=1)
    paths["bom_index"] = 100 * paths["rm_cost"] / cost0.sum()
    return paths


def with_unit_cost(paths: pd.DataFrame, total_at_origin: float, origin: str) -> pd.DataFrame:
    """Add a constant non-raw-material cost so that unit cost at the origin = total_at_origin."""
    rm0 = paths.loc[:origin, "rm_cost"].iloc[-1]
    out = paths.copy()
    out["non_rm"] = total_at_origin - rm0
    out["unit_cost"] = out["rm_cost"] + out["non_rm"]
    return out


def materials_of(paths: pd.DataFrame) -> list[str]:
    return [c for c in paths.columns if c not in ("rm_cost", "bom_index", "non_rm", "unit_cost")]


def build_costs(panel: pd.DataFrame, bcfg: dict) -> dict:
    """{(case, drive): DataFrame} for the cases and both drive modes, with unit cost."""
    out = {}
    for case in bcfg["cases"] + bcfg["nickel_check_cases"]:
        total = bcfg["total_unit_cost"]["RM6" if case.startswith("RM6") else "AirSeT"]
        drives = ["driver"] if "nickel" in case else ["driver", "market"]
        for d in drives:
            out[(case, d)] = with_unit_cost(material_paths(case, panel, bcfg["origin"], d),
                                            total, bcfg["origin"])
    return out
