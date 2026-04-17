from scripts.run_collatz_critical_q1_phase_kernel_hardening import build_lean_source, build_payload


def test_phase_kernel_tracks_all_bifurcate_step_and_two_bit_return() -> None:
    payload = build_payload()

    assert payload["phase_states"] == [
        {
            "state": "A",
            "residues_mod_256": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
            "counts": [1, 2, 3, 4, 8],
        },
        {
            "state": "B",
            "residues_mod_256": [27, 103, 127, 159, 191, 239],
            "counts": [9, 18, 28, 39, 78],
        },
        {
            "state": "C",
            "residues_mod_256": [255],
            "counts": [37, 74, 120, 176, 352],
        },
    ]

    assert payload["transitions"]["65536_to_131072"] == {
        "A": {"source_count": 1, "target_count": 2, "child_count_stats": {2: 1}},
        "B": {"source_count": 9, "target_count": 18, "child_count_stats": {2: 9}},
        "C": {"source_count": 37, "target_count": 74, "child_count_stats": {2: 37}},
    }
    assert payload["transitions"]["262144_to_524288"] == {
        "A": {"source_count": 3, "target_count": 4, "child_count_stats": {1: 2, 2: 1}},
        "B": {"source_count": 28, "target_count": 39, "child_count_stats": {1: 17, 2: 11}},
        "C": {"source_count": 120, "target_count": 176, "child_count_stats": {1: 64, 2: 56}},
    }
    assert payload["transitions"]["524288_to_1048576"] == {
        "A": {"source_count": 4, "target_count": 8, "child_count_stats": {2: 4}},
        "B": {"source_count": 39, "target_count": 78, "child_count_stats": {2: 39}},
        "C": {"source_count": 176, "target_count": 352, "child_count_stats": {2: 176}},
    }


def test_phase_kernel_two_bit_bounds_remain_subcritical() -> None:
    payload = build_payload()

    assert payload["two_bit_uniform_subcritical_bounds"] == {
        "A": {"rational": "3/4", "float": 3 / 4},
        "B": {"rational": "7/9", "float": 7 / 9},
        "C": {"rational": "30/37", "float": 30 / 37},
    }
    assert payload["two_bit_uniform_subcritical_bounds"]["C"]["float"] < 1.0
    assert payload["four_step_uniform_subcritical_bounds"] == {
        "A": {"rational": "1/2", "float": 1 / 2},
        "B": {"rational": "13/24", "float": 13 / 24},
        "C": {"rational": "22/37", "float": 22 / 37},
    }
    assert payload["four_step_uniform_subcritical_bounds"]["C"]["float"] < 1.0


def test_phase_kernel_generated_source_compiles_in_lean() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "theorem critical_q1_all_bifurcate_65536_to_131072" in source
    assert "theorem critical_q1_two_bit_return_65536_to_262144" in source
    assert "theorem critical_q1_phase_prefix_65536_to_1048576" in source
    assert "theorem critical_q1_midcycle_return_262144_to_524288" in source
    assert "theorem critical_q1_all_bifurcate_524288_to_1048576" in source
    assert "theorem critical_q1_two_bit_uniform_subcritical" in source
    assert "theorem critical_q1_four_step_uniform_subcritical" in source
