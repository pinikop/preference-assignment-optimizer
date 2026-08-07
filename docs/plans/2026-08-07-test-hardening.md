# Test Suite Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the test suite with property-based math verification (hypothesis + brute-force reference), a deterministic edge-case catalog, and thorough Streamlit AppTest UI coverage.

**Architecture:** Additive only - the existing 7 test files stay untouched. New files: `tests/conftest.py` (slow marker + `--runslow` flag), `tests/reference.py` (brute-force reference solver), `tests/test_properties.py` (hypothesis, slow), `tests/test_edge_cases.py` (deterministic, fast), `tests/test_app_ui.py` (AppTest, slow). Design doc: `docs/plans/2026-08-07-test-hardening-design.md`.

**Tech Stack:** pytest, hypothesis (new dev dep), streamlit.testing.v1.AppTest, PuLP/CBC.

**Important execution rules:**
- These tests verify *existing, believed-correct* behavior, so most pass immediately. The RED step is replaced where noted by a **mutation check**: deliberately break the solver, watch the test fail, revert. Never skip it - a property test that can't fail is worthless.
- If any new test FAILS against the real code, STOP - you may have found a real bug. Investigate with superpowers:systematic-debugging before touching the test.
- Run `uv run pytest` (fast) after every task; run `uv run pytest --runslow` where noted.

---

### Task 1: Tooling - hypothesis dependency and `--runslow` infrastructure

**Files:**
- Create: `tests/conftest.py`
- Modify: `pyproject.toml` (via uv)

**Step 1: Add hypothesis**

Run: `uv add --dev hypothesis`
Expected: resolves and adds to `[dependency-groups] dev`.

**Step 2: Write conftest**

Create `tests/conftest.py`:

```python
"""Shared pytest configuration: slow marker and --runslow flag."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slow test, skipped unless --runslow")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="needs --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
```

**Step 3: Verify the flag works**

Run: `uv run pytest --runslow 2>&1 | tail -1` and `uv run pytest 2>&1 | tail -1`
Expected: both show `91 passed` (no slow tests exist yet, flag accepted, nothing broken).

**Step 4: Commit**

```bash
git add tests/conftest.py pyproject.toml uv.lock
git commit -m "Add hypothesis dependency and --runslow test infrastructure"
```

---

### Task 2: Brute-force reference solver (TDD proper - test first)

**Files:**
- Create: `tests/reference.py`
- Create: `tests/test_properties.py` (reference self-tests only, fast)

**Step 1: Write failing tests for the reference solver**

Create `tests/test_properties.py`:

```python
"""Property-based verification of the ILP solver against a brute-force reference."""

import pytest

from src.solver import solve_assignment
from src.types import AssignmentStatus, SolverStatus
from tests.reference import brute_force_optimum


class TestReferenceSolver:
    """Hand-computed cases proving the reference solver itself is correct."""

    def test_forced_pairing_optimum(self):
        """Same instance as TestKnownOptimum: optimum is 2+2+2+1 = 7."""
        preferences = {
            "p1": [("o1", 2), ("o2", 1)],
            "p2": [("o1", 2)],
            "p3": [("o1", 2), ("o2", 1)],
            "p4": [("o2", 2)],
        }
        best, assignment = brute_force_optimum(
            ["p1", "p2", "p3", "p4"], ["o1", "o2"], preferences,
            min_quota=2, max_quota=2, option_weight=0.0,
        )
        assert best == 7
        assert assignment["p2"] == "o1"
        assert assignment["p4"] == "o2"

    def test_weight_counts_active_options(self):
        preferences = {"p1": [("o1", 1)], "p2": [("o1", 1)]}
        best, _ = brute_force_optimum(
            ["p1", "p2"], ["o1", "o2"], preferences,
            min_quota=2, max_quota=2, option_weight=0.5,
        )
        assert best == 2.5  # satisfaction 2 + 0.5 * 1 active option

    def test_infeasible_returns_none(self):
        preferences = {"p1": [("o1", 1)]}
        best, assignment = brute_force_optimum(
            ["p1"], ["o1"], preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        assert best is None
        assert assignment is None

    def test_no_preferences_is_trivially_optimal(self):
        best, assignment = brute_force_optimum(
            ["p1"], ["o1"], {}, min_quota=1, max_quota=3, option_weight=0.5
        )
        assert best == 0.0
        assert assignment == {}
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_properties.py -v`
Expected: FAIL / collection error - `tests.reference` does not exist.

