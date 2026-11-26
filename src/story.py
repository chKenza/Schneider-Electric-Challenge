"""Step 10 – one set of numbers for the story, the slides and the app

Run from the repo root, after Steps 7–9:
    uv run python -m src.story

Reads the committed Step 7, 8 and 9 tables (no confidential data needed) and writes
report/problem1/step10_tables/:
  - key_numbers.csv          every number the story and slides quote, with its source
  - margin_at_risk.csv       headline margin points at risk per product × horizon (both steel cases)
  - quote_rule_headline.csv  the quote rule at the headline settings (90 % and 95 % confidence)
  - consistency_checks.csv   cross-step checks (Step 8 vs Step 9 vs outlook)

Never type a number into the slides by hand: take it from key_numbers.csv. When the corrected
BOM (a_v1) arrives, rerun Steps 8–9 and then this module, and the story numbers update.
"""

from __future__ import annotations

import pandas as pd

from src.config import REPO_ROOT

P1 = REPO_ROOT / "report" / "problem1"
OUT_DIR = P1 / "step10_tables"

# ---- headline settings, agreed by the team (report/problem1/step10_story.md §0) ----
HEADLINE_CASES = {"RM6": "RM6", "AirSeT": "AirSeT, nickel check"}  # Step 9 main cases (BOM v1)
HEADLINE_STEEL = "market"  # MEPS-like spread: closer to what Schneider pays → the recommendation
CSV_STEEL = "PPI"          # the submission CSV forecasts the PPIs (S09, S10)
CONFIDENCE = 0.90
ACCEPTED_LOSS = 0.5        # margin points the business accepts losing (decision variable, Step 9)
HORIZONS = [3, 6, 9]
ALT_COPPER = ["RM6 copper 13.8 kg", "RM6 copper 8.6 kg"]  # "if the teardown is right"
FINAL_MODEL = "conformal_combo"   # Step 6 / 7 final model
BOM_MODEL = "step8_simulation"    # gives the CSV's BOM rows


def load_tables(p1=P1) -> dict[str, pd.DataFrame]:
    files = {
        "jury": "step7_tables/jury_table.csv",
        "bom_jury": "step7_tables/bom_jury_table.csv",
        "bom": "step8_tables/bom_index_and_margin_points.csv",
        "eur": "step8_tables/eur_per_material_p90.csv",
        "rule": "step9_tables/quote_rule.csv",
        "curve": "step9_tables/buffer_curve.csv",
        "hist": "step9_tables/strategies_historical.csv",
        "sim": "step9_tables/strategies_simulated.csv",
        "backtest": "step9_tables/margin_backtest.csv",
        "outlook": "step9_tables/outlook_2027.csv",
        "scen": "step9_tables/scenarios.csv",
    }
    return {k: pd.read_csv(p1 / f) for k, f in files.items()}


def one(df: pd.DataFrame, **filters) -> pd.Series:
    """The single row matching every filter; fails loudly if there is not exactly one."""
    mask = pd.Series(True, index=df.index)
    for col, val in filters.items():
        mask &= df[col] == val
    rows = df[mask]
    if len(rows) != 1:
        raise ValueError(f"expected 1 row for {filters}, got {len(rows)}")
    return rows.iloc[0]


