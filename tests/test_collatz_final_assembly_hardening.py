from pathlib import Path

from scripts.run_collatz_final_assembly_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_final_assembly_exposes_explicit_nat_level_theorems() -> None:
    payload = build_payload()

    assert payload["theorem_names"] == [
        "kernel_bound_has_finite_base_coverage",
        "collatz_from_eventual_positive_descent",
        "eventual_positive_descent_from_full_kernel",
        "collatz_nat_level_no_scaffold",
    ]
    assert payload["interface_names"] == [
        "critical_template_kernel_exactness_all_depth",
        "critical_template_kernel_density_zero_nat",
        "NoDangerousFrontier",
    ]
    assert payload["anti_circularity"] == {
        "axiom": False,
        "sorry": False,
        "bool_field": False,
        "abstract_shadow_control": False,
        "abstract_phase_coverage": False,
        "explicit_base_assumption": False,
    }


def test_final_assembly_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def critical_template_kernel_density_zero_nat : Prop" in source
    assert "PhaseKernelExactCoverage" not in source
    assert "hBase" not in source
    assert "theorem kernel_bound_has_finite_base_coverage" in source
    assert "theorem collatz_nat_level_no_scaffold" in source
    assert Path(LEAN_PATH).read_text() == source
