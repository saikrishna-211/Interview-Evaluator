def get_next_difficulty(
    current_difficulty: str,
    score: float
) -> str:

    difficulty_order = [
        "easy",
        "medium",
        "hard"
    ]

    current_index = difficulty_order.index(
        current_difficulty
    )

    # Strong answer → move up
    if score >= 8:
        current_index = min(
            current_index + 1,
            len(difficulty_order) - 1
        )

    # Weak answer → move down
    elif score < 5:
        current_index = max(
            current_index - 1,
            0
        )

    return difficulty_order[current_index]