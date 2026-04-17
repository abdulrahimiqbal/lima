from scripts.run_collatz_critical_q1_recurrence_subcritical_hardening import (
    build_lean_source,
    build_payload,
)


def test_recurrence_subcritical_hardening_compiles_in_lean() -> None:
    payload = build_payload()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]


def test_recurrence_subcritical_hardening_tracks_expected_theorems() -> None:
    payload = build_payload()

    assert payload["theorem_names"] == [
        "aSeq_fixed",
        "bSeq_recurrence",
        "cSeq_recurrence",
        "b_lt_c",
        "b_subcritical",
        "c_subcritical",
        "critical_q1_abstract_kernel_uniform_subcritical",
    ]


def test_generated_source_contains_uniform_subcritical_bundle() -> None:
    source = build_lean_source()

    assert "theorem b_subcritical" in source
    assert "theorem c_subcritical" in source
    assert "theorem critical_q1_abstract_kernel_uniform_subcritical" in source
