# Preference Assignment Optimizer

A student-project assignment optimization tool using Binary Integer Programming (BIP). This tool assigns students to projects based on their ranked preferences while optimizing overall satisfaction.

## Features

- Load student preferences from CSV files
- Optimize assignments using BIP to maximize overall preference satisfaction
- Handle multiple students and projects efficiently
- Score-based preference system (5 points for 1st choice, 4 for 2nd, etc.)
- Configurable quotas (min/max participants per option)
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

```csv
participant_id,choice_1,choice_2,choice_3,choice_4,choice_5
student_001,Project_01,Project_02,Project_03,Project_04,Project_05
student_002,Project_03,Project_01,Project_05,Project_02,Project_04
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

Where `preference_score` is 5 for 1st choice, 4 for 2nd choice, down to 1 for 5th choice.

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
