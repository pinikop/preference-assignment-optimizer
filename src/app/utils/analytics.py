"""Analytics functions for preference data analysis."""

from collections import Counter

import pandas as pd
import streamlit as st


@st.cache_data
def calculate_option_popularity(
    options: list[str], preferences: dict[str, list[tuple[str, int]]]
) -> pd.DataFrame:
    """Calculate how many times each option was selected (at any rank)."""
    counts: Counter[str] = Counter()
    for prefs in preferences.values():
        for option, _ in prefs:
            counts[option] += 1

    # Include options with 0 selections
    for option in options:
        if option not in counts:
            counts[option] = 0

    df = pd.DataFrame(
        [(option, count) for option, count in counts.items()],
        columns=["Option", "Total Selections"],
    )
    return df.sort_values("Total Selections", ascending=False).reset_index(drop=True)


@st.cache_data
def calculate_weighted_popularity(
    options: list[str], preferences: dict[str, list[tuple[str, int]]]
) -> pd.DataFrame:
    """Calculate weighted popularity (1st choice = 5pts, 5th = 1pt)."""
    scores: Counter[str] = Counter()
    for prefs in preferences.values():
        for option, score in prefs:
            scores[option] += score

    # Include options with 0 score
    for option in options:
        if option not in scores:
            scores[option] = 0

    df = pd.DataFrame(
        [(option, score) for option, score in scores.items()],
        columns=["Option", "Weighted Score"],
    )
    return df.sort_values("Weighted Score", ascending=False).reset_index(drop=True)


@st.cache_data
def calculate_competition_index(
    options: list[str], preferences: dict[str, list[tuple[str, int]]], capacity: int = 3
) -> pd.DataFrame:
    """Calculate competition index (demand / capacity) per option."""
    # Count how many participants have each option as 1st or 2nd choice
    demand: Counter[str] = Counter()
    for prefs in preferences.values():
        for idx, (option, _) in enumerate(prefs[:2]):  # Top 2 choices
            demand[option] += 1

    for option in options:
        if option not in demand:
            demand[option] = 0

    df = pd.DataFrame(
        [
            (option, count, round(count / capacity, 2))
            for option, count in demand.items()
        ],
        columns=["Option", "Top-2 Demand", "Competition Index"],
    )
    return df.sort_values("Competition Index", ascending=False).reset_index(drop=True)


@st.cache_data
def get_results_csv(result) -> str:
    """Generate CSV content from results."""
    from io import StringIO

    output = StringIO()
    output.write(
        "participant_id,assigned_option,preference_rank,preference_score,status\n"
    )
    for participant, assignment in sorted(result.participant_assignments.items()):
        output.write(
            f"{participant},{assignment.option},{assignment.preference_rank or ''},"
            f"{assignment.preference_score},{assignment.status.value}\n"
        )
    return output.getvalue()
