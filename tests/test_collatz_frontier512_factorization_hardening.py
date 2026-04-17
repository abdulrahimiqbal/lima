from scripts.run_collatz_frontier512_factorization_hardening import build_payload, build_lean_source


def test_factor_cases_capture_single_child_reductions_at_512_layer() -> None:
    payload = build_payload()
    cases = {item["parent_residue"]: item for item in payload["factor_cases"]}

    assert cases[63]["open_children"] == [63]
    assert cases[63]["resolved_children"] == [575]
    assert cases[71]["open_children"] == [71]
    assert cases[71]["resolved_children"] == [583]
    assert cases[223]["open_children"] == [223]
    assert cases[223]["resolved_children"] == [735]
    assert cases[287]["open_children"] == [799]
    assert cases[287]["resolved_children"] == [287]
    assert cases[347]["open_children"] == [859]
    assert cases[347]["resolved_children"] == [347]
    assert cases[507]["open_children"] == [1019]
    assert cases[507]["resolved_children"] == [507]


def test_generated_source_contains_new_direct_1024_descent_theorems() -> None:
    source = build_lean_source()

    assert "theorem fam_1024_423_descends : FamilyDescends 1024 423" in source
    assert "theorem fam_1024_735_descends : FamilyDescends 1024 735" in source
    assert "theorem fam_1024_923_descends : FamilyDescends 1024 923" in source
    assert "theorem fam_1024_999_descends : FamilyDescends 1024 999" in source
    assert "theorem fam_512_287_factorization" in source
    assert "theorem frontier512_factorization_bundle" in source
