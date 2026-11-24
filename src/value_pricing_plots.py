"""Charts for Problem 2 Step 7. Run after src.value_pricing:
    uv run python -m src.value_pricing_plots
"""
import matplotlib.pyplot as plt
import pandas as pd

from src.market_evidence import ROOT
from src.value_pricing import EXTRA_COST_BASE, TABLE_DIR

PLOT_DIR = ROOT / "plots" / "problem2"


def price_window_plot(w: pd.DataFrame) -> None:
    """Per segment: the premium range where both the customer and Schneider win."""
    d = w[w.extra_cost_pct == EXTRA_COST_BASE].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    for i, r in d.iterrows():
        color = "#1baf7a" if r.window_open else "#eb6834"
        ax.plot([r.floor_pct, r.ceiling_pct], [i, i], color=color, lw=8, alpha=0.6)
        ax.plot(r.floor_pct, i, "|", color="black", ms=18)
        ax.plot(r.ceiling_pct, i, "o", color="black")
    ax.axvline(22, ls="--", color="grey")
    ax.text(21.7, -0.4, "today's premium 22 %", fontsize=8, color="grey", ha="right")    
    ax.set_yticks(range(len(d)), d.segment)
    ax.set_xlabel("AirSeT premium over RM6 (%)")
    ax.set_title(f"Price window: | = lowest price for Schneider, ● = highest price for the customer\n"
                 f"(green = a price works for both; AirSeT extra cost {EXTRA_COST_BASE} %)", fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "10_price_window.png", dpi=150)


def options_plot(o: pd.DataFrame) -> None:
    """Each pricing option: what the customer saves vs what Schneider keeps."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for seg, d in o.groupby("segment"):
        ax.scatter(d.margin_vs_rm6_pts, -d.customer_tco_gap_eur, label=seg)
        for _, r in d.iterrows():
            ax.annotate(r.option.split(" (")[0], (r.margin_vs_rm6_pts, -r.customer_tco_gap_eur),
                        fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.axhline(0, color="grey", lw=0.8)
    ax.axvline(0, color="grey", lw=0.8)
    ax.set(xlabel="Schneider margin vs RM6 (points)",
           ylabel="customer lifetime saving with AirSeT (EUR)",
           title="Top right = both win")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "11_pricing_options.png", dpi=150)


def main() -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    price_window_plot(pd.read_csv(TABLE_DIR / "price_window.csv"))
    options_plot(pd.read_csv(TABLE_DIR / "pricing_options.csv"))
    print(f"Charts written to {PLOT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()