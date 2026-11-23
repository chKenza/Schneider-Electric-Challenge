"""Charts for the Step 6 report. Each function saves a PNG in plots/step6/ and returns the figure.

Style and colours are the Step 4 ones (src/feature_plots.py): blue = the final model,
orange = the random walk (the reference) or a miss, aqua = a third series, muted = others.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.feature_plots import AQUA, BAND, BLUE, INK, INK2, MUTED, ORANGE, TARGET_NAMES

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step6"
GROUP_COLOR = {"ppi": BLUE, "market": AQUA, "epoxy": MUTED}
GROUP_LABEL = {"ppi": "Producer price indices", "market": "Market prices", "epoxy": "Epoxy"}


def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def variance_ratio(vr: pd.DataFrame, name: str = "01_variance_ratio"):
    """Bar per target: variance of 9-month changes / (9 x variance of monthly changes).
    1 = independent months (sqrt(H) scaling is right); > 1 = momentum (sqrt(H) too narrow)."""
    d = vr.sort_values("ratio")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.barh([TARGET_NAMES[t] for t in d["target"]], d["ratio"],
            color=[GROUP_COLOR[g] for g in d["group"]], height=0.62)
    ax.axvline(1, color=INK2, lw=1, ls="--")
    ax.text(1.03, -0.9, "1 = sqrt(H) scaling is right", color=INK2, fontsize=8, va="bottom")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=GROUP_LABEL[g]) for g, c in GROUP_COLOR.items()],
              loc="lower right")
    ax.set_xlabel("variance of 9-month changes / (9 x variance of monthly changes)")
    ax.set_title("Price indices move in trends: sqrt(H) bands would be far too narrow", loc="left")
    ax.grid(axis="y", visible=False)
    return _save(fig, name)


def skill_vs_coverage(summary: pd.DataFrame, final: str, name: str = "02_skill_vs_coverage"):
    """One dot per model, backtest: x = P10-P90 coverage (target 80 %), y = skill vs RW."""
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.axvspan(0.70, 0.90, color=BAND, zorder=0)
    ax.axvline(0.80, color=INK2, lw=0.8, ls="--")
    ax.axhline(0, color=INK2, lw=0.8)
    for model, r in summary.iterrows():
        color = BLUE if model == final else ORANGE if model == "random_walk" else MUTED
        size = 70 if color != MUTED else 34
        ax.scatter(r["coverage"], 100 * r["skill"], s=size, color=color, zorder=3,
                   edgecolor="white", linewidth=1.5)
        ax.annotate(model, (r["coverage"], 100 * r["skill"]), xytext=(5, 3),
                    textcoords="offset points", fontsize=7.5,
                    color=INK if color != MUTED else INK2)
    ax.set_xlabel("coverage of the 80 % band (backtest); shaded = acceptable (80 % +- 10)")
    ax.set_ylabel("pinball skill vs random walk (%)")
    ax.set_title("Backtest: volatility-scaled models and the combination lead", loc="left")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    return _save(fig, name)


def backtest_vs_holdout(df: pd.DataFrame, final: str, name: str = "03_backtest_vs_holdout"):
    """Dumbbell per model: open circle = backtest (where choices were made), filled dot =
    single hold-out evaluation."""
    d = df.sort_values("pinball_skill_vs_rw_holdout")
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    ax.axvline(0, color=INK2, lw=0.8)
    for i, (model, r) in enumerate(d.iterrows()):
        color = BLUE if model == final else ORANGE if model == "random_walk" else MUTED
        b, h = 100 * r["pinball_skill_vs_rw_backtest"], 100 * r["pinball_skill_vs_rw_holdout"]
        ax.plot([b, h], [i, i], color=color, lw=2, alpha=0.6)
        ax.scatter(b, i, s=46, facecolor="white", edgecolor=color, linewidth=1.8, zorder=3)
        ax.scatter(h, i, s=52, color=color, zorder=4)
    ax.set_yticks(y, d.index)
    ax.scatter([], [], s=46, facecolor="white", edgecolor=MUTED, linewidth=1.8, label="backtest")
    ax.scatter([], [], s=52, color=MUTED, label="hold-out (opened once)")
    ax.legend(loc="lower right")
    ax.set_xlabel("pinball skill vs random walk (%), mean over the cells each model covers "
                  "(45; features_scaled: 17)")
    ax.set_title("Most of the backtest edge disappears on the hold-out", loc="left")
    ax.grid(axis="y", visible=False)
    return _save(fig, name)


def holdout_coverage_width(m: pd.DataFrame, final: str, name: str = "04_holdout_coverage_width"):
    """Hold-out, by group and horizon: coverage (left) and band width (right),
    random walk vs final model."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    cells = [(g, h) for g in ["ppi", "market", "epoxy"] for h in (3, 6, 9)]
    x = np.arange(len(cells))
    labels = [f"{GROUP_LABEL[g].split()[0]} {h}m" for g, h in cells]
    for ax, metric, title in [(axes[0], "coverage_80", "Coverage of the 80 % band"),
                              (axes[1], "width_80", "Width of the 80 % band (% of price)")]:
        for k, (model, color, off) in enumerate([("random_walk", ORANGE, -0.18), (final, BLUE, 0.18)]):
            vals = [m[(m["model"] == model) & (m["grp"] == g) & (m["horizon"] == h)][metric].mean()
                    for g, h in cells]
            ax.bar(x + off, vals, width=0.34, color=color, label="random walk" if k == 0 else final)
        if metric == "coverage_80":
            ax.axhline(0.8, color=INK2, lw=1, ls="--")
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
            ax.set_ylim(0.5, 1.02)
        ax.set_xticks(x, labels, rotation=45, ha="right")
        ax.set_title(title, loc="left")
        ax.grid(axis="x", visible=False)
    fig.suptitle("Hold-out: right coverage with much narrower bands", x=0.01, ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncols=2, bbox_to_anchor=(0.99, 1.0))
    return _save(fig, name)


