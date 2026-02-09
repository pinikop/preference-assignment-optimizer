# Preference Assignment Optimizer

A participant-to-option assignment optimization tool using Binary Integer Programming (BIP). This tool assigns participants to options based on their ranked preferences while maximizing overall satisfaction.

## Features

- Load participant preferences from CSV files
- Optimize assignments using BIP to maximize overall preference satisfaction
- Handle multiple participants and options efficiently
- Dynamic score-based preference system (N points for 1st choice, N-1 for 2nd, etc., where N is the number of choice columns)
- Configurable quotas (min/max participants per option)
- Interactive web app (Streamlit) for exploring data and running the optimizer
- Export results to CSV

## Installation

This project requires Python 3.12 or higher.

```bash
# Clone the repository
git clone https://github.com/pinikop/preference-assignment-optimizer.git
cd preference-assignment-optimizer

# Install dependencies
uv sync
```

## Usage

### Web App (Streamlit)

```bash
# Using the dedicated entry point
uv run preference-optimizer-app

# Or directly with streamlit
uv run streamlit run src/app/streamlit.py
```

This opens an interactive web interface where you can:
- Upload a preferences CSV file
- Explore participant preferences and option popularity
- Adjust solver parameters (quotas, option weight)
- Run the optimizer and view results
- Download assignment results as CSV

### Command Line

```bash
# Run with preferences file
uv run preference-optimizer data/mock_preferences.csv

# Run with custom option weight
uv run preference-optimizer data/mock_preferences.csv --option-weight 0.5

# Export results to CSV
uv run preference-optimizer data/mock_preferences.csv -o results.csv

# Show all options
uv run preference-optimizer --help
```

### CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--min-quota` | `-m` | Minimum participants per active option | 2 |
| `--max-quota` | `-q` | Maximum participants per option | 3 |
| `--option-weight` | `-w` | Weight for option utilization | 1.0 |
| `--shuffle` | | Shuffle participant order (affects tie-breaking) | False |
| `--seed` | `-s` | Random seed (implies --shuffle) | None |
| `--output` | `-o` | Export results to CSV file | None |

### Input CSV Format

The first column is the participant ID, and subsequent columns are their ranked choices (any number of choice columns is supported):

```csv
participant_id,choice_1,choice_2,choice_3,choice_4,choice_5
student_001,Project_01,Project_02,Project_03,Project_04,Project_05
student_002,Project_03,Project_01,Project_05,Project_02,Project_04
```

- Missing values (empty cells) are allowed and will be skipped
- Duplicate options for the same participant will raise an error

## Programmatic Usage

The solver can be used directly in Python code:

```python
from src.solver import PreferenceAssignmentSolver, solve_assignment

# Option 1: Class-based (recommended for advanced use)
solver = PreferenceAssignmentSolver(
    participants=["Alice", "Bob", "Charlie"],
    options=["Project_A", "Project_B"],
    preferences={
        "Alice": [("Project_A", 2), ("Project_B", 1)],
        "Bob": [("Project_B", 2), ("Project_A", 1)],
        "Charlie": [("Project_A", 2), ("Project_B", 1)],
    },
    min_quota=1,
    max_quota=2,
    option_weight=0.5,
)
result = solver.solve()

# Option 2: Function-based (backward-compatible)
result = solve_assignment(
    participants, options, preferences,
    min_quota=2, max_quota=3, option_weight=1.0
)

# Access results
print(result.status)                    # SolverStatus.OPTIMAL
print(result.assignments)               # {'Project_A': ['Alice'], 'Project_B': ['Bob', 'Charlie']}
print(result.metrics.active_options)    # 2
```

## How the Solver Works

The optimizer uses **Binary Integer Programming (BIP)** via PuLP to find optimal assignments.

### Decision Variables

- **x[i,j]**: Binary variable. 1 if participant `i` is assigned to option `j`, 0 otherwise.
- **y[j]**: Binary variable. 1 if option `j` is active (has participants), 0 otherwise.

### Objective Function

The solver maximizes:

```
Σ (x[i,j] × preference_score[i,j]) + option_weight × Σ y[j]
```

Where `preference_score` is N for 1st choice, N-1 for 2nd choice, down to 1 for Nth choice (N = number of choice columns in the CSV).

### Constraints

1. **One assignment per participant**: Each participant is assigned to exactly one of their preferred options.

2. **Quota constraints**: Each option must have either:
   - 0 participants (inactive), OR
   - Between `min_quota` and `max_quota` participants (active)

   This is enforced via:
   ```
   min_quota × y[j] ≤ count[j] ≤ max_quota × y[j]
   ```

### The `option_weight` Parameter

Controls the trade-off between participant satisfaction and option utilization:

| Value | Behavior |
|-------|----------|
| 0 | Only optimize for participant preferences |
| 0.1–0.5 | Mild preference for using more options |
| 1.0+ | Strongly favor activating more options |

## License

MIT License - see LICENSE file for details

## Author

Pini Koplovitch
