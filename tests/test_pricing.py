"""Checks for the Step 9 strategy mechanics. Run: uv run pytest tests/test_pricing.py

Synthetic data only (no confidential files), so these can run in CI.
"""

import numpy as np
import pandas as pd
import pytest

from src import pricing as p

PRICE = 1000.0


@pytest.fixture
def rm6():
    """5 paths, two materials: copper (indexed for RM6) and steel."""
    rng = np.random.default_rng(0)
    delta = pd.DataFrame({"Copper": rng.normal(20, 30, 5), "Carbon steel FR": rng.normal(5, 10, 5)})
    base = pd.DataFrame({"Copper": [500.0] * 5, "Carbon steel FR": [200.0] * 5})
    return delta, base


def test_fixed_price_is_the_cost_change_in_points(rm6):
    delta, base = rm6
    out = p.strategy_losses(delta, base, PRICE, "RM6", {}, 0.05, 0.0)
    assert np.allclose(out["fixed price"], delta.sum(axis=1) * 100 / PRICE)


def test_buffer_lowers_the_loss_by_exactly_the_buffer(rm6):
    delta, base = rm6
    out = p.strategy_losses(delta, base, PRICE, "RM6", {"P90": 0.7}, 0.05, 0.0)
    assert np.allclose(out["fixed price"] - out["fixed + buffer P90"], 0.7)


def test_indexation_limits(rm6):
    delta, base = rm6
    zero = p.strategy_losses(delta, base, PRICE, "RM6", {}, 0.0, 0.0)
    huge = p.strategy_losses(delta, base, PRICE, "RM6", {}, 10.0, 0.0)
    # band 0: the customer pays every copper move, only steel is left
    assert np.allclose(zero["indexation"], delta["Carbon steel FR"] * 100 / PRICE)
    # band too wide to trigger: same as a fixed price
    assert np.allclose(huge["indexation"], huge["fixed price"])


def test_copper_hedge_at_zero_cost_removes_copper(rm6):
    delta, base = rm6
    out = p.strategy_losses(delta, base, PRICE, "RM6", {}, 0.05, 0.0)
    assert np.allclose(out["copper hedge"], delta["Carbon steel FR"] * 100 / PRICE)


def test_uplift_meets_the_tolerated_erosion():
    loss = pd.Series(np.random.default_rng(1).normal(0.3, 1.0, 100_000))
    for e in p.TOLERATED_EROSION:
        for c in p.CONFIDENCE:
            adj, buf = p.required_uplift(loss, e, c)
            assert (loss - adj - buf > e).mean() <= 1 - c + 0.005


def test_effect_vs_fixed_is_zero_for_the_fixed_price(rm6):
    delta, base = rm6
    d = p.describe_losses(p.strategy_losses(delta, base, PRICE, "RM6", {}, 0.05, 0.0))
    assert d.set_index("strategy").loc["fixed price", "gain_vs_fixed_mean_pts"] == 0