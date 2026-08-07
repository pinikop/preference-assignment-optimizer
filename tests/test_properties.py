"""Property-based verification of the ILP solver against a brute-force reference."""

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.solver import solve_assignment
from src.types import AssignmentStatus, SolverStatus
from tests.reference import brute_force_optimum

# Hostile IDs: spaces, underscores, commas, unicode - keeps the
# PuLP-name-sanitization fix honest.
ID_ALPHABET = string.ascii_letters + string.digits + " _-,éÜ"
ids = st.text(alphabet=ID_ALPHABET, min_size=1, max_size=8).map(str.strip).filter(bool)


@st.composite
def instances(draw, max_participants=8, max_options=4):
    participants = draw(st.lists(ids, min_size=1, max_size=max_participants, unique=True))
    options = draw(st.lists(ids, min_size=1, max_size=max_options, unique=True))
    preferences = {}
    for p in participants:
        k = draw(st.integers(0, len(options)))
        if k:
            ranked = draw(st.permutations(options))[:k]
            preferences[p] = [(o, k - i) for i, o in enumerate(ranked)]
    min_q = draw(st.integers(1, 3))
    max_q = draw(st.integers(min_q, 4))
    weight = draw(st.sampled_from([0.0, 0.25, 0.5, 1.0, 3.0]))
    return participants, options, preferences, min_q, max_q, weight


def assert_solver_invariants(result, participants, preferences, min_q, max_q, weight):
    """Invariants that must hold for every OPTIMAL result."""
    # Quota rule: 0 or [min_quota, max_quota]
    for option, count in result.option_counts.items():
        assert count == 0 or min_q <= count <= max_q, (option, count)

    # Assignment validity
    for p in participants:
        assignment = result.participant_assignments[p]
        if preferences.get(p):
            assert assignment.status == AssignmentStatus.ASSIGNED
            assert assignment.option in [o for o, _ in preferences[p]]
        else:
            assert assignment.status == AssignmentStatus.NO_PREFERENCES

    # Objective identity (regression: ghost-y inflation bug)
    m = result.metrics
    assert m.objective_value == pytest.approx(m.preference_satisfaction + weight * m.active_options)

    # Metrics consistency
    assert m.preference_satisfaction == sum(
        a.preference_score for a in result.participant_assignments.values()
    )
    assert sum(m.preference_distribution.values()) == len(participants)
    assert result.option_counts == {o: len(ps) for o, ps in result.assignments.items()}


class TestReferenceSolver:
    """Hand-computed cases proving the reference solver itself is correct."""

    def test_forced_pairing_optimum(self):
        """Same instance as TestKnownOptimum: optimum is 2+2+2+1 = 7."""
        preferences = {
            "p1": [("o1", 2), ("o2", 1)],
            "p2": [("o1", 2)],
            "p3": [("o1", 2), ("o2", 1)],
            "p4": [("o2", 2)],
        }
        best, assignment = brute_force_optimum(
            ["p1", "p2", "p3", "p4"],
            ["o1", "o2"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.0,
        )
        assert best == 7
        assert assignment["p2"] == "o1"
        assert assignment["p4"] == "o2"

    def test_weight_counts_active_options(self):
        preferences = {"p1": [("o1", 1)], "p2": [("o1", 1)]}
        best, _ = brute_force_optimum(
            ["p1", "p2"],
            ["o1", "o2"],
            preferences,
            min_quota=2,
            max_quota=2,
            option_weight=0.5,
        )
        assert best == 2.5  # satisfaction 2 + 0.5 * 1 active option

    def test_infeasible_returns_none(self):
        preferences = {"p1": [("o1", 1)]}
        best, assignment = brute_force_optimum(
            ["p1"], ["o1"], preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert best is None
        assert assignment is None

    def test_no_preferences_is_trivially_optimal(self):
        best, assignment = brute_force_optimum(
            ["p1"], ["o1"], {}, min_quota=1, max_quota=3, option_weight=0.5
        )
        assert best == 0.0
        assert assignment == {}


@pytest.mark.slow
class TestSolverInvariants:
    @given(instance=instances())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_invariants_hold(self, instance):
        participants, options, preferences, min_q, max_q, weight = instance
        result = solve_assignment(
            participants,
            options,
            preferences,
            min_quota=min_q,
            max_quota=max_q,
            option_weight=weight,
        )
        if result.status == SolverStatus.OPTIMAL:
            assert_solver_invariants(result, participants, preferences, min_q, max_q, weight)
        else:
            assert result.status == SolverStatus.INFEASIBLE
            assert result.infeasibility_hints


@pytest.mark.slow
class TestBruteForceAgreement:
    """The killer property: the ILP must agree with exhaustive enumeration."""

    @given(instance=instances(max_participants=6, max_options=4))
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_optimality_and_feasibility(self, instance):
        participants, options, preferences, min_q, max_q, weight = instance
        result = solve_assignment(
            participants,
            options,
            preferences,
            min_quota=min_q,
            max_quota=max_q,
            option_weight=weight,
        )
        best, _ = brute_force_optimum(participants, options, preferences, min_q, max_q, weight)
        if best is None:
            assert result.status == SolverStatus.INFEASIBLE
        else:
            assert result.status == SolverStatus.OPTIMAL
            assert result.metrics.objective_value == pytest.approx(best)
