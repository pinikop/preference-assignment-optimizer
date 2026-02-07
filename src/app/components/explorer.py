"""Preference Explorer UI component."""

import pandas as pd
import streamlit as st

from src.app.utils.analytics import (
    calculate_competition_index,
    calculate_option_popularity,
    calculate_weighted_popularity,
)
from src.app.utils.visualizations import (
    create_competition_index_chart,
    create_preference_heatmap,
    create_weighted_popularity_chart,
)


def render_explorer(
    raw_df: pd.DataFrame,
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    num_choices: int,
) -> None:
    """Render the preference explorer section with multiple tabs."""
    st.header("📋 Preference Explorer")

    explorer_tabs = st.tabs(
        [
            "Full Table",
            "Participant Lookup",
            "Most/Least Popular",
            "Competition Index",
            "Preference Heatmap",
        ]
    )

    with explorer_tabs[0]:
        st.subheader("Raw Preferences Table")
        st.dataframe(raw_df, use_container_width=True, height=400)

    with explorer_tabs[1]:
        st.subheader("Participant Lookup")
        selected_participant = st.selectbox(
            "Select a participant",
            participants,
            key="participant_lookup",
        )
        if selected_participant:
            prefs = preferences.get(selected_participant, [])
            if prefs:
                st.write(f"**{selected_participant}'s ranked choices:**")
                pref_df = pd.DataFrame(
                    [
                        (rank, option, score)
                        for rank, (option, score) in enumerate(prefs, 1)
                    ],
                    columns=["Rank", "Option", "Score"],
                )
                st.table(pref_df)
            else:
                st.warning("No preferences found for this participant.")

    with explorer_tabs[2]:
        st.subheader("Option Popularity")

        col1, col2 = st.columns(2)

        with col1:
            k = st.slider(
                "Top/Bottom K options", 3, min(10, len(options)), 5, key="popularity_k"
            )

        popularity_df = calculate_option_popularity(options, preferences)
        weighted_df = calculate_weighted_popularity(options, preferences)

        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Top {k} Most Wanted** (by total selections)")
            st.dataframe(
                popularity_df.head(k), use_container_width=True, hide_index=True
            )

            st.write(f"**Bottom {k} Least Wanted**")
            bottom_k = popularity_df.tail(k).iloc[::-1]
            st.dataframe(bottom_k, use_container_width=True, hide_index=True)

        with col2:
            st.write(f"**Top {k} by Weighted Score** (1st=5pts, 5th=1pt)")
            st.dataframe(weighted_df.head(k), use_container_width=True, hide_index=True)

            # Bar chart
            fig = create_weighted_popularity_chart(weighted_df)
            st.plotly_chart(fig, use_container_width=True)

    with explorer_tabs[3]:
        st.subheader("Competition Index")
        st.markdown(
            "Competition Index = (# participants with option in top 2 choices) ÷ capacity. "
            "Values > 1.0 indicate oversubscribed options."
        )

        capacity = st.number_input(
            "Capacity (max quota)",
            min_value=1,
            max_value=10,
            value=3,
            key="comp_capacity",
        )
        competition_df = calculate_competition_index(options, preferences, capacity)

        col1, col2 = st.columns([1, 2])

        with col1:
            st.dataframe(competition_df, use_container_width=True, hide_index=True)

        with col2:
            fig = create_competition_index_chart(competition_df)
            st.plotly_chart(fig, use_container_width=True)

    with explorer_tabs[4]:
        st.subheader("Preference Heatmap")
        st.markdown("Shows how often each option appears at each preference rank.")
        fig = create_preference_heatmap(options, preferences, num_choices)
        st.plotly_chart(fig, use_container_width=True)
