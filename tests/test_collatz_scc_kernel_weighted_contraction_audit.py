from scripts.run_collatz_scc_kernel_weighted_contraction_audit import build_payload


def test_phase0_cycle_has_uniform_explicit_contraction_bound_below_one() -> None:
    payload = build_payload()
    phase0 = payload["phase0_cycle"]

    assert phase0["worst_source_state"] == "Q1"
    assert phase0["uniform_cycle_upper_bound"] > 0.94
    assert phase0["uniform_cycle_upper_bound"] < 0.941
    assert phase0["source_summaries"]["Q3"]["critical_split_upper_bound"] < 0.75
    assert phase0["source_summaries"]["Q6"]["critical_split_upper_bound"] < 0.75


def test_phase1_cycle_has_uniform_explicit_contraction_bound_below_one() -> None:
    payload = build_payload()
    phase1 = payload["phase1_cycle"]

    assert phase1["worst_source_state"] == "Q1"
    assert phase1["uniform_cycle_upper_bound"] > 0.951
    assert phase1["uniform_cycle_upper_bound"] < 0.952
    assert phase1["source_summaries"]["Q2"]["critical_split_upper_bound"] < 0.813
    assert phase1["source_summaries"]["Q5"]["critical_split_upper_bound"] < 0.75
    assert phase1["source_summaries"]["Q8"]["critical_split_upper_bound"] < 0.75


def test_global_uniform_upper_bound_is_below_one() -> None:
    payload = build_payload()

    assert payload["global_uniform_upper_bound"] < 1.0
    assert payload["global_uniform_upper_bound"] > 0.951
