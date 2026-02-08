"""Solver module for preference assignment optimization using ILP."""

from collections import defaultdict

from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value

from src.types import (
    AssignmentStatus,
    Metrics,
    ModelComponents,
    ParticipantAssignment,
    SolverResult,
    SolverStatus,
)

# Values above threshold are treated as 1, otherwise 0 (handles floating-point precision)
BINARY_THRESHOLD = 0.5


def _find_preference_rank(prefs: list[tuple[str, int]], option: str) -> int | None:
    """Find the 1-based rank of an option in a participant's preference list."""
    for idx, (pref_option, _) in enumerate(prefs):
        if pref_option == option:
            return idx + 1
    return None


def _build_model(
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    option_weight: float,
) -> ModelComponents:
    """
    Build the ILP model with decision variables and objective function.

    Returns:
        ModelComponents containing model, x (assignment vars), and y (option usage vars)
    """
    model = LpProblem("Preference-Assignment", LpMaximize)

    # Decision variables for participant-option assignments
    x: dict[tuple[str, str], LpVariable] = {}
    for participant in participants:
        for option, _ in preferences.get(participant, []):
            x[participant, option] = LpVariable(
                f"x_{participant}_{option}", cat="Binary"
            )

    # Decision variables for option usage
    y = {option: LpVariable(f"y_{option}", cat="Binary") for option in options}

    # Objective function:
    # 1. Maximize preference score
    # 2. Maximize number of options used (with weight)
    preference_sum = lpSum(
        x[participant, option] * score
        for participant in participants
        for option, score in preferences.get(participant, [])
    )
    option_utilization = lpSum(y[option] for option in options)
    model += preference_sum + option_weight * option_utilization

    return ModelComponents(model=model, x=x, y=y)


def _add_constraints(
    model: LpProblem,
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    x: dict[tuple[str, str], LpVariable],
    y: dict[str, LpVariable],
    option_to_participants: dict[str, set[str]],
    min_quota: int,
    max_quota: int,
) -> None:
    """Add all constraints to the model."""
    # Constraint: Each participant with preferences is assigned to exactly one option
    for participant in participants:
        participant_prefs = preferences.get(participant, [])
        if participant_prefs:
            model += (
                lpSum(x[participant, option] for option, _ in participant_prefs) == 1
            )

    # Constraints for option usage and size
    # Simplified: if y=0 then count=0, if y=1 then count in {2,3}
    for option in options:
        participants_with_option = option_to_participants.get(option, set())

        if not participants_with_option:
            continue

        option_count = lpSum(
            x[participant, option] for participant in participants_with_option
        )

        # If active (y=1), at least min_quota participants; if inactive (y=0), must be 0
        model += option_count >= min_quota * y[option]
        model += option_count <= max_quota * y[option]


def _process_assignments(
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    x: dict[tuple[str, str], LpVariable],
) -> tuple[dict[str, list[str]], dict[str, ParticipantAssignment]]:
    """
    Extract assignments from the solved model.

    Returns:
        Tuple of (option_assignments, participant_assignments)
    """
    option_assignments: dict[str, list[str]] = {option: [] for option in options}
    participant_assignments: dict[str, ParticipantAssignment] = {}

    for participant in participants:
        participant_prefs = preferences.get(participant, [])

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
                value(x[participant, option]) if (participant, option) in x else 0.0
            )
            if (
                var_value is not None
                and isinstance(var_value, (int, float))
                and var_value > BINARY_THRESHOLD
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
    participants: list[str],
    options: list[str],
    option_assignments: dict[str, list[str]],
    participant_assignments: dict[str, ParticipantAssignment],
    objective_value: float,
    min_quota: int,
    max_quota: int,
) -> Metrics:
    """Calculate metrics from the solved assignments."""
    # Calculate preference satisfaction
    preference_satisfaction = sum(
        assignment.preference_score for assignment in participant_assignments.values()
    )

    # Count active options
    option_counts = {
        option: len(assigned) for option, assigned in option_assignments.items()
    }
    active_options = sum(1 for count in option_counts.values() if count > 0)

    # Calculate preference distribution
    preference_distribution: dict[int | str, int] = {
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 0,
        "unassigned": 0,
        "no_preferences": 0,
    }

    for assignment in participant_assignments.values():
        if assignment.status == AssignmentStatus.UNASSIGNED:
            preference_distribution["unassigned"] += 1
        elif assignment.status == AssignmentStatus.NO_PREFERENCES:
            preference_distribution["no_preferences"] += 1
        elif (
            assignment.preference_rank is not None
            and 1 <= assignment.preference_rank <= 5
        ):
            preference_distribution[assignment.preference_rank] += 1

    # Find unused options
    unused_options = [option for option, count in option_counts.items() if count == 0]

    # Check for constraint violations
    constraint_violations = []
    for option, count in option_counts.items():
        if count > 0 and (count < min_quota or count > max_quota):
            constraint_violations.append(
                f"Option {option} has {count} participants, "
                f"but should have 0 or {min_quota}-{max_quota}"
            )

    return Metrics(
        preference_satisfaction=preference_satisfaction,
        active_options=active_options,
        average_satisfaction=(
            preference_satisfaction / len(participants) if participants else 0.0
        ),
        objective_value=objective_value,
        preference_distribution=preference_distribution,
        unused_options=unused_options,
        constraint_violations=constraint_violations,
    )


