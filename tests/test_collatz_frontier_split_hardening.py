from scripts.run_collatz_frontier_split_hardening import build_lean_source, build_payload


def test_frontier_split_certificates_match_expected_leaves() -> None:
    payload = build_payload()
    summaries = {item["residue"]: item for item in payload["certificate_summaries"]}

    assert summaries[39]["steps"] == 13
    assert summaries[39]["leaf_coeff"] == 243
    assert summaries[39]["leaf_const"] == 38

    assert summaries[79]["steps"] == 13
    assert summaries[79]["leaf_coeff"] == 243
    assert summaries[79]["leaf_const"] == 76

    assert summaries[95]["steps"] == 13
    assert summaries[95]["leaf_coeff"] == 243
    assert summaries[95]["leaf_const"] == 91

    assert summaries[123]["steps"] == 13
    assert summaries[123]["leaf_coeff"] == 243
    assert summaries[123]["leaf_const"] == 118


def test_generated_source_contains_frontier_split_theorems() -> None:
    source = build_lean_source()

    assert "theorem fam_256_39_descends : FamilyDescends 256 39" in source
    assert "theorem fam_256_79_descends : FamilyDescends 256 79" in source
    assert "theorem fam_256_95_descends : FamilyDescends 256 95" in source
    assert "theorem fam_256_123_descends : FamilyDescends 256 123" in source
    assert "theorem frontier128_composed_descended_cases" in source
    assert "theorem frontier128_split_or_descend_family" in source
