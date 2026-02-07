"""Solver Controls UI component."""

import random

import streamlit as st

from src.solver import solve_assignment


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
            "Min Quota", 1, 5, 2, help="Minimum participants per active option"
        )

    with col2:
        max_quota = st.slider(
            "Max Quota", min_quota, 10, 3, help="Maximum participants per option"
        )

    with col3:
        option_weight = st.slider(
            "Option Weight",
            0.0,
            2.0,
            1.0,
            0.1,
            help="Weight for option utilization. Higher = favor more active options.",
        )

    with col4:
        seed = st.number_input(
            "Random Seed",
            min_value=0,
            max_value=9999,
            value=0,
            help="Set to 0 for no shuffling, or a positive number for reproducible shuffling.",
        )

    if st.button("🚀 Run Solver", type="primary"):
        with st.spinner("Solving assignment problem..."):
            # Optionally shuffle participants
            solve_participants = participants.copy()
            if seed > 0:
                random.seed(seed)
                random.shuffle(solve_participants)

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
