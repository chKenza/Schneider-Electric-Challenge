"""Leakage checks for the Step 6 models. Run: uv run pytest tests/test_models.py

Two kinds of test:
  * the real checks: every implemented model and the conformal layer, on EVERY origin
    (and every conformal gamma), must give the same forecasts when everything not yet
    known at the forecast date is replaced with random numbers;
  * power checks: deliberately leaky code must FAIL the same checks, which shows the
    checks can actually catch leakage.

Skipped when the (confidential) processed data is not present, e.g. in CI.
"""

import importlib.util

import numpy as np
import pandas as pd
import pytest

from src.data_prep import OUT
from src.external_data import EXT

pytestmark = pytest.mark.skipif(
    not (OUT / "panel_monthly.csv").exists() or not (EXT / "external_monthly.csv").exists()
    or not (OUT / "features").exists(),
    reason="needs Data/processed (src.data_prep, src.features) and Data/external",
)

IMPLEMENTED = ["ewma_fhs", "garch_fhs", "gjr_fhs", "features_scaled", "pooled_qr",
               "auto_ets", "auto_arima", "auto_theta"]  # add each new model
# Chronos is an optional extra (uv run --extra chronos pytest ...): tested when installed.
if importlib.util.find_spec("chronos") is not None:
    IMPLEMENTED.append("chronos_bolt")


@pytest.fixture(scope="module")
def setup():
    from src.baselines import load_selected
    from src.feature_selection import load_tables
    from src.features import load_config, load_inputs

    cfg = load_config()
    return cfg, load_inputs(), load_tables(cfg), load_selected()


@pytest.fixture(scope="module")
def ewma_predictions(setup):
    import src.models as M

    cfg, inputs, tables, selected = setup
    return M.run_model("ewma_fhs", inputs, tables, selected, cfg)


# --------------------------------------------------------------------------- real checks
@pytest.mark.parametrize("name", IMPLEMENTED)
def test_base_model_ignores_future_data_at_every_origin(setup, name):
    import src.models as M

    cfg, inputs, tables, selected = setup
    result = M.poisoned_future_check(name, inputs, tables, selected, cfg)  # every origin
    every_origin = {f"{T:%Y-%m}" for k in tables for T in M.evaluation_origins(tables[k], cfg)}
    assert set(result["origin"]) == every_origin  # backtest, hold-out and live row
    assert result["unchanged"].all(), result[~result["unchanged"]]


def test_conformal_ignores_future_outcomes_at_every_origin_and_gamma(ewma_predictions):
    import src.models as M

    result = M.conformal_leakage_check(ewma_predictions)  # every origin x full gamma grid
    grid = [g for g in M.SETTINGS["conformal_gammas"] if g > 0]
    assert set(result["gamma"]) == set(grid)
    assert result["origin"].nunique() == ewma_predictions["origin"].nunique()
    assert result["unchanged"].all(), result[~result["unchanged"]]


def test_ewma_vol_is_causal(setup):
    import src.models as M

    _, inputs, _, _ = setup
    r = np.log(inputs.data["S09"].dropna()).diff()
    full = M.ewma_vol(r, 0.97)
    for cut in ["2019-06", "2021-12", "2024-03"]:
        assert np.allclose(full.loc[:cut], M.ewma_vol(r.loc[:cut], 0.97), equal_nan=True)


def test_nothing_is_chosen_on_the_holdout(setup, ewma_predictions):
    import src.models as M

    cfg = setup[0]
    holdout = ewma_predictions[ewma_predictions["target_month"] > pd.Timestamp(cfg["selection"]["select_end"])]
    with pytest.raises(ValueError):
        M.backtest_only(holdout, cfg)


# --------------------------------------------------------------------------- power checks
def test_base_check_catches_a_model_reading_future_rows(setup):
    import src.models as M

    cfg, inputs, tables, selected = setup

    @M.register("_leaky_table", approach="direct")
    def leaky(ctx, p):  # reads the feature table through a global, not through ctx
        return np.repeat(tables[(ctx.target, ctx.h)]["y"].iloc[-2], 4)

    try:
        res = M.poisoned_future_check("_leaky_table", inputs, tables, selected, cfg, n=3,
                                      targets=["S09"], horizons=[3])
        assert not res["unchanged"].any()
    finally:
        M.MODELS.pop("_leaky_table")


def test_base_check_catches_a_model_reading_unpublished_data(setup):
    import src.models as M

    cfg, inputs, tables, selected = setup

    @M.register("_leaky_panel", approach="direct")
    def leaky(ctx, p):  # reads the panel through a global, beyond the publication lags
        return np.repeat(np.log(inputs.data[ctx.target].iloc[-1]), 4)

    try:
        res = M.poisoned_future_check("_leaky_panel", inputs, tables, selected, cfg, n=3,
                                      targets=["S09"], horizons=[3])
        assert not res["unchanged"].any()
    finally:
        M.MODELS.pop("_leaky_panel")


