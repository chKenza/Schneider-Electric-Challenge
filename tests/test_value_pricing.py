"""Checks for Problem 2 Step 7. Run: uv run pytest tests/test_value_pricing.py
Uses only committed files (market_evidence/, step9_tables/), so it runs in CI."""
import pytest

from src import tco
from src import value_pricing as vp
from src.market_evidence import MarketEvidence


@pytest.fixture(scope="module")
def p2():
    return MarketEvidence.load()


def test_tco_based_price_leaves_the_customer_even(p2):
    for seg, s in vp.SEGMENTS.items():
        x = vp.segment_inputs(p2, seg)
        ceiling = vp.price_ceiling_pct(x, s["view"])
        if ceiling > 0:
            gap = tco.tco_gap(tco.replace(x, premium_pct=ceiling), s["view"])
            assert abs(gap) < 1e-6


def test_margin_at_the_floor_is_the_accepted_give(p2):
    price = p2.param("rm6_price_eur", "base")
    for c in vp.EXTRA_COST_PCT:
        floor = vp.price_floor_pct(c, price)
        assert vp.margin_vs_rm6_pts(floor, c, price) == pytest.approx(-vp.MARGIN_GIVE_PTS)


def test_floor_rises_with_extra_cost(p2):
    price = p2.param("rm6_price_eur", "base")
    floors = [vp.price_floor_pct(c, price) for c in vp.EXTRA_COST_PCT]
    assert floors == sorted(floors)


def test_raw_material_risk_is_read(p2):
    r = vp.raw_material_risk_eur()
    assert r["RM6"] > 0 and r["AirSeT"] > 0


def test_sf6_rules_add_upkeep(p2):
    with_rules = vp.segment_inputs(p2, "Australia colocation")
    without = vp.segment_inputs(p2, "Johor-Singapore data centres")
    assert with_rules.sf6_admin_eur_yr > without.sf6_admin_eur_yr