"""Deterministic adversarial edge cases across all modules (fast suite)."""

import csv
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.data_loader import load_preferences_from_csv
from src.main import app
from src.output import export_results_to_csv, print_assignment_summary
from src.solver import solve_assignment
from src.types import AssignmentStatus, SolverStatus

runner = CliRunner()
MOCK_CSV = str(Path(__file__).parent.parent / "data" / "mock_preferences.csv")


class TestQuotaBoundaries:
    def test_single_participant_single_option(self):
        result = solve_assignment(
            ["p1"],
            ["o1"],
            {"p1": [("o1", 1)]},
            min_quota=1,
            max_quota=1,
            option_weight=0.5,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.option_counts["o1"] == 1
        assert result.metrics.objective_value == pytest.approx(1.5)

    def test_exact_quota_groups(self):
        """min_quota == max_quota forces exact group sizes."""
        preferences = {f"p{i}": [("o1", 2), ("o2", 1)] for i in range(4)}
        result = solve_assignment(
            list(preferences),
            ["o1", "o2"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.0,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert all(c in (0, 2) for c in result.option_counts.values())

    def test_one_giant_group_allowed(self):
        """max_quota == participant count lets one option take everyone."""
        preferences = {f"p{i}": [("o1", 1)] for i in range(3)}
        result = solve_assignment(
            list(preferences),
            ["o1"],
            preferences,
            min_quota=1,
            max_quota=3,
            option_weight=0.5,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.option_counts["o1"] == 3

    def test_min_quota_exceeds_participants(self):
        preferences = {"p1": [("o1", 1)], "p2": [("o1", 1)]}
        result = solve_assignment(
            ["p1", "p2"],
            ["o1"],
            preferences,
            min_quota=3,
            max_quota=3,
            option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert result.infeasibility_hints


class TestParityTrap:
    def test_five_participants_pairs_only(self):
        """Capacity suffices (3 options x 2 = 6 >= 5) but an odd count
        can't be split into exact pairs - pure parity infeasibility,
        exercising the generic partitioning hint."""
        preferences = {f"p{i}": [("o1", 3), ("o2", 2), ("o3", 1)] for i in range(5)}
        result = solve_assignment(
            list(preferences),
            ["o1", "o2", "o3"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert result.infeasibility_hints
        assert not any("capacity" in h.lower() for h in result.infeasibility_hints)


class TestTies:
    def test_identical_preference_lists(self):
        """Any optimal split is acceptable; pin the optimal VALUE only."""
        preferences = {f"p{i}": [("o1", 2), ("o2", 1)] for i in range(4)}
        result = solve_assignment(
            list(preferences),
            ["o1", "o2"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.0,
        )
        assert result.status == SolverStatus.OPTIMAL
        # 2 participants get o1 (2 each), 2 get o2 (1 each): 2+2+1+1
        assert result.metrics.preference_satisfaction == 6


class TestDegenerateInputs:
    def test_no_participants_no_options(self):
        result = solve_assignment([], [], {}, min_quota=1, max_quota=3, option_weight=0.5)
        assert result.status == SolverStatus.OPTIMAL
        assert result.assignments == {}
        assert result.metrics.preference_satisfaction == 0
        assert result.metrics.average_satisfaction == 0.0

    def test_all_participants_without_preferences(self):
        result = solve_assignment(
            ["p1", "p2"], ["o1"], {}, min_quota=1, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.OPTIMAL
        statuses = {a.status for a in result.participant_assignments.values()}
        assert statuses == {AssignmentStatus.NO_PREFERENCES}
        assert result.metrics.preference_distribution == {"no_preferences": 2}


class TestNonLadderScores:
    def test_all_equal_scores(self):
        """The solver accepts arbitrary ints; identity must still hold."""
        preferences = {"p1": [("o1", 1), ("o2", 1)], "p2": [("o1", 1), ("o2", 1)]}
        result = solve_assignment(
            ["p1", "p2"],
            ["o1", "o2"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.25,
        )
        assert result.status == SolverStatus.OPTIMAL
        m = result.metrics
        assert m.objective_value == pytest.approx(
            m.preference_satisfaction + 0.25 * m.active_options
        )


class TestLoaderRobustness:
    def _load(self, tmp_path: Path, content: str, name: str = "t.csv"):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return load_preferences_from_csv(p)

    def test_unicode_names(self, tmp_path):
        _, options, prefs = self._load(
            tmp_path, "id,c1,c2\nJosé,Option-É,Übung\nÜser,Übung,Option-É\n"
        )
        assert set(options) == {"Option-É", "Übung"}
        assert prefs["José"][0] == ("Option-É", 2)

    def test_quoted_commas_in_names(self, tmp_path):
        _, options, prefs = self._load(
            tmp_path, 'id,c1\n"Smith, John","Opt, A"\n"Doe, Jane","Opt, A"\n'
        )
        assert options == ["Opt, A"]
        assert prefs["Smith, John"] == [("Opt, A", 1)]

    def test_whitespace_is_preserved(self, tmp_path):
        """Loader does not strip; ' A' and 'A' are distinct options."""
        _, options, _ = self._load(tmp_path, "id,c1\np1, A\np2,A\n")
        assert set(options) == {" A", "A"}

    def test_numeric_participant_ids(self, tmp_path):
        """Numeric IDs are coerced to strings, honoring the loader's contract."""
        participants, _, prefs = self._load(tmp_path, "id,c1\n1,A\n2,B\n")
        assert participants == ["1", "2"]
        assert prefs["1"] == [("A", 1)]

    def test_numeric_option_values_are_coerced_to_strings(self, tmp_path):
        """Option values honor the loader's str contract, like participant IDs."""
        _, options, prefs = self._load(tmp_path, "id,c1\np1,101\np2,102\n")
        assert options == ["101", "102"]
        assert prefs["p1"] == [("101", 1)]

    def test_single_column_csv_raises(self, tmp_path):
        """IDs only, zero choice columns -> no data rows."""
        with pytest.raises(ValueError):
            self._load(tmp_path, "id\np1\np2\n")

    def test_all_nan_row_yields_empty_preferences(self, tmp_path):
        _, _, prefs = self._load(tmp_path, "id,c1,c2\np1,A,B\np2,,\n")
        assert prefs["p2"] == []

    def test_gap_in_middle_keeps_column_rank(self, tmp_path):
        """Score comes from column position, not from compacting."""
        _, _, prefs = self._load(tmp_path, "id,c1,c2,c3\np1,A,,C\n")
        assert prefs["p1"] == [("A", 3), ("C", 1)]

    def test_crlf_and_trailing_newlines(self, tmp_path):
        participants, _, _ = self._load(tmp_path, "id,c1\r\np1,A\r\np2,B\r\n\r\n")
        assert participants == ["p1", "p2"]

    def test_ragged_row_raises_parse_error(self, tmp_path):
        with pytest.raises(ValueError, match="Failed to parse"):
            self._load(tmp_path, "id,c1\np1,A\np2,B,EXTRA,MORE\n")


class TestInfeasibleOutput:
    def test_summary_prints_hints(self, capsys):
        preferences = {"p1": [("o1", 1)]}
        result = solve_assignment(
            ["p1"], ["o1"], preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        print_assignment_summary(result)
        out = capsys.readouterr().out
        assert "Likely causes" in out
        assert "p1" in out


class TestCLIValidation:
    def test_min_quota_greater_than_max_quota_errors(self):
        result = runner.invoke(app, [MOCK_CSV, "-m", "5", "-q", "2"])
        assert result.exit_code == 1
        assert "cannot be greater" in result.output


class TestExportDegenerate:
    def test_export_when_everyone_has_no_preferences(self, tmp_path):
        result = solve_assignment(
            ["p1", "p2"], ["o1"], {}, min_quota=1, max_quota=3, option_weight=0.5
        )
        out_path = tmp_path / "results.csv"
        export_results_to_csv(result, out_path)
        rows = list(csv.DictReader(out_path.open()))
        assert len(rows) == 2
        assert all(r["status"] == "NO_PREFERENCES" for r in rows)
        assert all(r["assigned_option"] == "" for r in rows)
