"""Results Dashboard UI component."""

import pandas as pd
import streamlit as st

from src.app.utils.analytics import calculate_competition_index, get_results_csv
from src.app.utils.visualizations import (
    create_option_fill_pie_chart,
    create_preference_distribution_chart,
    create_satisfaction_histogram,
)
from src.types import SolverStatus


def render_results_dashboard(
    result,
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    num_choices: int,
    min_quota: int,
    max_quota: int,
) -> None:
    """Render the results dashboard with metrics and detailed tabs."""
    st.header("📈 Results Dashboard")

    # Status badge
    if result.status == SolverStatus.OPTIMAL:
        st.success(f"✅ Solver Status: **{result.status.value}**")
    else:
        st.error(f"❌ Solver Status: **{result.status.value}**")

    if result.metrics is None:
        st.warning("No solution found. Try adjusting parameters.")
        return

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

    col1, col2 = st.columns([2, 1])

    with col1:
        fig = create_preference_distribution_chart(dist_data)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Option fill rate pie chart
        fill_counts = {"Min quota": 0, "Above min": 0}
        for count in result.option_counts.values():
            if count == min_quota:
                fill_counts["Min quota"] += 1
            elif count > min_quota:
                fill_counts["Above min"] += 1

        if any(v > 0 for v in fill_counts.values()):
            fig = create_option_fill_pie_chart(fill_counts)
            st.plotly_chart(fig, use_container_width=True)

    # Detailed Results Section
    st.header("📋 Detailed Results")

    result_tabs = st.tabs(
        ["All Assignments", "Participant Lookup", "Option Breakdown", "Insights"]
    )

    with result_tabs[0]:
        _render_all_assignments_tab(result)

    with result_tabs[1]:
        _render_participant_lookup_tab(result, participants, preferences)

    with result_tabs[2]:
        _render_option_breakdown_tab(result, metrics)

    with result_tabs[3]:
        _render_insights_tab(result, options, preferences, max_quota, num_choices)

    # Download Results
    st.header("📥 Download Results")

    csv_content = get_results_csv(result)
    st.download_button(
        label="Download Results CSV",
        data=csv_content,
        file_name="assignment_results.csv",
        mime="text/csv",
    )


def _render_all_assignments_tab(result) -> None:
    """Render the All Assignments tab."""
    st.subheader("All Participant Assignments")

    assignments_data = []
    for participant, assignment in sorted(result.participant_assignments.items()):
        assignments_data.append(
            {
                "Participant": participant,
                "Assigned Option": assignment.option if assignment.option else "—",
                "Preference Rank": assignment.preference_rank or "—",
                "Score": assignment.preference_score,
                "Status": assignment.status.value,
            }
        )

    assignments_df = pd.DataFrame(assignments_data)
    st.dataframe(assignments_df, use_container_width=True, height=400, hide_index=True)


def _render_participant_lookup_tab(
    result, participants: list[str], preferences: dict[str, list[tuple[str, int]]]
) -> None:
    """Render the Participant Lookup tab."""
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


def _render_option_breakdown_tab(result, metrics) -> None:
    """Render the Option Breakdown tab."""
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
                        option_data.append(
                            {
                                "Participant": p,
                                "Preference Rank": assignment.preference_rank,
                                "Score": assignment.preference_score,
                            }
                        )
                option_df = pd.DataFrame(option_data)
                st.dataframe(option_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No active options found.")

    # Show unused options
    if metrics.unused_options:
        st.write("**Unused Options:**")
        st.write(", ".join(sorted(metrics.unused_options)))


def _render_insights_tab(
    result,
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    max_quota: int,
    num_choices: int,
) -> None:
    """Render the Insights tab."""
    st.subheader("Additional Insights")

    # Lucky participants: got 1st choice for a high-demand option
    competition_df = calculate_competition_index(options, preferences, max_quota)
    high_demand_options = set(
        competition_df[competition_df["Competition Index"] >= 1.0]["Option"]
    )

    lucky = []
    for p, assignment in result.participant_assignments.items():
        if assignment.preference_rank == 1 and assignment.option in high_demand_options:
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
    fig = create_satisfaction_histogram(scores, num_choices)
    st.plotly_chart(fig, use_container_width=True)
