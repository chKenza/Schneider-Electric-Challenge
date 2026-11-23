"""Checks for the Step 8 simulation. Run: uv run pytest tests/test_simulation.py

  * the simulated percentiles equal the Step 7 forecast (P10 / P50 / P90 / P95);
  * no future data: at a past origin, the result does not change when everything
    after the origin (residuals and prices) is replaced with random numbers;
  * reproducible: same seed -> same paths; different seed -> different paths;
  * joint bootstrap: every simulated month is a real month (all materials together).

Skipped when the (confidential) processed data is not present, e.g. in CI.
"""

import numpy as np
import pandas as pd
import pytest

import src.simulation as s
from src.data_prep import OUT

PREDS = OUT / "models" / "predictions_conformal_combo.csv"
pytestmark = pytest.mark.skipif(
    not (s.STEP8 / "marginals_202609.csv").exists() or not PREDS.exists(),
    reason="needs Data/processed (src.models --stage export)",
)
PAST = "2023-06"
N = 500  # small, for speed


@pytest.fixture(scope="module")
def data():
    residuals, marginals = s.read_historical_prices()
    preds = pd.read_csv(PREDS, parse_dates=["origin"])
    return s.load_panel(), residuals, marginals, preds


def _scramble_after(df, origin, seed=0):
    """Replace every row after `origin` with random positive numbers."""
    out = df.copy()
    late = out.index > pd.Timestamp(origin)
    rng = np.random.default_rng(seed)
    num = out.select_dtypes("number").columns
    out.loc[late, num] = rng.uniform(1, 1000, size=(late.sum(), len(num)))
    return out


def test_percentiles_match_the_forecast(data):
    _, residuals, marginals, _ = data
    ratios = s.simulate_driver_ratios("2026-09", marginals, residuals, n_paths=2000)
    for h, r in ratios.items():
        for d, t in zip(s.DRIVERS, s.TARGETS):
            k = marginals[(marginals.target == t) & (marginals.horizon == h)].iloc[0]
            want = np.maximum.accumulate(k[s.QCOLS].to_numpy(float))
            got = np.quantile(np.log(r[d]), s.LEVELS)
            assert np.allclose(got, want, atol=1e-3), (d, h, got, want)


def test_no_future_data(data):
    panel, residuals, _, preds = data
    clean = s.simulate_bom(PAST, preds, residuals, panel, n_paths=N)
    leaky = s.simulate_bom(PAST, preds, _scramble_after(residuals, PAST),
                           _scramble_after(panel, PAST), n_paths=N)
    pd.testing.assert_frame_equal(clean, leaky)


def test_reproducible(data):
    _, residuals, marginals, _ = data
    a = s.simulate_driver_ratios("2026-09", marginals, residuals, n_paths=N, seed=1)
    b = s.simulate_driver_ratios("2026-09", marginals, residuals, n_paths=N, seed=1)
    c = s.simulate_driver_ratios("2026-09", marginals, residuals, n_paths=N, seed=2)
    for h in s.HORIZONS:
        pd.testing.assert_frame_equal(a[h], b[h])
        assert not a[h].equals(c[h])


def test_blocks_keep_materials_on_the_same_months(data):
    _, residuals, _, _ = data
    known = residuals[s.TARGETS].dropna()
    paths = s.bootstrap_prices(horizon=9, returns=known, n_paths=50, seed=0)
    real = {tuple(row) for row in known.to_numpy().round(12)}
    assert all(tuple(m) in real for p in paths for m in p.round(12))