"""Charts for Problem 2 Step 9. Run after src.strategy:
    uv run python -m src.strategy_plots
"""
import matplotlib.pyplot as plt
import pandas as pd

from src.market_evidence import ROOT
from src.strategy import COST_PATHS, TABLE_DIR, YEARS, cost_path

PLOT_DIR = ROOT / "plots" / "problem2"

SEGMENT_COLORS = {
    "Australia colocation": "#1baf7a",
    "Johor-Singapore data centres": "#2a78d6",
    "Australia utilities": "#d6a12a",
    "Gulf data centres": "#eb6834",
}

# Roadmap phases: (label, start, end, row). Years are fractional for drawing.
ROADMAP = [
    ("Johor: AirTrunk lead deal", 2027.0, 2028.0, "Phase 1 - prove"),
    ("India: extend Tata Power / BSES utility orders into frameworks", 2027.0, 2031.0, "Phase 1 - prove"),
    ("Gulf: private DC framework deals, SEC pilot (volume, not margin)", 2027.0, 2031.0, "Phase 1 - prove"),
    ("Johor-Singapore: TCO-based price (~9 %), all operators", 2028.0, 2031.0, "Phase 2 - scale"),
    ("Utility fleets (Australia, Saudi Arabia, Japan): fleet pitch", 2028.5, 2031.0, "Phase 2 - scale"),
    ("US data-centre states, UK, if a trigger fires", 2029.0, 2031.0, "Phase 3 - extend"),
]


def window_opening_plot(w: pd.DataFrame) -> None:
    """AirSeT extra-cost paths vs the threshold below which each segment's window opens."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    styles = ["-", "--", ":"]
    for style, path in zip(styles, COST_PATHS):
        ax.plot(YEARS, cost_path(path).values, style, color="black", lw=1.6, label=path)
    thresholds = w.drop_duplicates("segment").set_index("segment").max_extra_cost_pct
    for seg, color in SEGMENT_COLORS.items():
        t = thresholds[seg]
        ax.axhline(t, color=color, lw=1.2)
        ax.text(YEARS[-1] + 0.05, t + 0.15, f"{seg} ({t:.1f} %)", color=color, fontsize=8,
                va="bottom")
    ax.set_xlim(YEARS[0] - 0.2, YEARS[-1] + 1.9)
    ax.set_ylim(0, 18)
    ax.set_xticks(YEARS)
    ax.set_ylabel("AirSeT extra unit cost vs RM6 (% of RM6 price)")
    ax.set_title("A segment opens when AirSeT's extra cost falls below its line\n"
                 "(paths are illustrative; start = 10 % placeholder)", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "12_window_opening.png", dpi=150)


def roadmap_plot() -> None:
    """One-slide roadmap, 2027-2030."""
    fig, ax = plt.subplots(figsize=(9, 3.4))
    phase_color = {"Phase 1 - prove": "#2a78d6", "Phase 2 - scale": "#1baf7a",
                   "Phase 3 - extend": "#9b9b9b"}
    for i, (label, start, end, phase) in enumerate(reversed(ROADMAP)):
        ax.barh(i, end - start, left=start, color=phase_color[phase], alpha=0.75)
        ax.text(start + 0.05, i, label, va="center", fontsize=8, color="white")
    for phase, c in phase_color.items():
        ax.barh(-10, 0, color=c, label=phase)
    ax.set_ylim(-0.6, len(ROADMAP) - 0.4)
    ax.set_yticks([])
    ax.set_xticks([2027, 2028, 2029, 2030, 2031], ["2027", "2028", "2029", "2030", ""])
    ax.set_xlim(2027, 2031)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)
    ax.set_title("RM AirSeT voluntary-switch roadmap", fontsize=10)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "13_roadmap.png", dpi=150)


def main() -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    window_opening_plot(pd.read_csv(TABLE_DIR / "window_opening.csv"))
    roadmap_plot()
    print(f"Charts written to {PLOT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
