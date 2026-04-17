from pathlib import Path

from scripts.run_collatz_final_assembly_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_final_assembly_exposes_explicit_nat_level_theorems() -> None:
    payload = build_payload()

    assert payload["theorem_names"] == [
        "collatz_from_eventual_positive_descent",
        "eventual_positive_descent_from_full_kernel",
        "collatz_nat_level_no_scaffold",
    ]
    assert payload["interface_names"] == [
        "critical_template_kernel_exactness_all_depth",
        "PhaseKernelExactCoverage",
        "critical_template_kernel_density_zero_nat",
        "NoDangerousFrontier",
        "PressureHeightExit",
    ]
    assert payload["anti_circularity"] == {
        "axiom": False,
        "sorry": False,
        "bool_field": False,
        "abstract_shadow_control": False,
    }


def test_final_assembly_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def critical_template_kernel_density_zero_nat : Prop" in source
    assert "theorem critical_q1_excludes_dangerous_frontier" in source
    assert "theorem pressure_height_exit_exists_nat" in source
    assert "theorem collatz_nat_level_no_scaffold" in source
    assert Path(LEAN_PATH).read_text() == source
