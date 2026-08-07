# Test Suite Hardening Design

Date: 2026-08-07
Status: Approved

## Goal

Cover edge cases across all modules and verify the solver math against an
independent reference. Line coverage of core modules is already ~95%, but
input-space coverage is thin (the objective-inflation bug lived on fully
covered lines) and the Streamlit layer is at 0%.

## Decisions

- Math: property-based testing (hypothesis) + brute-force reference solver.
- UI: thorough coverage via Streamlit AppTest.
- Runtime: `slow` marker + `--runslow` flag; default runs stay fast.
- Structure: additive files, existing 4 test files unchanged (Approach A).

## Math verification

`tests/reference.py`: brute-force reference solver. Enumerates every
assignment of participants to their ranked options, filters by the
0-or-[min_quota, max_quota] rule, returns the true optimum of
`satisfaction + weight * active_options`. Obviously correct by construction;
tractable for <=8 participants x <=4 options each (~65k combinations).

`tests/test_properties.py` (slow): hypothesis strategies generate 1-8
participants, 1-6 options, random preference subsets (including empty),
quotas with min <= max, weight in {0, 0.25, 0.5, 1.0, 3.0}, and hostile ID
strings (spaces, underscores, unicode, commas).

Properties per instance:

1. Optimality: ILP OPTIMAL objective equals brute-force maximum.
2. Feasibility agreement: INFEASIBLE iff brute force finds no valid assignment.
3. Quota invariant: every option count is 0 or in [min_quota, max_quota].
4. Assignment validity: participants with preferences get exactly one option
   they ranked; others are NO_PREFERENCES.
5. Objective identity: objective_value == satisfaction + weight * active.
6. Metrics consistency: satisfaction = sum of assigned scores; distribution
   sums to participant count; option_counts matches assignments.

Properties 3-6 also run on larger instances (up to ~30 participants) without
brute-force comparison.

Hypothesis config: ~100 examples for invariants, ~50 for brute-force
agreement, deadline=None (CBC subprocess timing varies).

## Edge-case catalog

`tests/test_edge_cases.py` (fast, deterministic):

Solver:
- Single participant/option with min_quota=1; min_quota == max_quota;
  max_quota == len(participants).
- min_quota > participant count (infeasible, hints present).
- Unanimous single-option demand: fits exactly vs exceeds capacity.
- Parity trap: 5 participants, quotas 2-2, two options (infeasible).
- Identical preference lists (assert invariants + optimal value, not
  specific assignment).
- option_weight=0 and score-dominating weight.
- Empty participants/options; all participants with no preferences.
- Non-ladder scores (e.g. all equal).

Loader:
- Whitespace, unicode, quoted commas in names.
- Numeric participant IDs end-to-end.
- Single-column CSV (no choice columns).
- All-NaN row (NO_PREFERENCES from file); gap in the middle of a row.
- CRLF endings; trailing blank lines; ParserError path.

Output/CLI:
- INFEASIBLE summary printing with hints.
- CLI min_quota > max_quota error path.
- Export when everyone is NO_PREFERENCES.

## UI coverage

`tests/test_app_ui.py` (slow), using streamlit.testing.v1.AppTest:
- Boot without upload; info message.
- Upload: valid CSV (arbitrary column names -> correct counts), duplicate-ID
  and empty CSVs -> error banner, no crash.
- Explorer renders for loaded data.
- Controls: defaults (weight 0.5), seed disabled until shuffle checked,
  Run stores result + quotas in session state.
- Dashboard: metric values, violation and no-preferences flags, infeasible
  hints list, download serves shared quoted CSV.
- visualizations.py builders called directly; assert figure structure.
- app/cli.py entry point unit-tested.

## Tooling and structure

- `uv add --dev hypothesis`.
- `tests/conftest.py`: `--runslow` flag + `slow` marker registration.
- Fast default suite (~5s); full suite via `uv run pytest --runslow`.

```
tests/
├── conftest.py          # --runslow flag, slow marker, shared fixtures
├── reference.py         # brute-force reference solver (not collected)
├── test_properties.py   # hypothesis properties + brute-force agreement [slow]
├── test_edge_cases.py   # deterministic adversarial catalog             [fast]
├── test_app_ui.py       # AppTest UI coverage                           [slow]
└── existing files unchanged
```

## Success criteria

- Fast suite under ~5s; existing 91 tests unchanged and passing.
- Optimality proven against brute force on generated instances.
- Core modules >= 95% line coverage; app layer >= 80% (from 0%).
