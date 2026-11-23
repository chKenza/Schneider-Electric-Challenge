"""Unit tests for the Step 7 evaluation formulas. Synthetic numbers only: no data needed,
so these also run in CI."""

import numpy as np
import pandas as pd
import pytest

from src.evaluation import (
    add_window,
    crps_from_quantiles,
    dm_hln,
    mase_scale,
    pinball,
    restrict_common,
)


def test_pinball_matches_the_definition():
    y = np.array([0.0, 1.0])
    q = np.array([[-1.0, 0.0, 1.0], [-1.0, 0.0, 1.0]])
    # y = 0: losses 0.1*1, 0, 0.1*1 -> mean 0.0667; y = 1: 0.1*2, 0.5*1, 0 -> mean 0.2333
    assert np.allclose(pinball(y, q), [0.2 / 3, 0.7 / 3])


def test_crps_is_zero_for_a_perfect_point_forecast_and_grows_with_error():
    y = np.array([0.05, 0.05])
    sharp_right = np.full((1, 3), 0.05)
    assert crps_from_quantiles(y[:1], sharp_right)[0] == pytest.approx(0.0, abs=1e-12)
    near, far = np.array([[0.0, 0.05, 0.1]]), np.array([[0.2, 0.25, 0.3]])
    assert crps_from_quantiles(y[:1], near)[0] < crps_from_quantiles(y[:1], far)[0]


def test_crps_of_a_point_forecast_equals_absolute_error():
    # A degenerate distribution at x has CRPS = |y - x| (here over the 5-95 % grid: 0.9 x).
    y, x = np.array([0.3]), np.full((1, 3), 0.1)
    grid = np.round(np.arange(0.05, 0.951, 0.05), 2)
    expected = 2 * np.mean(np.maximum(grid * 0.2, (grid - 1) * 0.2))
    assert crps_from_quantiles(y, x)[0] == pytest.approx(expected)


def test_dm_detects_a_clearly_better_model_and_not_a_tie():
    rng = np.random.default_rng(0)
    better = -0.5 + rng.normal(0, 0.3, 60)  # model loss always lower
    assert dm_hln(better, h=3)["dm_p_model_better"] < 0.01
    noise = rng.normal(0, 0.3, 60)  # no difference on average
    assert dm_hln(noise, h=3)["dm_p_two_sided"] > 0.05
    assert np.isnan(dm_hln(np.zeros(30), h=3)["dm_stat"])  # identical forecasts


def test_mase_scale_only_uses_outcomes_known_at_the_origin():
    months = pd.date_range("2020-01-01", periods=12, freq="MS")
    rw = pd.DataFrame({"model": "random_walk", "target": "X", "horizon": 3, "origin": months,
                       "target_month": months + pd.DateOffset(months=3),
                       "y": np.arange(1, 13, dtype=float)})
    s = mase_scale(rw).set_index("origin")["mase_scale"]
    # At origin 2020-06 the outcomes known are those with target month <= 2020-06,
    # i.e. origins 2020-01..2020-03 (y = 1, 2, 3): scale = 2.
    assert s[pd.Timestamp("2020-06-01")] == pytest.approx(2.0)
    assert np.isnan(s[pd.Timestamp("2020-01-01")])  # nothing known yet
    # Changing a later outcome must not change the scale at an earlier origin.
    rw2 = rw.copy()
    rw2.loc[rw2["origin"] >= "2020-04-01", "y"] = 1e6
    s2 = mase_scale(rw2).set_index("origin")["mase_scale"]
    assert s2[pd.Timestamp("2020-06-01")] == pytest.approx(2.0)


def test_windows_and_common_rows():
    df = pd.DataFrame({"model": ["a", "b", "a"], "target": "X", "horizon": 3,
                       "origin": pd.to_datetime(["2024-11-01", "2024-11-01", "2025-03-01"]),
                       "target_month": pd.to_datetime(["2025-02-01", "2025-02-01", "2025-06-01"])})
    w = add_window(df, "2025-03")
    assert list(w["window"]) == ["backtest", "backtest", "holdout"]
    assert list(w["strict"]) == [False, False, True]
    common = restrict_common(w, ["a", "b"])
    assert len(common) == 2 and set(common["origin"]) == {pd.Timestamp("2024-11-01")}


