"""Leakage checks for the Step 4 features. Run: uv run pytest tests/

Skipped when the (confidential) processed data is not present, e.g. in CI.
"""

import pandas as pd
import pytest

from src.data_prep import OUT
from src.external_data import EXT

pytestmark = pytest.mark.skipif(
    not (OUT / "panel_monthly.csv").exists() or not (EXT / "external_monthly.csv").exists(),
    reason="needs Data/processed (src.data_prep) and Data/external (src.external_data)",
)


@pytest.fixture(scope="module")
def setup():
    from src.features import load_config, load_inputs

    return load_config(), load_inputs()


def test_every_feature_respects_publication_lags(setup):
    from src.features import known_at_forecast_time

    cfg, inputs = setup
    table = known_at_forecast_time(inputs, cfg, ["2019-03", "2022-06", "2026-09"])
    assert table["rule_ok"].all(), table[~table["rule_ok"]]


def test_features_ignore_future_data(setup):
    from src.features import poisoned_future_test

    cfg, inputs = setup
    result = poisoned_future_test(inputs, cfg, n=6, seed=1)
    assert result["features_unchanged"].all()


def test_target_is_the_log_change_from_the_origin(setup):
    import numpy as np

    from src.features import target_change

    _, inputs = setup
    s = inputs.data["S09"]
    o = pd.Timestamp("2022-01-01")
    expected = np.log(s[o + pd.DateOffset(months=6)] / s[o])
    assert target_change(inputs.data, "S09", o, 6) == pytest.approx(expected)
