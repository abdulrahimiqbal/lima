from scripts.run_collatz_scc_kernel_phase_cycle_audit import build_payload


def test_phase_cycle_state_sets_match_three_step_kernel_layers() -> None:
    payload = build_payload()

    assert payload["state_count"] == 9
    assert payload["phase_state_sets"] == {
        "phase0_mod_1024": ["Q1", "Q3", "Q6"],
        "phase1_mod_2048": ["Q1", "Q2", "Q5", "Q8"],
        "phase2_mod_4096": ["Q1", "Q2", "Q4", "Q7"],
    }


def test_phase0_return_cycle_is_strongly_subcritical_after_density_normalization() -> None:
    payload = build_payload()
    cycle = payload["phase0_return_cycle"]

    assert cycle["density_normalized_row_sums"] == [1.0, 0.875, 0.5]
    assert cycle["density_normalized_radius"] > 0.74
    assert cycle["density_normalized_radius"] < 0.75


def test_phase1_return_cycle_is_strongly_subcritical_after_density_normalization() -> None:
    payload = build_payload()
    cycle = payload["phase1_return_cycle"]

    assert cycle["density_normalized_row_sums"] == [1.0, 1.0, 0.75, 0.25]
    assert cycle["density_normalized_radius"] > 0.74
    assert cycle["density_normalized_radius"] < 0.76
