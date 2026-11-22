"""Step 3 scoring: criteria are bounded, weights are explicit, and the top of
the ranking is stable under reasonable weight changes."""
import pandas as pd

from src.market_evidence import MarketEvidence
from src.market_scoring import CRITERIA, WEIGHTS, criteria_table, ranking, score


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9
    assert set(WEIGHTS) == set(CRITERIA)


def test_criteria_are_between_0_and_1_and_exclude_reference_markets():
    crit = criteria_table(MarketEvidence.load())
    vals = crit[list(WEIGHTS)]
    assert ((vals >= 0) & (vals <= 1)).all().all()
    assert not {"EU", "CH", "US-CA", "US-FED"} & set(crit.index)


def test_unresearched_presence_is_neutral_not_best():
    crit = criteria_table(MarketEvidence.load())
    unknown = crit[~crit.presence_known]
    assert (unknown.competition == 0.5).all() and (unknown.schneider == 0.5).all()


def test_us_states_inherit_national_rivals():
    crit = criteria_table(MarketEvidence.load())
    assert (crit.loc[crit.index.str.startswith("US-"), "rivals"] >= 2).all()


def test_top_of_ranking_is_stable():
    res = ranking(MarketEvidence.load())
    top5 = res.head(5)
    assert (res.head(2).top5_share >= 0.99).all()  # the leaders never leave the top 5
    assert (top5.top5_share >= 0.85).all()
    assert pd.Series(score(criteria_table(MarketEvidence.load()))).index[0] in top5.index
