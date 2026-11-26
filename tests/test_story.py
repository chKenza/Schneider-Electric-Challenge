"""Checks for Step 10. Run: uv run pytest tests/test_story.py

Reads the committed Step 7–9 tables (no confidential files), so it runs in CI.
Two kinds of test:
  - mechanics: the numbers are read correctly and agree across steps;
  - story claims: each qualitative sentence of report/problem1/step10_story.md still holds.
    If a rerun (e.g. the corrected BOM a_v1) breaks one, the test names the sentence to rewrite.
"""

import pandas as pd
import pytest

from src import story as s


@pytest.fixture(scope="module")
def out():
    return s.build(s.load_tables())


@pytest.fixture(scope="module")
def k(out):
    return out["key_numbers"].set_index("key").value


# ---------------------------------------------------------------- mechanics
def test_one_fails_loudly_on_zero_or_many_rows():
    df = pd.DataFrame({"a": [1, 1, 2]})
    assert s.one(df, a=2).a == 2
    with pytest.raises(ValueError):
        s.one(df, a=1)
    with pytest.raises(ValueError):
        s.one(df, a=3)


def test_key_numbers_are_unique_and_sourced(out):
    kn = out["key_numbers"]
    assert kn.key.is_unique
    assert kn.value.notna().all()
    assert (kn.source.str.len() > 0).all()


def test_steps_8_and_9_agree(out):
    bad = out["consistency_checks"][~out["consistency_checks"].ok]
    assert bad.empty, bad.to_string()


def test_tables_cover_every_product_and_horizon(out):
    for name in ["margin_at_risk", "quote_rule_headline"]:
        df = out[name]
        assert set(df["product"]) == {"RM6", "AirSeT"}
        assert set(df.horizon_m) == set(s.HORIZONS)


def test_bom_index_quantiles_are_ordered(out):
    m = out["margin_at_risk"]
    assert ((m.index_p10 <= m.index_p50) & (m.index_p50 <= m.index_p90)).all()


# ---------------------------------------------------------------- story claims
def test_claim_fixed_prices_lost_margin_in_2022(k):
    """'In 2022, fixed prices cost about 2.4 margin points': cost rose far faster than price."""
    assert k["rm6_margin_pts_2022_vs_2018"] < -1.5
    assert k["rm6_rm_cost_change_2018_2022"] > 3 * k["rm6_price_change_2018_2022"]


def test_claim_rm6_copper_airset_steel(k):
    """'RM6 is a copper bet; AirSeT a steel + stainless and copper bet' (BOM v1)."""
    for steel in ["market", "PPI"]:
        assert k[f"rm6_copper_share_p90_9m_{steel}"] > 50
        assert k[f"airset_steel_share_p90_9m_{steel}"] > 40
        assert k[f"airset_copper_share_p90_9m_{steel}"] > 35
        assert k[f"airset_steel_share_p90_9m_{steel}"] + k[f"airset_copper_share_p90_9m_{steel}"] > 90


def test_claim_band_not_median(k):
    """'The median is no better than no change; the band beats the random walk in the backtest.'"""
    assert abs(k["mae_skill_min"]) < 5 and abs(k["mae_skill_max"]) < 5
    for h in s.HORIZONS:
        assert k[f"pinball_skill_backtest_{h}m"] > 0


def test_claim_risk_grows_with_validity(out):
    """'Margin at risk grows with the quote's validity.'"""
    for (_, _), g in out["margin_at_risk"].groupby(["product", "steel"]):
        assert g.sort_values("horizon_m").total_at_risk_p90_pts.is_monotonic_increasing


def test_claim_almost_all_risk_is_buffer(out):
    """'The price adjustment is small: almost all the risk is in the buffer.'"""
    m = out["margin_at_risk"]
    assert (m.price_adjustment_pts.abs() < 0.5 * m.total_at_risk_p90_pts).all()


def test_claim_rm6_9m_needs_a_clause(out):
    """'RM6: 9-month quotes need a copper clause' (headline settings)."""
    r = out["quote_rule_headline"]
    r = r[(r["product"] == "RM6") & (r.horizon_m == 9) & (r.confidence == s.CONFIDENCE)]
    assert r.mechanism.str.contains("indexation").all()


def test_claim_airset_clause_beats_buffer_on_past_paths(k):
    """'AirSeT: on past paths the clause loses far less than a P90 buffer, and costs the customer less.'"""
    assert k["airset_hist_9m_clause_p95"] < 0.5 * k["airset_hist_9m_buffer_p90_p95"]
    assert k["airset_hist_9m_clause_cost_to_customer"] < k["airset_hist_9m_buffer_p90_cost_to_customer"]


def test_claim_rm6_p90_is_a_floor(k):
    """'RM6's P90 is a floor': more than 10 % of hold-out outcomes ended above it."""
    assert k["rm6_holdout_above_p90_6m"] > 10 and k["rm6_holdout_above_p90_9m"] > 10


def test_claim_weak_support_for_convergence(k):
    """'RM6's cost rises more than AirSeT's in only about half the paths: weak support for convergence.'"""
    assert 40 < k["p_rm6_rises_more_jun2027"] < 65
