from scripts.run_collatz_scc_kernel_branching_audit import build_payload


def test_branching_audit_reports_supercritical_unweighted_operator() -> None:
    payload = build_payload()

    assert payload["states"] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]
    assert payload["unweighted_radius"] > 1.8
    assert payload["unweighted_radius"] < 1.85


def test_branching_audit_reports_subcritical_density_normalized_operator() -> None:
    payload = build_payload()

    assert payload["density_normalized_radius"] > 0.9
    assert payload["density_normalized_radius"] < 0.92