def test_conformal_check_catches_an_off_by_one_horizon(ewma_predictions):
    """A calibrator that learns from outcomes one month too early (target_month <= T + 1,
    i.e. an off-by-one on the arrival date) must be caught."""
    import src.models as M

    def leaky(pred, gamma):
        shifted = pred.assign(target_month=pred["target_month"] - pd.DateOffset(months=1))
        out = M.adaptive_conformal(shifted, gamma)
        return out.assign(target_month=out["target_month"] + pd.DateOffset(months=1))

    sub = ewma_predictions[ewma_predictions["target"].isin(["S09", "D01"])]
    res = M.conformal_leakage_check(sub, gammas=[0.1], calibrate=leaky)
    assert not res["unchanged"].all()


def test_combination_and_its_calibration_ignore_the_future(setup, ewma_predictions):
    """The combination only averages forecasts issued at the same origin: poisoning every
    forecast issued after T and every outcome not known at T must leave every combined
    forecast issued at T or before unchanged, and the same for its conformal version
    (every origin, full gamma grid)."""
    import src.models as M

    cfg, inputs, tables, selected = setup
    other = M.run_model("ewma_fhs", inputs, tables, selected, cfg, params={"ewma_lambda": 0.94})
    members = pd.concat([ewma_predictions, other.assign(model="ewma_094")], ignore_index=True)
    cols = ["p10", "p50", "p90", "p95"]
    key = ["target", "horizon", "origin"]
    clean = M.combine(members, ["ewma_fhs", "ewma_094"]).sort_values(key).reset_index(drop=True)
    rng = np.random.default_rng(0)
    for T in sorted(members["origin"].unique())[::4]:
        bad = members.copy()
        later = bad["origin"] > T
        bad.loc[later, cols] = np.sort(rng.uniform(-5, 5, (later.sum(), 4)), axis=1)
        hidden = bad["target_month"] > T
        bad.loc[hidden, "y"] = rng.uniform(-5, 5, hidden.sum())
        poisoned = M.combine(bad, ["ewma_fhs", "ewma_094"]).sort_values(key).reset_index(drop=True)
        upto = clean["origin"] <= T
        assert np.allclose(clean.loc[upto, cols], poisoned.loc[upto, cols])
    result = M.conformal_leakage_check(clean)
    assert result["unchanged"].all(), result[~result["unchanged"]]


def test_members_are_chosen_on_the_backtest_only(setup, ewma_predictions):
    import src.models as M

    cfg = setup[0]
    holdout = ewma_predictions.assign(window="holdout")
    with pytest.raises(ValueError):
        M.select_members(holdout, cfg, 3)


def test_step8_export_is_consistent(setup, tmp_path):
    """The Step 8 inputs only use months up to the live origin, the marginals are the live
    forecasts of the chosen model, and the ratios are exp(log-change quantiles)."""
    import src.models as M

    if not (M.MODEL_DIR / f"predictions_{M.STEP8_MODEL}.csv").exists():
        pytest.skip("run `python -m src.models` first")
    cfg, inputs, _, _ = setup
    out = M.export_residuals(cfg, inputs, out_dir=tmp_path)
    marg = out["marginals_202609"]
    origin = pd.Timestamp(marg["origin"].iloc[0])
    assert out["residuals_monthly"].index.max() <= origin
    for h in cfg["settings"]["horizons"]:
        assert out[f"joint_z_h{h}"].index.max() <= origin - pd.DateOffset(months=h)
    assert len(marg) == 45 and marg[["p10", "p50", "p90", "p95"]].notna().all().all()
    assert np.allclose(marg["ratio_p90"], np.exp(marg["p90"]))
    assert (marg["p10"] <= marg["p50"]).all() and (marg["p90"] <= marg["p95"]).all()


def test_holdout_refuses_to_run_after_a_change(setup, tmp_path, monkeypatch):
    """Once the hold-out has been opened, changing any frozen prediction file or setting
    must make the hold-out evaluation refuse to run (no silent re-tuning on the hold-out)."""
    import json

    import src.models as M

    if not (M.MODEL_DIR / f"predictions_{M.FINAL_MODEL}.csv").exists():
        pytest.skip("run `python -m src.models` first")
    cfg = setup[0]
    manifest = M.freeze_manifest(cfg)
    manifest["files"][next(iter(manifest["files"]))] = "0" * 64  # pretend a file changed
    fake = tmp_path / "holdout_freeze.json"
    fake.write_text(json.dumps(manifest, default=str))
    monkeypatch.setattr(M, "FREEZE_FILE", fake)
    with pytest.raises(RuntimeError, match="already opened"):
        M.holdout_evaluation(cfg)
