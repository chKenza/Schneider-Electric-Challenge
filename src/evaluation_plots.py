"""Charts for the Step 7 report. Each function saves a PNG in plots/step7/ and returns the figure.

Style and colours are the Step 4 ones (src/feature_plots.py): blue = the final model,
orange = the random walk, aqua / ink for a third / fourth series, muted for others.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from src.feature_plots import AQUA, BAND, BLUE, INK, INK2, MUTED, ORANGE, set_style
from src.models import FINAL_MODEL

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step7"
H_COLOR = {3: BLUE, 6: AQUA, 9: INK2}
WINDOW_LABEL = {"backtest": "Backtest (Feb 2022 - Mar 2025)",
                "holdout": "Hold-out (Apr 2025 - Sep 2026)"}


def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def pit_histogram(pit: pd.DataFrame, model: str = FINAL_MODEL, name: str = "01_pit_histogram"):
    """Where outcomes fell relative to the final model's quantiles (5 bins), backtest and
    hold-out, per horizon. Bars = observed share, outline = expected share."""
    d = pit[pit["model"] == model]
    bins = ["below P10", "P10-P50", "P50-P90", "P90-P95", "above P95"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.2), sharey=True)
    for i, w in enumerate(["backtest", "holdout"]):
        for j, h in enumerate([3, 6, 9]):
            ax = axes[i, j]
            g = d[(d["window"] == w) & (d["horizon"] == h)].set_index("bin").reindex(bins)
            x = np.arange(len(bins))
            ax.bar(x, g["observed"], width=0.62, color=BLUE)
            ax.bar(x, g["expected"], width=0.62, fill=False, edgecolor=INK, lw=1.2, ls="--")
            ax.set_xticks(x, bins, rotation=35, ha="right", fontsize=7.5)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
            ax.set_title(f"{WINDOW_LABEL[w].split(' (')[0]}, {h} months (n = {int(g['n'].iloc[0])})",
                         loc="left")
            ax.grid(axis="x", visible=False)
    axes[0, 0].legend(handles=[Patch(color=BLUE, label="observed"),
                               Patch(fill=False, edgecolor=INK, ls="--", label="expected")],
                      loc="upper left")
    fig.suptitle("Where outcomes fell relative to the final model's quantiles", x=0.01,
                 ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, name)


def coverage_with_ci(cal: pd.DataFrame, models=("random_walk", FINAL_MODEL),
                     name: str = "02_coverage_ci"):
    """Coverage of the P10-P90 band (target 80 %) and one-sided P90 coverage (target 90 %),
    with 95 % block-bootstrap CIs, random walk vs final model, both windows."""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), sharey=False)
    colors = {"random_walk": ORANGE, FINAL_MODEL: BLUE}
    cells = [(w, h) for w in ["backtest", "holdout"] for h in (3, 6, 9)]
    x = np.arange(len(cells))
    for ax, (col, target, title) in zip(axes, [("coverage_80", 0.8, "Coverage of the P10-P90 band"),
                                                ("coverage_p90", 0.9, "Share of outcomes below P90")]):
        ax.axhline(target, color=INK2, lw=1, ls="--")
        ax.axvspan(2.5, 5.5, color=BAND, zorder=0)
        for k, m in enumerate(models):
            g = cal[cal["model"] == m].set_index(["window", "horizon"]).reindex(cells)
            off = -0.13 if k == 0 else 0.13
            ax.errorbar(x + off, g[col], yerr=[g[col] - g[f"{col}_lo"], g[f"{col}_hi"] - g[col]],
                        fmt="o", color=colors[m], ms=6, capsize=3, lw=1.4,
                        label="random walk" if m == "random_walk" else m)
        ax.set_xticks(x, [f"{h} m" for _, h in cells])
        ax.text(1, 1.005, "backtest", transform=ax.get_xaxis_transform(), ha="center", color=INK2, fontsize=8)
        ax.text(4, 1.005, "hold-out", transform=ax.get_xaxis_transform(), ha="center", color=INK2, fontsize=8)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.set_title(title, loc="left", pad=14)
        ax.grid(axis="x", visible=False)
    axes[0].legend(loc="lower left")
    fig.tight_layout()
    return _save(fig, name)


def subperiod_skill(sp: pd.DataFrame, models=(FINAL_MODEL, "gjr_fhs", "chronos_bolt"),
                    name: str = "03_subperiod_skill"):
    """Pinball skill vs the random walk by sub-period and horizon (describe, don't test)."""
    periods = list(dict.fromkeys(sp.sort_values("period")["period"]))
    periods = sorted(periods, key=lambda p: ("2022" not in p, "2023" not in p))
    colors = [BLUE, AQUA, MUTED]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.0), sharey=True)
    for ax, h in zip(axes, [3, 6, 9]):
        x = np.arange(len(periods))
        for k, m in enumerate(models):
            g = sp[(sp["model"] == m) & (sp["horizon"] == h)].set_index("period").reindex(periods)
            ax.bar(x + (k - 1) * 0.26, 100 * g["pinball_skill"], width=0.24, color=colors[k], label=m)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(x, [p.replace(" (", "\n(") for p in periods], fontsize=7.5)
        ax.set_title(f"{h} months", loc="left")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("pinball skill vs random walk (%)")
    axes[0].legend(loc="lower left")
    fig.suptitle("Skill by sub-period: the gain holds in 2022 and 2023-25, and fades in the hold-out", x=0.01,
                 ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, name)


