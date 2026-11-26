"""Chart for the Step 10 story: saves PNGs in plots/step10/.

Run after `uv run python -m src.story`:
    uv run python -m src.story_plots
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.feature_plots import AQUA, BLUE, INK2, MUTED, ORANGE, set_style
from src.story import HEADLINE_CASES, HEADLINE_STEEL, P1

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots" / "step10"
STRATEGIES = {  # strategy → (label, colour, line style)
    "fixed price": ("fixed price (today)", ORANGE, "-"),
    "fixed + buffer P90": ("fixed + P90 buffer", INK2, "--"),
    "validity 3 m": ("re-quote every 3 months", AQUA, ":"),
    "indexation": ("indexation clause ±5 %", BLUE, "-"),
}


def validity_vs_loss(hist: pd.DataFrame, steel=HEADLINE_STEEL, name="01_validity_vs_loss"):
    """Worst-5 % margin loss on past quotes (2018 →) by validity: risk grows with validity, the clause caps it."""
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, (product, case) in zip(axes, HEADLINE_CASES.items()):
        d = hist[(hist.case == case) & (hist.steel == steel)]
        for strat, (label, color, ls) in STRATEGIES.items():
            c = d[d.strategy == strat].sort_values("horizon_m")
            if c.empty:
                continue
            ax.plot(c.horizon_m, c.p95_pts, color=color, ls=ls, marker="o", ms=3.5, label=label)
            last = c.iloc[-1]
            ax.annotate(f"{last.p95_pts:.1f}", (last.horizon_m, last.p95_pts), xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=7, color=color)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set(title=product, xticks=[3, 6, 9], xlabel="quote validity (months)", xlim=(2.5, 9.8))
    axes[0].set_ylabel("margin points lost, worst 5 % of past quotes")
    axes[0].legend(frameon=False, fontsize=7, loc="upper left")
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / f"{name}.png")
    return fig


def main():
    hist = pd.read_csv(P1 / "step9_tables" / "strategies_historical.csv")
    validity_vs_loss(hist)
    print(f"wrote 1 plot to {PLOT_DIR}/")


if __name__ == "__main__":
    main()