class Numbers:
    """Collects key numbers with their unit and source, in the order the story uses them."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, key, value, unit, source, note="", product="", horizon_m=None, steel=""):
        self.rows.append({"key": key, "value": round(float(value), 4), "unit": unit, "product": product,
                              "horizon_m": horizon_m, "steel": steel, "source": source, "note": note})

    def frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.rows)
        if df.key.duplicated().any():
            raise ValueError(f"duplicate keys: {df.key[df.key.duplicated()].tolist()}")
        return df


# ---------------------------------------------------------------- sections of the story
def story_problem(t, n: Numbers) -> None:
    """Message 1: fixed prices are a margin bet (Step 9 margin backtest)."""
    bt = t["backtest"].set_index("year")
    src = "step9_tables/margin_backtest.csv"
    n.add("rm6_margin_pts_2022_vs_2018", bt.loc[2022, "margin_pts_vs_2018"], "margin pts", src,
          "fixed prices, no protection", "RM6")
    n.add("rm6_price_change_2018_2022", 100 * (bt.loc[2022, "selling_price_eur"] / bt.loc[2018, "selling_price_eur"] - 1),
          "%", src, "", "RM6")
    n.add("rm6_rm_cost_change_2018_2022", 100 * (bt.loc[2022, "rm_cost_eur"] / bt.loc[2018, "rm_cost_eur"] - 1),
          "%", src, "", "RM6")
    rm6 = one(t["bom"], case="RM6", steel=CSV_STEEL, horizon_m=9)
    air = one(t["bom"], case=HEADLINE_CASES["AirSeT"], steel=CSV_STEEL, horizon_m=9)
    src = "step8_tables/bom_index_and_margin_points.csv"
    for p, r in [("RM6", rm6), ("AirSeT", air)]:
        k = p.lower()
        n.add(f"{k}_rm_cost_today_eur", r.cost_today_eur, "EUR", src, "Sep 2026", p)
        n.add(f"{k}_selling_price_eur", r.selling_price_eur, "EUR", src,
              "benchmark P50 2025" if p == "RM6" else "ASSUMPTION: RM6 + 20 %", p)
        n.add(f"{k}_rm_share_of_price", 100 * r.cost_today_eur / r.selling_price_eur, "%", src, "", p)


def story_drivers(t, n: Numbers) -> None:
    """Message 2: RM6 is a copper bet, AirSeT a steel + stainless + copper bet (€ near P90, 9 months)."""
    e = t["eur"]
    src = "step8_tables/eur_per_material_p90.csv"
    for steel in [HEADLINE_STEEL, CSV_STEEL]:
        rm6 = e[(e.case == "RM6") & (e.steel == steel) & (e.horizon_m == 9)].set_index("material").eur_at_p90
        air = e[(e.case == HEADLINE_CASES["AirSeT"]) & (e.steel == steel) & (e.horizon_m == 9)].set_index("material").eur_at_p90
        steel_air = air[[m for m in air.index if "steel" in m.lower() or "stainless" in m.lower()]].sum()
        n.add(f"rm6_eur_copper_p90_9m_{steel}", rm6["Copper"], "EUR", src, "", "RM6", 9, steel)
        n.add(f"rm6_eur_total_p90_9m_{steel}", rm6.sum(), "EUR", src, "", "RM6", 9, steel)
        n.add(f"rm6_copper_share_p90_9m_{steel}", 100 * rm6["Copper"] / rm6.sum(), "%", src, "", "RM6", 9, steel)
        n.add(f"airset_eur_steel_stainless_p90_9m_{steel}", steel_air, "EUR", src,
              "carbon steel + stainless base + alloy surcharge", "AirSeT", 9, steel)
        n.add(f"airset_eur_nickel_surcharge_p90_9m_{steel}", air["Stainless alloy surcharge"], "EUR", src,
              "", "AirSeT", 9, steel)
        n.add(f"airset_eur_copper_p90_9m_{steel}", air["Copper"], "EUR", src, "BOM v1: 28.46 kg",
              "AirSeT", 9, steel)
        n.add(f"airset_copper_share_p90_9m_{steel}", 100 * air["Copper"] / air.sum(), "%", src, "",
              "AirSeT", 9, steel)
        n.add(f"airset_eur_total_p90_9m_{steel}", air.sum(), "EUR", src, "", "AirSeT", 9, steel)
        n.add(f"airset_steel_share_p90_9m_{steel}", 100 * steel_air / air.sum(), "%", src, "", "AirSeT", 9, steel)


def story_forecast(t, n: Numbers) -> None:
    """Message 3: the median is no better than 'no change'; the band is (Step 7)."""
    j = t["jury"][t["jury"].model == FINAL_MODEL]
    src = "step7_tables/jury_table.csv"
    for window in ["backtest", "holdout"]:
        for h in HORIZONS:
            r = one(j, window=window, horizon=h)
            n.add(f"pinball_skill_{window}_{h}m", 100 * r.pinball_skill, "%", src,
                  f"vs random walk, 95 % CI {100 * r.pinball_skill_lo:.1f} to {100 * r.pinball_skill_hi:.1f}; "
                  f"DM p = {r.dm_pinball_p_model_better:.3f}", "materials", h)
            n.add(f"coverage_80_{window}_{h}m", 100 * r.coverage_80, "%", src, "target 80 %", "materials", h)
    bt = j[j.window.isin(["backtest", "holdout"])]
    n.add("mae_skill_min", 100 * bt.mae_skill.min(), "%", src, "median vs 'no change', both windows", "materials")
    n.add("mae_skill_max", 100 * bt.mae_skill.max(), "%", src, "", "materials")
    b = t["bom_jury"]
    b = b[(b.model == BOM_MODEL) & (b.window == "holdout")]
    src = "step7_tables/bom_jury_table.csv"
    for h in [6, 9]:
        r = one(b, product="RM6", horizon=h)
        n.add(f"rm6_holdout_above_p90_{h}m", 100 * (1 - r.coverage_p90), "%", src,
              "target 10 %; RM6's P90 is a floor", "RM6", h)
    a = b[b["product"].str.startswith("AirSeT")]
    n.add("airset_holdout_pinball_skill_min", 100 * a.pinball_skill.min(), "%", src, "all AirSeT cases", "AirSeT")
    n.add("airset_holdout_pinball_skill_max", 100 * a.pinball_skill.max(), "%", src, "", "AirSeT")


def margin_at_risk(t) -> pd.DataFrame:
    """Headline table: margin points at risk per product × horizon, for both steel cases."""
    rows = []
    for p, case in HEADLINE_CASES.items():
        for steel in [HEADLINE_STEEL, CSV_STEEL]:
            for h in HORIZONS:
                r = one(t["bom"], case=case, steel=steel, horizon_m=h)
                rows.append({"product": p, "case": case, "steel": steel, "horizon_m": h,
                                 "index_p10": r.index_p10, "index_p50": r.index_p50, "index_p90": r.index_p90,
                                 "eur_increase_p90": r.cost_p90_eur - r.cost_today_eur,
                                 "price_adjustment_pts": r.price_adjustment_pts,
                                 "risk_buffer_p90_pts": r.risk_buffer_p90_pts,
                                 "total_at_risk_p90_pts": r.total_at_risk_p90_pts,
                                 "total_at_risk_p95_pts": r.total_at_risk_p95_pts})
    return pd.DataFrame(rows)


def story_risk(t, n: Numbers, mar: pd.DataFrame) -> None:
    """Message 4: risk grows with validity (Step 8), with the ranges around the headline."""
    src = "step8_tables/bom_index_and_margin_points.csv"
    for r in mar.itertuples():
        k = f"{r.product.lower()}_at_risk_p90_{r.horizon_m}m_{r.steel}"
        n.add(k, r.total_at_risk_p90_pts, "margin pts", src, r.case, r.product, r.horizon_m, r.steel)
        if r.steel == HEADLINE_STEEL:
            n.add(f"{r.product.lower()}_eur_increase_p90_{r.horizon_m}m", r.eur_increase_p90, "EUR", src,
                  r.case, r.product, r.horizon_m, r.steel)
            n.add(f"{r.product.lower()}_price_adjustment_{r.horizon_m}m", r.price_adjustment_pts, "margin pts",
                  src, "P50 drift", r.product, r.horizon_m, r.steel)
    b9 = t["bom"][t["bom"].horizon_m == 9]
    air = b9[b9.case.str.startswith("AirSeT")]
    n.add("airset_at_risk_p90_9m_range_min", air.total_at_risk_p90_pts.min(), "margin pts", src,
          "all AirSeT nickel / steel cases", "AirSeT", 9)
    n.add("airset_at_risk_p90_9m_range_max", air.total_at_risk_p90_pts.max(), "margin pts", src, "", "AirSeT", 9)
    for case in ALT_COPPER:
        r = one(t["bom"], case=case, steel=HEADLINE_STEEL, horizon_m=9)
        kg = case.split("copper ")[1].replace(" kg", "").replace(".", "_")
        n.add(f"rm6_at_risk_p90_9m_copper_{kg}kg", r.total_at_risk_p90_pts, "margin pts", src,
              "if the teardown BOM is right", "RM6", 9, HEADLINE_STEEL)


def quote_rule_headline(t) -> pd.DataFrame:
    """The quote rule at the headline steel case and accepted loss, at 90 % and 95 %."""
    q = t["rule"]
    rows = []
    for p, case in HEADLINE_CASES.items():
        for conf in [CONFIDENCE, 0.95]:
            for h in HORIZONS:
                r = one(q, case=case, steel=HEADLINE_STEEL, horizon_m=h,
                        tolerated_erosion_pts=ACCEPTED_LOSS, confidence=conf)
                rows.append({"product": p, "case": case, "steel": HEADLINE_STEEL, "accepted_loss_pts": ACCEPTED_LOSS,
                                 "confidence": conf, "horizon_m": h, "mechanism": r.recommendation,
                                 "indexation_band": r.indexation_band,
                                 "price_adjustment_pts": r.price_adjustment_pts,
                                 "uplift_charged_pts": r.uplift_charged_pts,
                                 "max_fixed_validity_m": r.max_fixed_validity_m})
    return pd.DataFrame(rows)


def story_rule(t, n: Numbers, rule: pd.DataFrame) -> None:
    """Message 5: the quote rule (slide 15's four items)."""
    src = "step9_tables/quote_rule.csv"
    for r in rule.itertuples():
        c = round(100 * r.confidence)
        n.add(f"{r.product.lower()}_uplift_{r.horizon_m}m_conf{c}", r.uplift_charged_pts, "margin pts", src,
              r.mechanism, r.product, r.horizon_m, r.steel)
    curve = t["curve"]
    for p, case in HEADLINE_CASES.items():
        r = one(curve, case=case, steel=HEADLINE_STEEL, horizon_m=9, buffer_pts=1.0)
        n.add(f"{p.lower()}_p_breach_1pt_buffer_9m", 100 * r.p_breach, "%", "step9_tables/buffer_curve.csv",
              "chance a 1-point buffer is not enough", p, 9, HEADLINE_STEEL)


def story_strategies(t, n: Numbers) -> None:
    """Message 6: what fixes it — 9-month quotes on past (historical) and simulated paths."""
    keep = {"fixed price": "fixed", "fixed + buffer P90": "buffer_p90", "indexation": "clause",
            "copper hedge": "hedge", "validity 3 m": "requote_3m"}
    for which, src in [("hist", "step9_tables/strategies_historical.csv"),
                       ("sim", "step9_tables/strategies_simulated.csv")]:
        d = t[which]
        for p, case in HEADLINE_CASES.items():
            for strat, short in keep.items():
                m = (d.case == case) & (d.steel == HEADLINE_STEEL) & (d.horizon_m == 9) & (d.strategy == strat)
                if not m.any():
                    continue  # no copper hedge for AirSeT
                r = d[m].iloc[0]
                base = f"{p.lower()}_{which}_9m_{short}"
                n.add(f"{base}_p95", r.p95_pts, "margin pts", src, "P95 loss", p, 9, HEADLINE_STEEL)
                n.add(f"{base}_worst", r.worst_pts, "margin pts", src, "worst loss", p, 9, HEADLINE_STEEL)
                n.add(f"{base}_cost_to_customer", r.gain_vs_fixed_mean_pts, "margin pts", src,
                      "mean extra the customer pays vs a fixed price", p, 9, HEADLINE_STEEL)


def story_problem2(t, n: Numbers) -> None:
    """Message 8: handover to Problem 2 (outlook to Jun 2027)."""
    o = t["outlook"]
    src = "step9_tables/outlook_2027.csv"
    gap = one(o, case="RM6 − AirSeT gap change", horizon_m=9)
    n.add("p_rm6_rises_more_jun2027", 100 * gap.p_rm6_rises_more, "%", src, "", "both", 9, CSV_STEEL)
    for q in ["p10", "p50", "p90"]:
        n.add(f"gap_change_jun2027_{q}", gap[f"cost_{q}_eur"], "EUR", src,
              "RM6 − AirSeT raw-material cost gap", "both", 9, CSV_STEEL)


# ---------------------------------------------------------------- consistency
def consistency_checks(t, tol: float = 0.02) -> pd.DataFrame:
    """The same quantity, read from two steps, must agree (rounding tolerance in points / %)."""
    rows = []
    for case in HEADLINE_CASES.values():
        for steel in [HEADLINE_STEEL, CSV_STEEL]:
            for h in HORIZONS:
                b = one(t["bom"], case=case, steel=steel, horizon_m=h)
                s = one(t["scen"], case=case, steel=steel, horizon_m=h, scenario="upside")
                rows.append({"check": "Step 8 P90 margin points = Step 9 upside scenario", "case": case,
                                 "steel": steel, "horizon_m": h, "a": b.total_at_risk_p90_pts, "b": s.margin_pts_lost})
                f = one(t["sim"], case=case, steel=steel, horizon_m=h, strategy="fixed price")
                rows.append({"check": "Step 8 P90 margin points = Step 9 fixed-price P90 loss", "case": case,
                                 "steel": steel, "horizon_m": h, "a": b.total_at_risk_p90_pts, "b": f.p90_pts})
        for h in HORIZONS:
            b = one(t["bom"], case=case, steel=CSV_STEEL, horizon_m=h)
            o = one(t["outlook"], case=case, horizon_m=h)
            rows.append({"check": "Step 8 P90 cost (€) = Step 9 outlook P90 cost (€)", "case": case,
                             "steel": CSV_STEEL, "horizon_m": h, "a": b.cost_p90_eur, "b": o.cost_p90_eur})
    df = pd.DataFrame(rows)
    rel = (df.a - df.b).abs() / df[["a", "b"]].abs().max(axis=1).clip(lower=1)
    df["ok"] = ((df.a - df.b).abs() <= tol) | (rel <= 0.005)
    return df


def build(t) -> dict[str, pd.DataFrame]:
    n = Numbers()
    mar = margin_at_risk(t)
    rule = quote_rule_headline(t)
    story_problem(t, n)
    story_drivers(t, n)
    story_forecast(t, n)
    story_risk(t, n, mar)
    story_rule(t, n, rule)
    story_strategies(t, n)
    story_problem2(t, n)
    return {"key_numbers": n.frame(), "margin_at_risk": mar, "quote_rule_headline": rule,
            "consistency_checks": consistency_checks(t)}


def main() -> None:
    out = build(load_tables())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False, float_format="%.4g")
        print(f"wrote {OUT_DIR / name}.csv ({len(df)} rows)")
    bad = out["consistency_checks"][~out["consistency_checks"].ok]
    if len(bad):
        print("CONSISTENCY ISSUES:\n", bad.to_string())
    else:
        print("all consistency checks pass")


if __name__ == "__main__":
    main()
