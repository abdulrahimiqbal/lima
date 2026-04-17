from scripts.run_collatz_critical_q1_child_law_audit import build_payload


def test_singleton_and_seven_class_transition_laws_hold_across_checked_lifts() -> None:
    payload = build_payload()

    for transition_key, classes in payload["singleton_pattern"].items():
        for residue, summary in classes.items():
            assert summary == {
                "source_count": 1,
                "target_count": 1,
                "child_count_stats": {1: 1},
            }

    expected_seven = {
        "16384_to_32768": {"source_count": 7, "target_count": 8, "child_count_stats": {1: 6, 2: 1}},
        "32768_to_65536": {"source_count": 8, "target_count": 9, "child_count_stats": {1: 7, 2: 1}},
    }
    for transition_key, classes in payload["seven_pattern"].items():
        for residue, summary in classes.items():
            assert summary == expected_seven[transition_key]


def test_heavy_class_transition_law_matches_b_class_growth() -> None:
    payload = build_payload()

    assert payload["heavy_pattern"] == {
        "16384_to_32768": {
            "source_count": 22,
            "target_count": 29,
            "child_count_stats": {1: 15, 2: 7},
        },
        "32768_to_65536": {
            "source_count": 29,
            "target_count": 37,
            "child_count_stats": {1: 21, 2: 8},
        },
    }
    assert payload["recurrence_summary"]["observed_counts"] == {
        "a": [1, 1, 1],
        "b": [7, 8, 9],
        "c": [22, 29, 37],
    }
