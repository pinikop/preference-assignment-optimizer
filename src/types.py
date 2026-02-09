"""Type definitions for the preference assignment optimizer."""

from dataclasses import dataclass, field
from enum import Enum


class SolverStatus(Enum):
    """Status of the solver result."""

    OPTIMAL = "Optimal"
    INFEASIBLE = "Infeasible"
    UNBOUNDED = "Unbounded"
    NOT_SOLVED = "Not Solved"


class AssignmentStatus(Enum):
    """Status of a participant's assignment."""

    ASSIGNED = "ASSIGNED"
    UNASSIGNED = "UNASSIGNED"
    NO_PREFERENCES = "NO_PREFERENCES"


@dataclass
class ParticipantAssignment:
    """Assignment result for a single participant."""

    option: str
    status: AssignmentStatus
    preference_rank: int | None = None
    preference_score: int = 0


@dataclass
class Metrics:
    """Metrics for solver results."""

    preference_satisfaction: int
    active_options: int
    average_satisfaction: float
    objective_value: float
    preference_distribution: dict[int | str, int]
    unused_options: list[str]
    constraint_violations: list[str] = field(default_factory=list)


@dataclass
class SolverResult:
    """Complete result from the solver."""

    status: SolverStatus
    assignments: dict[str, list[str]]  # option -> [participants]
    option_counts: dict[str, int]
    participant_assignments: dict[str, ParticipantAssignment]
    metrics: Metrics | None = None


