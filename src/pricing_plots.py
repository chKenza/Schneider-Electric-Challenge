"""Charts for the Step 9 report. Each function saves a PNG in plots/step9/ and returns the figure.

Run after `uv run python -m src.pricing`:
    uv run python -m src.pricing_plots
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.feature_plots import AQUA, BLUE, INK2, MUTED, ORANGE, set_style

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step9"
MAIN = ["RM6", "AirSeT epoxy low, nickel check"]
COLOR = {"RM6": ORANGE, "AirSeT epoxy low, nickel check": BLUE}
H_STYLE = {3: ":", 6: "--", 9: "-"}


def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def buffer_vs_breach(curve: pd.DataFrame, steel="PPI", name="01_buffer_vs_breach"):
    """The competitiveness trade-off: a bigger buffer is breached less often."""
    set_style()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    d = curve[curve.steel == steel]
    for case in MAIN:
        for h, ls in H_STYLE.items():
            c = d[(d.case == case) & (d.horizon_m == h)]
            ax.plot(c.buffer_pts, 100 * c.p_breach, ls=ls, color=COLOR[case], label=f"{case}, {h} m")
    ax.axhline(10, color=MUTED, lw=0.8)
    ax.set(xlabel="buffer added to the price (margin points)", ylabel="chance the loss exceeds it (%)")
    ax.legend(frameon=False, fontsize=7)
    return _save(fig, name)


def strategy_comparison(sim: pd.DataFrame, hist: pd.DataFrame, h=9, steel="PPI",
                        name="02_strategy_comparison"):
    """P95 margin points lost per strategy, simulated vs historical paths, h-month quotes."""
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), sharex=True)
    for ax, case in zip(axes, MAIN):
        s = sim.query("case == @case and steel == @steel and horizon_m == @h").set_index("strategy")
        hi = hist.query("case == @case and steel == @steel and horizon_m == @h").set_index("strategy")
        t = pd.DataFrame({"simulated": s.p95_pts, "historical (2018 →)": hi.p95_pts}).iloc[::-1]
        t.plot.barh(ax=ax, color=[BLUE, AQUA], width=0.75, legend=case == MAIN[0])
        ax.axvline(0, color=MUTED, lw=0.8)
        ax.set(title=case, xlabel=f"margin points lost, P95, {h}-month quote", ylabel="")
    if axes[0].get_legend():
        axes[0].legend(frameon=False, fontsize=7)
    return _save(fig, name)


def margin_backtest_plot(bt: pd.DataFrame, name="03_margin_backtest"):
    """Sticky prices: RM6 cost shocks squeeze the margin for about a year."""
    set_style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3))
    a.plot(bt.year, 100 * bt.selling_price_eur / bt.selling_price_eur.iloc[0], color=INK2, label="selling price")
    a.plot(bt.year, 100 * bt.rm_cost_eur / bt.rm_cost_eur.iloc[0], color=ORANGE, label="RM6 raw-material cost")
    a.set(ylabel="index (2018 = 100)")
    a.legend(frameon=False)
    b.bar(bt.year, bt.margin_pts_vs_2018, color=[ORANGE if v < 0 else BLUE for v in bt.margin_pts_vs_2018])
    b.axhline(0, color=MUTED, lw=0.8)
    b.set(ylabel="margin points vs 2018")
    return _save(fig, name)


def outlook_plot(outlook: pd.DataFrame, name="04_outlook_2027"):
    """RM6 vs AirSeT raw-material cost to mid-2027 (P10-P90 band, P50 line), € per unit."""
    set_style()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for case in MAIN:
        c = outlook[outlook.case == case].sort_values("horizon_m")
        x = ["2026-09"] + c.month.tolist()
        c0 = c.cost_today_eur.iloc[0]
        ax.fill_between(x, [c0] + c.cost_p10_eur.tolist(), [c0] + c.cost_p90_eur.tolist(),
                        color=COLOR[case], alpha=0.15)
        ax.plot(x, [c0] + c.cost_p50_eur.tolist(), color=COLOR[case], label=f"{case} (P50, P10-P90)")
    ax.set(ylabel="raw-material cost (€ per unit)")
    ax.legend(frameon=False)
    return _save(fig, name)


def main():
    from src.pricing import TABLE_DIR
    t = {n: pd.read_csv(TABLE_DIR / f"{n}.csv") for n in
         ["buffer_curve", "strategies_simulated", "strategies_historical", "margin_backtest", "outlook_2027"]}
    buffer_vs_breach(t["buffer_curve"])
    strategy_comparison(t["strategies_simulated"], t["strategies_historical"])
    margin_backtest_plot(t["margin_backtest"])
    outlook_plot(t["outlook_2027"])
    print(f"wrote 4 plots to {PLOT_DIR}/")


if __name__ == "__main__":
    main()