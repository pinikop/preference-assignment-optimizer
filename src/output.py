"""Output formatting and export for solver results."""

import csv
from pathlib import Path

from src.types import SolverResult


def print_assignment_summary(result: SolverResult) -> None:
    """Pretty-print assignment results."""
    print(f"\n=== Solver Status: {result.status.value} ===\n")

    if result.metrics:
        m = result.metrics
        print(f"Preference Satisfaction: {m.preference_satisfaction}")
        print(f"Active Options: {m.active_options}")
        print(f"Average Satisfaction: {m.average_satisfaction:.2f}")
        print(f"Objective Value: {m.objective_value:.2f}")

        print("\nPreference Distribution:")
        for rank, count in sorted(m.preference_distribution.items(), key=lambda x: str(x[0])):
            if count > 0:
                print(f"  {rank}: {count}")

        if m.constraint_violations:
            print("\n⚠️  Constraint Violations:")
            for v in m.constraint_violations:
                print(f"  - {v}")

    print("\n=== Assignments by Option ===")
    for option, participants in sorted(result.assignments.items()):
        if participants:
            print(f"{option}: {', '.join(participants)}")


def export_results_to_csv(result: SolverResult, filepath: Path | str) -> None:
    """Export participant assignments to CSV."""
    try:
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["participant_id", "assigned_option", "preference_rank", "preference_score", "status"]
            )
            for participant, assignment in sorted(result.participant_assignments.items()):
                writer.writerow([
                    participant,
                    assignment.option,
                    assignment.preference_rank or "",
                    assignment.preference_score,
                    assignment.status.value,
                ])
    except OSError as e:
        raise OSError(f"Failed to write results to '{filepath}': {e}") from e