**Step 3: Implement the reference solver**

Create `tests/reference.py`:

```python
"""Brute-force reference solver: obviously correct by construction.

Enumerates every way to give each preference-holding participant one of
their ranked options (the ILP's == 1 semantics), keeps combinations where
every used option has min_quota..max_quota participants, and maximizes
satisfaction + option_weight * active_options.
"""

from itertools import product


def brute_force_optimum(
    participants: list[str],
    options: list[str],
    preferences: dict[str, list[tuple[str, int]]],
    min_quota: int,
    max_quota: int,
    option_weight: float,
) -> tuple[float | None, dict[str, str] | None]:
    """Return (best_objective, best_assignment), or (None, None) if infeasible."""
    active = [p for p in participants if preferences.get(p)]
    if not active:
        return 0.0, {}

    per_participant = [
        [(p, option, score) for option, score in preferences[p]] for p in active
    ]
    best_objective: float | None = None
    best_assignment: dict[str, str] | None = None

    for combo in product(*per_participant):
        counts: dict[str, int] = {}
        for _, option, _ in combo:
            counts[option] = counts.get(option, 0) + 1
        if any(c < min_quota or c > max_quota for c in counts.values()):
            continue
        satisfaction = sum(score for _, _, score in combo)
        objective = satisfaction + option_weight * len(counts)
        if best_objective is None or objective > best_objective:
            best_objective = objective
            best_assignment = {p: option for p, option, _ in combo}

    return best_objective, best_assignment
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_properties.py -v`
Expected: 4 passed.

**Step 5: Commit**

```bash
git add tests/reference.py tests/test_properties.py
git commit -m "Add brute-force reference solver with self-tests"
```

---

### Task 3: Hypothesis strategies and solver invariant properties

**Files:**
- Modify: `tests/test_properties.py` (append)

**Step 1: Append strategies and the invariant helper**

Append to `tests/test_properties.py`:

```python
import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Hostile IDs: spaces, underscores, commas, unicode - keeps the
# PuLP-name-sanitization fix honest.
ID_ALPHABET = string.ascii_letters + string.digits + " _-,éÜ"
ids = (
    st.text(alphabet=ID_ALPHABET, min_size=1, max_size=8)
    .map(str.strip)
    .filter(bool)
)


@st.composite
def instances(draw, max_participants=8, max_options=4):
    participants = draw(
        st.lists(ids, min_size=1, max_size=max_participants, unique=True)
    )
    options = draw(st.lists(ids, min_size=1, max_size=max_options, unique=True))
    preferences = {}
    for p in participants:
        k = draw(st.integers(0, len(options)))
        if k:
            ranked = draw(st.permutations(options))[:k]
            preferences[p] = [(o, k - i) for i, o in enumerate(ranked)]
    min_q = draw(st.integers(1, 3))
    max_q = draw(st.integers(min_q, 4))
    weight = draw(st.sampled_from([0.0, 0.25, 0.5, 1.0, 3.0]))
    return participants, options, preferences, min_q, max_q, weight


def assert_solver_invariants(result, participants, preferences, min_q, max_q, weight):
    """Invariants that must hold for every OPTIMAL result."""
    # Quota rule: 0 or [min_quota, max_quota]
    for option, count in result.option_counts.items():
        assert count == 0 or min_q <= count <= max_q, (option, count)

    # Assignment validity
    for p in participants:
        assignment = result.participant_assignments[p]
        if preferences.get(p):
            assert assignment.status == AssignmentStatus.ASSIGNED
            assert assignment.option in [o for o, _ in preferences[p]]
        else:
            assert assignment.status == AssignmentStatus.NO_PREFERENCES

    # Objective identity (regression: ghost-y inflation bug)
    m = result.metrics
    assert m.objective_value == pytest.approx(
        m.preference_satisfaction + weight * m.active_options
    )

    # Metrics consistency
    assert m.preference_satisfaction == sum(
        a.preference_score for a in result.participant_assignments.values()
    )
    assert sum(m.preference_distribution.values()) == len(participants)
    assert result.option_counts == {
        o: len(ps) for o, ps in result.assignments.items()
    }


@pytest.mark.slow
class TestSolverInvariants:
    @given(instance=instances())
    @settings(
        max_examples=100, deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_invariants_hold(self, instance):
        participants, options, preferences, min_q, max_q, weight = instance
        result = solve_assignment(
            participants, options, preferences,
            min_quota=min_q, max_quota=max_q, option_weight=weight,
        )
        if result.status == SolverStatus.OPTIMAL:
            assert_solver_invariants(
                result, participants, preferences, min_q, max_q, weight
            )
        else:
            assert result.status == SolverStatus.INFEASIBLE
            assert result.infeasibility_hints
```

