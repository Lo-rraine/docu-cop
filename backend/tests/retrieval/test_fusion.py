"""Unit tests for Reciprocal Rank Fusion."""

import pytest
from app.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_single_list():
    """Single list should maintain order by RRF score."""
    items = ["a", "b", "c"]
    result = reciprocal_rank_fusion([items])
    ids, scores = zip(*result)
    assert ids == ("a", "b", "c")
    assert scores[0] > scores[1] > scores[2]


def test_rrf_two_lists():
    """Item in both lists should score higher than item in one."""
    list1 = ["a", "b", "c"]
    list2 = ["b", "c", "d"]
    result = reciprocal_rank_fusion([list1, list2])
    result_dict = {item_id: score for item_id, score in result}

    assert result_dict["b"] > result_dict["a"]
    assert result_dict["b"] > result_dict["d"]


def test_rrf_item_ranked_first_in_both():
    """Item ranked 1st in both lists beats item ranked 1st in one list."""
    list1 = ["a", "b"]
    list2 = ["a", "c"]
    result = reciprocal_rank_fusion([list1, list2])
    result_dict = {item_id: score for item_id, score in result}

    assert result_dict["a"] > result_dict["b"]
    assert result_dict["a"] > result_dict["c"]


def test_rrf_empty_lists():
    """Empty input should return empty result."""
    result = reciprocal_rank_fusion([])
    assert result == []


def test_rrf_empty_sublist():
    """List with empty sublists should skip them."""
    result = reciprocal_rank_fusion([[], ["a"]])
    assert len(result) == 1
    assert result[0][0] == "a"


def test_rrf_k_parameter():
    """Different k values should affect score magnitudes."""
    items = ["a", "b"]
    result_k60 = reciprocal_rank_fusion([items], k=60)
    result_k100 = reciprocal_rank_fusion([items], k=100)

    scores_60 = {item_id: score for item_id, score in result_k60}
    scores_100 = {item_id: score for item_id, score in result_k100}

    assert scores_60["a"] > scores_100["a"]
    assert scores_60["b"] > scores_100["b"]
