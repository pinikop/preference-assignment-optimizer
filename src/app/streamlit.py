"""Streamlit app for the Preference Assignment Optimizer."""

import tempfile

import pandas as pd
import streamlit as st

from src.app.components.explorer import render_explorer
from src.app.components.results import render_results_dashboard
from src.app.components.solver_controls import render_solver_controls
from src.data_loader import load_preferences_from_csv


def main():
    st.set_page_config(
        page_title="Preference Assignment Optimizer", page_icon="📊", layout="wide"
    )

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

    # --- Render Components ---
    render_explorer(raw_df, participants, options, preferences, num_choices)

    render_solver_controls(participants, options, preferences)

    # --- Results Dashboard ---
    if st.session_state.result is not None:
        result = st.session_state.result
        min_quota = st.session_state.get("min_quota", 2)
        max_quota = st.session_state.get("max_quota", 3)
        render_results_dashboard(
            result,
            participants,
            options,
            preferences,
            num_choices,
            min_quota,
            max_quota,
        )


if __name__ == "__main__":
    main()
