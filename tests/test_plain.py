"""Plain-language rendering of stored rules."""

from app.services.plain import describe_diff_lines, profile_rows, rule_phrase


def test_rule_phrase_reads_as_a_sentence():
    phrase = rule_phrase(
        {"attr": "age", "op": "between", "value": [18, 45], "source_quote": "aged between 18 and 45 years"}
    )
    assert phrase == "Age is 18 to 45"
    assert "between" not in phrase


def test_diff_does_not_dump_json():
    lines = describe_diff_lines(
        {
            "changed_conditions": [
                {
                    "id": "c2",
                    "before": {"id": "c2", "attr": "age", "op": "between", "value": [18, 45]},
                    "after": {"id": "c2", "attr": "age", "op": "between", "value": [18, 35]},
                }
            ],
            "added_conditions": [],
            "removed_conditions": [],
            "deadline_changed": False,
            "documents_added": [],
            "documents_removed": [],
        }
    )
    text = " ".join(lines)
    assert "18 to 45" in text
    assert "18 to 35" in text
    assert "{" not in text


def test_profile_rows_hide_raw_keys():
    rows = {row["label"]: row["value"] for row in profile_rows({"age": 40, "disability": True, "education_level": "tertiary"})}
    assert rows["Age"] == "40"
    assert rows["Disability"] == "Yes"
    assert rows["Education"] == "University or college"
    assert "education_level" not in rows
