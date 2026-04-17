from scripts.run_collatz_frontier_child_reduction_hardening import build_payload, build_lean_source


def test_child_reduction_map_matches_expected_open_children() -> None:
    payload = build_payload()
    reductions = {
        item["parent_residue"]: (item["open_child"], item["resolved_child"])
        for item in payload["child_reductions"]
    }

    assert reductions[39] == (167, 39)
    assert reductions[47] == (47, 175)
    assert reductions[71] == (71, 199)
    assert reductions[79] == (207, 79)
    assert reductions[91] == (91, 219)
    assert reductions[95] == (223, 95)
    assert reductions[123] == (251, 123)


def test_generated_source_contains_branch_reduction_theorems() -> None:
    source = build_lean_source()

    assert "theorem fam_128_39_descends_of_167" in source
    assert "theorem fam_128_47_descends_of_47" in source
    assert "theorem fam_128_71_descends_of_71" in source
    assert "theorem fam_128_79_descends_of_207" in source
    assert "theorem fam_128_91_descends_of_91" in source
    assert "theorem fam_128_95_descends_of_223" in source
    assert "theorem fam_128_123_descends_of_251" in source
