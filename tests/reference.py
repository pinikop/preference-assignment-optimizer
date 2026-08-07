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

    per_participant = [[(p, option, score) for option, score in preferences[p]] for p in active]
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
