import copy

from eval import labels


def test_shipped_labels_are_valid():
    data = labels.load()
    assert labels.schema_errors(data) == []
    assert len(data["items"]) >= 30


def test_every_expected_source_is_a_knowledge_base_file():
    data = labels.load()
    names = {p.name for p in (labels.KB_DIR / "ai_ml").glob("*.pdf")}
    for item in data["items"]:
        for entry in item["expected"]:
            assert entry["source"] in names, (item["id"], entry["source"])


def _minimal():
    return {"items": [{
        "id": "x",
        "profile": {"role": "ai_ml", "skills": ["a"], "domain_exposure": ["b"], "seniority_level": "mid"},
        "expected": [{"source": "AIML1.pdf", "anchor": "four words are enough"}],
    }]}


def test_schema_catches_problems():
    assert labels.schema_errors(_minimal()) == []

    no_expected = _minimal()
    no_expected["items"][0]["expected"] = []
    assert any("expected" in e for e in labels.schema_errors(no_expected))

    short_anchor = copy.deepcopy(_minimal())
    short_anchor["items"][0]["expected"][0]["anchor"] = "too short"
    assert any("anchor" in e for e in labels.schema_errors(short_anchor))

    dup = _minimal()
    dup["items"].append(copy.deepcopy(dup["items"][0]))
    assert any("duplicate" in e for e in labels.schema_errors(dup))

    bad_level = _minimal()
    bad_level["items"][0]["profile"]["seniority_level"] = "principal"
    assert any("seniority" in e for e in labels.schema_errors(bad_level))
