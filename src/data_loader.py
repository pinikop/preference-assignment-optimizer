"""Load student preferences from CSV files."""

from pathlib import Path

import pandas as pd


def rank_to_score(rank: int, max_rank: int = 5) -> int:
    """Convert a preference ranking to a score.

    Args:
        rank: 1 for first choice, 2 for second, etc.
        max_rank (optional): The maximum rank value (e.g., 5 for five choices). Defaults to 5.
    Returns:
        Score where higher is better (5 for rank 1, 4 for rank 2, etc.)
    """
    return max_rank - rank + 1


def load_preferences_from_csv(
    filepath: Path | str,
) -> tuple[list[str], list[str], dict[str, list[tuple[str, int]]]]:
    """Load student preferences from a CSV file.

    Args:
        filepath: Path to CSV where the 1st column is participants and subsequent columns are ordered choices (choice_1, choice_2, ..., choice_5)

    Returns:
        Tuple of (participants, options, preferences) where:
        - participants: List of participant
        - options: List of unique options
        - preferences: Dict mapping participant_id -> [(option, score), ...]
          where score is len(choices) for 1st choice, len(choices)-1 for 2nd, etc.
    """
    if isinstance(filepath, str):
        filepath = Path(filepath)

    df = pd.read_csv(
        filepath, index_col=0
    )  # Assume first column is participant's unique identifier

    participants = df.index.tolist()
    options = sorted({val for val in df.values.flatten() if pd.notna(val)})
    num_choices = len(df.columns)

    preferences = {}
    for row in df.itertuples():
        preferences[row.Index] = [
            (option, rank_to_score(rank, num_choices))
            for rank, option in enumerate(row[1:], start=1)  # Skip index
            if pd.notna(option)
        ]

    return participants, options, preferences
