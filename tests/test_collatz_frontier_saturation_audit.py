from scripts.run_collatz_frontier_saturation_audit import build_payload


def test_root_frontier_is_stable_across_larger_search_budgets() -> None:
    payload = build_payload()
    expected = [27, 31, 47, 63, 71, 91, 103, 111, 127]

    for item in payload["root_budget_audit"]:
        assert item["unresolved_roots"] == expected


def test_child_frontier_keeps_the_two_observed_obstruction_sizes() -> None:
    payload = build_payload()
    parents = payload["child_budget_audit"]["parents"]
    counts = {item["parent_residue"]: len(item["unresolved_children"]) for item in parents}

    assert counts[27] == 15
    assert counts[103] == 15
    assert counts[127] == 15

    for residue in [31, 47, 63, 71, 91, 111]:
        assert counts[residue] == 10
