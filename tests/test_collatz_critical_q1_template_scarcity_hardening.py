from pathlib import Path

from scripts.run_collatz_critical_q1_template_scarcity_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_template_scarcity_tracks_exact_uniform_epsilon_and_ratios() -> None:
    payload = build_payload()

    assert payload["epsilon"] == {"rational": "1/2", "float": 0.5}
    assert payload["worst_ratio"] == {"rational": "1/2", "float": 0.5}
    assert payload["per_state_two_bit_ratio"] == {
        "T1": {"rational": "1/2", "float": 1 / 2},
        "T2": {"rational": "1/2", "float": 1 / 2},
        "T3": {"rational": "1/2", "float": 1 / 2},
        "T4": {"rational": "39/112", "float": 39 / 112},
        "T5": {"rational": "43/104", "float": 43 / 104},
        "T6": {"rational": "193/516", "float": 193 / 516},
        "T7": {"rational": "1/3", "float": 1 / 3},
        "T8": {"rational": "13/32", "float": 13 / 32},
        "T9": {"rational": "19/52", "float": 19 / 52},
        "T10": {"rational": "11/30", "float": 11 / 30},
        "T11": {"rational": "595/1408", "float": 595 / 1408},
        "T12": {"rational": "131/340", "float": 917 / 2380},
    }


def test_template_scarcity_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "theorem critical_template_kernel_weight_positive" in source
    assert "theorem critical_template_kernel_two_bit_contraction" in source
    assert "theorem critical_template_kernel_density_zero" in source
    assert Path(LEAN_PATH).read_text() == source
