import pytest

from eval import metrics as m


def test_normalize_matches_ingest_cleaning_rules():
    assert m.normalize("  Café ‘Bagging’\n\tis  GOOD ") == "caf bagging is good"


def test_matched_entries_needs_source_and_anchor():
    expected = [
        {"source_key": "A", "anchor": "random forests are one way"},
        {"source_key": "B", "anchor": "version space"},
    ]
    text = "Random   forests are one way to address this problem."
    assert m.matched_entries("A", text, expected) == [0]
    assert m.matched_entries("B", text, expected) == []  # right text, wrong book
    assert m.matched_entries("A", "unrelated", expected) == []


def test_matched_entries_identical_files_share_a_key():
    # Two filenames with the same md5 resolve to one source_key upstream.
    expected = [{"source_key": "same", "anchor": "genetic algorithms provide"}]
    assert m.matched_entries("same", "Genetic algorithms provide a method", expected) == [0]


@pytest.mark.parametrize(
    "matches, k, want",
    [
        ([[0], [], []], 1, 1.0),
        ([[], [0], []], 1, 0.0),
        ([[], [0], []], 3, 1.0),
        ([[], [], [], [0]], 3, 0.0),
        ([], 5, 0.0),
    ],
)
def test_hit_at_k(matches, k, want):
    assert m.hit_at_k(matches, k) == want


@pytest.mark.parametrize(
    "matches, want",
    [
        ([[0]], 1.0),
        ([[], [0]], 0.5),
        ([[], [], [1], [0]], 1 / 3),
        ([[], [], []], 0.0),
        ([], 0.0),
    ],
)
def test_reciprocal_rank(matches, want):
    assert m.reciprocal_rank(matches) == pytest.approx(want)


def test_recall_counts_distinct_entries_once():
    matches = [[0], [0], [1]]  # entry 0 hit twice, entry 1 once, entry 2 never
    assert m.recall_at_k(matches, n_expected=3, k=2) == pytest.approx(1 / 3)
    assert m.recall_at_k(matches, n_expected=3, k=3) == pytest.approx(2 / 3)


def test_recall_rejects_item_without_expected():
    with pytest.raises(ValueError):
        m.recall_at_k([[0]], n_expected=0, k=1)


def test_duplicate_rate():
    assert m.duplicate_rate_at_k(["a", "b", "a", "c"], 4) == pytest.approx(0.25)
    assert m.duplicate_rate_at_k(["a", "b", "a", "c"], 2) == 0.0
    assert m.duplicate_rate_at_k([], 5) == 0.0


def test_score_item_and_aggregate():
    hit = {"matches": [[0], []], "text_hashes": ["a", "b"], "n_expected": 1}
    miss = {"matches": [[], []], "text_hashes": ["c", "c"], "n_expected": 2}
    scored = [m.score_item(hit, ks=(1, 3)), m.score_item(miss, ks=(1, 3))]
    assert scored[0]["hit@1"] == 1.0 and scored[1]["hit@1"] == 0.0
    agg = m.aggregate(scored)
    assert agg["hit@1"] == 0.5
    assert agg["mrr"] == 0.5
    assert agg["dup@3"] == pytest.approx(0.25)  # (0 + 0.5) / 2
    assert agg["recall@3"] == 0.5


def test_aggregate_rejects_empty():
    with pytest.raises(ValueError):
        m.aggregate([])