def rolling_ratio(rr: pd.DataFrame, select_end: str = "2025-03-01", name: str = "04_rolling_loss_ratio"):
    """Rolling 12-month ratio of the final model's pinball loss to the random walk's, per
    horizon (Rossi, 2013 style). Below 1 = the final model is doing better."""
    fig, ax = plt.subplots(figsize=(10, 4.0))
    ax.axhline(1, color=INK2, lw=1)
    ax.axvspan(pd.Timestamp(select_end), rr["target_month"].max(), color=BAND, zorder=0)
    for h, g in rr.groupby("horizon"):
        ax.plot(g["target_month"], g["loss_ratio"], color=H_COLOR[h], lw=2, label=f"{h} months")
    ax.text(pd.Timestamp(select_end), ax.get_ylim()[1], "  hold-out", color=INK2, fontsize=8, va="top")
    ax.set_ylabel("final model loss / random-walk loss")
    ax.set_xlabel("target month (end of the 12-month window)")
    ax.set_title("Rolling 12-month loss ratio: below 1 = better than the random walk", loc="left")
    ax.legend(handles=[Line2D([], [], color=H_COLOR[h], lw=2, label=f"{h} months") for h in (3, 6, 9)],
              loc="upper left", ncols=3)
    return _save(fig, name)


def bom_skill(bj: pd.DataFrame, name: str = "05_bom_skill"):
    """BOM cost index forecast directly: pinball skill of the final model's recipe vs the
    random walk, with 95 % CI, per product, horizon and window."""
    d = bj[bj["model"] == FINAL_MODEL]
    products = ["RM6", "AirSeT"]
    fig, axes = plt.subplots(1, len(products), figsize=(12.5, 3.9), sharey=True)
    for ax, prod in zip(axes, products):
        for k, (w, color) in enumerate([("backtest", MUTED), ("holdout", BLUE)]):
            g = d[(d["product"] == prod) & (d["window"] == w)].set_index("horizon").reindex([3, 6, 9])
            x = np.arange(3) + (k - 0.5) * 0.36
            ax.bar(x, 100 * g["pinball_skill"], width=0.34, color=color,
                   label=WINDOW_LABEL[w].split(" (")[0])
            ax.errorbar(x, 100 * g["pinball_skill"],
                        yerr=[100 * (g["pinball_skill"] - g["pinball_skill_lo"]).fillna(0),
                              100 * (g["pinball_skill_hi"] - g["pinball_skill"]).fillna(0)],
                        fmt="none", ecolor=INK, capsize=3, lw=1)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(range(3), ["3 m", "6 m", "9 m"])
        ax.set_title(prod, loc="left")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("pinball skill vs random walk (%)")
    axes[0].legend(loc="upper left")
    fig.suptitle("BOM cost index: large gain for AirSeT, none for RM6 in the copper rally", x=0.01,
                 ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, name)


