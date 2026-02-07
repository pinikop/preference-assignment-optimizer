def rank_to_score(rank: int, max_rank: int = 5) -> int:
    """Convert a preference ranking to a score.

    Args:
        rank: 1 for first choice, 2 for second, etc.
        max_rank (optional): The maximum rank value (e.g., 5 for five choices). Defaults to 5.
    Returns:
        Score where higher is better (5 for rank 1, 4 for rank 2, etc.)
    """
    return max_rank - rank + 1
