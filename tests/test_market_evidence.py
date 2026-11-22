"""Problem 2 market evidence: the data files load, every source is traceable,
and the verification rule cannot be bypassed."""
import shutil

import pandas as pd
import pytest

from src.market_evidence import DATA_DIR, MarketEvidence, _sanity_check


@pytest.fixture
def data_copy(tmp_path):
    shutil.copytree(DATA_DIR, tmp_path / "d")
    return tmp_path / "d"


def _edit(folder, name, fn):
    df = pd.read_csv(folder / name, dtype=str)
    fn(df)
    df.to_csv(folder / name, index=False)


def test_data_loads_and_reproduces_framing_break_even():
    p2 = MarketEvidence.load()
    _sanity_check(p2)
    assert set(p2.markets.index) == set(p2.regulation.index)


def test_every_verified_row_cites_a_high_or_medium_source():
    p2 = MarketEvidence.load()
    for table in ("regulation", "markets", "customers", "competitors", "assumptions"):
        df = getattr(p2, table)
        for key, row in df[df.verified.fillna(False)].iterrows():
            assert p2.reliability(row.evidence_ids) in {"high", "medium"}, (table, key)


def test_verified_without_good_source_is_rejected(data_copy):
    # E70 alone is Low: it cannot back verified=True
    def fn(d):
        d.loc[d.country_id == "MY", ["evidence_ids", "verified"]] = ["E70", "True"]
    _edit(data_copy, "regulation.csv", fn)
    with pytest.raises(ValueError, match="verified=True without a High/Medium source"):
        MarketEvidence.load(data_copy)


def test_unknown_evidence_id_is_rejected(data_copy):
    def fn(d):
        d.loc[d.country_id == "JP", "evidence_ids"] = "E999"
    _edit(data_copy, "regulation.csv", fn)
    with pytest.raises(ValueError, match="not in evidence.csv"):
        MarketEvidence.load(data_copy)


def test_markets_must_cover_every_country(data_copy):
    _edit(data_copy, "markets.csv", lambda d: d.drop(d.index[d.country_id == "JP"], inplace=True))
    with pytest.raises(ValueError, match="markets.csv is missing countries"):
        MarketEvidence.load(data_copy)


def test_invalid_category_is_rejected(data_copy):
    def fn(d):
        d.loc[d.customer_id == "google", "mentions_sf6"] = "maybe"
    _edit(data_copy, "customers.csv", fn)
    with pytest.raises(ValueError, match="mentions_sf6 must be one of"):
        MarketEvidence.load(data_copy)


def test_report_tables_list_every_country_and_competitor():
    p2 = MarketEvidence.load()
    reg, comp = p2.regulation_markdown(), p2.competitors_markdown()
    assert all(f"| {c} |" in reg for c in p2.regulation.country)
    assert all(f"**{c}**" in comp for c in p2.competitors.competitor)


def test_value_without_source_is_rejected(data_copy):
    def fn(d):  # Japan keeps its status values but loses its sources
        d.loc[d.country_id == "JP", "evidence_ids"] = ""
        d.loc[d.country_id == "JP", "verified"] = "False"
    _edit(data_copy, "regulation.csv", fn)
    with pytest.raises(ValueError, match="rows with values but no evidence_ids"):
        MarketEvidence.load(data_copy)
