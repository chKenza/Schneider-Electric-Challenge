"""Step 12 – the forecast CSV: the validator catches every slide-17 rule, and the built
material rows match the final model's live predictions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data_prep import OUT
from src.models import FINAL_MODEL, MODEL_DIR

pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / f"predictions_{FINAL_MODEL}.csv").exists(),
    reason="needs Data/processed (run src.data_prep ... src.models first)",
)


@pytest.fixture(scope="module")
def rows() -> pd.DataFrame:
    from src.submission import material_rows
    return material_rows()


def test_built_rows_are_valid(rows):
    from src.submission import validate
    assert validate(rows) == []
    assert len(rows) == 15 * 3


def test_rows_match_live_predictions(rows):
    from src.submission import ORIGIN
    preds = pd.read_csv(MODEL_DIR / f"predictions_{FINAL_MODEL}.csv", parse_dates=["origin"])
    live = preds[preds["origin"] == ORIGIN].set_index(["target", "horizon"])
    panel = pd.read_csv(OUT / "panel_monthly.csv", index_col="month", parse_dates=["month"])
    for r in rows.itertuples():
        base = panel.loc[ORIGIN, r.target_id] if r.unit == "EUR/t" else 100.0
        expected = base * np.exp(live.loc[(r.target_id, r.horizon_m), ["p10", "p50", "p90"]].to_numpy(float))
        assert np.allclose([r.p10, r.p50, r.p90], expected, rtol=1e-4), r.target_id


def test_confidential_epoxy_level_is_not_published(rows):
    assert (rows.loc[rows.target_id == "EPOXY_EUR", "unit"] == "index (origin=100)").all()


@pytest.mark.parametrize("break_it, message", [
    (lambda d: d.drop(index=0), "missing material rows"),
    (lambda d: d.assign(p10=d["p50"] + 1), "p10 <= p50 <= p90"),
    (lambda d: d.assign(target_month="2026-12"), "target_month = origin + horizon"),
    (lambda d: d.assign(unit="USD/t"), "unit"),
    (lambda d: d.assign(region="EU"), "region differs"),
    (lambda d: pd.concat([d, d.iloc[[0]]]), "duplicate rows"),
    (lambda d: d.assign(p50=np.nan), "missing values"),
    (lambda d: d[d.columns[::-1]], "columns must be exactly"),
    (lambda d: d.assign(target_type="bom_index", unit="EUR/t"), "bom_index unit"),
])
def test_validator_catches(rows, break_it, message):
    from src.submission import validate
    errs = validate(break_it(rows.copy()).reset_index(drop=True))
    assert any(message in e for e in errs), errs
