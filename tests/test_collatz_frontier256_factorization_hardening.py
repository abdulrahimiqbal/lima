from scripts.run_collatz_frontier256_factorization_hardening import build_payload, build_lean_source


def test_factor_cases_capture_all_open_mod256_residues() -> None:
    payload = build_payload()
    cases = {item["parent_residue"]: item["open_children"] for item in payload["factor_cases"]}

    assert sorted(cases) == [27, 31, 47, 63, 71, 91, 103, 111, 127, 155, 159, 167, 191, 207, 223, 231, 239, 251, 255]
    assert cases[27] == [27, 283]
    assert cases[31] == [31, 287]
    assert cases[47] == [47, 303]
    assert cases[63] == [63, 319]
    assert cases[71] == [71, 327]
    assert cases[91] == [91, 347]
    assert cases[103] == [103, 359]
    assert cases[111] == [111, 367]
    assert cases[127] == [127, 383]
    assert cases[255] == [255, 511]


def test_generated_source_contains_factorization_bundle() -> None:
    source = build_lean_source()

    assert "theorem fam_256_27_factorization" in source
    assert "theorem fam_256_167_factorization" in source
    assert "theorem fam_256_255_factorization" in source
    assert "theorem frontier256_factorization_bundle" in source
