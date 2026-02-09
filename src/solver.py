"""Solver module for preference assignment optimization using ILP."""

from collections import defaultdict

from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value
from pulp.constants import (
    LpStatusInfeasible,
    LpStatusNotSolved,
    LpStatusOptimal,
    LpStatusUnbounded,
)

from src.types import (
    AssignmentStatus,
    Metrics,
    ParticipantAssignment,
    SolverResult,
    SolverStatus,
)


def _find_preference_rank(prefs: list[tuple[str, int]], option: str) -> int | None:
    """Find the 1-based rank of an option in a participant's preference list."""
    for idx, (pref_option, _) in enumerate(prefs):
        if pref_option == option:
            return idx + 1
    return None


class PreferenceAssignmentSolver:
    """
    ILP-based solver for preference assignment optimization.

    This solver assigns participants to options based on ranked preferences,
    maximizing preference satisfaction while respecting quota constraints.

    Attributes:
        participants: List of participant IDs
        options: List of option IDs
        preferences: Dictionary mapping participants to their option preferences with scores
        min_quota: Minimum participants per active option
        max_quota: Maximum participants per option
        option_weight: Weight for the option utilization objective
    """

    def __init__(
        self,
        participants: list[str],
        options: list[str],
        preferences: dict[str, list[tuple[str, int]]],
        min_quota: int = 2,
        max_quota: int = 3,
        option_weight: float = 1.0,
    ):
        """
        Initialize the solver with problem data.

        Parameters:
            participants: List of participant IDs
            options: List of option IDs
            preferences: Dictionary mapping participants to their option preferences with scores
                         e.g., {'Participant1': [('OptionA', 5), ('OptionB', 4), ...]}
            min_quota: Minimum participants per active option (default: 2)
            max_quota: Maximum participants per option (default: 3)
            option_weight: Weight for the option utilization objective (default: 1.0)

        Raises:
            ValueError: If min_quota < 1 or max_quota < min_quota
        """
        if min_quota < 1:
            raise ValueError("min_quota must be at least 1")
        if max_quota < min_quota:
            raise ValueError("max_quota must be >= min_quota")

        self.participants = participants
        self.options = options
        self.preferences = preferences
        self.min_quota = min_quota
        self.max_quota = max_quota
        self.option_weight = option_weight

        # Pre-compute option -> participants mapping
        self._option_to_participants = self._build_option_index()

        # Model state (set during solve)
        self._model: LpProblem | None = None
        self._x: dict[tuple[str, str], LpVariable] = {}
        self._y: dict[str, LpVariable] = {}

    def _build_option_index(self) -> dict[str, set[str]]:
        """Pre-compute inverted index: option -> participants who have it in preferences."""
        option_to_participants: dict[str, set[str]] = defaultdict(set)
        for participant, prefs in self.preferences.items():
            for option, _ in prefs:
                option_to_participants[option].add(participant)
        return option_to_participants

    def _build_model(self) -> None:
        """Build the ILP model with decision variables and objective function."""
        self._model = LpProblem("Preference-Assignment", LpMaximize)

        # Decision variables for participant-option assignments
        self._x = {}
        for participant in self.participants:
            for option, _ in self.preferences.get(participant, []):
                self._x[participant, option] = LpVariable(
                    f"x_{participant}_{option}", cat="Binary"
                )

        # Decision variables for option usage
        self._y = {
            option: LpVariable(f"y_{option}", cat="Binary") for option in self.options
        }

        # Objective function:
        # 1. Maximize preference score
        # 2. Maximize number of options used (with weight)
        preference_sum = lpSum(
            self._x[participant, option] * score
            for participant in self.participants
            for option, score in self.preferences.get(participant, [])
        )
        option_utilization = lpSum(self._y[option] for option in self.options)
        self._model += preference_sum + self.option_weight * option_utilization

    def _add_constraints(self) -> None:
        """Add all constraints to the model."""
        if self._model is None:
            raise RuntimeError("Model must be built before adding constraints")

        # Constraint: Each participant with preferences is assigned to exactly one option
        for participant in self.participants:
            participant_prefs = self.preferences.get(participant, [])
            if participant_prefs:
                constraint = (
                    lpSum(
                        self._x[participant, option] for option, _ in participant_prefs
                    )
                    == 1
                )
                self._model += constraint  # type: ignore[assignment]

        # Big-M formulation: if y[option]=0 (inactive), count=0; if y[option]=1, count in [min_quota, max_quota]
        for option in self.options:
            participants_with_option = self._option_to_participants.get(option, set())

            if not participants_with_option:
                continue

            option_count = lpSum(
                self._x[participant, option] for participant in participants_with_option
            )

            # If active (y=1), at least min_quota participants; if inactive (y=0), must be 0
            self._model += option_count >= self.min_quota * self._y[option]
            self._model += option_count <= self.max_quota * self._y[option]

    def _process_assignments(
        self,
    ) -> tuple[dict[str, list[str]], dict[str, ParticipantAssignment]]:
        """
        Extract assignments from the solved model.

        Returns:
            Tuple of (option_assignments, participant_assignments)
        """
        option_assignments: dict[str, list[str]] = {
            option: [] for option in self.options
        }
        participant_assignments: dict[str, ParticipantAssignment] = {}

        for participant in self.participants:
            participant_prefs = self.preferences.get(participant, [])

            if not participant_prefs:
                participant_assignments[participant] = ParticipantAssignment(
                    option="",
                    status=AssignmentStatus.NO_PREFERENCES,
                    preference_rank=None,
                    preference_score=0,
                )
                continue

            assigned = False
            for option, score in participant_prefs:
                var_value = (
                    value(self._x[participant, option])
                    if (participant, option) in self._x
                    else 0.0
                )
                # value() returns either float or None
                if (
                    var_value is not None
                    and isinstance(var_value, (int, float))
                    and round(var_value) == 1
                ):
                    option_assignments[option].append(participant)
                    rank = _find_preference_rank(participant_prefs, option)

                    participant_assignments[participant] = ParticipantAssignment(
                        option=option,
                        status=AssignmentStatus.ASSIGNED,
                        preference_rank=rank,
                        preference_score=score,
                    )
                    assigned = True
                    break

            if not assigned:
                participant_assignments[participant] = ParticipantAssignment(
                    option="",
                    status=AssignmentStatus.UNASSIGNED,
                    preference_rank=None,
                    preference_score=0,
                )

        return option_assignments, participant_assignments

    def _calculate_metrics(
        self,
        option_assignments: dict[str, list[str]],
        participant_assignments: dict[str, ParticipantAssignment],
        objective_value: float,
    ) -> Metrics:
        """Calculate metrics from the solved assignments."""
        # Calculate preference satisfaction
        preference_satisfaction = sum(
            assignment.preference_score
            for assignment in participant_assignments.values()
        )

        # Count active options
        option_counts = {
            option: len(assigned) for option, assigned in option_assignments.items()
        }
        active_options = sum(1 for count in option_counts.values() if count > 0)

        # Calculate preference distribution (dynamic, supports any number of choices)
        preference_distribution: dict[int | str, int] = defaultdict(int)

        for assignment in participant_assignments.values():
            if assignment.status == AssignmentStatus.UNASSIGNED:
                preference_distribution["unassigned"] += 1
            elif assignment.status == AssignmentStatus.NO_PREFERENCES:
                preference_distribution["no_preferences"] += 1
            elif assignment.preference_rank is not None:
                preference_distribution[assignment.preference_rank] += 1

        # Find unused options
        unused_options = [
            option for option, count in option_counts.items() if count == 0
        ]

        # Check for constraint violations
        constraint_violations = []
        for option, count in option_counts.items():
            if count > 0 and (count < self.min_quota or count > self.max_quota):
                constraint_violations.append(
                    f"Option {option} has {count} participants, "
                    f"but should have 0 or {self.min_quota}-{self.max_quota}"
                )

        return Metrics(
            preference_satisfaction=preference_satisfaction,
            active_options=active_options,
            average_satisfaction=(
                preference_satisfaction / len(self.participants)
                if self.participants
                else 0.0
            ),
            objective_value=objective_value,
            preference_distribution=preference_distribution,
            unused_options=unused_options,
            constraint_violations=constraint_violations,
        )

    def solve(self) -> SolverResult:
        """
        Solve the preference assignment problem.

        Option constraints:
            - Each option must have either 0 participants OR between min_quota and max_quota

        Objective:
            Maximize weighted sum of preference satisfaction (weight=1.0) and
            number of options used (weight=option_weight). Higher option_weight
            favors more active options; lower values favor pure preference satisfaction.

        Returns:
            SolverResult with assignment results and metrics
        """
        # Build model with variables and objective
        self._build_model()

        # Add constraints
        self._add_constraints()

        # Solve
        if self._model is None:
            raise RuntimeError("Model was not built")

        status_code = self._model.solve()

        # Map PuLP status codes to SolverStatus
        status_map = {
            LpStatusOptimal: SolverStatus.OPTIMAL,
            LpStatusInfeasible: SolverStatus.INFEASIBLE,
            LpStatusUnbounded: SolverStatus.UNBOUNDED,
            LpStatusNotSolved: SolverStatus.NOT_SOLVED,
        }
        solver_status = status_map.get(status_code, SolverStatus.NOT_SOLVED)

        # Initialize result structure
        option_assignments: dict[str, list[str]] = {
            option: [] for option in self.options
        }
        participant_assignments: dict[str, ParticipantAssignment] = {}
        option_counts: dict[str, int] = {option: 0 for option in self.options}
        metrics: Metrics | None = None

        if solver_status == SolverStatus.OPTIMAL:
            # Process assignments
            option_assignments, participant_assignments = self._process_assignments()

            # Calculate option counts
            option_counts = {
                option: len(assigned) for option, assigned in option_assignments.items()
            }

            # Calculate metrics
            objective_value = value(self._model.objective)
            obj_float = (
                float(objective_value)
                if objective_value is not None
                and isinstance(objective_value, (int, float))
                else 0.0
            )
            metrics = self._calculate_metrics(
                option_assignments,
                participant_assignments,
                obj_float,
            )

        return SolverResult(
            status=solver_status,
            assignments=option_assignments,
            option_counts=option_counts,
            participant_assignments=participant_assignments,
            metrics=metrics,
        )


def solve_assignment(
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    min_quota: int,
    max_quota: int,
    option_weight: float,
) -> SolverResult:
    """
    Solve the preference assignment problem using integer programming.

    This is a backward-compatible wrapper around PreferenceAssignmentSolver.

    Parameters:
        participants: List of participant IDs
        options: List of option IDs
        preferences: Dictionary mapping participants to their option preferences with scores
                     e.g., {'Participant1': [('OptionA', 5), ('OptionB', 4), ...]}
        min_quota: Minimum participants per active option
        max_quota: Maximum participants per option
        option_weight: Weight for the option utilization objective.
                       Higher values prioritize using more options

    Option constraints:
        - Each option must have either 0 participants OR between min_quota and max_quota

    Objective:
        Maximize weighted sum of preference satisfaction (weight=1.0) and
        number of options used (weight=option_weight). Higher option_weight
        favors more active options; lower values favor pure preference satisfaction.

    Returns:
        SolverResult with assignment results and metrics
    """
    solver = PreferenceAssignmentSolver(
        participants=participants,
        options=options,
        preferences=preferences,
        min_quota=min_quota,
        max_quota=max_quota,
        option_weight=option_weight,
    )
    return solver.solve()
