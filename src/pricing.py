"""Step 9 – define pricing rules and test different strategies

Run from the repo root, after `uv run python -m src.simulation` (Step 8):
    uv run python -m src.pricing


gives price adjustment, rsik buffer, quoatation validity and indexation clause per product and horizon. 

Margin points lost on a quote = 100 × (raw-material cost at delivery − cost at quote) ÷ selling price.
Positive = margin lost. Raw materials only; everything else is held constant.
The client gives no target margin, so the margin the business accepts losing
("tolerated erosion") is a decision variable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import cost_model as cm
from src.config import REPO_ROOT
from src.data_prep import OUT
from src.eda_cost import material_paths
from src.simulation import ALL_CASES, HORIZONS, material_ratios, selling_price, steel_market

TABLE_DIR = REPO_ROOT / "report" / "problem1" / "step9_tables"
ORIGIN = "2026-09"

# ---- decision variables and assumptions (all stated in the report) ----
TOLERATED_EROSION = [0.25, 0.5, 1.0, 2.0]  # margin points the business accepts losing
CONFIDENCE = [0.90, 0.95]
BUFFER_LEVELS = [0.75, 0.90, 0.95]          # buffer at P75 / P90 / P95 (P90 = main)
MAX_BUFFER_PTS = 1.0  # ASSUMPTION: largest uplift sales can add and stay competitive
TRIGGERS = [0.02, 0.05, 0.10, 0.15]  # indexation band on the indexed materials' cost
MAIN_TRIGGER = 0.05
SHORT_VALIDITY = 3   # "shorter validity" strategy: re-quote every 3 months
BUFFER_GRID = np.round(np.arange(0, 3.01, 0.1), 2)
STEELS = ["PPI", "market"]  # steel moves like the PPI (main) or like MEPS market prices
# Materials an indexation clause follows: copper for RM6; steel + stainless for AirSeT
# (Schneider already buys steel on MEPS / CRU indices).
INDEXED = {
    "RM6": ["Copper"],
    "AirSeT": ["Carbon steel DE", "Stainless steel", "Stainless base", "Stainless alloy surcharge"],
}
MAIN_CASES = ["RM6", "AirSeT epoxy low, nickel check"]  # TO CONFIRM with Karin
SCENARIOS = {"downside": 0.10, "baseline": 0.50, "upside": 0.90}
RM6_PRICE_2025 = 8740 #price benchmark


"""
helper functions
"""
def product(case: str) -> str:
    return "RM6" if case.startswith("RM6") else "AirSeT"


def points(delta: pd.DataFrame, price: float) -> pd.Series:
    """Margin points lost on each path (all materials)."""
    return delta.sum(axis=1) * 100 / price

def load_paths() -> pd.DataFrame:
    """Step 8 driver ratios: index (horizon_m, path), one column per driver."""
    return pd.read_csv(OUT / "simulated_driver_ratios.csv", index_col=["horizon_m", "path"])

def eur_changes(case: str, panel: pd.DataFrame, driver_ratios: pd.DataFrame):
    """eur change per material on each simulated path, and eur cost per material at the quote."""
    bd = cm.cost_breakdown(ALL_CASES[case], panel, ORIGIN)
    cost0 = bd.dropna(subset=["cost_eur"]).set_index("material")["cost_eur"]
    ratios = material_ratios(bd, driver_ratios.reset_index(drop=True))
    delta = ratios[cost0.index] * cost0 - cost0
    base = pd.DataFrame([cost0.to_numpy()] * len(delta), columns=cost0.index, index=delta.index)
    return delta, base

def build_sims(panel: pd.DataFrame, paths: pd.DataFrame) -> dict:
    """{(case, steel, h): (delta, base, price)}. Path i is the same path at every horizon,
    so the 3-month change of path i is the start of its 9-month change."""
    sims = {}
    for h in HORIZONS:
        ppi = paths.loc[h].reset_index(drop=True)
        ratios = {"PPI": ppi, "market": steel_market(ppi, panel, h, ORIGIN)}
        for steel in STEELS:
            for case in ALL_CASES:
                delta, base = eur_changes(case, panel, ratios[steel])
                sims[(case, steel, h)] = (delta, base, selling_price(case))
    return sims

def hedge_cost_rate(panel: pd.DataFrame, h: int) -> pd.Series:
    """Cost of buying copper forward for h months, as a share of the cash price, per month.

    LME 3-month − cash spread ÷ cash, scaled to h months. Negative (backwardation) = a gain.
    ASSUMPTION: the 3-month spread scales linearly to 6 and 9 months; no broker fees.
    """
    p = panel[["LME_CU_SPREAD_EUR", "LME_CU_CASH_EUR"]].dropna()
    return p["LME_CU_SPREAD_EUR"] / p["LME_CU_CASH_EUR"] * h / 3

def strategy_losses(delta: pd.DataFrame, base: pd.DataFrame, price: float, case: str,
                    buffers: dict, trigger: float, hedge_rate, short_delta=None) -> pd.DataFrame:
    """Margin points lost on each quote under each strategy (positive = loss).

    Same price path for every strategy: only the pricing mechanism changes.
      fixed price        today's practice: no protection (the reference)
      fixed + buffer Pxx price raised by the buffer at the quote (one column per level)
      indexation         the price follows the indexed materials' cost beyond ±trigger
                         (symmetric: the customer also gets falls beyond the band)
      copper hedge       copper bought forward at the quote (RM6 only)
      shorter validity   re-quoted every SHORT_VALIDITY months: only the first months'
                         change is lost (short_delta = € change over those months)
    """
    pts = 100 / price
    total = delta.sum(axis=1)
    out = {"fixed price": total * pts}
    for name, b in buffers.items():
        out[f"fixed + buffer {name}"] = total * pts - b

    cov = [m for m in INDEXED[product(case)] if m in delta.columns]
    cap = trigger * base[cov].sum(axis=1)
    covered = delta[cov].sum(axis=1)
    out["indexation"] = (total - covered + covered.clip(-cap, cap)) * pts

    if "Copper" in delta.columns:
        out["copper hedge"] = (total - delta["Copper"] + hedge_rate * base["Copper"]) * pts
    if short_delta is not None:
        out[f"validity {SHORT_VALIDITY} m"] = short_delta.sum(axis=1).to_numpy() * pts
    return pd.DataFrame(out)


def describe_losses(losses: pd.DataFrame) -> pd.DataFrame:
    """Per strategy: size and frequency of margin erosion, and the effect vs the fixed price."""
    fixed = losses["fixed price"]
    rows = []
    for s, x in losses.items():
        gain = fixed - x  # margin points kept vs today's practice, on the same path
        rows.append({
            "strategy": s,
            "mean_pts": x.mean(),
            "p90_pts": x.quantile(0.90),
            "p95_pts": x.quantile(0.95),
            "worst_pts": x.max(),
            "p_any_loss": (x > 0).mean(),
            **{f"p_loss_above_{e}": (x > e).mean() for e in TOLERATED_EROSION},
            "gain_vs_fixed_mean_pts": gain.mean(),
            "gain_vs_fixed_p10_pts": gain.quantile(0.10),
            "gain_vs_fixed_p90_pts": gain.quantile(0.90),
        })
    return pd.DataFrame(rows)


def buffers_from(sim_loss: pd.Series) -> dict:
    """Buffer at each level = that percentile of the simulated loss (Step 8 split: P50 + buffer)."""
    return {f"P{round(100 * q)}": max(0.0, sim_loss.quantile(q)) for q in BUFFER_LEVELS}


def simulated_strategies(sims: dict, panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rate = {h: hedge_cost_rate(panel, h).loc[:ORIGIN].iloc[-1] for h in HORIZONS}
    for (case, steel, h), (delta, base, price) in sims.items():
        short = sims[(case, steel, SHORT_VALIDITY)][0] if h > SHORT_VALIDITY else None
        losses = strategy_losses(delta, base, price, case, buffers_from(points(delta, price)),
                                 MAIN_TRIGGER, rate[h], short)
        rows.append(describe_losses(losses).assign(case=case, steel=steel, horizon_m=h))
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------- the decision rule
def scenario_table(sims: dict) -> pd.DataFrame:
    """Downside / baseline / upside (P10 / P50 / P90 of cost): € change and margin points."""
    rows = []
    for (case, steel, h), (delta, base, price) in sims.items():
        cost0 = base.iloc[0].sum()
        change = delta.sum(axis=1)
        for name, q in SCENARIOS.items():
            c = change.quantile(q)
            rows.append({"case": case, "steel": steel, "horizon_m": h, "scenario": name,
                         "cost_today_eur": cost0, "cost_eur": cost0 + c, "cost_change_eur": c,
                         "margin_pts_lost": 100 * c / price})
    return pd.DataFrame(rows)


def required_uplift(loss: pd.Series, erosion: float, conf: float) -> tuple[float, float]:
    """(price adjustment, risk buffer) in points so the loss stays ≤ erosion with prob. conf."""
    adjustment = max(0.0, loss.median())
    buffer = max(0.0, loss.quantile(conf) - erosion - adjustment)
    return adjustment, buffer


def clause_option(delta, base, price, case, erosion, conf) -> tuple[float, float] | None:
    """Widest indexation band whose remaining uplift fits under MAX_BUFFER_PTS,
    as (band, uplift). None if no band is enough."""
    options = []
    for t in TRIGGERS:
        loss = strategy_losses(delta, base, price, case, {}, t, 0)["indexation"]
        adj, buf = required_uplift(loss, erosion, conf)
        if adj + buf <= MAX_BUFFER_PTS:
            options.append((t, adj + buf))
    return max(options) if options else None


def quote_rule(sims: dict) -> pd.DataFrame:
    """One row per case × steel × horizon × tolerated erosion × confidence.

    Options are tried from the simplest for the customer to the most protective:
      1. fixed price + adjustment + buffer, if the uplift fits under MAX_BUFFER_PTS;
      2. indexation clause (widest band that works) + a smaller buffer;
      3. otherwise: shorten the validity (or hedge copper, for RM6).
    """
    rows = []
    for (case, steel, h), (delta, base, price) in sims.items():
        loss = points(delta, price)
        for e in TOLERATED_EROSION:
            for c in CONFIDENCE:
                adj, buf = required_uplift(loss, e, c)
                band, uplift = None, adj + buf
                if uplift <= MAX_BUFFER_PTS:
                    rec = "fixed price + buffer"
                elif (clause := clause_option(delta, base, price, case, e, c)) is not None:
                    band, uplift = clause
                    rec = f"indexation clause ±{band:.0%} + buffer"
                else:
                    rec = "shorter validity (or copper hedge for RM6)"
                rows.append({"case": case, "steel": steel, "horizon_m": h,
                             "tolerated_erosion_pts": e, "confidence": c,
                             "price_adjustment_pts": adj, "risk_buffer_fixed_pts": buf,
                             "indexation_band": band, "uplift_charged_pts": uplift,
                             "recommendation": rec})
    rule = pd.DataFrame(rows)
    keys = ["case", "steel", "tolerated_erosion_pts", "confidence"]
    fixed_ok = rule[rule["recommendation"] == "fixed price + buffer"]
    maxval = fixed_ok.groupby(keys)["horizon_m"].max().rename("max_fixed_validity_m")
    return rule.merge(maxval, on=keys, how="left")


def buffer_curve(sims: dict) -> pd.DataFrame:
    """Probability the loss exceeds the buffer, for buffers from 0 to 3 points."""
    rows = []
    for (case, steel, h), (delta, _, price) in sims.items():
        loss = points(delta, price)
        rows += [{"case": case, "steel": steel, "horizon_m": h, "buffer_pts": b,
                  "p_breach": (loss > b).mean()} for b in BUFFER_GRID]
    return pd.DataFrame(rows)


# ------------------------------------------------------- historical replay
def historical_strategies(panel: pd.DataFrame, sims: dict) -> pd.DataFrame:
    """Replay every past quote month with today's recipe and today's buffers.

    steel = "PPI": materials move with their Step 2 drivers; "market": with their own €/t
    series (MEPS / CRU steel). An illustration of how each strategy behaves on real paths
    (2021–22 shock, 2025–26 copper rally), not a test of the buffer: the buffer is
    today's, not the one the model would have given at each past date.
    """
    rows = []
    for case in MAIN_CASES:
        price = selling_price(case)
        for steel, drive in [("PPI", "driver"), ("market", "market")]:
            paths = material_paths(case, panel, ORIGIN, drive=drive)
            mats = [c for c in paths.columns if c not in ("rm_cost", "bom_index")]
            short = (paths[mats].shift(-SHORT_VALIDITY) - paths[mats])
            for h in HORIZONS:
                delta = (paths[mats].shift(-h) - paths[mats]).dropna()
                base = paths[mats].loc[delta.index]
                rate = hedge_cost_rate(panel, h).reindex(delta.index).fillna(0)
                sim_delta, _, sim_price = sims[(case, steel, h)]
                buffers = buffers_from(points(sim_delta, sim_price))
                s = short.loc[delta.index] if h > SHORT_VALIDITY else None
                losses = strategy_losses(delta, base, price, case, buffers, MAIN_TRIGGER, rate, s)
                rows.append(describe_losses(losses).assign(
                    case=case, steel=steel, horizon_m=h, n_quotes=len(delta),
                    first_quote=f"{delta.index[0]:%Y-%m}", last_quote=f"{delta.index[-1]:%Y-%m}"))
    return pd.concat(rows, ignore_index=True)


def margin_backtest(panel: pd.DataFrame) -> pd.DataFrame:
    """Schneider's yearly selling price vs RM6 raw-material cost, 2018–2025 (2026 excluded:
    SF6-ban price jump). Prices are sticky, so cost shocks squeeze the margin.

    Price in € = the Step 3 benchmark index (2018 = 100) scaled to €8,740 in 2025.
    Cost = yearly average RM6 raw-material cost (today's recipe, Step 2 drivers).
    Illustration only (8 yearly points, synthetic prices).
    """
    idx = pd.read_csv(REPO_ROOT / "report" / "problem1" / "step3_tables" / "price_vs_cost_index.csv",
                      index_col="year")["Schneider Electric"].loc[2018:2025]
    price = RM6_PRICE_2025 * idx / idx.loc[2025]
    cost = material_paths("RM6", panel, ORIGIN)["rm_cost"]
    cost = cost.groupby(cost.index.year).mean().reindex(price.index)
    out = pd.DataFrame({"selling_price_eur": price, "rm_cost_eur": cost})
    out["rm_share_of_price_pts"] = 100 * out.rm_cost_eur / out.selling_price_eur
    out["margin_pts_vs_2018"] = -(out.rm_share_of_price_pts - out.rm_share_of_price_pts.iloc[0])
    out["price_change_pct"] = 100 * out.selling_price_eur.pct_change()
    out["cost_change_pct"] = 100 * out.rm_cost_eur.pct_change()
    return out.rename_axis("year").reset_index()


# ----------------------------------------------------------- 2027 outlook
def outlook_2027(sims: dict, steel: str = "PPI") -> pd.DataFrame:
    """RM6 vs AirSeT raw-material cost to mid-2027 under the three scenarios, the price
    change that would keep today's margin, and the change in the gap between them."""
    months = {3: "2026-12", 6: "2027-03", 9: "2027-06"}
    rows = []
    for h in HORIZONS:
        costs = {}
        for case in MAIN_CASES:
            delta, base, price = sims[(case, steel, h)]
            cost0 = base.iloc[0].sum()
            costs[case] = (cost0, cost0 + delta.sum(axis=1))
            q = np.percentile(costs[case][1], [10, 50, 90])
            rows.append({"case": case, "horizon_m": h, "month": months[h], "cost_today_eur": cost0,
                         "cost_p10_eur": q[0], "cost_p50_eur": q[1], "cost_p90_eur": q[2],
                         **{f"price_change_to_hold_margin_{n}_pct": 100 * (v - cost0) / price
                            for n, v in zip(["p10", "p50", "p90"], q)}})
        (r0, rm6), (a0, air) = costs[MAIN_CASES[0]], costs[MAIN_CASES[1]]
        gap_change = (rm6 - air) - (r0 - a0)  # > 0: RM6's cost rose more than AirSeT's
        q = np.percentile(gap_change, [10, 50, 90])
        rows.append({"case": "RM6 − AirSeT gap change", "horizon_m": h, "month": months[h],
                     "cost_p10_eur": q[0], "cost_p50_eur": q[1], "cost_p90_eur": q[2],
                     "p_rm6_rises_more": (gap_change > 0).mean()})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- run
def main() -> None:
    panel = cm.load_panel()
    sims = build_sims(panel, load_paths())

    tables = {
        "scenarios": scenario_table(sims),
        "quote_rule": quote_rule(sims),
        "strategies_simulated": simulated_strategies(sims, panel),
        "strategies_historical": historical_strategies(panel, sims),
        "buffer_curve": buffer_curve(sims),
        "margin_backtest": margin_backtest(panel),
        "outlook_2027": outlook_2027(sims),
    }
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(TABLE_DIR / f"{name}.csv", index=False, float_format="%.4g")

    pd.set_option("display.width", 220)
    rule = tables["quote_rule"].query("case in @MAIN_CASES and steel == 'PPI' and confidence == 0.9")
    print(rule[["case", "horizon_m", "tolerated_erosion_pts", "uplift_charged_pts",
                "recommendation", "max_fixed_validity_m"]].round(2).to_string(index=False))
    print(f"wrote {len(tables)} tables to {TABLE_DIR}/")


if __name__ == "__main__":
    main()