def test_kupiec_accepts_the_right_rate_and_rejects_a_wrong_one():
    from src.evaluation import kupiec

    right = np.r_[np.ones(10), np.zeros(90)]  # 10 % misses
    assert kupiec(right, 0.10)["kupiec_p"] == pytest.approx(1.0)
    wrong = np.r_[np.ones(30), np.zeros(70)]  # 30 % misses for a 10 % target
    assert kupiec(wrong, 0.10)["kupiec_p"] < 0.001


def test_christoffersen_flags_clustered_misses_not_spread_ones():
    from src.evaluation import christoffersen

    clustered = [np.r_[np.zeros(40), np.ones(10), np.zeros(50)]]  # all misses in a row
    spread = [np.tile(np.r_[1, np.zeros(9)], 10)]  # one miss every 10
    assert christoffersen(clustered)["christoffersen_p"] < 0.001
    assert christoffersen(spread)["christoffersen_p"] > 0.05


def test_non_overlapping_keeps_every_hth_origin_per_target():
    from src.evaluation import non_overlapping

    o = pd.date_range("2022-01-01", periods=9, freq="MS")
    rows = pd.DataFrame({"target": ["A"] * 9 + ["B"] * 9, "origin": list(o) * 2})
    sub = non_overlapping(rows, 3, offset=1)
    assert len(sub) == 6
    assert set(sub["origin"]) == {o[1], o[4], o[7]}


def test_sub_periods_follow_the_holdout_boundary():
    from src.evaluation import sub_period

    tm = pd.Series(pd.to_datetime(["2022-05-01", "2025-03-01", "2025-04-01"]))
    p = sub_period(tm)
    assert p.iloc[0].startswith("2022") and p.iloc[1].startswith("2023")
    assert "hold-out" in p.iloc[2]


# --------------------------------------------------------------------------- needs the data
needs_data = pytest.mark.skipif(
    not (__import__("src.data_prep", fromlist=["OUT"]).OUT / "panel_monthly.csv").exists(),
    reason="needs Data/processed (confidential)")


@needs_data
def test_bom_index_forecasts_ignore_future_data_at_every_origin():
    """The BOM-index backtest goes through the Step 6 Context: poisoning everything not yet
    known at each origin must not change any forecast (every origin, every model)."""
    from src.evaluation import bom_leakage_check
    from src.features import load_config

    result = bom_leakage_check(load_config())
    assert result["origin"].nunique() > 40
    assert result["unchanged"].all(), result[~result["unchanged"]]


@needs_data
def test_bom_index_lag_is_its_slowest_driver():
    from src.evaluation import BOM_SERIES, bom_inputs
    from src.features import load_config

    inputs = bom_inputs(load_config())
    for col in BOM_SERIES.values():
        assert inputs.lags[col] == 2  # S09 / S10 / D01 / D02 publish with 2 months' lag


@needs_data
def test_causal_tuning_only_uses_outcomes_known_at_each_origin():
    """Every choice of the causal procedure (lambda, members, specialist, gamma) is made from
    outcomes known at the origin: poisoning later outcomes and later forecasts must leave
    the causal forecast unchanged."""
    from src.evaluation import EVAL_DIR, causal_leakage_check, lambda_variants
    from src.features import load_config

    cfg = load_config()
    f = EVAL_DIR / "lambda_variant_predictions.csv"
    extra = (pd.read_csv(f, parse_dates=["origin", "target_month"]) if f.exists()
             else lambda_variants(cfg))
    result = causal_leakage_check(cfg, extra, ["2023-03-01", "2025-06-01"])
    assert result["unchanged"].all(), result


@needs_data
def test_sliding_window_variant_ignores_future_data_at_every_origin():
    """The 60-month sliding-window variant of ewma_fhs goes through the Step 6 Context and
    runner: the poisoned-future check must pass at every origin."""
    from src import models as M
    from src.baselines import load_selected
    from src.evaluation import SLIDING_MONTHS, _sliding
    from src.feature_selection import load_tables
    from src.features import load_config, load_inputs

    cfg = load_config()
    inputs, tables, selected = load_inputs(), load_tables(cfg), load_selected()
    M.MODELS["_test_sliding"] = {"fn": _sliding(M.ewma_fhs, SLIDING_MONTHS), "approach": "direct", "needs": ()}
    try:
        result = M.poisoned_future_check("_test_sliding", inputs, tables, selected, cfg)
    finally:
        M.MODELS.pop("_test_sliding")
    assert result["origin"].nunique() == 57
    assert result["unchanged"].all(), result[~result["unchanged"]]
