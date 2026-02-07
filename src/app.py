"""Streamlit app for the Preference Assignment Optimizer."""

import tempfile
from collections import Counter
from io import StringIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data_loader import load_preferences_from_csv
from src.solver import solve_assignment
from src.types import SolverStatus


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


def create_preference_heatmap(
    options: list[str], preferences: dict[str, list[tuple[str, int]]], num_choices: int = 5
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


def get_results_csv(result) -> str:
    """Generate CSV content from results."""
    output = StringIO()
    output.write("participant_id,assigned_option,preference_rank,preference_score,status\n")
    for participant, assignment in sorted(result.participant_assignments.items()):
        output.write(
            f"{participant},{assignment.option},{assignment.preference_rank or ''},"
            f"{assignment.preference_score},{assignment.status.value}\n"
        )
    return output.getvalue()


def main():
    st.set_page_config(page_title="Preference Assignment Optimizer", page_icon="📊", layout="wide")

    st.title("📊 Preference Assignment Optimizer")
    st.markdown("Optimally assign participants to options based on ranked preferences.")

    # Initialize session state
    if "result" not in st.session_state:
        st.session_state.result = None
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False

    # --- File Upload Section ---
    st.header("📁 Upload Preferences CSV")

    uploaded_file = st.file_uploader(
        "Upload a CSV file with participant preferences",
        type="csv",
        help="CSV should have participant_id as first column, followed by choice_1, choice_2, etc.",
    )

    if uploaded_file is not None:
        # Save to temp file for load_preferences_from_csv
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            participants, options, preferences = load_preferences_from_csv(tmp_path)
            st.session_state.participants = participants
            st.session_state.options = options
            st.session_state.preferences = preferences
            st.session_state.data_loaded = True

            # Read raw data for display
            uploaded_file.seek(0)
            raw_df = pd.read_csv(uploaded_file)
            st.session_state.raw_df = raw_df

            # Determine number of choices
            num_choices = len([c for c in raw_df.columns if c.startswith("choice")])
            st.session_state.num_choices = num_choices

            st.success(
                f"Loaded: **{len(participants)}** participants, "
                f"**{len(options)}** options, "
                f"**{num_choices}** choices each"
            )
        except Exception as e:
            st.error(f"Error loading CSV: {e}")
            st.session_state.data_loaded = False

    if not st.session_state.data_loaded:
        st.info("Upload a CSV file to get started.")
        return

    # Get data from session state
    participants = st.session_state.participants
    options = st.session_state.options
    preferences = st.session_state.preferences
    raw_df = st.session_state.raw_df
    num_choices = st.session_state.num_choices

    # --- Preference Explorer Section ---
    st.header("📋 Preference Explorer")

    explorer_tabs = st.tabs([
        "Full Table",
        "Participant Lookup",
        "Most/Least Popular",
        "Competition Index",
        "Preference Heatmap",
    ])

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
                    [(rank, option, score) for rank, (option, score) in enumerate(prefs, 1)],
                    columns=["Rank", "Option", "Score"],
                )
                st.table(pref_df)
            else:
                st.warning("No preferences found for this participant.")

    with explorer_tabs[2]:
        st.subheader("Option Popularity")

        col1, col2 = st.columns(2)

        with col1:
            k = st.slider("Top/Bottom K options", 3, min(10, len(options)), 5, key="popularity_k")

        popularity_df = calculate_option_popularity(options, preferences)
        weighted_df = calculate_weighted_popularity(options, preferences)

        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Top {k} Most Wanted** (by total selections)")
            st.dataframe(popularity_df.head(k), use_container_width=True, hide_index=True)

            st.write(f"**Bottom {k} Least Wanted**")
            bottom_k = popularity_df.tail(k).iloc[::-1]
            st.dataframe(bottom_k, use_container_width=True, hide_index=True)

        with col2:
            st.write(f"**Top {k} by Weighted Score** (1st=5pts, 5th=1pt)")
            st.dataframe(weighted_df.head(k), use_container_width=True, hide_index=True)

            # Bar chart
            fig = px.bar(
                weighted_df.head(10),
                x="Option",
                y="Weighted Score",
                title="Top 10 Options by Weighted Popularity",
            )
            st.plotly_chart(fig, use_container_width=True)

    with explorer_tabs[3]:
        st.subheader("Competition Index")
        st.markdown(
            "Competition Index = (# participants with option in top 2 choices) ÷ capacity. "
            "Values > 1.0 indicate oversubscribed options."
        )

        capacity = st.number_input(
            "Capacity (max quota)", min_value=1, max_value=10, value=3, key="comp_capacity"
        )
        competition_df = calculate_competition_index(options, preferences, capacity)

        col1, col2 = st.columns([1, 2])

        with col1:
            st.dataframe(competition_df, use_container_width=True, hide_index=True)

        with col2:
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
            st.plotly_chart(fig, use_container_width=True)

    with explorer_tabs[4]:
        st.subheader("Preference Heatmap")
        st.markdown("Shows how often each option appears at each preference rank.")
        fig = create_preference_heatmap(options, preferences, num_choices)
        st.plotly_chart(fig, use_container_width=True)

    # --- Solver Controls Section ---
    st.header("⚙️ Solver Settings")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        min_quota = st.slider("Min Quota", 1, 5, 2, help="Minimum participants per active option")

    with col2:
        max_quota = st.slider("Max Quota", min_quota, 10, 3, help="Maximum participants per option")

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
                import random
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

    # --- Results Dashboard ---
    if st.session_state.result is not None:
        result = st.session_state.result

        st.header("📈 Results Dashboard")

        # Status badge
        if result.status == SolverStatus.OPTIMAL:
            st.success(f"✅ Solver Status: **{result.status.value}**")
        else:
            st.error(f"❌ Solver Status: **{result.status.value}**")

        if result.metrics is None:
            st.warning("No solution found. Try adjusting parameters.")
        else:
            metrics = result.metrics

            # Key metrics
            col1, col2, col3, col4 = st.columns(4)

            # Calculate theoretical maximum satisfaction
            max_possible = len(participants) * num_choices  # Everyone gets 1st choice
            if max_possible > 0:
                satisfaction_pct = metrics.preference_satisfaction / max_possible * 100
            else:
                satisfaction_pct = 0

            with col1:
                sat_label = f"{metrics.preference_satisfaction} / {max_possible}"
                st.metric("Preference Satisfaction", sat_label)
                st.caption(f"{satisfaction_pct:.1f}% of maximum")

            with col2:
                st.metric("Average Satisfaction", f"{metrics.average_satisfaction:.2f}")

            with col3:
                st.metric("Active Options", f"{metrics.active_options} / {len(options)}")

            with col4:
                st.metric("Unused Options", len(metrics.unused_options))

            # Constraint violations warning
            if metrics.constraint_violations:
                st.warning("⚠️ Constraint Violations:")
                for v in metrics.constraint_violations:
                    st.write(f"- {v}")

            # Preference distribution chart
            st.subheader("Preference Distribution")

            dist = metrics.preference_distribution
            dist_data = []
            for rank in range(1, num_choices + 1):
                dist_data.append({"Rank": f"{rank}", "Count": dist.get(rank, 0)})
            if dist.get("unassigned", 0) > 0:
                dist_data.append({"Rank": "Unassigned", "Count": dist["unassigned"]})
            if dist.get("no_preferences", 0) > 0:
                dist_data.append({"Rank": "No Prefs", "Count": dist["no_preferences"]})

            dist_df = pd.DataFrame(dist_data)

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.bar(
                    dist_df,
                    x="Rank",
                    y="Count",
                    title="Participants by Assigned Preference Rank",
                    color="Count",
                    color_continuous_scale="Greens",
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Option fill rate pie chart
                fill_counts = {"Min quota": 0, "Above min": 0}
                for count in result.option_counts.values():
                    if count == min_quota:
                        fill_counts["Min quota"] += 1
                    elif count > min_quota:
                        fill_counts["Above min"] += 1

                fill_df = pd.DataFrame([
                    {"Fill Level": k, "Count": v}
                    for k, v in fill_counts.items() if v > 0
                ])
                if not fill_df.empty:
                    fig = px.pie(
                        fill_df,
                        values="Count",
                        names="Fill Level",
                        title="Active Option Fill Rates",
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Detailed Results Section
            st.header("📋 Detailed Results")

            result_tabs = st.tabs([
                "All Assignments", "Participant Lookup", "Option Breakdown", "Insights"
            ])

            with result_tabs[0]:
                st.subheader("All Participant Assignments")

                assignments_data = []
                for participant, assignment in sorted(result.participant_assignments.items()):
                    assignments_data.append({
                        "Participant": participant,
                        "Assigned Option": assignment.option if assignment.option else "—",
                        "Preference Rank": assignment.preference_rank or "—",
                        "Score": assignment.preference_score,
                        "Status": assignment.status.value,
                    })

                assignments_df = pd.DataFrame(assignments_data)
                st.dataframe(assignments_df, use_container_width=True, height=400, hide_index=True)

            with result_tabs[1]:
                st.subheader("Participant Lookup (Post-Solve)")

                selected = st.selectbox(
                    "Select a participant",
                    participants,
                    key="result_participant_lookup",
                )

                if selected:
                    assignment = result.participant_assignments.get(selected)
                    if assignment:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write("**Assignment Result:**")
                            st.write(f"- **Option:** {assignment.option or 'None'}")
                            st.write(f"- **Status:** {assignment.status.value}")
                            rank_str = assignment.preference_rank or "N/A"
                            st.write(f"- **Preference Rank:** {rank_str}")
                            st.write(f"- **Score:** {assignment.preference_score}")

                        with col2:
                            st.write("**Original Preferences:**")
                            prefs = preferences.get(selected, [])
                            for rank, (option, score) in enumerate(prefs, 1):
                                marker = "✅" if option == assignment.option else ""
                                st.write(f"{rank}. {option} (score: {score}) {marker}")

            with result_tabs[2]:
                st.subheader("Option Breakdown")

                # Filter to active options
                active_options = [opt for opt, count in result.option_counts.items() if count > 0]

                if active_options:
                    selected_option = st.selectbox(
                        "Select an option", sorted(active_options), key="option_breakdown"
                    )

                    if selected_option:
                        assigned_participants = result.assignments.get(selected_option, [])
                        count = len(assigned_participants)
                        st.write(f"**{selected_option}** — {count} participants")

                        if assigned_participants:
                            option_data = []
                            for p in assigned_participants:
                                assignment = result.participant_assignments.get(p)
                                if assignment:
                                    option_data.append({
                                        "Participant": p,
                                        "Preference Rank": assignment.preference_rank,
                                        "Score": assignment.preference_score,
                                    })
                            option_df = pd.DataFrame(option_data)
                            st.dataframe(option_df, use_container_width=True, hide_index=True)
                else:
                    st.warning("No active options found.")

                # Show unused options
                if metrics.unused_options:
                    st.write("**Unused Options:**")
                    st.write(", ".join(sorted(metrics.unused_options)))

            with result_tabs[3]:
                st.subheader("Additional Insights")

                # Lucky participants: got 1st choice for a high-demand option
                competition_df = calculate_competition_index(options, preferences, max_quota)
                high_demand_options = set(
                    competition_df[competition_df["Competition Index"] >= 1.0]["Option"]
                )

                lucky = []
                for p, assignment in result.participant_assignments.items():
                    if (
                        assignment.preference_rank == 1
                        and assignment.option in high_demand_options
                    ):
                        lucky.append((p, assignment.option))

                if lucky:
                    st.write("**Lucky Participants** (got 1st choice for high-demand option):")
                    for p, opt in lucky[:10]:
                        st.write(f"- {p} → {opt}")
                    if len(lucky) > 10:
                        st.write(f"... and {len(lucky) - 10} more")
                else:
                    st.write("No participants got 1st choice for a high-demand option.")

                # Satisfaction histogram
                st.write("**Individual Satisfaction Scores:**")
                scores = [a.preference_score for a in result.participant_assignments.values()]
                fig = px.histogram(
                    x=scores,
                    nbins=num_choices + 1,
                    labels={"x": "Satisfaction Score", "y": "Count"},
                    title="Distribution of Individual Satisfaction Scores",
                )
                st.plotly_chart(fig, use_container_width=True)

            # Download Results
            st.header("📥 Download Results")

            csv_content = get_results_csv(result)
            st.download_button(
                label="Download Results CSV",
                data=csv_content,
                file_name="assignment_results.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