**Step 2: Run (they should pass against correct code)**

Run: `uv run pytest tests/test_properties.py --runslow -v`
Expected: all pass, ~10-20s.

**Step 3: Mutation check (substitute for RED - MANDATORY)**

Temporarily edit `src/solver.py`: change the min-quota constraint line
`self._model += option_count >= self.min_quota * self._y[option]`
to
`self._model += option_count >= 0 * self._y[option]`

Run: `uv run pytest tests/test_properties.py::TestSolverInvariants --runslow`
Expected: FAIL (quota invariant violated on some generated instance).

**Revert the mutation** (`git checkout src/solver.py`), re-run, expected: PASS.

**Step 4: Commit**

```bash
git add tests/test_properties.py
git commit -m "Add hypothesis invariant properties for solver"
```

---

### Task 4: Brute-force agreement properties (optimality + feasibility)

**Files:**
- Modify: `tests/test_properties.py` (append)

**Step 1: Append the agreement class**

```python
@pytest.mark.slow
class TestBruteForceAgreement:
    """The killer property: the ILP must agree with exhaustive enumeration."""

    @given(instance=instances(max_participants=6, max_options=4))
    @settings(
        max_examples=50, deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_optimality_and_feasibility(self, instance):
        participants, options, preferences, min_q, max_q, weight = instance
        result = solve_assignment(
            participants, options, preferences,
            min_quota=min_q, max_quota=max_q, option_weight=weight,
        )
        best, _ = brute_force_optimum(
            participants, options, preferences, min_q, max_q, weight
        )
        if best is None:
            assert result.status == SolverStatus.INFEASIBLE
        else:
            assert result.status == SolverStatus.OPTIMAL
            assert result.metrics.objective_value == pytest.approx(best)
```

**Step 2: Run**

Run: `uv run pytest tests/test_properties.py::TestBruteForceAgreement --runslow -v`
Expected: PASS.

**Step 3: Mutation check (MANDATORY)**

Temporarily edit `src/solver.py` objective: change
`self._model += preference_sum + self.option_weight * option_utilization`
to
`self._model += preference_sum` (drop utilization term).

Run: expected FAIL (objective disagrees whenever weight > 0 and options differ).
Revert (`git checkout src/solver.py`), re-run, expected PASS.

**Step 4: Commit**

```bash
git add tests/test_properties.py
git commit -m "Add brute-force optimality agreement property"
```

---

### Task 5: Large-instance invariants (brute force skipped)

**Files:**
- Modify: `tests/test_properties.py` (append)

**Step 1: Append**

