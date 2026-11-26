"""Step 12 – the forecast CSV: the validator catches every slide-17 rule, the built
material rows match the final model's live predictions, and the BOM index rows match
the Step 8 joint simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import REPO_ROOT
from src.data_prep import OUT
from src.models import FINAL_MODEL, MODEL_DIR

STEP8_TABLE = REPO_ROOT / "report" / "problem1" / "step8_tables" / "bom_index_and_margin_points.csv"

pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / f"predictions_{FINAL_MODEL}.csv").exists()
    or not (OUT / "bom_index_simulated.csv").exists(),
    reason="needs Data/processed (run src.data_prep ... src.models, src.simulation first)",
)


@pytest.fixture(scope="module")
def rows() -> pd.DataFrame:
    from src.submission import bom_rows, material_rows
    return pd.concat([material_rows(), bom_rows()], ignore_index=True)


def test_built_rows_are_valid(rows):
    from src.submission import validate
    assert validate(rows) == []
    assert (rows.target_type == "material").sum() == 15 * 3
    assert (rows.target_type == "bom_index").sum() == 2 * 3


def test_bom_rows_match_the_step8_table(rows):
    """The CSV's BOM rows are Step 8's index quantiles: BOM v1 cases, steel at producer prices."""
    from src.submission import BOM_STEEL, BOM_TARGETS
    step8 = pd.read_csv(STEP8_TABLE).set_index(["case", "steel", "horizon_m"])
    bom = rows[rows.target_type == "bom_index"]
    for case, target_id in BOM_TARGETS.items():
        for r in bom[bom.target_id == target_id].itertuples():
            ref = step8.loc[(case, BOM_STEEL, r.horizon_m), ["index_p10", "index_p50", "index_p90"]]
            assert np.allclose([r.p10, r.p50, r.p90], ref.to_numpy(float), atol=0.011), (target_id, r.horizon_m)
            assert r.unit == "index (origin=100)" and r.region == "EU"


def test_committed_csv_is_the_built_one(rows):
    from src.submission import SUBMISSION
    committed = pd.read_csv(SUBMISSION)
    pd.testing.assert_frame_equal(committed, rows, check_dtype=False)


def test_rows_match_live_predictions(rows):
    from src.submission import ORIGIN
    preds = pd.read_csv(MODEL_DIR / f"predictions_{FINAL_MODEL}.csv", parse_dates=["origin"])
    live = preds[preds["origin"] == ORIGIN].set_index(["target", "horizon"])
    panel = pd.read_csv(OUT / "panel_monthly.csv", index_col="month", parse_dates=["month"])
    for r in rows[rows.target_type == "material"].itertuples():
        base = panel.loc[ORIGIN, r.target_id] if r.unit == "EUR/t" else 100.0
        expected = base * np.exp(live.loc[(r.target_id, r.horizon_m), ["p10", "p50", "p90"]].to_numpy(float))
        assert np.allclose([r.p10, r.p50, r.p90], expected, rtol=1e-4), r.target_id


def test_confidential_epoxy_level_is_not_published(rows):
    assert (rows.loc[rows.target_id == "EPOXY_EUR", "unit"] == "index (origin=100)").all()


@pytest.mark.parametrize("break_it, message", [
    (lambda d: d.drop(index=0), "missing material rows"),
    (lambda d: d[d.target_type == "material"], "missing bom_index rows"),
    (lambda d: d.assign(target_id=d.target_id.where(d.target_type == "material", "RM6")), "not RM6 / RM AirSeT"),
    (lambda d: d.assign(p10=d["p50"] + 1), "p10 <= p50 <= p90"),
    (lambda d: d.assign(target_month="2026-12"), "target_month = origin + horizon"),
    (lambda d: d.assign(unit="USD/t"), "unit"),
    (lambda d: d.assign(region="EU"), "region differs"),  # WW material rows relabelled EU
    (lambda d: pd.concat([d, d.iloc[[0]]]), "duplicate rows"),
    (lambda d: d.assign(p50=np.nan), "missing values"),
    (lambda d: d[d.columns[::-1]], "columns must be exactly"),
    (lambda d: d.assign(target_type="bom_index", unit="EUR/t"), "bom_index unit"),
])
def test_validator_catches(rows, break_it, message):
    from src.submission import validate
    errs = validate(break_it(rows.copy()).reset_index(drop=True))
    assert any(message in e for e in errs), errs
