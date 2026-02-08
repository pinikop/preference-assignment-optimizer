from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import load_preferences_from_csv, rank_to_score


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

    def test_custom_max_rank(self):
        assert rank_to_score(1, max_rank=3) == 3
        assert rank_to_score(2, max_rank=3) == 2
        assert rank_to_score(3, max_rank=3) == 1


class TestLoadPreferencesFromCSV:
    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        csv_content = """student_id,choice_1,choice_2,choice_3,choice_4,choice_5
student_001,Project_A,Project_B,Project_C,Project_D,Project_E
student_002,Project_B,Project_A,Project_D,Project_C,Project_F
student_003,Project_A,Project_C,Project_B,Project_E,Project_D
"""
        csv_path = tmp_path / "test_prefs.csv"
        csv_path.write_text(csv_content)
        return csv_path

    def test_returns_correct_students(self, sample_csv: Path):
        students, _, _ = load_preferences_from_csv(str(sample_csv))
        assert students == ["student_001", "student_002", "student_003"]

    def test_returns_all_unique_projects(self, sample_csv: Path):
        _, projects, _ = load_preferences_from_csv(str(sample_csv))
        expected = [
            "Project_A",
            "Project_B",
            "Project_C",
            "Project_D",
            "Project_E",
            "Project_F",
        ]
        assert projects == expected

    def test_preference_scores_are_correct(self, sample_csv: Path):
        _, _, preferences = load_preferences_from_csv(str(sample_csv))
        student_001_prefs = preferences["student_001"]
        assert student_001_prefs[0] == ("Project_A", 5)  # 1st choice
        assert student_001_prefs[1] == ("Project_B", 4)  # 2nd choice
        assert student_001_prefs[4] == ("Project_E", 1)  # 5th choice

    def test_each_student_has_five_preferences(self, sample_csv: Path):
        _, _, preferences = load_preferences_from_csv(str(sample_csv))
        for student_id, prefs in preferences.items():
            assert len(prefs) == 5, f"{student_id} should have 5 preferences"


class TestMissingValues:
    @pytest.fixture
    def csv_with_missing(self, tmp_path: Path) -> Path:
        csv_content = """student_id,choice_1,choice_2,choice_3,choice_4,choice_5
student_001,Project_A,Project_B,Project_C,,
student_002,Project_B,Project_A,,,
"""
        csv_path = tmp_path / "missing_prefs.csv"
        csv_path.write_text(csv_content)
        return csv_path

    def test_handles_missing_choices(self, csv_with_missing: Path):
        students, projects, preferences = load_preferences_from_csv(
            str(csv_with_missing)
        )
        assert len(preferences["student_001"]) == 3
        assert len(preferences["student_002"]) == 2

    def test_missing_values_not_in_projects(self, csv_with_missing: Path):
        _, projects, _ = load_preferences_from_csv(str(csv_with_missing))
        assert "" not in projects
        assert None not in projects


class TestDuplicateOptions:
    def test_duplicate_option_raises_error(self, tmp_path: Path):
        """Duplicate options for same participant should raise ValueError."""
        csv_content = """student_id,choice_1,choice_2,choice_3
student_001,A,A,B
"""
        csv_path = tmp_path / "duplicate.csv"
        csv_path.write_text(csv_content)

        with pytest.raises(ValueError, match="Duplicate option 'A' for participant"):
            load_preferences_from_csv(csv_path)


class TestCSVValidation:
    def test_empty_csv_raises_error(self, tmp_path: Path):
        """Empty CSV should raise ValueError."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")

        with pytest.raises(ValueError, match="empty"):
            load_preferences_from_csv(csv_path)

    def test_headers_only_raises_error(self, tmp_path: Path):
        """CSV with only headers should raise ValueError."""
        csv_content = """student_id,choice_1,choice_2,choice_3
"""
        csv_path = tmp_path / "headers_only.csv"
        csv_path.write_text(csv_content)

        with pytest.raises(ValueError, match="no data rows"):
            load_preferences_from_csv(csv_path)

    def test_dynamic_number_of_choices(self, tmp_path: Path):
        """Should handle CSVs with varying number of choice columns."""
        csv_content = """student_id,choice_1,choice_2,choice_3
student_001,A,B,C
"""
        csv_path = tmp_path / "three_choices.csv"
        csv_path.write_text(csv_content)

        students, options, preferences = load_preferences_from_csv(csv_path)
        # With 3 choices: 1st=3, 2nd=2, 3rd=1
        assert preferences["student_001"] == [("A", 3), ("B", 2), ("C", 1)]