def solve_assignment(
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    min_quota: int = 2,
    max_quota: int = 3,
    option_weight: float = 1.0,
) -> SolverResult:
    """
    Solve the preference assignment problem using integer programming.

    Parameters:
        participants: List of participant IDs
        options: List of option IDs
        preferences: Dictionary mapping participants to their option preferences with scores
                     e.g., {'Participant1': [('OptionA', 5), ('OptionB', 4), ...]}
        min_quota: Minimum participants per active option (default 2)
        max_quota: Maximum participants per option (default 3)
        option_weight: Weight for the option utilization objective (default 1.0)
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
    # Validate quota parameters
    if min_quota < 1:
        raise ValueError("min_quota must be at least 1")
    if max_quota < min_quota:
        raise ValueError("max_quota must be >= min_quota")
    # Pre-compute inverted index: option -> participants who have it in preferences
    option_to_participants: dict[str, set[str]] = defaultdict(set)
    for participant, prefs in preferences.items():
        for option, _ in prefs:
            option_to_participants[option].add(participant)

    # Build model with variables and objective
    components = _build_model(participants, options, preferences, option_weight)

    # Add constraints
    _add_constraints(
        components.model,
        participants,
        options,
        preferences,
        components.x,
        components.y,
        option_to_participants,
        min_quota,
        max_quota,
    )

    # Solve
    status_code = components.model.solve()

    # Map PuLP status codes to SolverStatus
    status_map = {
        1: SolverStatus.OPTIMAL,
        -1: SolverStatus.INFEASIBLE,
        -2: SolverStatus.UNBOUNDED,
        0: SolverStatus.NOT_SOLVED,
    }
    solver_status = status_map.get(status_code, SolverStatus.NOT_SOLVED)

    # Initialize result structure
    option_assignments: dict[str, list[str]] = {option: [] for option in options}
    participant_assignments: dict[str, ParticipantAssignment] = {}
    option_counts: dict[str, int] = {option: 0 for option in options}
    metrics: Metrics | None = None

    if solver_status == SolverStatus.OPTIMAL:
        # Process assignments
        option_assignments, participant_assignments = _process_assignments(
            participants, options, preferences, components.x
        )

        # Calculate option counts
        option_counts = {
            option: len(assigned) for option, assigned in option_assignments.items()
        }

        # Calculate metrics
        objective_value = value(components.model.objective)
        obj_float = (
            float(objective_value)
            if objective_value is not None and isinstance(objective_value, (int, float))
            else 0.0
        )
        metrics = _calculate_metrics(
            participants,
            options,
            option_assignments,
            participant_assignments,
            obj_float,
            min_quota,
            max_quota,
        )

    return SolverResult(
        status=solver_status,
        assignments=option_assignments,
        option_counts=option_counts,
        participant_assignments=participant_assignments,
        metrics=metrics,
    )
