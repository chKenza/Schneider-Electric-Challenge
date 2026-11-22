"""Problem 2, Step 3: score the voluntary data-centre markets and pick targets.

Every criterion is computed from the sourced market-evidence CSVs
(src/market_evidence.py); nothing is typed in by hand. Each criterion is
scaled to 0-1 (1 = more attractive for an AirSeT push), the weights are
explicit, and `sensitivity()` checks that the ranking does not flip under
reasonable weight changes.

    uv run python src/market_scoring.py      # prints the ranking, writes tables + chart
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from src.market_evidence import ROOT, MarketEvidence, _ids
except ModuleNotFoundError:  # run as a script
    from market_evidence import ROOT, MarketEvidence, _ids

TABLE_DIR = ROOT / "report" / "problem2" / "01_tables"
PLOT_DIR = ROOT / "plots" / "problem2"

# criterion -> (weight, short description). Weights sum to 1.
CRITERIA = {
    "size":        (0.25, "Data-centre MW (operational + under construction), log scale"),
    "growth":      (0.15, "Inventory growth, % per year"),
    "regulation":  (0.15, "Regulatory trajectory: status 0 / 1 / 2 -> 0 / 0.5 / 1"),
    "sf6_cost":    (0.10, "SF6 cost reaching a data centre: priced 1, reporting 0.5, none 0"),
    "customer":    (0.15, "Customer pull: an operator counts SF6 there (0.5) + a utility switching voluntarily (0.5)"),
    "competition": (0.10, "Fewer SF6-free MV rivals present = higher"),
    "schneider":   (0.10, "Schneider already sells SF6-free MV there"),
}
WEIGHTS = {k: w for k, (w, _) in CRITERIA.items()}
EXCLUDED = {"US-FED": "sum of the US state rows (double count)"}  # reference markets are excluded by group
# Jurisdictions whose competitor and Schneider presence was researched (Step 1 Block F, Step 2):
# elsewhere "nothing found" means "not researched", so those criteria are scored neutral (0.5).
PRESENCE_RESEARCHED = {"US-FED", "JP", "IN", "MY", "SG", "AU", "AE", "SA"}


def _operators_counting_sf6(p2: MarketEvidence) -> set[str]:
    """Countries where a data-centre operator counts SF6 (AirTrunk: E85)."""
    c = p2.customers
    counts = c[(c.type.isin(["hyperscaler", "colocation"])) & (c.mentions_sf6 == "yes")
               & (c.sf6_policy_scope != "none")]
    # AirTrunk operates in Australia, Japan, Singapore, Malaysia, Hong Kong (E85)
    return {"AU", "JP", "SG", "MY"} if "airtrunk" in counts.index else set()


def _utilities_switching(p2: MarketEvidence) -> set[str]:
    """Countries where a utility buys SF6-free switchgear voluntarily (E126)."""
    hq = {"electranet": "AU", "chubu_pg": "JP", "kansai_td": "JP", "sec": "SA"}  # SCE excluded: forced by CA ban
    u = p2.customers[p2.customers.type == "utility"]
    return {hq[k] for k in u.index if k in hq}


def criteria_table(p2: MarketEvidence) -> pd.DataFrame:
    """One row per voluntary jurisdiction, raw inputs and 0-1 criterion scores."""
    land = p2.landscape()
    land = land[(land.group != "reference") & ~land.index.isin(list(EXCLUDED))].copy()
    ops, utils = _operators_counting_sf6(p2), _utilities_switching(p2)
    schneider = set(_ids(p2.competitors.loc["schneider", "sf6_free_sold_in"]))

    mw = land.dc_mw.fillna(0)
    logmw = np.log10(mw.clip(lower=100))                     # untracked markets sit at the floor
    out = pd.DataFrame(index=land.index)
    out["country"], out["region"], out["group"] = land.country, land.region, land.group
    out["dc_mw"], out["growth_pct"], out["rivals"] = land.dc_mw, land.dc_growth_pct, land.sf6_free_rivals
    out["growth_known"] = land.dc_growth_pct.notna()

    out["size"] = (logmw - logmw.min()) / (logmw.max() - logmw.min())
    g = land.dc_growth_pct
    out["growth"] = ((g - g.min()) / (g.max() - g.min())).fillna(0.5)  # unknown growth = neutral (flagged)
    out["regulation"] = (land.status.fillna(0) / 2).clip(upper=1)
    out["sf6_cost"] = land.sf6_pricing.map({"priced": 1.0, "reporting": 0.5}).fillna(0.0)
    out["customer"] = (0.5 * out.index.isin(list(ops)) + 0.5 * out.index.isin(list(utils))).astype(float)
    # US states inherit the presence recorded at US level (S&C, G&W, Eaton sell nationwide)
    full = p2.landscape()
    us = full.loc["US-FED", "sf6_free_rivals"]
    r = land.sf6_free_rivals.copy()
    r[r.index.str.startswith("US-")] = np.maximum(r[r.index.str.startswith("US-")], us)
    researched = pd.Series([c in PRESENCE_RESEARCHED or c.startswith("US-") or rv > 0 for c, rv in r.items()], index=r.index)
    out["rivals"], out["presence_known"] = r, researched
    out["competition"] = np.where(researched, 1 - r / max(r.max(), 1), 0.5)
    sch = pd.Series(out.index.isin(list(schneider)).astype(float), index=out.index)
    out["schneider"] = np.where(researched, sch, 0.5)
    return out


def score(crit: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    w = pd.Series(weights or WEIGHTS)
    w = w / w.sum()
    return (crit[w.index] * w).sum(axis=1).sort_values(ascending=False)


def sensitivity(crit: pd.DataFrame, n: int = 2000, concentration: float = 100.0, seed: int = 0) -> pd.DataFrame:
    """How stable is the ranking under reasonable weight changes?

    - 'Reasonable': n random weight sets drawn around the base weights
      (Dirichlet, mean = base weights; concentration 100 moves a 10 % weight
      by about +-30 %). Reported: 5th-95th percentile rank and the share of
      draws in the top 5.
    - Stress tests (reported separately): equal weights, and each criterion
      dropped in turn (worst rank over those 7 runs)."""
    rng = np.random.default_rng(seed)
    base = pd.Series(WEIGHTS)
    R = pd.concat([score(crit, dict(zip(base.index, w, strict=True))).rank(ascending=False)
                   for w in rng.dirichlet(base.values * concentration, size=n)], axis=1)
    equal = score(crit, dict.fromkeys(base.index, 1.0)).rank(ascending=False)
    drops = pd.concat([score(crit, {**WEIGHTS, k: 0.0}).rank(ascending=False) for k in base.index], axis=1)
    return pd.DataFrame({
        "base_rank": score(crit).rank(ascending=False),
        "rank_p05": R.quantile(0.05, axis=1), "rank_p95": R.quantile(0.95, axis=1),
        "top5_share": (R <= 5).mean(axis=1),
        "rank_equal_weights": equal, "worst_rank_drop_one": drops.max(axis=1),
    }).sort_values("base_rank")


def ranking(p2: MarketEvidence) -> pd.DataFrame:
    crit = criteria_table(p2)
    res = crit.join(score(crit).rename("score")).join(sensitivity(crit))
    return res.sort_values("score", ascending=False)


# ---------------------------------------------------------------- chart
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]  # slots 1-7
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#6b6a64", "#e6e5e0", "#fcfcfb"


def scoring_chart(res: pd.DataFrame, out: Path = PLOT_DIR) -> Path:
    res = res.iloc[::-1]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(10, 7.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    left = np.zeros(len(res))
    for (k, (w, _)), c in zip(CRITERIA.items(), COLORS, strict=True):
        vals = (res[k] * w).values
        ax.barh(range(len(res)), vals, left=left, color=c, height=0.62, edgecolor=SURFACE, linewidth=1, label=k)
        left += vals
    for i, (_, r) in enumerate(res.iterrows()):
        ax.text(r.score + 0.008, i, f"{r.score:.2f}   rank {r.rank_p05:.0f}–{r.rank_p95:.0f}",
                va="center", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(res)), [f"{c}" + ("" if g else " *") + ("" if pk else " †")
                                    for c, g, pk in zip(res.country, res.growth_known, res.presence_known, strict=True)],
                  color=INK)
    ax.set_xlim(0, 0.62)
    ax.set_xlabel("Weighted score (0 = least, 1 = most attractive for an AirSeT push)", color=INK)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    labels = [f"{k} ({w:.0%})" for k, (w, _) in CRITERIA.items()]
    ax.legend(labels=labels, loc="upper center", bbox_to_anchor=(0.45, -0.08), ncol=4, frameon=False, fontsize=8)
    fig.suptitle("Saudi Arabia, Malaysia, Australia and the UAE lead under every reasonable weighting",
                 x=0.02, ha="left", fontsize=12, color=INK)
    fig.text(0.02, 0.935, "Voluntary jurisdictions only (EU, Switzerland, California excluded). Rank range = 5th-95th percentile over "
             "2,000 weight sets\n(each weight moved about ±30 %).  * growth not published, † competitor presence not researched: "
             "scored as neutral (0.5).",
             fontsize=8, color=MUTED, va="top")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "03_target_market_scores.png"
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


if __name__ == "__main__":
    p2 = MarketEvidence.load()
    res = ranking(p2)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    res.round(3).to_csv(TABLE_DIR / "scoring_matrix.csv")
    pd.DataFrame([(k, w, d) for k, (w, d) in CRITERIA.items()], columns=["criterion", "weight", "measure"]).to_csv(
        TABLE_DIR / "criteria_weights.csv", index=False)
    print(scoring_chart(res))
    pd.set_option("display.width", 220)
    cols = ["country", "score", "size", "growth", "regulation", "sf6_cost", "customer", "competition", "schneider",
            "rank_p05", "rank_p95", "top5_share", "rank_equal_weights", "worst_rank_drop_one"]
    print(res[cols].round(2).to_string())
