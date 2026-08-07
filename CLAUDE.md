# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a preference assignment optimization tool that uses Binary Integer Programming (via PuLP) to optimally match ~40 participants to ~20 options based on ranked preferences.

**Core Constraint:** Each option must have either 0 participants OR between `min_quota` and `max_quota` participants (default: 2-3).

## Running the Code

```bash
# Install dependencies
uv sync

# Run with mock data
uv run preference-optimizer data/mock_preferences.csv --option-weight 0.5

# Run with output to CSV
uv run preference-optimizer data/mock_preferences.csv -w 0.5 -o results.csv

# Run tests
uv run pytest
```

### CLI Options

- `--min-quota, -m`: Minimum participants per active option (default: 2)
- `--max-quota, -q`: Maximum participants per option (default: 3)
- `--option-weight, -w`: Weight for option utilization (default: 0.5)
- `--shuffle`: Shuffle participant order (affects tie-breaking)
- `--seed, -s`: Random seed (implies --shuffle)
- `--output, -o`: Export results to CSV file

## Architecture

```
src/
├── main.py        # CLI entry point
├── data_loader.py # CSV preference loading
├── types.py       # Enums and dataclasses (SolverResult, Metrics, etc.)
├── solver.py      # ILP solver (PuLP)
├── output.py      # Results display and export
└── app/           # Streamlit web interface
```

### Module Functions

- **`data_loader.load_preferences_from_csv(filepath)`** - Reads preferences from CSV, returns `(participants, options, preferences_dict)`
- **`solver.solve_assignment(...)`** - Core ILP solver using PuLP. Returns `SolverResult` dataclass.
- **`output.print_assignment_summary(results)`** - Pretty-prints assignment results
- **`output.export_results_to_csv(results, filepath)`** - Exports to CSV

## Key Types (src/types.py)

```python
class SolverStatus(Enum):
    OPTIMAL, INFEASIBLE, UNBOUNDED, NOT_SOLVED

class AssignmentStatus(Enum):
    ASSIGNED, UNASSIGNED, NO_PREFERENCES

@dataclass
class ParticipantAssignment:
    option: str
    status: AssignmentStatus
    preference_rank: int | None
    preference_score: int

@dataclass
class Metrics:
    preference_satisfaction: int
    active_options: int
    average_satisfaction: float
    objective_value: float
    preference_distribution: dict[int | str, int]
    unused_options: list[str]
    constraint_violations: list[str]

@dataclass
class SolverResult:
    status: SolverStatus
    assignments: dict[str, list[str]]  # option -> [participants]
    option_counts: dict[str, int]
    participant_assignments: dict[str, ParticipantAssignment]
    metrics: Metrics | None
```

## Key Data Structures

**Preferences input:**
```python
{'Participant1': [('OptionA', 5), ('OptionB', 4), ('OptionC', 3), ...]}  # 5=1st choice, 1=5th choice
```

**Results output:**
```python
result = solve_assignment(participants, options, preferences)
result.status              # SolverStatus.OPTIMAL
result.assignments         # {'OptionA': ['Participant1', 'Participant2'], ...}
result.participant_assignments['Participant1'].option          # 'OptionA'
result.participant_assignments['Participant1'].preference_rank # 1
result.metrics.active_options        # 15
result.metrics.constraint_violations # []
```

## ILP Decision Variables

- `x[i,j]`: Binary - participant i assigned to option j
- `y[j]`: Binary - option j is active (has participants)
- Quota constraints enforce: options have 0 participants OR between min_quota and max_quota

## Key Parameter: `option_weight`

Controls trade-off between maximizing participant satisfaction vs. using more options:
- `0`: Only optimize for preferences
- `0.1-0.5`: Mild preference for more active options (recommended)
- `1.0+`: Strongly favor activating more options

Scores run 1..N (N = number of choice columns), so the weight is not normalized:
the same value is relatively stronger with fewer choices. Exactly 1.0 makes the
solver indifferent between a first choice and an extra option (order-sensitive).

## CSV Input Format

```csv
participant_id,choice_1,choice_2,choice_3,choice_4,choice_5
participant_001,Option_01,Option_02,Option_03,Option_04,Option_05
```
