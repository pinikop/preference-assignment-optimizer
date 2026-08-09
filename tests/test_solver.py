"""Tests for the solver module."""

import pytest

from src.solver import PreferenceAssignmentSolver, solve_assignment
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
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert isinstance(result, SolverResult)

    def test_optimal_status(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.status == SolverStatus.OPTIMAL

    def test_all_participants_assigned(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        for participant in participants:
            assert participant in result.participant_assignments
            assert result.participant_assignments[participant].status == AssignmentStatus.ASSIGNED

    def test_option_size_constraint(self, simple_problem):
        """Each option should have 0, 2, or 3 participants."""
        participants, options, preferences = simple_problem
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        for option, count in result.option_counts.items():
            assert count in [0, 2, 3], f"Option {option} has {count} participants"

    def test_no_constraint_violations(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.metrics is not None
        assert result.metrics.constraint_violations == []

    def test_metrics_calculated(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
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
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.participant_assignments["p5"].status == AssignmentStatus.NO_PREFERENCES

    def test_preference_rank_tracking(self, simple_problem):
        participants, options, preferences = simple_problem
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        for participant, assignment in result.participant_assignments.items():
            if assignment.status == AssignmentStatus.ASSIGNED:
                assert assignment.preference_rank is not None
                assert 1 <= assignment.preference_rank <= 5


class TestNameSanitization:
    """IDs that sanitize to the same PuLP variable name must not collide."""

    def test_ids_differing_only_in_special_chars(self):
        """'p 1' and 'p_1' both sanitize to 'p_1' in PuLP; raw-ID variable
        names crash CBC with a PulpSolverError."""
        participants = ["p 1", "p_1"]
        options = ["o1"]
        preferences = {
            "p 1": [("o1", 1)],
            "p_1": [("o1", 1)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=2, option_weight=0.5
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.option_counts["o1"] == 2
        for participant in participants:
            status = result.participant_assignments[participant].status
            assert status == AssignmentStatus.ASSIGNED


class TestDuplicatePreferenceValidation:
    """The solver API must reject duplicate options in a preference list
    (the CSV loader validates, but programmatic callers bypass it)."""

    def test_preference_for_unknown_participant_raises(self):
        """A preferences key absent from the participants list must raise a
        clear error, not a KeyError during constraint building."""
        with pytest.raises(ValueError, match="unknown participants"):
            PreferenceAssignmentSolver(
                ["p1"],
                ["o1"],
                {"p1": [("o1", 1)], "ghost": [("o1", 1)]},
                min_quota=1,
            )

    def test_duplicate_option_in_preferences_raises(self):
        with pytest.raises(ValueError, match="Duplicate option"):
            PreferenceAssignmentSolver(
                ["p1"],
                ["o1"],
                {"p1": [("o1", 2), ("o1", 1)]},
                min_quota=1,
            )

    def test_preference_for_unknown_option_raises(self):
        """An option missing from the options list would get no quota
        constraint at all, silently bypassing the core constraint."""
        with pytest.raises(ValueError, match="unknown option"):
            PreferenceAssignmentSolver(
                ["p1"],
                ["o1"],
                {"p1": [("o2", 1)]},
                min_quota=1,
            )


class TestMetricsImmutability:
    """Reading metrics must never mutate them."""

    def test_preference_distribution_is_a_plain_dict(self):
        """A defaultdict would silently insert keys on read access."""
        participants = ["p1", "p2"]
        options = ["o1"]
        preferences = {p: [("o1", 1)] for p in participants}
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert result.metrics is not None
        dist = result.metrics.preference_distribution
        with pytest.raises(KeyError):
            dist[999]
        assert 999 not in dist


class TestKnownOptimum:
    """Pin the solver to hand-computed optima where greedy assignment fails."""

    def test_beats_greedy_first_choice_assignment(self):
        """Greedy would give p1 its first choice o1, leaving p2 (who only
        ranked o1) unassignable. The optimum sacrifices p1's first choice:
        p1 -> o2, p2 -> o1, total satisfaction 1 + 2 = 3."""
        participants = ["p1", "p2"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 2), ("o2", 1)],
            "p2": [("o1", 2)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=1, max_quota=1, option_weight=0.0
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.participant_assignments["p1"].option == "o2"
        assert result.participant_assignments["p2"].option == "o1"
        assert result.metrics is not None
        assert result.metrics.preference_satisfaction == 3

    def test_forced_pairing_reaches_hand_computed_optimum(self):
        """p2 only ranked o1 and p4 only ranked o2, forcing the pairing;
        the optimum is exactly 2 + 2 + 2 + 1 = 7."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 2), ("o2", 1)],
            "p2": [("o1", 2)],
            "p3": [("o1", 2), ("o2", 1)],
            "p4": [("o2", 2)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=2, option_weight=0.0
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.participant_assignments["p2"].option == "o1"
        assert result.participant_assignments["p4"].option == "o2"
        assert result.metrics is not None
        assert result.metrics.preference_satisfaction == 7


class TestInfeasibilityDiagnostics:
    """An INFEASIBLE result must explain what likely caused it."""

    def test_impossible_participant_is_named_in_hints(self):
        """p3's only option is ranked by nobody else, so it can never reach min_quota."""
        participants = ["p1", "p2", "p3"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 2)],
            "p2": [("o1", 2)],
            "p3": [("o2", 2)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert any("p3" in hint for hint in result.infeasibility_hints)

    def test_capacity_shortfall_is_reported(self):
        """4 participants competing for a single option with max_quota=3."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1"]
        preferences = {p: [("o1", 1)] for p in participants}
        result = solve_assignment(
            participants, options, preferences, min_quota=1, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert any("capacity" in hint.lower() for hint in result.infeasibility_hints)

    def test_doomed_participants_are_aggregated_into_one_hint(self):
        """Multiple impossible participants share a single hint naming all
        of them, instead of one near-identical line each."""
        participants = ["p1", "p2"]
        options = ["o1", "o2"]
        preferences = {
            "p1": [("o1", 1)],
            "p2": [("o2", 1)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert len(result.infeasibility_hints) == 1
        assert "p1" in result.infeasibility_hints[0]
        assert "p2" in result.infeasibility_hints[0]

    def test_feasible_problem_has_no_hints(self):
        participants = ["p1", "p2"]
        options = ["o1"]
        preferences = {p: [("o1", 1)] for p in participants}
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.infeasibility_hints == []


class TestOptionWeightBehavior:
    """option_weight trades satisfaction for active options; the default must
    not sit at the tipping point where first choices get sacrificed."""

    def test_default_option_weight_is_half(self):
        solver = PreferenceAssignmentSolver(["p1"], ["o1"], {"p1": [("o1", 1)]}, min_quota=1)
        assert solver.option_weight == 0.5

    def test_default_weight_keeps_unanimous_first_choices(self):
        """When everyone ranks o1 first, the default weight must not split
        the group just to activate a second option."""
        participants = ["p1", "p2", "p3"]
        options = ["o1", "o2"]
        preferences = {p: [("o1", 2), ("o2", 1)] for p in participants}
        solver = PreferenceAssignmentSolver(
            participants, options, preferences, min_quota=1, max_quota=3
        )
        result = solver.solve()
        assert result.status == SolverStatus.OPTIMAL
        ranks = [a.preference_rank for a in result.participant_assignments.values()]
        assert ranks == [1, 1, 1]

    def test_zero_weight_maximizes_satisfaction_only(self):
        participants = ["p1", "p2", "p3"]
        options = ["o1", "o2"]
        preferences = {p: [("o1", 2), ("o2", 1)] for p in participants}
        result = solve_assignment(
            participants, options, preferences, min_quota=1, max_quota=3, option_weight=0.0
        )
        assert result.metrics is not None
        assert result.metrics.preference_satisfaction == 6

    def test_high_weight_activates_more_options(self):
        """A weight far above the score scale should force a split."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1", "o2"]
        preferences = {p: [("o1", 2), ("o2", 1)] for p in participants}
        result = solve_assignment(
            participants, options, preferences, min_quota=1, max_quota=4, option_weight=10.0
        )
        assert result.metrics is not None
        assert result.metrics.active_options == 2


class TestSolverOutput:
    """The solver must not spew CBC internals to stdout/stderr."""

    def test_solve_produces_no_solver_output(self, capfd):
        participants = ["p1", "p2"]
        options = ["o1"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o1", 4)],
        }
        solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        captured = capfd.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestObjectiveValue:
    """Tests that objective_value matches the documented objective formula."""

    def test_objective_identity_with_unranked_options(self):
        """objective_value == satisfaction + option_weight * active_options,
        even when some options are ranked by nobody."""
        participants = ["p1", "p2"]
        # o2, o3, o4 are ranked by nobody and must not inflate the objective
        options = ["o1", "o2", "o3", "o4"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o1", 4)],
        }
        option_weight = 1.0
        result = solve_assignment(
            participants,
            options,
            preferences,
            min_quota=2,
            max_quota=3,
            option_weight=option_weight,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.metrics is not None
        expected = (
            result.metrics.preference_satisfaction + option_weight * result.metrics.active_options
        )
        assert result.metrics.objective_value == pytest.approx(expected)

    def test_objective_identity_with_zero_weight(self):
        """With option_weight=0, objective_value equals preference satisfaction."""
        participants = ["p1", "p2"]
        options = ["o1", "o2", "o3"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o1", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=0.0
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.metrics is not None
        assert result.metrics.objective_value == pytest.approx(
            result.metrics.preference_satisfaction
        )


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


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_option_with_no_demand(self):
        """Options not in any preference list should have 0 assignments."""
        participants = ["p1", "p2"]
        options = ["o1", "o2", "unused_option"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o1", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.option_counts.get("unused_option", 0) == 0

    def test_infeasible_scenario(self):
        """Too few participants for min_quota should be infeasible."""
        participants = ["p1", "p2"]
        options = ["o1"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o1", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=5, max_quota=10, option_weight=1.0
        )
        assert result.status == SolverStatus.INFEASIBLE

    def test_empty_participants(self):
        """Empty participant list should return optimal with no assignments."""
        result = solve_assignment(
            participants=[],
            options=["o1", "o2"],
            preferences={},
            min_quota=2,
            max_quota=3,
            option_weight=1.0,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert all(count == 0 for count in result.option_counts.values())

    def test_all_participants_no_preferences(self):
        """All participants with no preferences get NO_PREFERENCES status."""
        participants = ["p1", "p2", "p3"]
        options = ["o1", "o2"]
        preferences = {}  # No one has preferences
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.status == SolverStatus.OPTIMAL
        for p in participants:
            assert result.participant_assignments[p].status == AssignmentStatus.NO_PREFERENCES


class TestMetricsValidation:
    """Tests to verify metrics calculations are correct."""

    def test_preference_satisfaction_equals_sum_of_scores(self):
        """preference_satisfaction should equal sum of assigned preference scores."""
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
        assert result.metrics is not None

        # Calculate expected sum from individual assignments
        expected_sum = sum(a.preference_score for a in result.participant_assignments.values())
        assert result.metrics.preference_satisfaction == expected_sum

    def test_active_options_count_matches_assignments(self):
        """active_options should match count of options with participants."""
        participants = ["p1", "p2", "p3", "p4"]
        options = ["o1", "o2", "o3"]
        preferences = {
            "p1": [("o1", 5)],
            "p2": [("o1", 4)],
            "p3": [("o2", 5)],
            "p4": [("o2", 4)],
        }
        result = solve_assignment(
            participants, options, preferences, min_quota=2, max_quota=3, option_weight=1.0
        )
        assert result.metrics is not None

        expected_active = sum(1 for count in result.option_counts.values() if count > 0)
        assert result.metrics.active_options == expected_active

    def test_average_satisfaction_calculation(self):
        """average_satisfaction should be preference_satisfaction / num_participants."""
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
        assert result.metrics is not None

        expected_avg = result.metrics.preference_satisfaction / len(participants)
        assert result.metrics.average_satisfaction == expected_avg
