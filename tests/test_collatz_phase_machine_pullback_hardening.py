from scripts.run_collatz_phase_machine_pullback_hardening import build_lean_source, build_payload


def test_phase_machine_pullback_tracks_exact_interfaces() -> None:
    payload = build_payload()

    assert payload["interface_names"] == [
        "CriticalPhaseMachineState",
        "CriticalPhaseMachine",
        "critical_q1_phase_machine_exactness",
        "critical_q1_phase_machine_subcritical",
        "phase_kernel_exact_coverage",
        "critical_q1_machine_bridge_to_no_dangerous_frontier",
        "critical_q1_excludes_dangerous_frontier",
        "kernel_control_implies_eventual_descent",
        "collatz_eventual_descent",
        "collatz_terminates",
    ]


def test_phase_machine_pullback_names_remaining_assumptions() -> None:
    payload = build_payload()

    assert payload["remaining_assumptions"] == [
        "critical_q1_phase_machine_exactness",
        "critical_q1_phase_machine_subcritical",
        "phase_kernel_exact_coverage",
        "critical_q1_machine_bridge_to_no_dangerous_frontier",
        "Nat-level exit existence and exit soundness from NoDangerousFrontier",
    ]


def test_phase_machine_pullback_generated_source_compiles_in_lean() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def critical_q1_phase_machine_exactness : Prop" in source
    assert "def critical_q1_phase_machine_subcritical : Prop" in source
    assert "def phase_kernel_exact_coverage : Prop" in source
    assert "theorem critical_q1_excludes_dangerous_frontier" in source
    assert "theorem kernel_control_implies_eventual_descent" in source
    assert "theorem collatz_eventual_descent" in source
    assert "theorem collatz_terminates" in source
