from scripts.run_collatz_critical_q1_phase_machine_exactness_hardening import (
    build_lean_source,
    build_payload,
)


def test_phase_machine_tracks_checked_prefix() -> None:
    payload = build_payload()

    assert payload["phase_states"] == [
        {
            "state": "A",
            "residues_mod_256": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
            "counts": [1, 2, 3, 4, 8, 13, 19],
        },
        {
            "state": "B",
            "residues_mod_256": [27, 103, 127, 159, 191, 239],
            "counts": [9, 18, 28, 39, 78, 129, 193],
        },
        {
            "state": "C",
            "residues_mod_256": [255],
            "counts": [37, 74, 120, 176, 352, 595, 917],
        },
    ]


def test_phase_machine_tracks_exact_transition_profiles() -> None:
    payload = build_payload()

    assert payload["transitions"]["65536_to_131072"]["A"] == {
        "source_count": 1,
        "target_count": 2,
        "one_child_sources": 0,
        "two_child_sources": 1,
    }
    assert payload["transitions"]["524288_to_1048576"]["C"] == {
        "source_count": 176,
        "target_count": 352,
        "one_child_sources": 0,
        "two_child_sources": 176,
    }
    assert payload["transitions"]["2097152_to_4194304"]["B"] == {
        "source_count": 129,
        "target_count": 193,
        "one_child_sources": 65,
        "two_child_sources": 64,
    }


def test_phase_machine_tracks_return_bounds() -> None:
    payload = build_payload()

    assert payload["two_bit_return_bounds"] == {
        "65536_to_262144": {
            "A": {"rational": "3/4", "float": 3 / 4},
            "B": {"rational": "7/9", "float": 7 / 9},
            "C": {"rational": "30/37", "float": 30 / 37},
        },
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
        "1048576_to_4194304": {
            "A": {"rational": "19/32", "float": 19 / 32},
            "B": {"rational": "193/312", "float": 193 / 312},
            "C": {"rational": "917/1408", "float": 917 / 1408},
        },
    }


def test_phase_machine_generated_source_compiles_in_lean() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "structure CriticalPhaseMachine" in source
    assert "theorem critical_q1_phase_machine_state_support" in source
    assert "theorem critical_q1_phase_machine_checked_counts" in source
    assert "theorem critical_q1_phase_machine_checked_transitions" in source
    assert "theorem critical_q1_phase_machine_checked_return_subcritical" in source
    assert "theorem critical_q1_phase_machine_witness_exists" in source
