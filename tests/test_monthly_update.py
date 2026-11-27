"""Monthly update: the checks on a new month in the client's format (needs Data/)."""

import io

import pandas as pd
import pytest

from src.config import REPO_ROOT

pytestmark = pytest.mark.skipif(not (REPO_ROOT / "Data" / "data").exists() and
                                not (REPO_ROOT / "Data" / "data.zip").exists(),
                                reason="needs the challenge data in Data/")


@pytest.fixture
def sep():
    from src import monthly_update as mu
    return pd.read_csv(io.BytesIO(mu.held_back_file("2026-09")))


def test_held_back_month_passes_unchanged(sep):
    from src import monthly_update as mu
    c = mu.check(sep)
    assert c.ok and c.month == "2026-09" and c.replaces
    # what is written to Data/updates/ is the client's row, unchanged
    orig = mu.history().loc[[pd.Timestamp("2026-09-01")]]
    pd.testing.assert_frame_equal(c.clean[mu.REQUIRED + ["D01", "D02"]],
                                  orig[mu.REQUIRED + ["D01", "D02"]].round(4),
                                  check_names=False, check_freq=False)


def test_long_format_gives_the_same_month(sep):
    from src import monthly_update as mu
    long = mu.read_raw_csv("rm_prices_monthly_long.csv")
    c = mu.check(mu.read_upload(long[long["month"] == "2026-09-01"].to_csv(index=False).encode()))
    assert c.ok and c.month == "2026-09"


def test_blank_series_and_typos_are_caught(sep):
    from src import monthly_update as mu
    bad = sep.copy()
    bad.loc[0, "S03"] = None          # blank nickel: error
    bad.loc[0, "S01"] *= 10           # decimal-point typo: flagged
    c = mu.check(bad)
    status = c.rows.set_index("rule")["status"]
    assert not c.ok
    assert status["Every free series S01–S13 filled"] == "error"
    assert c.values.set_index("series").loc["S01", "status"] == "warn"


def test_a_gap_after_the_data_on_file_is_an_error(sep):
    from src import monthly_update as mu
    gap = sep.assign(month="2026-12-01")
    assert not mu.check(gap).ok
