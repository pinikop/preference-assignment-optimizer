"""Load student preferences from CSV files."""

import pandas as pd


def load_preferences_from_csv(
    filepath: str,
) -> tuple[list[str], list[str], dict[str, list[tuple[str, int]]]]:
    """Load student preferences from a CSV file.

    Args:
        filepath: Path to CSV with columns: student_id, choice_1, choice_2, ..., choice_5

    Returns:
        Tuple of (students, projects, preferences) where:
        - students: List of student IDs
        - projects: List of unique project IDs
        - preferences: Dict mapping student_id -> [(project, score), ...]
          where score is 5 for 1st choice, 4 for 2nd, etc.
    """
    df = pd.read_csv(filepath)

    students = df["student_id"].tolist()

    choice_columns = [col for col in df.columns if col.startswith("choice_")]
    choice_columns.sort(key=lambda x: int(x.split("_")[1]))

    all_projects: set[str] = set()
    for col in choice_columns:
        all_projects.update(df[col].dropna().unique())
    projects = sorted(all_projects)

    preferences: dict[str, list[tuple[str, int]]] = {}
    for _, row in df.iterrows():
        student_id = row["student_id"]
        student_prefs: list[tuple[str, int]] = []
        for rank, col in enumerate(choice_columns, start=1):
            project = row[col]
            if pd.notna(project):
                score = ranking_to_score(rank)
                student_prefs.append((project, score))
        preferences[student_id] = student_prefs

    return students, projects, preferences


def ranking_to_score(rank: int) -> int:
    """Convert a preference ranking to a score.

    Args:
        rank: 1 for first choice, 2 for second, etc.

    Returns:
        Score where higher is better (5 for rank 1, 4 for rank 2, etc.)
    """
    return 6 - rank
