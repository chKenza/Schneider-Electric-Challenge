"""Problem 2 Steps 4-5: the TCO model's arithmetic and the cost-gap outlook."""
from dataclasses import replace

import numpy as np
import pytest

from src import tco
from src.market_evidence import MarketEvidence


@pytest.fixture(scope="module")
def p2():
    return MarketEvidence.load()


@pytest.fixture(scope="module")
def base(p2):
    return tco.inputs(p2, "base")


def test_reproduces_framing_break_even(p2):
    tco._sanity_check(p2)


def test_lines_add_up_and_gap_sign(base):
    for view in tco.VIEWS:
        lines = tco.tco_lines(base, view)
        assert lines.loc["total", "RM6"] == pytest.approx(lines.loc[tco.LINES, "RM6"].sum())
        assert lines.loc["purchase", "gap"] == pytest.approx(base.premium_eur)
        # AirSeT carries no SF6 cost line
        assert (lines.loc[["sf6_upkeep", "eol_handling", "regulation", "carbon"], "AirSeT"] == 0).all()


def test_break_even_closes_the_gap(base):
    for view in tco.VIEWS:
        be = tco.break_even_carbon(base, view)
        assert np.isfinite(be) and be > 0
        assert tco.tco_gap(replace(base, carbon_price=be), view) == pytest.approx(0, abs=1e-6)


def test_max_premium_closes_the_gap(base):
    for view in tco.VIEWS:
        pm = tco.max_premium_pct(base, view)
        assert tco.tco_gap(replace(base, premium_pct=pm), view) == pytest.approx(0, abs=1e-6)


def test_views_are_ordered(base):
    """Counting more of the SF6 can only lower the break-even carbon price."""
    be = {v: tco.break_even_carbon(base, v) for v in tco.VIEWS}
    assert be["whole_fill"] < be["lifecycle"] < be["leaks"]


def test_end_of_life_uses_gas_left_after_leaks(base):
    x = replace(base, discount_pct=0.0, leak_pct=1.0, life=40, eol_release_share=1.0)
    t, _ = tco.carbon_t(x, "lifecycle")
    assert t == pytest.approx(x.fill_t_co2e)          # 40 % leaked + 60 % released = whole fill
    x = replace(x, leak_pct=5.0)                      # leaks cannot exceed the fill
    assert tco.carbon_t(x, "lifecycle")[0] == pytest.approx(x.fill_t_co2e * 2)


def test_no_carbon_no_break_even(base):
    x = replace(base, sf6_kg=0.0)
    assert tco.break_even_carbon(x, "lifecycle") == np.inf


def test_tornado_covers_every_parameter(p2):
    t = tco.tornado(p2, "lifecycle")
    assert set(t.param) == set(tco.SENSITIVITY)
    assert (t.swing_eur.diff().dropna() <= 1e-9).all()  # sorted, largest first


needs_data = pytest.mark.skipif(not (tco.PROCESSED / "cost_breakdown.csv").exists(),
                                reason="run `python -m src.cost_model` first")


@needs_data
def test_copper_scenarios_sign(p2):
    c = tco.copper_scenarios(p2)
    bom = c[(c.rm6_copper.str.contains("BOM")) & (c.airset_copper.str.contains("BOM v1"))].iloc[0]
    assert bom.net_copper_eur > 0 and bom.copper_rise_to_close_premium_pct > 100
    worst = c[(c.rm6_copper.str.contains("teardown")) & (c.airset_copper.str.contains("Xiria"))].iloc[0]
    assert worst.net_copper_eur < 0                   # copper rally would widen the gap


@needs_data
def test_gap_history_matches_today(p2):
    h = tco.gap_history()
    today = tco.rm_cost_today()
    assert h["RM6"].iloc[-1] == pytest.approx(today["RM6"])
    assert h["gap"].iloc[-1] == pytest.approx(today["RM6"] - today["AirSeT"])


def test_gap_outlook_reads_problem1(p2):
    g = tco.gap_outlook(p2)
    assert list(g.horizon_m) == [3, 6, 9]
    assert (g.gap_change_p10_eur < g.gap_change_p50_eur).all()
    assert (g.gap_change_p50_eur < g.gap_change_p90_eur).all()
