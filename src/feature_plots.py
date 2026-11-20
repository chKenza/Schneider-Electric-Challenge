"""Charts for the Step 4 report. Each function saves a PNG in plots/step4/ and returns the figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step4"

# Validated categorical order (light mode); assigned in fixed order.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, MUTED, GRID, BAND = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#f0efec"
BLUES = LinearSegmentedColormap.from_list("blues", ["#f0efec", "#9ec5f4", "#3987e5", "#184f95"])

TARGET_NAMES = {
    "S01": "Copper USD", "D01": "Copper EUR", "S07": "EU copper PPI", "S02": "Aluminium USD",
    "D02": "Aluminium EUR", "S08": "EU alu. PPI", "S03": "Nickel", "S04": "Iron ore",
    "S05": "Zinc", "S09": "EU steel PPI", "S10": "DE steel PPI", "S11": "EU plastics PPI",
    "S12": "US steel PPI", "S13": "US plastics PPI", "EPOXY_EUR": "Epoxy",
}


def set_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.labelsize": 9,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
        "legend.fontsize": 8, "font.size": 9, "figure.dpi": 110, "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def pacf_grid(ap: pd.DataFrame, name: str = "01_pacf_own_price"):
    targets = list(dict.fromkeys(ap["target"]))
    fig, axes = plt.subplots(3, 5, figsize=(15, 6.6), sharey=True)
    for ax, t in zip(axes.flat, targets):
        d = ap[ap["target"] == t]
        band = d["band"].iloc[0]
        colors = [BLUE if abs(v) > band else "#b7d3f6" for v in d["pacf"]]
        ax.bar(d["lag"], d["pacf"], color=colors, width=0.65)
        ax.axhspan(-band, band, color=BAND, zorder=0)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_title(TARGET_NAMES[t], loc="left")
        ax.set_xticks([1, 3, 6, 9, 12])
        ax.set_ylim(-0.45, 0.9)
    for ax in axes[-1]:
        ax.set_xlabel("lag (months)")
    fig.suptitle("Partial autocorrelation of monthly price changes (dark bar = outside the "
                 "grey 95 % band)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, name)


def significance_vs_gain(evidence: pd.DataFrame, name: str = "02_significance_vs_backtest"):
    """Drivers: Granger significance (x) against out-of-sample gain (y)."""
    d = evidence[(evidence["group"] == "driver") & evidence["granger_p_holm"].notna()].copy()
    d["x"] = -np.log10(d["granger_p_holm"].clip(lower=1e-6))
    d["y"] = 100 * d["gain_alone"]
    d["cat"] = np.where(d["decision"] == "kept", "selected",
                        np.where(d["decision"] == "shortlist", "shortlist", "dropped"))
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for cat, color, size in [("dropped", "#b7b6b0", 22), ("shortlist", ORANGE, 40), ("selected", BLUE, 48)]:
        s = d[d["cat"] == cat]
        ax.scatter(s["x"], s["y"].clip(-40, 80), s=size, color=color, label=cat,
                   edgecolor=SURFACE, linewidth=0.8, zorder=3)
    ax.axvline(1, color=MUTED, ls="--", lw=0.8)
    ax.text(1.03, 76, "Holm p = 0.10", fontsize=7, color=INK2, va="top")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axhline(-1, color=MUTED, ls=":", lw=0.8)
    ax.set_xlabel("Granger significance, -log10(Holm-adjusted p)   (right = more significant)")
    ax.set_ylabel("backtest loss change when added (%)\n(below 0 = better forecasts)")
    ax.set_title("A significant Granger test does not guarantee better forecasts", loc="left")
    ax.legend(loc="upper right")
    return _save(fig, name)


def selection_matrix(evidence: pd.DataFrame, targets: list[str], horizons: list[int],
                     name: str = "03_selected_features"):
    used = evidence[evidence["decision"].isin(["kept", "shortlist"])]
    feats = list(dict.fromkeys(used.sort_values("group", ascending=False)["feature"]))
    rows = [(t, h) for t in targets for h in horizons]
    fig, ax = plt.subplots(figsize=(1.0 + 0.55 * len(feats), 0.24 * len(rows) + 1.6))
    for i, (t, h) in enumerate(rows):
        for j, f in enumerate(feats):
            r = evidence[(evidence.target == t) & (evidence.horizon == h) & (evidence.feature == f)]
            if r.empty:
                continue
            dec = r["decision"].iloc[0]
            if dec == "kept":
                ax.scatter(j, i, s=70, color=BLUE, zorder=3)
            elif dec == "shortlist":
                ax.scatter(j, i, s=70, facecolor=SURFACE, edgecolor=ORANGE, linewidth=1.6, zorder=3)
    ax.set_xticks(range(len(feats)), feats, rotation=60, ha="right")
    ax.set_yticks(range(len(rows)), [f"{TARGET_NAMES[t]}  {h}m" for t, h in rows])
    for i in range(0, len(rows), len(horizons)):
        ax.axhline(i - 0.5, color=GRID, lw=0.8)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.grid(False)
    ax.scatter([], [], s=70, color=BLUE, label="selected (passed every check)")
    ax.scatter([], [], s=70, facecolor=SURFACE, edgecolor=ORANGE, linewidth=1.6,
               label="shortlist (helped, but not robust)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.0 + 1.2 / len(rows)), ncol=2)
    return _save(fig, name)


def skill_heatmap(skill: pd.DataFrame, targets: list[str], horizons: list[int],
                  name: str = "04_gain_vs_historical_quantiles"):
    m = skill.pivot(index="target", columns="horizon", values="gain_vs_hist_quantiles").reindex(targets)
    v = -100 * m.to_numpy(float)
    fig, ax = plt.subplots(figsize=(4.6, 6.2))
    ax.imshow(v, cmap=BLUES, vmin=0, vmax=30, aspect="auto")
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            txt = "–" if v[i, j] == 0 else f"{v[i, j]:.0f} %"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8,
                    color="white" if v[i, j] > 18 else INK)
    ax.set_xticks(range(len(horizons)), [f"{h} months" for h in horizons])
    ax.set_yticks(range(len(targets)), [TARGET_NAMES[t] for t in targets])
    ax.grid(False)
    ax.set_title("Backtest loss reduction from the\nselected features (vs historical quantiles)",
                 loc="left")
    return _save(fig, name)


def driver_examples(tables: dict, examples: list[tuple], end: str, name: str = "05_driver_examples"):
    """Scatter of a feature (x) against the H-month change that followed (y)."""
    fig, axes = plt.subplots(1, len(examples), figsize=(4.4 * len(examples), 3.4))
    for ax, (t, h, f, xlabel) in zip(np.atleast_1d(axes), examples):
        d = tables[(t, h)]
        d = d[d["y"].notna() & (d["target_month"] <= pd.Timestamp(end))][[f, "y"]].dropna()
        ax.scatter(100 * d[f], 100 * d["y"], s=16, color=BLUE, alpha=0.75, edgecolor=SURFACE, lw=0.5)
        b = np.polyfit(d[f], d["y"], 1)
        xs = np.linspace(d[f].min(), d[f].max(), 50)
        ax.plot(100 * xs, 100 * np.polyval(b, xs), color=ORANGE, lw=1.8)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(f"{TARGET_NAMES[t]}: change over next {h} months (%)")
        rho = d[f].corr(d["y"], method="spearman")
        ax.set_title(f"{TARGET_NAMES[t]}, {h} months (rank corr. {rho:.2f})", loc="left")
    fig.tight_layout()
    return _save(fig, name)