def causal_vs_hindsight_chart(cv: pd.DataFrame, name: str = "06_causal_vs_hindsight"):
    """Step 6 choices made with hindsight vs the same procedure re-run causally."""
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    cells = [("backtest", "mean_cell_skill"), ("holdout", "mean_cell_skill")]
    x = np.arange(len(cells))
    for k, (m, color, label) in enumerate([(FINAL_MODEL, MUTED, "Step 6 (choices with hindsight)"),
                                           ("causal_combo", BLUE, "choices from the past only")]):
        vals = [cv[(cv["window"] == w) & (cv["model"] == m)][c].iloc[0] for w, c in cells]
        bars = ax.bar(x + (k - 0.5) * 0.36, [100 * v for v in vals], width=0.34, color=color, label=label)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, 100 * v + 0.15, f"{100 * v:+.1f} %",
                    ha="center", fontsize=8, color=INK)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, ["Backtest", "Hold-out"])
    ax.set_ylabel("pinball skill vs random walk (%)\nmean over cells")
    ax.set_title("About 3.6 of the 8.5 backtest points were hindsight", loc="left")
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)
    return _save(fig, name)


def compute_chart(cf: pd.DataFrame, name: str = "07_compute"):
    """Run time of one full backtest per model (all targets, horizons and origins)."""
    d = cf[~cf["model"].str.startswith("TOTAL")].sort_values("wall_seconds")
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.barh(d["model"], d["wall_seconds"], color=BLUE, height=0.6)
    for y, (v, e) in enumerate(zip(d["wall_seconds"], d["energy_wh"])):
        ax.text(v + 1, y, f"{v:.0f} s, {e:.2f} Wh", va="center", fontsize=8, color=INK2)
    total = cf[cf["model"].str.startswith("TOTAL")].iloc[0]
    ax.set_xlabel("wall time of one full backtest run (s), Apple M2, 8-core CPU (4P + 4E), CPU only")
    ax.set_title(f"Compute: {total['wall_seconds'] / 60:.1f} min and {total['energy_wh']:.1f} Wh "
                 "for one full Step 5 + 6 run", loc="left")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, d["wall_seconds"].max() * 1.35)
    return _save(fig, name)


def make_all(out: dict[str, pd.DataFrame]) -> None:
    """Every Step 7 chart whose table is in `out` (some need --compute / --sensitivity)."""
    set_style()
    pit_histogram(out["pit_bins"])
    coverage_with_ci(out["calibration"])
    subperiod_skill(out["subperiods"])
    rolling_ratio(out["rolling_loss_ratio"])
    if "bom_jury_table" in out:
        bom_skill(out["bom_jury_table"])
    if "causal_vs_hindsight" in out:
        causal_vs_hindsight_chart(out["causal_vs_hindsight"])
    if "compute_footprint" in out:
        compute_chart(out["compute_footprint"])
    plt.close("all")


def from_saved_tables(table_dir: Path) -> dict[str, pd.DataFrame]:
    """The saved step7_tables, as the dict make_all expects (for the notebook)."""
    out = {}
    for f in sorted(Path(table_dir).glob("*.csv")):
        df = pd.read_csv(f)
        for c in ("origin", "target_month"):
            if c in df:
                df[c] = pd.to_datetime(df[c])
        out[f.stem] = df
    return out
