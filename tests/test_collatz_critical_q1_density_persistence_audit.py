from scripts.run_collatz_critical_q1_density_persistence_audit import build_payload


def test_critical_q1_density_patterns_persist_through_65536() -> None:
    payload = build_payload()

    assert payload["archetypes"] == [
        {
            "count_pattern": [1, 1, 1],
            "residues_mod_256": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
            "normalized_factors": {
                "16384_to_32768": {"rational": "1/2", "float": 0.5},
                "32768_to_65536": {"rational": "1/2", "float": 0.5},
            },
        },
        {
            "count_pattern": [7, 8, 9],
            "residues_mod_256": [27, 103, 127, 159, 191, 239],
            "normalized_factors": {
                "16384_to_32768": {"rational": "4/7", "float": 4 / 7},
                "32768_to_65536": {"rational": "9/16", "float": 9 / 16},
            },
        },
        {
            "count_pattern": [22, 29, 37],
            "residues_mod_256": [255],
            "normalized_factors": {
                "16384_to_32768": {"rational": "29/44", "float": 29 / 44},
                "32768_to_65536": {"rational": "37/58", "float": 37 / 58},
            },
        },
    ]


def test_critical_q1_density_pairwise_uniform_bound_improves_at_next_lift() -> None:
    payload = build_payload()

    assert payload["pairwise_bounds"] == {
        "16384_to_32768": {
            "worst_residue_mod_256": 255,
            "uniform_normalized_upper_bound": {
                "rational": "29/44",
                "float": 29 / 44,
            },
        },
        "32768_to_65536": {
            "worst_residue_mod_256": 255,
            "uniform_normalized_upper_bound": {
                "rational": "37/58",
                "float": 37 / 58,
            },
        },
    }
    assert payload["pairwise_bounds"]["32768_to_65536"]["uniform_normalized_upper_bound"]["float"] < payload["pairwise_bounds"]["16384_to_32768"]["uniform_normalized_upper_bound"]["float"]
