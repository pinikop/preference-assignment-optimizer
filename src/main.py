"""CLI entry point for preference assignment optimizer."""

import random
from pathlib import Path
from typing import Annotated, Optional

import typer

from src.data_loader import load_preferences_from_csv
from src.output import export_results_to_csv, print_assignment_summary
from src.solver import solve_assignment

app = typer.Typer(
    help="Optimize participant-to-option assignments based on preferences"
)


@app.command()
def main(
    csv_file: Annotated[
        Path,
        typer.Argument(
            help="Path to preferences CSV file (column 1: participants, column 2+: options by priority)"
        ),
    ],
    min_quota: Annotated[
        int,
        typer.Option(
            "-m", "--min-quota", help="Minimum participants per active option"
        ),
    ] = 2,
    max_quota: Annotated[
        int, typer.Option("-q", "--max-quota", help="Maximum participants per option")
    ] = 3,
    option_weight: Annotated[
        float,
        typer.Option("-w", "--option-weight", help="Weight for option utilization"),
    ] = 1.0,
    shuffle: Annotated[
        bool,
        typer.Option(
            "--shuffle",
            help="Shuffle participant order (affects tie-breaking); if --seed is not set, not reproducible",
        ),
    ] = False,
    seed: Annotated[
        Optional[int],
        typer.Option(
            "-s",
            "--seed",
            help="Random seed for reproducible shuffling (implies --shuffle)",
        ),
    ] = None,
    output: Annotated[
        Optional[Path], typer.Option("-o", "--output", help="Export results to CSV")
    ] = None,
) -> None:
    """Run the preference assignment optimizer."""
    if not csv_file.exists():
        typer.echo(f"Error: File not found: {csv_file}", err=True)
        raise typer.Exit(1)

    if min_quota > max_quota:
        typer.echo(
            f"Error: min_quota ({min_quota}) cannot be greater than max_quota ({max_quota})",
            err=True,
        )
        raise typer.Exit(1)

    participants, options, preferences = load_preferences_from_csv(csv_file)

    # Shuffle participant order if requested (affects tie-breaking)
    if seed is not None or shuffle:
        if seed is not None:
            random.seed(seed)
        participants = participants.copy()  # Avoid modifying original list in-place
        random.shuffle(participants)

    result = solve_assignment(
        participants,
        options,
        preferences,
        min_quota=min_quota,
        max_quota=max_quota,
        option_weight=option_weight,
    )

    print_assignment_summary(result)

    if output:
        export_results_to_csv(result, str(output))
        typer.echo(f"\nResults exported to: {output}")


if __name__ == "__main__":
    app()