```python
@pytest.mark.slow
class TestLargeInstanceInvariants:
    """Invariants scale to realistic sizes; optimality checks don't."""

    @given(instance=instances(max_participants=30, max_options=10))
    @settings(
        max_examples=25, deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_invariants_hold_at_scale(self, instance):
        participants, options, preferences, min_q, max_q, weight = instance
        result = solve_assignment(
            participants, options, preferences,
            min_quota=min_q, max_quota=max_q, option_weight=weight,
        )
        if result.status == SolverStatus.OPTIMAL:
            assert_solver_invariants(
                result, participants, preferences, min_q, max_q, weight
            )
```

**Step 2: Run and commit**

Run: `uv run pytest tests/test_properties.py --runslow -v` - all pass.

```bash
git add tests/test_properties.py
git commit -m "Add large-instance invariant property"
```

---

### Task 6: Edge-case catalog - solver

**Files:**
- Create: `tests/test_edge_cases.py`

**Step 1: Write the solver edge cases**

Create `tests/test_edge_cases.py`:

```python
"""Deterministic adversarial edge cases across all modules (fast suite)."""

import csv
from io import StringIO
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.data_loader import load_preferences_from_csv
from src.main import app
from src.output import export_results_to_csv, print_assignment_summary
from src.solver import solve_assignment
from src.types import AssignmentStatus, SolverStatus

runner = CliRunner()
MOCK_CSV = str(Path(__file__).parent.parent / "data" / "mock_preferences.csv")


class TestQuotaBoundaries:
    def test_single_participant_single_option(self):
        result = solve_assignment(
            ["p1"], ["o1"], {"p1": [("o1", 1)]},
            min_quota=1, max_quota=1, option_weight=0.5,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.option_counts["o1"] == 1
        assert result.metrics.objective_value == pytest.approx(1.5)

    def test_exact_quota_groups(self):
        """min_quota == max_quota forces exact group sizes."""
        preferences = {f"p{i}": [("o1", 2), ("o2", 1)] for i in range(4)}
        result = solve_assignment(
            list(preferences), ["o1", "o2"], preferences,
            min_quota=2, max_quota=2, option_weight=0.0,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert all(c in (0, 2) for c in result.option_counts.values())

    def test_one_giant_group_allowed(self):
        """max_quota == participant count lets one option take everyone."""
        preferences = {f"p{i}": [("o1", 1)] for i in range(3)}
        result = solve_assignment(
            list(preferences), ["o1"], preferences,
            min_quota=1, max_quota=3, option_weight=0.5,
        )
        assert result.status == SolverStatus.OPTIMAL
        assert result.option_counts["o1"] == 3

    def test_min_quota_exceeds_participants(self):
        preferences = {"p1": [("o1", 1)], "p2": [("o1", 1)]}
        result = solve_assignment(
            ["p1", "p2"], ["o1"], preferences,
            min_quota=3, max_quota=3, option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert result.infeasibility_hints


class TestCapacity:
    def test_unanimous_demand_fits_exactly(self):
        preferences = {f"p{i}": [("o1", 1)] for i in range(3)}
        result = solve_assignment(
            list(preferences), ["o1"], preferences,
            min_quota=1, max_quota=3, option_weight=0.5,
        )
        assert result.status == SolverStatus.OPTIMAL

    def test_unanimous_demand_exceeds_capacity(self):
        preferences = {f"p{i}": [("o1", 1)] for i in range(4)}
        result = solve_assignment(
            list(preferences), ["o1"], preferences,
            min_quota=1, max_quota=3, option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert any("capacity" in h.lower() for h in result.infeasibility_hints)


class TestParityTrap:
    def test_five_participants_pairs_only(self):
        """5 participants, groups of exactly 2, two options: 5 is odd -> infeasible."""
        preferences = {f"p{i}": [("o1", 2), ("o2", 1)] for i in range(5)}
        result = solve_assignment(
            list(preferences), ["o1", "o2"], preferences,
            min_quota=2, max_quota=2, option_weight=0.5,
        )
        assert result.status == SolverStatus.INFEASIBLE
        assert result.infeasibility_hints  # generic partitioning hint


class TestTies:
    def test_identical_preference_lists(self):
        """Any optimal split is acceptable; pin the optimal VALUE only."""
        preferences = {f"p{i}": [("o1", 2), ("o2", 1)] for i in range(4)}
        result = solve_assignment(
            list(preferences), ["o1", "o2"], preferences,
            min_quota=2, max_quota=2, option_weight=0.0,
        )
        assert result.status == SolverStatus.OPTIMAL
        # 2 participants get o1 (2 each), 2 get o2 (1 each): 2+2+1+1
        assert result.metrics.preference_satisfaction == 6


class TestDegenerateInputs:
    def test_no_participants_no_options(self):
        result = solve_assignment([], [], {}, min_quota=1, max_quota=3, option_weight=0.5)
        assert result.status == SolverStatus.OPTIMAL
        assert result.assignments == {}
        assert result.metrics.preference_satisfaction == 0
        assert result.metrics.average_satisfaction == 0.0

    def test_all_participants_without_preferences(self):
        result = solve_assignment(
            ["p1", "p2"], ["o1"], {}, min_quota=1, max_quota=3, option_weight=0.5
        )
        assert result.status == SolverStatus.OPTIMAL
        statuses = {a.status for a in result.participant_assignments.values()}
        assert statuses == {AssignmentStatus.NO_PREFERENCES}
        assert result.metrics.preference_distribution == {"no_preferences": 2}


class TestNonLadderScores:
    def test_all_equal_scores(self):
        """The solver accepts arbitrary ints; identity must still hold."""
        preferences = {"p1": [("o1", 1), ("o2", 1)], "p2": [("o1", 1), ("o2", 1)]}
        result = solve_assignment(
            ["p1", "p2"], ["o1", "o2"], preferences,
            min_quota=2, max_quota=2, option_weight=0.25,
        )
        assert result.status == SolverStatus.OPTIMAL
        m = result.metrics
        assert m.objective_value == pytest.approx(
            m.preference_satisfaction + 0.25 * m.active_options
        )
```

