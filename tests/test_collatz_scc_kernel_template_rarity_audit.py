from scripts.run_collatz_scc_kernel_template_rarity_audit import build_payload


def test_phase0_template_inventory_is_finite_and_has_tiny_critical_q1_branch() -> None:
    payload = build_payload()
    phase0 = payload["phase0_cycle"]["source_inventory"]

    assert phase0["Q1"]["template_count"] == 5
    assert phase0["Q3"]["template_count"] == 1
    assert phase0["Q6"]["template_count"] == 1
    assert phase0["Q1"]["critical_template_probability"]["float"] < 4e-6
    assert phase0["Q1"]["critical_template_probability"]["float"] > 3e-6
    assert phase0["Q1"]["worst_noncritical_ratio"] < 0.95


def test_phase1_template_inventory_is_finite_and_has_tiny_critical_q1_branch() -> None:
    payload = build_payload()
    phase1 = payload["phase1_cycle"]["source_inventory"]

    assert phase1["Q1"]["template_count"] == 9
    assert phase1["Q2"]["template_count"] == 2
    assert phase1["Q5"]["template_count"] == 1
    assert phase1["Q8"]["template_count"] == 1
    assert phase1["Q1"]["critical_template_probability"]["float"] < 2e-5
    assert phase1["Q1"]["critical_template_probability"]["float"] > 1e-5
    assert phase1["Q1"]["worst_noncritical_ratio"] < 0.96
