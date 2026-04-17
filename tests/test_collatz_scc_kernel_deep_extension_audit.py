from scripts.run_collatz_scc_kernel_deep_extension_audit import build_payload


def test_deep_extension_refines_nine_state_kernel_to_ten_states() -> None:
    payload = build_payload()

    assert payload["state_count"] == 10


def test_deep_extension_exhibits_phase_pattern_then_refines_at_32768() -> None:
    payload = build_payload()

    assert payload["modulus_state_sets"] == {
        1024: ["Q1", "Q10", "Q3", "Q6"],
        2048: ["Q1", "Q10", "Q2", "Q5", "Q9"],
        4096: ["Q1", "Q10", "Q2", "Q4", "Q8"],
        8192: ["Q1", "Q10", "Q3", "Q6"],
        16384: ["Q1", "Q10", "Q2", "Q5", "Q9"],
        32768: ["Q1", "Q10", "Q3", "Q7"],
    }