**Step 2: Run**

Run: `uv run pytest tests/test_edge_cases.py -v`
Expected: all pass. If any FAILS, stop and investigate (possible real bug).

**Step 3: Commit**

```bash
git add tests/test_edge_cases.py
git commit -m "Add solver edge-case catalog"
```

---

### Task 7: Edge-case catalog - loader

**Files:**
- Modify: `tests/test_edge_cases.py` (append)

**Step 1: Append loader cases**

```python
class TestLoaderRobustness:
    def _load(self, tmp_path: Path, content: str, name: str = "t.csv"):
        p = tmp_path / name
        p.write_text(content)
        return load_preferences_from_csv(p)

    def test_unicode_names(self, tmp_path):
        _, options, prefs = self._load(
            tmp_path, "id,c1,c2\nJosé,Option-É,Übung\nÜser,Übung,Option-É\n"
        )
        assert set(options) == {"Option-É", "Übung"}
        assert prefs["José"][0] == ("Option-É", 2)

    def test_quoted_commas_in_names(self, tmp_path):
        _, options, prefs = self._load(
            tmp_path, 'id,c1\n"Smith, John","Opt, A"\n"Doe, Jane","Opt, A"\n'
        )
        assert options == ["Opt, A"]
        assert prefs["Smith, John"] == [("Opt, A", 1)]

    def test_whitespace_is_preserved(self, tmp_path):
        """Loader does not strip; ' A' and 'A' are distinct options."""
        _, options, _ = self._load(tmp_path, "id,c1\np1, A\np2,A\n")
        assert set(options) == {" A", "A"}

    def test_numeric_participant_ids(self, tmp_path):
        participants, _, prefs = self._load(tmp_path, "id,c1\n1,A\n2,B\n")
        assert participants == [1, 2]  # pandas keeps them as ints
        assert prefs[1] == [("A", 1)]

    def test_single_column_csv_raises(self, tmp_path):
        """IDs only, zero choice columns -> no data rows."""
        with pytest.raises(ValueError):
            self._load(tmp_path, "id\np1\np2\n")

    def test_all_nan_row_yields_empty_preferences(self, tmp_path):
        _, _, prefs = self._load(tmp_path, "id,c1,c2\np1,A,B\np2,,\n")
        assert prefs["p2"] == []

    def test_gap_in_middle_keeps_column_rank(self, tmp_path):
        """Score comes from column position, not from compacting."""
        _, _, prefs = self._load(tmp_path, "id,c1,c2,c3\np1,A,,C\n")
        assert prefs["p1"] == [("A", 3), ("C", 1)]

    def test_crlf_and_trailing_newlines(self, tmp_path):
        participants, _, _ = self._load(
            tmp_path, "id,c1\r\np1,A\r\np2,B\r\n\r\n"
        )
        assert participants == ["p1", "p2"]

    def test_ragged_row_raises_parse_error(self, tmp_path):
        with pytest.raises(ValueError, match="Failed to parse"):
            self._load(tmp_path, "id,c1\np1,A\np2,B,EXTRA,MORE\n")
```

