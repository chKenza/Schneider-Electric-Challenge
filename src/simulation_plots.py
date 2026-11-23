"""Charts for the Step 8 report. Each function saves a PNG in plots/step8/ and returns the figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.feature_plots import AQUA, BLUE, INK2, MUTED, ORANGE, set_style

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step8"
MAIN = ["RM6", "AirSeT epoxy low, nickel check"]
COLOR = {"RM6": ORANGE, "AirSeT epoxy low, nickel check": BLUE}


def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def bom_index_fan(summary: pd.DataFrame, name="01_bom_index_fan"):
    """BOM cost index P10-P90 band and P50, by horizon, for the main cases (PPI steel)."""
    set_style()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    d = summary[summary.steel == "PPI"]
    for case in MAIN:
        c = d[d.case == case].sort_values("horizon_m")
        x = [0] + c.horizon_m.tolist()
        ax.fill_between(x, [100] + c.index_p10.tolist(), [100] + c.index_p90.tolist(),
                        color=COLOR[case], alpha=0.15)
        ax.plot(x, [100] + c.index_p50.tolist(), color=COLOR[case], label=f"{case} (P50, P10-P90)")
    ax.axhline(100, color=MUTED, lw=0.8)
    ax.set(xticks=[0, 3, 6, 9], xlabel="months after Sep 2026", ylabel="BOM cost index (Sep 2026 = 100)")
    ax.legend(frameon=False)
    return _save(fig, name)


def eur_per_material(contrib: pd.DataFrame, h=9, name="02_eur_per_material_p90"):
    """€ each material adds to the P90 cost increase, main cases, PPI steel."""
    set_style()
    d = contrib[(contrib.horizon_m == h) & (contrib.steel == "PPI") & contrib.case.isin(MAIN)]
    t = d.pivot(index="material", columns="case", values="eur_at_p90").fillna(0)
    t = t.loc[t.abs().max(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    t[MAIN].plot.barh(ax=ax, color=[COLOR[c] for c in MAIN], width=0.75)
    ax.set(xlabel=f"€ per unit at P90, {h} months", ylabel="")
    ax.legend(frameon=False)
    return _save(fig, name)


def scenario_points(summary: pd.DataFrame, h=9, name="03_scenarios_margin_points"):
    """Total margin points at risk (P90), every BOM case x steel scenario."""
    set_style()
    d = summary[summary.horizon_m == h].pivot(index="case", columns="steel", values="total_at_risk_p90_pts")
    d = d.sort_values("PPI")
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    d[["PPI", "market"]].plot.barh(ax=ax, color=[BLUE, AQUA], width=0.75)
    ax.set(xlabel=f"margin points at risk, P90, {h} months", ylabel="")
    ax.legend(["steel follows PPI (S09/S10)", "steel follows MEPS market prices"], frameon=False)
    return _save(fig, name)


def block_sensitivity_plot(blocks: pd.DataFrame, name="04_block_length"):
    """9-month co-movement (copper-steel) and margin points at risk vs block length."""
    set_style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(8, 3))
    sim = blocks[blocks.block != "history"]
    hist = blocks[blocks.block == "history"].iloc[0]
    a.plot(sim.block.astype(int), sim["corr_D01_S09"], "o-", color=INK2)
    a.axhline(hist["corr_D01_S09"], color=ORANGE, ls="--", label="history")
    a.set(xlabel="block length (months)", ylabel="copper-steel 9 m rank corr.", xticks=[1, 3, 6, 9])
    a.legend(frameon=False)
    for case in MAIN:
        b.plot(sim.block.astype(int), sim[f"{case} P90 pts"], "o-", color=COLOR[case], label=case)
    b.set(xlabel="block length (months)", ylabel="margin points at risk, P90", xticks=[1, 3, 6, 9])
    b.legend(frameon=False)
    return _save(fig, name)

def main():
    from src.simulation import TABLE_DIR
    summary = pd.read_csv(TABLE_DIR / "bom_index_and_margin_points.csv")
    contrib = pd.read_csv(TABLE_DIR / "eur_per_material_p90.csv")
    blocks = pd.read_csv(TABLE_DIR / "block_sensitivity.csv")
    bom_index_fan(summary)
    eur_per_material(contrib)
    scenario_points(summary)
    block_sensitivity_plot(blocks)
    print(f"wrote 4 plots to {PLOT_DIR}/")


if __name__ == "__main__":
    main()