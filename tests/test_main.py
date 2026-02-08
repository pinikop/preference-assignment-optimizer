"""Tests for the CLI entry point."""

import csv
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app
from src.output import export_results_to_csv, print_assignment_summary
from src.types import AssignmentStatus, Metrics, ParticipantAssignment, SolverResult, SolverStatus

runner = CliRunner()


class TestCLI:
    """Tests for the CLI commands."""

    def test_cli_runs_with_mock_data(self):
        """Test that CLI runs successfully with mock data."""
        result = runner.invoke(app, ["data/mock_preferences.csv"])
        assert result.exit_code == 0
        assert "Solver Status: Optimal" in result.output

    def test_cli_with_option_weight(self):
        """Test CLI with option weight parameter."""
        result = runner.invoke(app, ["data/mock_preferences.csv", "-w", "0.5"])
        assert result.exit_code == 0
        assert "Solver Status: Optimal" in result.output

    def test_cli_with_quotas(self):
        """Test CLI with custom quota parameters."""
        result = runner.invoke(app, ["data/mock_preferences.csv", "-m", "1", "-q", "5"])
        assert result.exit_code == 0
        assert "Solver Status: Optimal" in result.output

    def test_cli_with_seed(self):
        """Test CLI with seed parameter for reproducibility."""
        result1 = runner.invoke(app, ["data/mock_preferences.csv", "-s", "42"])
        result2 = runner.invoke(app, ["data/mock_preferences.csv", "-s", "42"])
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # With same seed, output should be identical
        assert result1.output == result2.output

    def test_cli_with_shuffle(self):
        """Test CLI with shuffle flag."""
        result = runner.invoke(app, ["data/mock_preferences.csv", "--shuffle"])
        assert result.exit_code == 0
        assert "Solver Status: Optimal" in result.output

    def test_cli_csv_export(self):
        """Test that CSV export works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.csv"
            result = runner.invoke(
                app, ["data/mock_preferences.csv", "-o", str(output_path)]
            )
            assert result.exit_code == 0
            assert output_path.exists()
            assert f"Results exported to: {output_path}" in result.output

            # Verify CSV content
            with open(output_path) as f:
                reader = csv.reader(f)
                header = next(reader)
                assert header == [
                    "participant_id",
                    "assigned_option",
                    "preference_rank",
                    "preference_score",
                    "status",
                ]
                rows = list(reader)
                assert len(rows) > 0

    def test_cli_file_not_found(self):
        """Test that CLI shows error for non-existent file."""
        result = runner.invoke(app, ["nonexistent_file.csv"])
        assert result.exit_code == 1
        assert "Error: File not found" in result.output

    def test_cli_help(self):
        """Test that help shows all options."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--min-quota" in result.output
        assert "--max-quota" in result.output
        assert "--option-weight" in result.output
        assert "--seed" in result.output
        assert "--shuffle" in result.output
        assert "--output" in result.output


class TestOutput:
    """Tests for the output module."""

    def test_print_assignment_summary_optimal(self, capsys):
        """Test pretty-print for optimal result."""
        result = SolverResult(
            status=SolverStatus.OPTIMAL,
            assignments={"OptionA": ["P1", "P2"], "OptionB": ["P3"]},
            option_counts={"OptionA": 2, "OptionB": 1},
            participant_assignments={
                "P1": ParticipantAssignment(
                    option="OptionA",
                    status=AssignmentStatus.ASSIGNED,
                    preference_rank=1,
                    preference_score=5,
                ),
                "P2": ParticipantAssignment(
                    option="OptionA",
                    status=AssignmentStatus.ASSIGNED,
                    preference_rank=2,
                    preference_score=4,
                ),
                "P3": ParticipantAssignment(
                    option="OptionB",
                    status=AssignmentStatus.ASSIGNED,
                    preference_rank=1,
                    preference_score=5,
                ),
            },
            metrics=Metrics(
                preference_satisfaction=14,
                active_options=2,
                average_satisfaction=4.67,
                objective_value=16.0,
                preference_distribution={1: 2, 2: 1, 3: 0, 4: 0, 5: 0, "unassigned": 0},
                unused_options=[],
            ),
        )

        print_assignment_summary(result)
        captured = capsys.readouterr()

        assert "Solver Status: Optimal" in captured.out
        assert "Preference Satisfaction: 14" in captured.out
        assert "Active Options: 2" in captured.out
        assert "OptionA: P1, P2" in captured.out

    def test_print_assignment_summary_with_violations(self, capsys):
        """Test pretty-print shows constraint violations."""
        result = SolverResult(
            status=SolverStatus.OPTIMAL,
            assignments={"OptionA": ["P1"]},
            option_counts={"OptionA": 1},
            participant_assignments={
                "P1": ParticipantAssignment(
                    option="OptionA",
                    status=AssignmentStatus.ASSIGNED,
                    preference_rank=1,
                    preference_score=5,
                ),
            },
            metrics=Metrics(
                preference_satisfaction=5,
                active_options=1,
                average_satisfaction=5.0,
                objective_value=6.0,
                preference_distribution={1: 1},
                unused_options=[],
                constraint_violations=["OptionA has 1 participant, but should have 0 or 2-3"],
            ),
        )

        print_assignment_summary(result)
        captured = capsys.readouterr()

        assert "Constraint Violations" in captured.out
        assert "OptionA has 1 participant" in captured.out

    def test_export_results_to_csv(self):
        """Test CSV export functionality."""
        result = SolverResult(
            status=SolverStatus.OPTIMAL,
            assignments={"OptionA": ["P1", "P2"]},
            option_counts={"OptionA": 2},
            participant_assignments={
                "P1": ParticipantAssignment(
                    option="OptionA",
                    status=AssignmentStatus.ASSIGNED,
                    preference_rank=1,
                    preference_score=5,
                ),
                "P2": ParticipantAssignment(
                    option="OptionA",
                    status=AssignmentStatus.ASSIGNED,
                    preference_rank=2,
                    preference_score=4,
                ),
            },
            metrics=None,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_export.csv"
            export_results_to_csv(result, str(filepath))

            with open(filepath) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["participant_id"] == "P1"
            assert rows[0]["assigned_option"] == "OptionA"
            assert rows[0]["preference_rank"] == "1"
            assert rows[0]["preference_score"] == "5"
            assert rows[0]["status"] == "ASSIGNED"

    def test_export_to_invalid_path_raises_error(self):
        """Exporting to invalid path should raise OSError."""
        result = SolverResult(
            status=SolverStatus.OPTIMAL,
            assignments={},
            option_counts={},
            participant_assignments={},
            metrics=None,
        )

        with pytest.raises(OSError, match="Failed to write"):
            export_results_to_csv(result, "/nonexistent/directory/file.csv")
