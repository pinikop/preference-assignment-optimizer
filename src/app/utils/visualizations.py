"""Visualization functions for creating Plotly charts."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


@st.cache_data
def create_preference_heatmap(
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    num_choices: int = 5,
) -> go.Figure:
    """Create a heatmap showing how often each option appears at each rank."""
    # Initialize count matrix
    rank_counts: dict[str, dict[int, int]] = {
        option: {r: 0 for r in range(1, num_choices + 1)} for option in options
    }

    for prefs in preferences.values():
        for rank, (option, _) in enumerate(prefs, start=1):
            if rank <= num_choices:
                rank_counts[option][rank] += 1

    # Create DataFrame for heatmap
    df = pd.DataFrame(rank_counts).T
    df.columns = [f"Rank {i}" for i in range(1, num_choices + 1)]
    df = df.sort_index()

    fig = px.imshow(
        df,
        labels=dict(x="Preference Rank", y="Option", color="Count"),
        aspect="auto",
        color_continuous_scale="Blues",
    )
    fig.update_layout(title="Preference Distribution Heatmap")
    return fig


@st.cache_data
def create_weighted_popularity_chart(weighted_df: pd.DataFrame) -> go.Figure:
    """Create a bar chart for weighted popularity scores."""
    fig = px.bar(
        weighted_df.head(10),
        x="Option",
        y="Weighted Score",
        title="Top 10 Options by Weighted Popularity",
    )
    return fig


@st.cache_data
def create_competition_index_chart(competition_df: pd.DataFrame) -> go.Figure:
    """Create a bar chart for competition index with capacity threshold."""
    fig = px.bar(
        competition_df.head(15),
        x="Option",
        y="Competition Index",
        title="Competition Index (Top 15 Options)",
        color="Competition Index",
        color_continuous_scale="RdYlGn_r",
    )
    fig.add_hline(
        y=1.0, line_dash="dash", line_color="red", annotation_text="Capacity threshold"
    )
    return fig


@st.cache_data
def create_preference_distribution_chart(dist_data: list[dict]) -> go.Figure:
    """Create a bar chart showing how participants are distributed across preference ranks."""
    dist_df = pd.DataFrame(dist_data)
    fig = px.bar(
        dist_df,
        x="Rank",
        y="Count",
        title="Participants by Assigned Preference Rank",
        color="Count",
        color_continuous_scale="Greens",
    )
    return fig


@st.cache_data
def create_option_fill_pie_chart(fill_counts: dict[str, int]) -> go.Figure:
    """Create a pie chart showing option fill rates."""
    fill_df = pd.DataFrame(
        [{"Fill Level": k, "Count": v} for k, v in fill_counts.items() if v > 0]
    )
    fig = px.pie(
        fill_df,
        values="Count",
        names="Fill Level",
        title="Active Option Fill Rates",
    )
    return fig


@st.cache_data
def create_satisfaction_histogram(scores: list[int], num_choices: int) -> go.Figure:
    """Create a histogram showing distribution of individual satisfaction scores."""
    fig = px.histogram(
        x=scores,
        nbins=num_choices + 1,
        labels={"x": "Satisfaction Score", "y": "Count"},
        title="Distribution of Individual Satisfaction Scores",
    )
    return fig
