"""Checks for Problem 2 Step 9. Run: uv run python -m pytest tests/test_strategy.py
Uses only committed files (market_evidence/, step9_tables/), so it runs in CI."""
import pandas as pd
import pytest

from src import strategy as st
from src import value_pricing as vp
from src.market_evidence import MarketEvidence


@pytest.fixture(scope="module")
def p2():
    return MarketEvidence.load()


@pytest.fixture(scope="module")
def wc(p2):
    return st.win_conditions(p2).set_index("segment")


def test_thresholds_match_step7_price_window(p2, wc):
    """At the max extra cost, the Step 7 floor equals the ceiling."""
    for seg, (x, view) in st.segments(p2).items():
        c = wc.loc[seg, "max_extra_cost_pct"]
        assert vp.price_floor_pct(c, x.rm6_price) == pytest.approx(vp.price_ceiling_pct(x, view))


def test_step7_windows_reproduced(wc):
    w = pd.read_csv(vp.TABLE_DIR / "price_window.csv")
    w = w[w.extra_cost_pct == vp.EXTRA_COST_BASE].set_index("segment")
    for seg in vp.SEGMENTS:
        assert bool(wc.loc[seg, "window_open_at_placeholder"]) == bool(w.loc[seg, "window_open"])


def test_entry_give_raises_threshold_by_give(wc):
    diff = wc.max_extra_cost_pct_with_entry_give - wc.max_extra_cost_pct
    assert (diff.round(9) == st.ENTRY_GIVE_PTS).all()


def test_carbon_to_open_closes_the_window(p2, wc):
    """At that carbon price, the customer's ceiling reaches the Schneider floor."""
    from dataclasses import replace
    for seg, (x, view) in st.segments(p2).items():
        cp = wc.loc[seg, "carbon_to_open_at_placeholder_eur_t"]
        if pd.notna(cp) and cp not in (0, float("inf")):
            y = replace(x, carbon_price=cp)
            floor = vp.price_floor_pct(vp.EXTRA_COST_BASE, x.rm6_price)
            assert vp.price_ceiling_pct(y, view) == pytest.approx(floor, abs=1e-6)


def test_windows_open_no_earlier_on_slower_paths(p2):
    w = st.window_opening(p2)
    big = 9999
    for seg, d in w.groupby("segment"):
        d = d.set_index("cost_path").opens.fillna(big)
        assert d[st.BASE_PATH] <= d["slow (UK review, top of range)"] <= d["no volume gain"]


def test_whole_fill_is_the_largest_co2_view(p2):
    c = st.co2_avoided(p2).pivot(index="scenario", columns="view", values="t_co2e_per_unit")
    assert (c.whole_fill >= c.lifecycle).all() and (c.lifecycle >= c.leaks).all()
    assert c.loc["base", "whole_fill"] == pytest.approx(1.5 * 23500 / 1000)


def test_triggers_have_thresholds_and_actions(p2):
    t = st.triggers(p2)
    assert len(t) >= 6 and t.notna().all().all()
