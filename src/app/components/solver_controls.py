"""Solver Controls UI component."""

import random

import streamlit as st

from src.solver import solve_assignment
from src.types import DEFAULT_MAX_QUOTA, DEFAULT_MIN_QUOTA


def render_solver_controls(
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
) -> None:
    """Render the solver settings and run button."""
    st.header("⚙️ Solver Settings")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        min_quota = st.slider(
            "Min Quota", 1, 5, DEFAULT_MIN_QUOTA, help="Minimum participants per active option"
        )

    with col2:
        max_quota = st.slider(
            "Max Quota", min_quota, 10, DEFAULT_MAX_QUOTA, help="Maximum participants per option"
        )

    with col3:
        option_weight = st.slider(
            "Option Weight",
            0.0,
            2.0,
            0.5,
            0.1,
            help="Weight for option utilization. Higher = favor more active options.",
        )

    with col4:
        shuffle = st.checkbox(
            "Shuffle participants",
            help="Shuffle participant order (affects tie-breaking).",
        )
        seed = st.number_input(
            "Random Seed",
            min_value=0,
            max_value=9999,
            value=42,
            disabled=not shuffle,
            help="Seed for reproducible shuffling.",
        )

    if st.button("🚀 Run Solver", type="primary"):
        with st.spinner("Solving assignment problem..."):
            # Optionally shuffle participants
            solve_participants = participants.copy()
            if shuffle:
                random.Random(seed).shuffle(solve_participants)

            result = solve_assignment(
                participants=solve_participants,
                options=options,
                preferences=preferences,
                min_quota=min_quota,
                max_quota=max_quota,
                option_weight=option_weight,
            )
            st.session_state.result = result
            # Store solver params for results dashboard
            st.session_state.min_quota = min_quota
            st.session_state.max_quota = max_quota
