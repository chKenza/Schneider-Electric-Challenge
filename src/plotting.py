"""Matplotlib charts for the EDA. Every function saves a PNG to the plots folder and returns the figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from src.data_loading import SERIES_LABELS, SHORT

# Validated categorical order (light mode) – assigned in fixed order, never cycled.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
REGIME_FILL = "#f0efec"
REGIME_FILLS = ["#ecebe6", "#f5f4f0"]  # alternating so adjacent regimes stay distinguishable

# Fixed colour per material family (colour follows the entity in every chart)
MATERIAL_COLORS = {
    "copper": SERIES[0], "stainless": SERIES[1], "carbon_steel": SERIES[2], "galvanised": SERIES[3],
    "aluminium": SERIES[4], "plastics": SERIES[5], "epoxy": SERIES[6], "brass": SERIES[7],
}


def material_family(name: str) -> str:
    n = name.lower()
    for key, fam in [("copper", "copper"), ("stainless", "stainless"), ("carbon", "carbon_steel"),
                     ("hdg", "galvanised"), ("galvan", "galvanised"), ("alu", "aluminium"),
                     ("epoxy", "epoxy"), ("brass", "brass"), ("pbt", "plastics"), ("pet", "plastics"), ("etp", "plastics")]:
        if key in n:
            return fam
    return "other"


def regime_caption(regimes: dict) -> str:
    return "Shaded: " + " | ".join(f"{k} {a}→{b}" for k, (a, b) in regimes.items())
DIVERGING = LinearSegmentedColormap.from_list("blue_gray_red", ["#184f95", "#6da7ec", "#f0efec",
                                                                "#ec835a", "#b53b3a"])


def set_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.labelsize": 9,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "lines.linewidth": 1.6, "legend.frameon": False, "legend.fontsize": 8,
        "font.size": 9, "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
        "axes.prop_cycle": plt.cycler(color=SERIES),
    })


def _save(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png")
    return fig


def _shade_regimes(ax, regimes: dict, label: bool = False) -> None:
    for i, (name, (a, b)) in enumerate(regimes.items()):
        a, b = pd.Timestamp(a), pd.Timestamp(b) + pd.offsets.MonthEnd(0)
        ax.axvspan(a, b, color=REGIME_FILLS[i % 2], zorder=0, lw=0)


def _grid(n: int, ncols: int = 3, h: float = 2.3, w: float = 4.0):
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(w * ncols, h * nrows), squeeze=False)
    for ax in axes.flat[n:]:
        ax.set_visible(False)
    return fig, axes.flat


# --------------------------------------------------------------------------- 3.1
def price_history(panel, cols, regimes, out_dir, name="01_price_history"):
    fig, axes = _grid(len(cols))
    for i, (ax, c) in enumerate(zip(axes, cols)):
        s = panel[c].dropna()
        ax.plot(s.index, s.values, color=SERIES[0])
        ax.set_title(SERIES_LABELS[c], loc="left")
        _shade_regimes(ax, regimes, label=(i == 0))
        last = s.index[-1]
        ax.annotate(f"{s.iloc[-1]:,.0f}  ({last:%b %y})", (last, s.iloc[-1]), fontsize=7,
                    color=INK2, ha="right", va="bottom", xytext=(0, 4), textcoords="offset points")
    fig.suptitle("Price levels. " + regime_caption(regimes), x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def returns_grid(rets, cols, regimes, out_dir, name="02_log_returns"):
    fig, axes = _grid(len(cols))
    for ax, c in zip(axes, cols):
        r = 100 * rets[c].dropna()
        ax.bar(r.index, r.values, width=25, color=np.where(r.values >= 0, SERIES[0], SERIES[7]))
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_title(f"{SHORT[c]} – monthly log-return (%)", loc="left")
        _shade_regimes(ax, regimes)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def h_change_hist(panel, cols, horizons, out_dir, name="03_h_month_change_distributions"):
    from src.eda import h_month_changes
    fig, axes = _grid(len(cols))
    for ax, c in zip(axes, cols):
        allv = np.concatenate([100 * h_month_changes(panel, c, h).values for h in horizons])
        bins = np.linspace(np.percentile(allv, 0.5), np.percentile(allv, 99.5), 30)
        for j, h in enumerate(horizons):
            ch = 100 * h_month_changes(panel, c, h)
            ax.hist(ch, bins=bins, histtype="step", lw=1.8, color=SERIES[j], label=f"H = {h}m")
            ax.axvline(ch.quantile(0.95), color=SERIES[j], lw=1, ls="--")
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.set_title(f"{SHORT[c]} – H-month change (%)", loc="left")
    axes[0].legend(loc="upper left")
    fig.suptitle("Distribution of H-month price changes (dashed = 95th percentile)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def ppi_vs_market(panel, pairs, regimes, out_dir, base="2017-01", name="04_ppi_vs_market"):
    fig, axes = _grid(len(pairs), ncols=2, w=5.5)
    for ax, (mkt, ppi) in zip(axes, pairs):
        d = panel[[mkt, ppi]].dropna()
        d = 100 * d / d.loc[pd.Timestamp(base)]
        ax.plot(d.index, d[mkt], color=SERIES[0], label=f"{SHORT[mkt]} (market)")
        ax.plot(d.index, d[ppi], color=SERIES[1], label=f"{SHORT[ppi]}")
        ax.set_title(f"{SHORT[mkt]} vs {SHORT[ppi]} (Jan 2017 = 100)", loc="left")
        ax.legend(loc="upper left")
        _shade_regimes(ax, regimes)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def rolling_vol_plot(rv, cols, regimes, out_dir, name="05_rolling_volatility"):
    groups = [cols[i:i + 3] for i in range(0, len(cols), 3)]
    fig, axes = _grid(len(groups), ncols=2, w=5.5, h=2.6)
    for ax, g in zip(axes, groups):
        for j, c in enumerate(g):
            s = rv[c].dropna()
            ax.plot(s.index, s.values, color=SERIES[j], label=SHORT[c])
        ax.legend(loc="upper left")
        ax.set_ylabel("ann. vol (%)")
        _shade_regimes(ax, regimes)
    fig.suptitle("Rolling 12-month volatility of monthly log-returns", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def acf_squared(rets, cols, out_dir, lags=12, name="06_acf_squared_returns"):
    fig, axes = _grid(len(cols), ncols=3, h=2.0)
    for ax, c in zip(axes, cols):
        r = rets[c].dropna()
        r2 = (r - r.mean()) ** 2
        acf = [r2.autocorr(k) for k in range(1, lags + 1)]
        ax.bar(range(1, lags + 1), acf, color=SERIES[0], width=0.6)
        band = 1.96 / np.sqrt(len(r2))
        ax.axhspan(-band, band, color=REGIME_FILL, zorder=0)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_title(f"{SHORT[c]} – ACF of r²", loc="left")
        ax.set_ylim(-0.4, 0.8)
    fig.suptitle("Autocorrelation of squared returns (grey band = ±1.96/√n)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, out_dir, name)


# --------------------------------------------------------------------------- 3.2
def corr_heatmaps(full, stress, out_dir, stress_label, name="07_correlation_heatmap"):
    n = len(full)
    fig, axes = plt.subplots(1, 2, figsize=(2 * (0.42 * n + 2), 0.42 * n + 1.2))
    for ax, m, t in [(axes[0], full, "Full sample"), (axes[1], stress, f"Stress {stress_label}")]:
        im = ax.imshow(m.values, cmap=DIVERGING, vmin=-1, vmax=1)
        ax.set_xticks(range(n), m.columns, rotation=90)
        ax.set_yticks(range(n), m.index)
        ax.grid(False)
        for i in range(n):
            for j in range(n):
                v = m.values[i, j]
                if i != j and abs(v) >= 0.4:
                    ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6,
                            color="white" if abs(v) > 0.7 else INK)
        ax.set_title(f"{t} – monthly log-returns", loc="left")
    fig.colorbar(im, ax=axes, shrink=0.7, label="Pearson correlation")
    return _save(fig, out_dir, name)


def lead_lag_plot(ll, n, out_dir, name="08_lead_lag"):
    fig, axes = _grid(len(ll), ncols=3, h=2.0)
    band = 1.96 / np.sqrt(n)
    for ax, (pair, row) in zip(axes, ll.iterrows()):
        cols = [SERIES[0] if abs(v) > band else "#b7d3f6" for v in row.values]
        ax.bar(row.index, row.values, color=cols, width=0.6)
        ax.axhspan(-band, band, color=REGIME_FILL, zorder=0)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_title(pair, loc="left", fontsize=9)
        ax.set_ylim(-0.5, 1.0)
        ax.set_xlabel("leader shifted by k months")
    fig.suptitle("Lead–lag: corr(Δleader at t−k, Δfollower at t); dark = outside ±1.96/√n",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, out_dir, name)


# --------------------------------------------------------------------------- 3.3
def cost_stack(costs: dict, regimes, out_dir, name="09_unit_rm_cost_history"):
    fig, axes = plt.subplots(1, len(costs), figsize=(5.4 * len(costs), 3.4), squeeze=False)
    for ax, (prod, df) in zip(axes.flat, costs.items()):
        mats = [c for c in df.columns if c not in ("rm_cost", "bom_index", "non_rm", "unit_cost")]
        order = df[mats].mean().sort_values(ascending=False).index
        ax.stackplot(df.index, *[df[m] for m in order], labels=[m.replace("_", " ") for m in order],
                     colors=[MATERIAL_COLORS[material_family(m)] for m in order],
                     edgecolor=SURFACE, linewidth=0.8)
        ax.set_title(f"{prod} – raw-material basket (€ per unit)", loc="left")
        ax.legend(loc="upper left", ncol=2)
        _shade_regimes(ax, regimes)
        ax.set_ylim(0, df["rm_cost"].max() * 1.35)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def cost_change_hist(costs: dict, horizons, out_dir, name="10_unit_cost_change_distributions"):
    fig, axes = plt.subplots(1, len(costs), figsize=(5.5 * len(costs), 3.0), squeeze=False, sharey=True)
    for ax, (prod, df) in zip(axes.flat, costs.items()):
        vals = {h: 100 * (df["unit_cost"].shift(-h) / df["unit_cost"] - 1).dropna() for h in horizons}
        lo = min(v.min() for v in vals.values())
        hi = max(v.max() for v in vals.values())
        bins = np.linspace(lo, hi, 28)
        for j, h in enumerate(horizons):
            ax.hist(vals[h], bins=bins, histtype="step", lw=1.8, color=SERIES[j], label=f"H = {h}m")
            ax.axvline(vals[h].quantile(.95), color=SERIES[j], ls="--", lw=1)
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.set_title(f"{prod} – H-month change of unit cost (%)", loc="left")
        ax.legend()
    fig.tight_layout()
    return _save(fig, out_dir, name)


def risk_contribution_plot(contribs: dict, out_dir, name="11_risk_contribution"):
    """contribs: {panel title: DataFrame}, each with index = (case, H) and one column per
    material (shares summing to 1). Materials are grouped into families so that each family
    keeps one fixed colour across panels (e.g. stainless base + surcharge = stainless).
    """
    fams = {t: c.T.groupby(lambda m: material_family(m)).sum().T for t, c in contribs.items()}
    used = [f for f in MATERIAL_COLORS if any(f in d.columns and d[f].abs().sum() > 0 for d in fams.values())]
    n = max(len(d) for d in fams.values())
    fig, axes = plt.subplots(1, len(fams), figsize=(6.4 * len(fams), 0.42 * n + 1.8), squeeze=False)
    for ax, (title, fam) in zip(axes.flat, fams.items()):
        fam = fam.reindex(columns=used).fillna(0)
        labels = [f"{p}  H={h}m" for p, h in fam.index]
        left = np.zeros(len(fam))
        for f in used:
            v = fam[f].clip(lower=0).values * 100
            ax.barh(labels, v, left=left, color=MATERIAL_COLORS[f], label=f.replace("_", " "),
                    edgecolor=SURFACE, linewidth=1.5, height=0.7)
            for k, (x, w) in enumerate(zip(left, v)):
                if w >= 7:
                    ax.text(x + w / 2, k, f"{w:.0f}%", ha="center", va="center", fontsize=7,
                            color="white")
            left += v
        ax.set_xlim(0, 100)
        ax.grid(axis="y", visible=False)
        ax.set_title(title, loc="left")
        ax.set_xlabel("share of the variance of the H-month € change (%)")
        ax.invert_yaxis()
    handles, lbls = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, lbls, ncol=len(used), loc="lower center", bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("Which material drives raw-material cost risk? (Euler variance decomposition)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def margin_gamble_plot(gambles: dict, target, regimes, out_dir, name="12_margin_gamble"):
    """gambles: {product: {H: DataFrame from eda.margin_gamble}}."""
    fig, axes = plt.subplots(len(gambles), 1, figsize=(10, 2.8 * len(gambles)), squeeze=False, sharex=True)
    for ax, (prod, by_h) in zip(axes.flat, gambles.items()):
        for j, (h, g) in enumerate(by_h.items()):
            ax.plot(g.index, 100 * g["realised_margin"], color=SERIES[j], label=f"H = {h}m")
        ax.axhline(100 * target, color=INK, lw=1, ls="--")
        ax.text(ax.get_xlim()[0], 100 * target, " target", va="bottom", fontsize=7, color=INK2)
        ax.set_ylabel("realised margin (%)")
        ax.set_title(f"{prod} – margin realised if price fixed at signature month (x-axis) "
                     f"and material bought at delivery", loc="left")
        ax.legend(loc="lower left", ncol=3)
        _shade_regimes(ax, regimes)
    fig.tight_layout()
    return _save(fig, out_dir, name)


def price_vs_cost_plot(idx: pd.DataFrame, out_dir, name="13_selling_price_vs_cost"):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2), sharey=True)
    a = idx[["Schneider Electric", "RM6 RM basket", "RM6 unit cost"]]
    for j, c in enumerate(a.columns):
        axes[0].plot(a.index, a[c], marker="o", ms=4, color=SERIES[j], label=c)
    base = int(idx.index[0])
    axes[0].set_title(f"Schneider P50 selling price vs RM6 cost ({base} = 100)", loc="left")
    brands = [b for b in idx.columns if b not in ("RM6 RM basket", "RM6 unit cost")]
    eaton = "Eaton"
    others = [b for b in brands if b != eaton]
    axes[1].plot(idx.index, idx[others].mean(axis=1), marker="o", ms=4, color=SERIES[0],
                 label="SF6 brands (mean of 5)")
    axes[1].plot(idx.index, idx[eaton], marker="o", ms=4, color=SERIES[1], label="Eaton (SF6-free)")
    axes[1].set_title(f"Selling-price P50 by insulation technology ({base} = 100)", loc="left")
    for ax in axes:
        ax.legend(loc="upper left")
        ax.axvline(2025.5, color=MUTED, ls=":", lw=1)
    return _save(fig, out_dir, name)
