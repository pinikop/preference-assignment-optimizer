"""Tests for the Streamlit app analytics functions."""

import pandas as pd

from src.app.utils.analytics import (
    calculate_competition_index,
    calculate_option_popularity,
    calculate_weighted_popularity,
)

OPTIONS = ["A", "B", "C", "D"]
PREFERENCES = {
    "p1": [("A", 3), ("B", 2), ("C", 1)],
    "p2": [("A", 3), ("C", 2), ("B", 1)],
}


def _by_option(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index("Option")


class TestOptionPopularity:
    def test_counts_selections_at_any_rank(self):
        df = _by_option(calculate_option_popularity(OPTIONS, PREFERENCES))
        assert df.loc["A", "Total Selections"] == 2
        assert df.loc["B", "Total Selections"] == 2
        assert df.loc["C", "Total Selections"] == 2

    def test_includes_unselected_options_with_zero(self):
        df = _by_option(calculate_option_popularity(OPTIONS, PREFERENCES))
        assert df.loc["D", "Total Selections"] == 0

    def test_sorted_descending(self):
        df = calculate_option_popularity(OPTIONS, PREFERENCES)
        counts = df["Total Selections"].tolist()
        assert counts == sorted(counts, reverse=True)


class TestWeightedPopularity:
    def test_sums_preference_scores(self):
        df = _by_option(calculate_weighted_popularity(OPTIONS, PREFERENCES))
        assert df.loc["A", "Weighted Score"] == 6  # 3 + 3
        assert df.loc["B", "Weighted Score"] == 3  # 2 + 1
        assert df.loc["C", "Weighted Score"] == 3  # 1 + 2
        assert df.loc["D", "Weighted Score"] == 0


class TestCompetitionIndex:
    def test_counts_top_two_demand(self):
        df = _by_option(calculate_competition_index(OPTIONS, PREFERENCES, capacity=2))
        assert df.loc["A", "Top-2 Demand"] == 2  # both rank A in top 2
        assert df.loc["B", "Top-2 Demand"] == 1  # only p1
        assert df.loc["C", "Top-2 Demand"] == 1  # only p2
        assert df.loc["D", "Top-2 Demand"] == 0

    def test_index_is_demand_over_capacity(self):
        df = _by_option(calculate_competition_index(OPTIONS, PREFERENCES, capacity=2))
        assert df.loc["A", "Competition Index"] == 1.0
        assert df.loc["B", "Competition Index"] == 0.5
