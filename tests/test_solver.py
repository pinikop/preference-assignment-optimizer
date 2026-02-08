"""Tests for the solver module."""

import pytest

from src.solver import solve_assignment
from src.types import (
    AssignmentStatus,
    Metrics,
    ParticipantAssignment,
    SolverResult,
    SolverStatus,
)


class TestSolverStatus:
    def test_optimal_status_value(self):
        assert SolverStatus.OPTIMAL.value == "Optimal"

    def test_infeasible_status_value(self):
        assert SolverStatus.INFEASIBLE.value == "Infeasible"

    def test_status_comparison(self):
        assert SolverStatus.OPTIMAL == SolverStatus.OPTIMAL
        assert SolverStatus.OPTIMAL != SolverStatus.INFEASIBLE


class TestAssignmentStatus:
    def test_assigned_status_value(self):
        assert AssignmentStatus.ASSIGNED.value == "ASSIGNED"

    def test_unassigned_status_value(self):
        assert AssignmentStatus.UNASSIGNED.value == "UNASSIGNED"

    def test_no_preferences_status_value(self):
        assert AssignmentStatus.NO_PREFERENCES.value == "NO_PREFERENCES"


class TestParticipantAssignment:
    def test_assigned_participant(self):
        assignment = ParticipantAssignment(
            option="Option_A",
            status=AssignmentStatus.ASSIGNED,
            preference_rank=1,
            preference_score=5,
        )
        assert assignment.option == "Option_A"
        assert assignment.status == AssignmentStatus.ASSIGNED
        assert assignment.preference_rank == 1
        assert assignment.preference_score == 5

    def test_unassigned_participant(self):
        assignment = ParticipantAssignment(
            option="",
            status=AssignmentStatus.UNASSIGNED,
        )
        assert assignment.status == AssignmentStatus.UNASSIGNED
        assert assignment.preference_rank is None
        assert assignment.preference_score == 0


class TestMetrics:
    def test_metrics_creation(self):
        metrics = Metrics(
            preference_satisfaction=100,
            active_options=5,
            average_satisfaction=4.5,
            objective_value=110.0,
            preference_distribution={1: 10, 2: 5, 3: 3, 4: 2, 5: 0, "unassigned": 0},
            unused_options=["Option_X"],
        )
        assert metrics.preference_satisfaction == 100
        assert metrics.active_options == 5
        assert metrics.constraint_violations == []

    def test_metrics_with_violations(self):
        metrics = Metrics(
            preference_satisfaction=100,
            active_options=5,
            average_satisfaction=4.5,
            objective_value=110.0,
            preference_distribution={},
            unused_options=[],
            constraint_violations=["Option A has 1 participant"],
        )
        assert len(metrics.constraint_violations) == 1


