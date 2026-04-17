from pathlib import Path

from scripts.run_pressure_height_kernel_bridge_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_pressure_height_bridge_exposes_explicit_theorem_interface() -> None:
    payload = build_payload()

    assert payload["theorem_names"] == [
        "kernel_bound_has_finite_base_coverage",
        "critical_q1_excludes_dangerous_frontier",
        "pressure_height_exit_exists_nat",
        "pressure_height_exit_sound_nat",
        "eventual_positive_descent_from_periodic_kernel",
    ]
    assert payload["interface_names"] == [
        "critical_template_kernel_exactness_all_depth",
        "critical_template_kernel_density_zero_nat",
        "NoDangerousFrontier",
        "PressureHeightExit",
    ]
    assert payload["anti_circularity"] == {
        "axiom": False,
        "sorry": False,
        "bool_field": False,
        "abstract_shadow_control": False,
        "abstract_phase_coverage": False,
        "explicit_base_assumption": False,
    }


def test_pressure_height_bridge_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def critical_template_kernel_density_zero_nat : Prop" in source
    assert "PhaseKernelExactCoverage" not in source
    assert "hBase" not in source
    assert "theorem kernel_bound_has_finite_base_coverage" in source
    assert "theorem critical_q1_excludes_dangerous_frontier" in source
    assert "theorem pressure_height_exit_exists_nat" in source
    assert "theorem pressure_height_exit_sound_nat" in source
    assert "theorem eventual_positive_descent_from_periodic_kernel" in source
    assert Path(LEAN_PATH).read_text() == source
