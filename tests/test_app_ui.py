"""Streamlit AppTest coverage for the web interface (slow suite)."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.slow

APP_PATH = "src/app/streamlit.py"

RAW_DF = pd.DataFrame(
    {
        "participant_id": ["p1", "p2", "p3", "p4"],
        "choice_1": ["o1", "o1", "o2", "o2"],
        "choice_2": ["o2", "o2", "o1", "o1"],
    }
)
PREFERENCES = {
    "p1": [("o1", 2), ("o2", 1)],
    "p2": [("o1", 2), ("o2", 1)],
    "p3": [("o2", 2), ("o1", 1)],
    "p4": [("o2", 2), ("o1", 1)],
}


def loaded_app(preferences=PREFERENCES, raw_df=RAW_DF) -> AppTest:
    """AppTest seeded as if a CSV was uploaded (file_uploader is not drivable)."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.session_state["data_loaded"] = True
    at.session_state["participants"] = list(preferences) or list(raw_df.iloc[:, 0])
    at.session_state["options"] = sorted(
        {o for prefs in preferences.values() for o, _ in prefs}
    ) or ["o1"]
    at.session_state["preferences"] = preferences
    at.session_state["raw_df"] = raw_df
    at.session_state["num_choices"] = len(raw_df.columns) - 1
    at.session_state["result"] = None
    return at


class TestBoot:
    def test_boots_without_upload(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        assert not at.exception
        assert any("Upload a CSV" in str(i.value) for i in at.info)


class TestExplorer:
    def test_renders_for_loaded_data(self):
        at = loaded_app().run()
        assert not at.exception
        headers = [h.value for h in at.header]
        assert any("Preference Explorer" in h for h in headers)
        assert len(at.dataframe) > 0


class TestSolverControls:
    def test_defaults(self):
        at = loaded_app().run()
        sliders = {s.label: s.value for s in at.slider}
        assert sliders["Min Quota"] == 2
        assert sliders["Max Quota"] == 3
        assert sliders["Option Weight"] == 0.5  # regression: CLI-aligned default

    def test_seed_disabled_until_shuffle(self):
        at = loaded_app().run()
        seed_input = [n for n in at.number_input if n.label == "Random Seed"][0]
        assert seed_input.disabled
        checkbox = [c for c in at.checkbox if "Shuffle" in c.label][0]
        at = checkbox.check().run()
        seed_input = [n for n in at.number_input if n.label == "Random Seed"][0]
        assert not seed_input.disabled
