"""Reciprocal Rank Fusion for combining multiple ranked lists."""


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        ranked_lists: Each element is a list of item IDs, ordered best to worst.
        k: RRF constant (default 60, per the original RRF paper).

    Returns:
        List of (item_id, rrf_score) tuples, sorted by score descending.
    """
    scores: dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, item_id in enumerate(ranked_list, start=1):
            score = 1.0 / (k + rank)
            scores[item_id] = scores.get(item_id, 0) + score

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_items
