"""Deterministic adversarial edge cases across all modules (fast suite)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

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


class TestCapacity:
    def test_unanimous_demand_fits_exactly(self):
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

    def test_unanimous_demand_exceeds_capacity(self):
        preferences = {f"p{i}": [("o1", 1)] for i in range(4)}
        result = solve_assignment(
            list(preferences),
            ["o1"],
            preferences,
            min_quota=1,
            max_quota=3,
            option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert any("capacity" in h.lower() for h in result.infeasibility_hints)


class TestParityTrap:
    def test_five_participants_pairs_only(self):
        """5 participants, groups of exactly 2, two options: 5 is odd -> infeasible."""
        preferences = {f"p{i}": [("o1", 2), ("o2", 1)] for i in range(5)}
        result = solve_assignment(
            list(preferences),
            ["o1", "o2"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert result.infeasibility_hints  # generic partitioning hint


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
