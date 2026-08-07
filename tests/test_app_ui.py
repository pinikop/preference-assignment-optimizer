"""Streamlit AppTest coverage for the web interface (slow suite)."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.types import SolverStatus

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


def run_solver(at: AppTest) -> AppTest:
    button = [b for b in at.button if "Run Solver" in b.label][0]
    return button.click().run()


class TestSolveFlow:
    def test_run_stores_result_and_quotas(self):
        at = run_solver(loaded_app().run())
        assert not at.exception
        result = at.session_state["result"]
        assert result.status == SolverStatus.OPTIMAL
        assert at.session_state["min_quota"] == 2
        assert at.session_state["max_quota"] == 3

    def test_dashboard_shows_metrics(self):
        at = run_solver(loaded_app().run())
        metric_labels = [m.label for m in at.metric]
        assert "Preference Satisfaction" in metric_labels
        assert "Active Options" in metric_labels

    def test_success_badge_for_optimal(self):
        at = run_solver(loaded_app().run())
        assert any("Optimal" in str(s.value) for s in at.success)


class TestInfeasibleFlow:
    def test_hints_rendered(self):
        # p1's only option can never reach min_quota=2
        prefs = {"p1": [("o1", 1)]}
        raw = pd.DataFrame({"participant_id": ["p1"], "choice_1": ["o1"]})
        at = run_solver(loaded_app(preferences=prefs, raw_df=raw).run())
        assert any("Infeasible" in str(e.value) for e in at.error)
        markdown_text = " ".join(str(m.value) for m in at.markdown)
        assert "p1" in markdown_text  # hint names the impossible participant


class TestNoPreferencesFlag:
    def test_participant_without_prefs_is_named(self):
        prefs = dict(PREFERENCES)  # p5 in participants but has no preferences
        raw = pd.DataFrame(
            {
                "participant_id": ["p1", "p2", "p3", "p4", "p5"],
                "choice_1": ["o1", "o1", "o2", "o2", None],
                "choice_2": ["o2", "o2", "o1", "o1", None],
            }
        )
        at = loaded_app(preferences=prefs, raw_df=raw)
        at.session_state["participants"] = ["p1", "p2", "p3", "p4", "p5"]
        at = run_solver(at.run())
        infos = " ".join(str(i.value) for i in at.info)
        assert "p5" in infos