**Step 2: Run**

Run: `uv run pytest tests/test_edge_cases.py::TestLoaderRobustness -v`
Expected: pass. The whitespace/numeric-ID tests *document actual behavior* - if
reality differs from the assertion, fix the assertion to match reality and note
the surprise, unless it reveals genuine data corruption.

**Step 3: Commit**

```bash
git add tests/test_edge_cases.py
git commit -m "Add loader edge-case catalog"
```

---

### Task 8: Edge-case catalog - output and CLI

**Files:**
- Modify: `tests/test_edge_cases.py` (append)

**Step 1: Append**

```python
class TestInfeasibleOutput:
    def test_summary_prints_hints(self, capsys):
        preferences = {"p1": [("o1", 1)]}
        result = solve_assignment(
            ["p1"], ["o1"], preferences, min_quota=2, max_quota=3, option_weight=0.5
        )
        print_assignment_summary(result)
        out = capsys.readouterr().out
        assert "Likely causes" in out
        assert "p1" in out


class TestCLIValidation:
    def test_min_quota_greater_than_max_quota_errors(self):
        result = runner.invoke(app, [MOCK_CSV, "-m", "5", "-q", "2"])
        assert result.exit_code == 1
        assert "cannot be greater" in result.output


class TestExportDegenerate:
    def test_export_when_everyone_has_no_preferences(self, tmp_path):
        result = solve_assignment(
            ["p1", "p2"], ["o1"], {}, min_quota=1, max_quota=3, option_weight=0.5
        )
        out_path = tmp_path / "results.csv"
        export_results_to_csv(result, out_path)
        rows = list(csv.DictReader(out_path.open()))
        assert len(rows) == 2
        assert all(r["status"] == "NO_PREFERENCES" for r in rows)
        assert all(r["assigned_option"] == "" for r in rows)
```

**Step 2: Run full fast suite**

Run: `uv run pytest`
Expected: everything passes, still fast (~5s).

**Step 3: Commit**

```bash
git add tests/test_edge_cases.py
git commit -m "Add output and CLI edge cases"
```

---

### Task 9: AppTest UI - boot, loaded state, explorer, controls

**Files:**
- Create: `tests/test_app_ui.py`

**Key constraint:** AppTest cannot drive `st.file_uploader`. Tests seed
`st.session_state` with the exact keys `streamlit.py` stores after upload
(`data_loaded`, `participants`, `options`, `preferences`, `raw_df`,
`num_choices`). The upload branch's logic (loader + `count_choice_columns`)
is already unit-tested elsewhere.

**Step 1: Write the file**

Create `tests/test_app_ui.py`:

```python
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
```

**Step 2: Run**

Run: `uv run pytest tests/test_app_ui.py --runslow -v`
Expected: pass. If `seed_input.disabled` is not exposed by the installed
Streamlit version, drop that assertion line and keep the check/uncheck flow.

**Step 3: Commit**

