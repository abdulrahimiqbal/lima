from scripts.run_collatz_frontier128_factorization_hardening import build_payload, build_lean_source


def test_factor_cases_capture_all_13_mod128_frontier_families() -> None:
    payload = build_payload()
    cases = {item["parent_residue"]: item for item in payload["factor_cases"]}

    assert sorted(cases) == [27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127]
    assert cases[39]["open_children"] == [167]
    assert cases[47]["open_children"] == [47]
    assert cases[71]["open_children"] == [71]
    assert cases[79]["open_children"] == [207]
    assert cases[91]["open_children"] == [91]
    assert cases[95]["open_children"] == [223]
    assert cases[123]["open_children"] == [251]
    assert cases[27]["open_children"] == [27, 155]
    assert cases[31]["open_children"] == [31, 159]
    assert cases[63]["open_children"] == [63, 191]
    assert cases[103]["open_children"] == [103, 231]
    assert cases[111]["open_children"] == [111, 239]
    assert cases[127]["open_children"] == [127, 255]


def test_generated_source_contains_factorization_bundle() -> None:
    source = build_lean_source()

    assert "theorem fam_128_27_factorization" in source
    assert "theorem fam_128_39_factorization" in source
    assert "theorem fam_128_79_factorization" in source
    assert "theorem fam_128_127_factorization" in source
    assert "theorem frontier128_factorization_bundle" in source
