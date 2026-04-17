from pathlib import Path

from scripts.run_collatz_critical_q1_template_density_zero_nat_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_template_density_zero_nat_exposes_concrete_interfaces() -> None:
    payload = build_payload()

    assert payload["interface_names"] == [
        "critical_template_kernel_exactness_all_depth",
        "PhaseKernelExactCoverage",
        "NoDangerousFrontier",
        "critical_template_kernel_density_zero_nat",
    ]
    assert payload["anti_circularity"] == {
        "axiom": False,
        "sorry": False,
        "bool_field": False,
        "abstract_density_bridge": False,
    }


def test_template_density_zero_nat_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def critical_template_kernel_density_zero_nat : Prop" in source
    assert (
        "theorem critical_template_kernel_density_zero_nat_implies_no_dangerous_frontier"
        in source
    )
    assert Path(LEAN_PATH).read_text() == source
