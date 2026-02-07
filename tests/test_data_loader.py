from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import rank_to_score


class TestMockDataFile:
    MOCK_PATH = Path(__file__).parent.parent / "data" / "mock_preferences.csv"

    def test_mock_preferences_file_exists(self):
        if not self.MOCK_PATH.exists():
            pytest.skip("Mock data file not found")

    def test_mock_preferences_integrity(self):
        df = pd.read_csv(self.MOCK_PATH, index_col=0)
        assert df.shape == (
            45,
            5,
        ), "Mock data should have 45 students and 5 choices each"

        assert df.index.is_unique, "Student IDs should be unique"
        assert df.index.tolist() == [
            f"student_{i:03d}" for i in range(1, 46)
        ], "Student IDs should be student_001 to student_045"

        assert df.columns.is_unique, "Choice columns should be unique"
        assert df.columns.tolist() == [
            f"choice_{i}" for i in range(1, 6)
        ], "Columns should be choice_1 to choice_5"

        assert df.notna().all().all(), "Mock data should not contain missing values"


class TestRankingToScore:
    def test_first_choice_is_5(self):
        assert rank_to_score(1) == 5

    def test_second_choice_is_4(self):
        assert rank_to_score(2) == 4

    def test_fifth_choice_is_1(self):
        assert rank_to_score(5) == 1
