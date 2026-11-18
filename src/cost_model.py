"""Provisional unit-cost model used by the business EDA (plan Step 3.3).

    UnitCost(t) = NonRMCost + Σ_i  kg_i × Price_i(t) / 1000

* ``kg_i`` from ``bom_materials.csv`` (copied into ``configs/eda.yaml``).
* ``Price_i`` in EUR/t from :func:`src.data_loading.build_eur_panel`.
* Polymers have no €/t level in the data: an assumed 2021 level is moved with
  the EU plastics PPI (S11, 2021 = 100).
* ``NonRMCost`` (components, labour, overhead) is held constant and sized so
  that UnitCost(reference_month) = ``total_unit_cost_ref``.

This is a placeholder for the Step 2 workstream; all assumptions live in the config.
"""

from __future__ import annotations

import copy

import pandas as pd


def add_plastic_prices(panel: pd.DataFrame, levels_2021: dict) -> pd.DataFrame:
    """Add PBT / PET / ETP €/t columns = assumed 2021 level × S11 / 100."""
    out = panel.copy()
    for name, lvl in levels_2021.items():
        out[name] = lvl * out["ppi_plastics"] / 100.0
    return out


def product_materials(cfg: dict, product: str, scenario: str | None = None) -> dict:
    """Material dict ``{name: {series, kg}}`` for a product, optionally with a BOM scenario applied."""
    mats = copy.deepcopy(cfg["cost_model"]["products"][product]["materials"])
    if scenario:
        sc = cfg["cost_model"]["scenarios"][scenario]
        if sc["product"] != product:
            raise ValueError(f"Scenario {scenario} is for {sc['product']}, not {product}")
        for m, kg in sc.get("override", {}).items():
            mats[m]["kg"] = kg
        mats.update(copy.deepcopy(sc.get("add", {})))
    return mats


def material_costs(panel: pd.DataFrame, materials: dict) -> pd.DataFrame:
    """€ per unit for each material over time (kg × €/t / 1000). Rows with any NaN are dropped."""
    df = pd.DataFrame({m: panel[v["series"]] * v["kg"] / 1000.0 for m, v in materials.items()})
    return df.dropna()


def unit_cost(panel: pd.DataFrame, cfg: dict, product: str, scenario: str | None = None) -> pd.DataFrame:
    """Material € columns + ``rm_cost`` (raw-material basket), ``non_rm`` and ``unit_cost``."""
    cm = cfg["cost_model"]
    mc = material_costs(panel, product_materials(cfg, product, scenario))
    mc["rm_cost"] = mc.sum(axis=1)
    ref = pd.Timestamp(cm["reference_month"])
    non_rm = cm["products"][product]["total_unit_cost_ref"] - mc.loc[ref, "rm_cost"]
    mc["non_rm"] = non_rm
    mc["unit_cost"] = mc["rm_cost"] + non_rm
    return mc
