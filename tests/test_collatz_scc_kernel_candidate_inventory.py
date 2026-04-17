from scripts.run_collatz_scc_kernel_candidate_inventory import build_payload


def test_kernel_candidate_inventory_has_nine_states() -> None:
    payload = build_payload()

    assert payload["state_count"] == 9

    by_id = {item["state_id"]: item for item in payload["state_inventory"]}
    assert by_id["Q1"]["profile"] == [[0, 2], [0, 4], [0, 8], [0, 16]]
    assert by_id["Q3"]["profile"] == [[0, 2], [0, 4], [1, 7], [0, 14]]
    assert by_id["Q6"]["profile"] == [[0, 2], [1, 3], [2, 4], [0, 8]]
    assert by_id["Q9"]["profile"] == [[1, 1], [1, 1], [1, 1], [1, 1]]


def test_kernel_candidate_transition_structure_is_regular() -> None:
    payload = build_payload()
    transitions = {
        (item["source_modulus"], item["source_state_id"]): item["child_multisets"]
        for item in payload["transition_inventory"]
    }

    assert transitions[(1024, "Q1")] == [
        {"children": ["Q1", "Q2"], "count": 8},
        {"children": ["Q1", "Q1"], "count": 1},
    ]
    assert transitions[(1024, "Q3")] == [
        {"children": ["Q2", "Q5"], "count": 25},
    ]
    assert transitions[(1024, "Q6")] == [
        {"children": ["Q5", "Q8"], "count": 30},
    ]
    assert transitions[(2048, "Q2")] == [
        {"children": ["Q2", "Q4"], "count": 33},
    ]
    assert transitions[(2048, "Q5")] == [
        {"children": ["Q4", "Q7"], "count": 55},
    ]
    assert transitions[(2048, "Q8")] == [
        {"children": ["Q7"], "count": 30},
    ]
