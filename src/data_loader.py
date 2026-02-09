"""Load student preferences from CSV files."""

from pathlib import Path

import pandas as pd


def rank_to_score(rank: int, max_rank: int) -> int:
    """Convert a preference ranking to a score.

    Args:
        rank: 1 for first choice, 2 for second, etc.
        max_rank: The maximum rank value (e.g., 5 for five choices).
    Returns:
        Score where higher is better (5 for rank 1, 4 for rank 2, etc.)
    """
    return max_rank - rank + 1


def load_preferences_from_csv(
    filepath: Path | str,
) -> tuple[list[str], list[str], dict[str, list[tuple[str, int]]]]:
    """Load student preferences from a CSV file.

    Args:
        filepath: Path to CSV where the 1st column is participants and
            subsequent columns are ordered choices (any number of columns).

    Returns:
        Tuple of (participants, options, preferences) where:
        - participants: List of participant IDs (from CSV index column)
        - options: List of unique options derived from all preference values in CSV
        - preferences: Dict mapping participant_id -> [(option, score), ...]
          where score is len(choices) for 1st choice, len(choices)-1 for 2nd, etc.

    Raises:
        ValueError: If CSV is empty, malformed, or contains duplicate options for a participant.
    """
    if isinstance(filepath, str):
        filepath = Path(filepath)

    try:
        df = pd.read_csv(filepath, index_col=0)
    except pd.errors.EmptyDataError as e:
        raise ValueError(f"CSV file is empty: {filepath}") from e
    except pd.errors.ParserError as e:
        raise ValueError(f"Failed to parse CSV: {e}") from e

    if df.empty:
        raise ValueError(f"CSV file contains no data rows: {filepath}")

    participants = df.index.tolist()
    options = sorted({val for val in df.values.flatten() if pd.notna(val)})
    num_choices = len(df.columns)

    preferences = {}
    for row in df.itertuples():
        prefs = [
            (option, rank_to_score(rank, num_choices))
            for rank, option in enumerate(row[1:], start=1)
            if pd.notna(option)
        ]

        # Check for duplicate options
        seen: set[str] = set()
        for option, _ in prefs:
            if option in seen:
                raise ValueError(
                    f"Duplicate option '{option}' for participant '{row.Index}'"
                )
            seen.add(option)

        preferences[row.Index] = prefs

    return participants, options, preferences