class TestSolverResult:
    def test_result_creation(self):
        result = SolverResult(
            status=SolverStatus.OPTIMAL,
            assignments={"Option_A": ["participant_001"]},
            option_counts={"Option_A": 1},
            participant_assignments={},
            metrics=None,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.metrics is None


class TestQuotaValidation:
    """Tests for min_quota and max_quota parameter validation."""

    def test_min_quota_must_be_at_least_one(self):
        """min_quota must be at least 1."""
        with pytest.raises(ValueError, match="min_quota must be at least 1"):
            solve_assignment(["p1"], ["o1"], {}, min_quota=0, max_quota=3, option_weight=1.0)

    def test_max_quota_must_be_at_least_min_quota(self):
        """max_quota must be >= min_quota."""
        with pytest.raises(ValueError, match="max_quota must be >= min_quota"):
            solve_assignment(["p1"], ["o1"], {}, min_quota=3, max_quota=2, option_weight=1.0)

    def test_valid_quota_combination(self):
        """Valid quota combinations should not raise."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 5), ("o2", 4)],
            "p2": [("o1", 5), ("o2", 4)],
            "p3": [("o2", 5), ("o1", 4)],
            "p4": [("o2", 5), ("o1", 4)],
        }
        # Should not raise
        result = solve_assignment(
            participants, options, preferences, min_quota=1, max_quota=5, option_weight=1.0
        )
        assert result.status == SolverStatus.OPTIMAL


class TestCustomMinQuota:
    """Tests for various min_quota values."""

    def test_min_quota_one_allows_single_participant(self):
        """With min_quota=1, options can have a single participant."""
        participants = ["p1", "p2", "p3"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o2", 5)],
            "p3": [("o2", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=1, max_quota=3, option_weight=1.0
        )
        assert result.status == SolverStatus.OPTIMAL
        # With min_quota=1, o1 can have just p1
        assert result.option_counts["o1"] in [0, 1, 2, 3]
        assert result.metrics is not None
        assert result.metrics.constraint_violations == []

    def test_min_quota_three_requires_three_per_option(self):
        """With min_quota=3, max_quota=3, options must have exactly 0 or 3."""
        participants = ["p1", "p2", "p3", "p4", "p5", "p6"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 5), ("o2", 4)],
            "p2": [("o1", 5), ("o2", 4)],
            "p3": [("o1", 5), ("o2", 4)],
            "p4": [("o2", 5), ("o1", 4)],
            "p5": [("o2", 5), ("o1", 4)],
            "p6": [("o2", 5), ("o1", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=3, max_quota=3, option_weight=1.0
        )
        assert result.status == SolverStatus.OPTIMAL
        # Both options should have exactly 3 participants
        for option, count in result.option_counts.items():
            assert count in [0, 3], f"Option {option} has {count}, expected 0 or 3"

    def test_quota_two_to_three_enforces_valid_counts(self):
        """min_quota=2, max_quota=3 enforces 0, 2, or 3."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 5), ("o2", 4)],
            "p2": [("o1", 5), ("o2", 4)],
            "p3": [("o2", 5), ("o1", 4)],
            "p4": [("o2", 5), ("o1", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.status == SolverStatus.OPTIMAL
        for option, count in result.option_counts.items():
            assert count in [0, 2, 3], f"Option {option} has {count}"


class TestSolveAssignment:
    @pytest.fixture
    def simple_problem(self):
        """Simple problem with 4 participants and 2 options."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 5), ("o2", 4)],
            "p2": [("o1", 5), ("o2", 4)],
            "p3": [("o2", 5), ("o1", 4)],
            "p4": [("o2", 5), ("o1", 4)],
        }
        return participants, options, preferences

    def test_returns_solver_result(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        assert isinstance(result, SolverResult)

    def test_optimal_status(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        assert result.status == SolverStatus.OPTIMAL

    def test_all_participants_assigned(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        for participant in participants:
            assert participant in result.participant_assignments
            assert result.participant_assignments[participant].status == AssignmentStatus.ASSIGNED

    def test_option_size_constraint(self, simple_problem):
        """Each option should have 0, 2, or 3 participants."""
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        for option, count in result.option_counts.items():
            assert count in [0, 2, 3], f"Option {option} has {count} participants"

    def test_no_constraint_violations(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        assert result.metrics is not None
        assert result.metrics.constraint_violations == []

    def test_metrics_calculated(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        assert result.metrics is not None
        assert result.metrics.preference_satisfaction > 0
        assert result.metrics.active_options > 0

    def test_participant_without_preferences(self):
        """Participant with no preferences should get NO_PREFERENCES status."""
        participants = ["p1", "p2", "p3", "p4", "p5"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 5), ("o2", 4)],
            "p2": [("o1", 5), ("o2", 4)],
            "p3": [("o2", 5), ("o1", 4)],
            "p4": [("o2", 5), ("o1", 4)],
            # p5 has no preferences
        }
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        assert result.participant_assignments["p5"].status == AssignmentStatus.NO_PREFERENCES

    def test_preference_rank_tracking(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0)
        for participant, assignment in result.participant_assignments.items():
            if assignment.status == AssignmentStatus.ASSIGNED:
                assert assignment.preference_rank is not None
                assert 1 <= assignment.preference_rank <= 5


class TestSolverWithMockData:
    """Integration tests using the mock preferences file."""

    @pytest.fixture
    def mock_data(self):
        from pathlib import Path

        from src.data_loader import load_preferences_from_csv

        mock_path = Path(__file__).parent.parent / "data" / "mock_preferences.csv"
        if not mock_path.exists():
            pytest.skip("Mock data file not found")
        return load_preferences_from_csv(str(mock_path))

    def test_solves_mock_data(self, mock_data):
        participants, options, preferences = mock_data
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.OPTIMAL

    def test_no_violations_with_mock_data(self, mock_data):
        participants, options, preferences = mock_data
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert result.metrics is not None
        assert result.metrics.constraint_violations == []

    def test_all_participants_assigned_with_mock_data(self, mock_data):
        participants, options, preferences = mock_data
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        unassigned = [
            p
            for p, a in result.participant_assignments.items()
            if a.status == AssignmentStatus.UNASSIGNED
        ]
        assert unassigned == [], f"Unassigned participants: {unassigned}"