def upside_tail(pred: pd.DataFrame, target: str, h: int, select_end: str,
                name: str = "05_upside_tail"):
    """Realised H-month change vs the final model's P10-P90 band and P95, over time;
    orange = outcome above P90."""
    d = pred[(pred["target"] == target) & (pred["horizon"] == h)].dropna(subset=["y"]).sort_values("origin")
    t = pd.to_datetime(d["target_month"])
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.fill_between(t, 100 * d["p10"], 100 * d["p90"], color="#c9ddf7", lw=0, label="P10-P90")
    ax.plot(t, 100 * d["p95"], color=BLUE, lw=1, ls="--", label="P95")
    ax.plot(t, 100 * d["y"], color=INK, lw=1.6, label="actual change")
    above = d["y"] > d["p90"]
    ax.scatter(t[above], 100 * d.loc[above, "y"], color=ORANGE, s=22, zorder=4, label="above P90")
    ax.axvline(pd.Timestamp(select_end), color=INK2, lw=0.8, ls=":")
    ax.text(pd.Timestamp(select_end), ax.get_ylim()[1], "  hold-out", color=INK2, fontsize=8, va="top")
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_ylabel(f"change over {h} months (%)")
    ax.set_xlabel("month the outcome is known (target month)")
    ax.set_title(f"{TARGET_NAMES[target]}, {h} months: the 2025-26 rally breaks the upper band",
                 loc="left")
    ax.legend(loc="upper left", ncols=4)
    return _save(fig, name)


def live_fan(live: pd.DataFrame, targets: list[str], name: str = "06_live_forecasts"):
    """Forecasts at the Sep 2026 origin as a price index (origin = 100): P10-P90 range and
    P50 per horizon, random walk (orange) vs final model (blue)."""
    fig, axes = plt.subplots(1, len(targets), figsize=(3.0 * len(targets), 3.6), sharey=True)
    for ax, t in zip(np.atleast_1d(axes), targets):
        for model, color, off in [("random_walk", ORANGE, -0.45), ("final", BLUE, 0.45)]:
            d = live[(live["target"] == t) & (live["model"] == model)].sort_values("horizon")
            x = d["horizon"] + off
            ax.vlines(x, d["index_p10"], d["index_p90"], color=color, lw=5, alpha=0.85)
            ax.scatter(x, d["index_p50"], color="white", edgecolor=color, s=26, zorder=3, linewidth=1.5)
        ax.axhline(100, color=MUTED, lw=0.6)
        ax.set_xticks([3, 6, 9], ["3 m", "6 m", "9 m"])
        ax.set_title(TARGET_NAMES[t], loc="left")
        ax.grid(axis="x", visible=False)
    np.atleast_1d(axes)[0].set_ylabel("price index, Sep 2026 = 100")
    np.atleast_1d(axes)[0].vlines([], [], [], color=ORANGE, lw=5, label="random walk P10-P90")
    np.atleast_1d(axes)[0].vlines([], [], [], color=BLUE, lw=5, label="final model P10-P90")
    np.atleast_1d(axes)[0].legend(loc="upper left")
    fig.tight_layout()
    return _save(fig, name)
