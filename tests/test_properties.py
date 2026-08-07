"""Property-based verification of the ILP solver against a brute-force reference."""

from tests.reference import brute_force_optimum


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