```bash
git add tests/test_app_ui.py
git commit -m "Add AppTest coverage for boot, explorer, and controls"
```

---

### Task 10: AppTest UI - solve flow, dashboard, infeasible path

**Files:**
- Modify: `tests/test_app_ui.py` (append)

**Step 1: Append**

```python
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
        prefs = dict(PREFERENCES)  # p5 in raw_df/session but no preferences
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
```

**Step 2: Run**

Run: `uv run pytest tests/test_app_ui.py --runslow -v`
Expected: pass.

**Step 3: Commit**

```bash
git add tests/test_app_ui.py
git commit -m "Add AppTest coverage for solve flow and dashboards"
```

---

### Task 11: Visualization builders and app CLI entry point

**Files:**
- Modify: `tests/test_app_ui.py` (append)

**Step 1: Append**

```python
import plotly.graph_objects as go

from src.app.utils.visualizations import (
    create_competition_index_chart,
    create_option_fill_pie_chart,
    create_preference_distribution_chart,
    create_preference_heatmap,
    create_satisfaction_histogram,
    create_weighted_popularity_chart,
)


class TestVisualizationBuilders:
    def test_preference_heatmap(self):
        fig = create_preference_heatmap(["o1", "o2"], PREFERENCES, num_choices=2)
        assert isinstance(fig, go.Figure)
        assert "Heatmap" in fig.layout.title.text

    def test_weighted_popularity_chart(self):
        df = pd.DataFrame({"Option": ["o1"], "Weighted Score": [5]})
        fig = create_weighted_popularity_chart(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_competition_index_chart(self):
        df = pd.DataFrame(
            {"Option": ["o1"], "Top-2 Demand": [4], "Competition Index": [1.33]}
        )
        fig = create_competition_index_chart(df)
        assert isinstance(fig, go.Figure)

    def test_distribution_chart(self):
        fig = create_preference_distribution_chart(
            [{"Rank": "1", "Count": 3}, {"Rank": "2", "Count": 1}]
        )
        assert isinstance(fig, go.Figure)

    def test_fill_pie_chart(self):
        fig = create_option_fill_pie_chart({"Min quota": 2, "Above min": 1})
        assert isinstance(fig, go.Figure)

    def test_satisfaction_histogram(self):
        fig = create_satisfaction_histogram([2, 2, 1, 1], num_choices=2)
        assert isinstance(fig, go.Figure)


class TestAppCli:
    def test_builds_streamlit_run_argv(self, monkeypatch):
        import sys

        import streamlit.web.cli as st_cli

        from src.app import cli as app_cli

        captured = {}
        monkeypatch.setattr(
            st_cli, "main", lambda: captured.setdefault("argv", sys.argv[:])
        )
        app_cli.main()
        assert captured["argv"][:2] == ["streamlit", "run"]
        assert captured["argv"][2].endswith("streamlit.py")
```

**Step 2: Run everything**

Run: `uv run pytest --runslow`
Expected: full suite passes.

**Step 3: Commit**

```bash
git add tests/test_app_ui.py
git commit -m "Add visualization builder and app CLI tests"
```

---

### Task 12: Coverage verification and docs

**Files:**
- Modify: `README.md`, `CLAUDE.md` (test commands)

**Step 1: Measure**

Run: `uv run --with pytest-cov pytest --runslow --cov=src --cov-report=term-missing 2>&1 | tail -20`
Expected: core modules >= 95%; `src/app/` files >= 80% overall. If a file falls
short, check the Missing column - add a targeted test only if the gap is logic
(not pure Streamlit layout calls).

**Step 2: Verify the fast suite is still fast**

Run: `time uv run pytest`
Expected: all fast tests pass in under ~5s.

**Step 3: Document the two-tier suite**

In `README.md` and `CLAUDE.md`, replace the test command section:

```markdown
# Run fast tests (default)
uv run pytest

# Run everything, including property-based and UI tests
uv run pytest --runslow
```

**Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "Document two-tier test suite"
```
