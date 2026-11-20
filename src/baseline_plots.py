"""Charts for the Step 5 report: what the next models should improve on.

Run from the repo root, after src.baselines:

    uv run python -m src.baseline_plots

Saves PNGs in plots/step5/. Style and colours are the Step 4 ones (src/feature_plots.py).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from src.baselines import PRED_DIR, TABLE_DIR
from src.feature_plots import BLUE, INK, INK2, MUTED, ORANGE, TARGET_NAMES, set_style

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step5"
SELECT_END = pd.Timestamp("2025-03-01")
LIGHT_BLUE = "#c9ddf7"
# Diverging: orange = band too narrow (under-covers), grey = 80 % (right), blue = too wide.
COVERAGE_CMAP = LinearSegmentedColormap.from_list("coverage", [ORANGE, "#f6c9b3", "#f0efec", "#9ec5f4", BLUE])

TARGET_ORDER = ["S01", "D01", "S02", "D02", "S03", "S04", "S05",
                "S07", "S08", "S09", "S10", "S11", "S12", "S13", "EPOXY_EUR"]


def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def bands_vs_outcomes(pred: pd.DataFrame, cells: list[tuple[str, int]],
                      model: str = "random_walk", name: str = "01_bands_vs_outcomes"):
    """Random-walk P10-P90 band and the actual change, by target month; misses in orange."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 6.4), sharex=True)
    for ax, (t, h) in zip(axes.flat, cells):
        d = pred[(pred["target"] == t) & (pred["horizon"] == h) & (pred["model"] == model)
                 & pred["y"].notna()].sort_values("target_month")
        x = d["target_month"]
        y, lo, hi = 100 * d["y"], 100 * d["p10"], 100 * d["p90"]
        ax.fill_between(x, lo, hi, color=LIGHT_BLUE, lw=0, label="80 % band (P10–P90)")
        ax.plot(x, y, color=INK2, lw=1.2, label="actual change")
        miss = (y < lo) | (y > hi)
        ax.scatter(x[miss], y[miss], s=22, color=ORANGE, zorder=3, edgecolor="white", lw=0.8,
                   label="outside the band")
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.axvline(SELECT_END, color=MUTED, lw=0.8, ls="--")
        cov = 1 - miss.mean()
        ax.text(SELECT_END, 0.97, "  hold-out →", transform=ax.get_xaxis_transform(),
                fontsize=8, color=MUTED, va="top")
        ax.set_title(f"{TARGET_NAMES[t]}, {h} months  ·  coverage {cov:.0%}", loc="left")
        ax.set_ylabel(f"{h}-month change (%)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("Random-walk bands do not follow volatility: too narrow in 2022, too wide in 2025",
                 x=0.01, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, name)


def coverage_heatmap(metrics: pd.DataFrame, model: str = "random_walk",
                     name: str = "02_coverage_heatmap"):
    """Coverage of the 80 % band per target x horizon, backtest vs hold-out."""
    m = metrics[metrics["model"] == model]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 6.2), sharey=True)
    norm = TwoSlopeNorm(vmin=0.4, vcenter=0.8, vmax=1.0)
    for ax, (w, title) in zip(axes, [("backtest", "Backtest (Feb 2022 → Mar 2025)"),
                                      ("holdout", "Hold-out (Apr 2025 → Sep 2026)")]):
        grid = (m[m["window"] == w].pivot(index="target", columns="horizon", values="coverage_80")
                .reindex(TARGET_ORDER))
        im = ax.imshow(grid.values, cmap=COVERAGE_CMAP, norm=norm, aspect="auto")
        for i in range(grid.shape[0]):
            for j in range(grid.shape[1]):
                v = grid.values[i, j]
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=8,
                        color="white" if (v < 0.55 or v > 0.97) else INK)
        ax.set_xticks(range(3), [f"{h} m" for h in grid.columns])
        ax.set_yticks(range(len(grid)), [TARGET_NAMES[t] for t in grid.index])
        ax.set_title(title, loc="left")
        ax.grid(False)
        ax.axhline(6.5, color="white", lw=2)  # market prices above, price indices and epoxy below
    cb = fig.colorbar(im, ax=axes, shrink=0.6, ticks=[0.4, 0.6, 0.8, 0.9, 1.0])
    cb.ax.set_yticklabels(["40 % too narrow", "60 %", "80 % right", "90 %", "100 % too wide"])
    fig.suptitle("Share of outcomes inside the random-walk 80 % band (should be 80 %)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold", color=INK)
    return _save(fig, name)


def feature_skill(metrics: pd.DataFrame, model: str = "features_qr",
                  name: str = "03_feature_skill_backtest_vs_holdout"):
    """Pinball skill vs random walk, backtest (open) vs hold-out (filled), per target x horizon."""
    m = metrics[metrics["model"] == model]
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.6), sharey=True)
    for ax, h in zip(axes, [3, 6, 9]):
        d = m[m["horizon"] == h].pivot(index="target", columns="window",
                                       values="pinball_skill_vs_rw").reindex(TARGET_ORDER[::-1])
        ypos = np.arange(len(d))
        bt, ho = 100 * d["backtest"], 100 * d["holdout"]
        ax.hlines(ypos, bt, ho, color=MUTED, lw=1)
        ax.scatter(bt, ypos, s=40, facecolor="white", edgecolor=BLUE, lw=1.5, zorder=3,
                   label="backtest (features chosen here)")
        ax.scatter(ho, ypos, s=40, color=BLUE, edgecolor="white", lw=0.8, zorder=3,
                   label="hold-out (clean)")
        ax.axvline(0, color=INK2, lw=0.8)
        ax.axvspan(0, 45, color="#eef4fc", zorder=0, lw=0)
        ax.set_xlim(-40, 45)
        ax.set_title(f"{h} months", loc="left")
        ax.set_xlabel("skill vs random walk (%)  →  better")
        ax.set_yticks(ypos, [TARGET_NAMES[t] for t in d.index])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.05))
    fig.suptitle("The features beat the random walk only for EU steel and aluminium PPIs at 3 months",
                 x=0.01, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, name)


def main() -> None:
    set_style()
    pred = pd.read_csv(PRED_DIR / "predictions.csv", parse_dates=["origin", "target_month"])
    metrics = pd.read_csv(TABLE_DIR / "metrics.csv")
    bands_vs_outcomes(pred, [("S09", 3), ("S08", 3), ("D01", 9), ("S03", 9)])
    coverage_heatmap(metrics)
    feature_skill(metrics)
    print(f"charts written to {PLOT_DIR}")


if __name__ == "__main__":
    main()
