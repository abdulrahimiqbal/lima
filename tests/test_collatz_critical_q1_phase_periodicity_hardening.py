from scripts.run_collatz_critical_q1_phase_periodicity_hardening import build_lean_source, build_payload


def test_phase_periodicity_tracks_mixed_and_all_bifurcate_steps() -> None:
    payload = build_payload()

    assert payload["phase_states"] == [
        {
            "state": "A",
            "residues_mod_256": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
            "counts": [3, 4, 8, 13],
        },
        {
            "state": "B",
            "residues_mod_256": [27, 103, 127, 159, 191, 239],
            "counts": [28, 39, 78, 129],
        },
        {
            "state": "C",
            "residues_mod_256": [255],
            "counts": [120, 176, 352, 595],
        },
    ]

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
    assert payload["transitions"]["1048576_to_2097152"] == {
        "A": {"source_count": 8, "target_count": 13, "child_count_stats": {1: 3, 2: 5}},
        "B": {"source_count": 78, "target_count": 129, "child_count_stats": {1: 27, 2: 51}},
        "C": {"source_count": 352, "target_count": 595, "child_count_stats": {1: 109, 2: 243}},
    }


def test_phase_periodicity_two_bit_returns_remain_subcritical() -> None:
    payload = build_payload()

    assert payload["two_bit_subcritical_bounds"] == {
        "262144_to_1048576": {
            "A": {"rational": "2/3", "float": 2 / 3},
            "B": {"rational": "39/56", "float": 39 / 56},
            "C": {"rational": "11/15", "float": 11 / 15},
        },
        "524288_to_2097152": {
            "A": {"rational": "13/16", "float": 13 / 16},
            "B": {"rational": "43/52", "float": 43 / 52},
            "C": {"rational": "595/704", "float": 595 / 704},
        },
    }


def test_phase_periodicity_generated_source_compiles_in_lean() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "theorem critical_q1_mixed_phase_262144_to_524288" in source
    assert "theorem critical_q1_all_bifurcate_524288_to_1048576" in source
    assert "theorem critical_q1_mixed_phase_1048576_to_2097152" in source
