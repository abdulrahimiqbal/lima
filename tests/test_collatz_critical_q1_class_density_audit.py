from scripts.run_collatz_critical_q1_class_density_audit import build_payload


def test_critical_q1_class_density_falls_into_three_archetypes() -> None:
    payload = build_payload()

    assert payload["archetypes"] == [
        {
            "source_count": 1,
            "target_count": 1,
            "normalized_density_factor": {
                "rational": "1/2",
                "float": 0.5,
            },
            "residues_mod_256": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
        },
        {
            "source_count": 7,
            "target_count": 8,
            "normalized_density_factor": {
                "rational": "4/7",
                "float": 4 / 7,
            },
            "residues_mod_256": [27, 103, 127, 159, 191, 239],
        },
        {
            "source_count": 22,
            "target_count": 29,
            "normalized_density_factor": {
                "rational": "29/44",
                "float": 29 / 44,
            },
            "residues_mod_256": [255],
        },
    ]


def test_critical_q1_class_density_has_uniform_bound_below_two_thirds() -> None:
    payload = build_payload()

    assert payload["worst_residue_mod_256"] == 255
    assert payload["uniform_normalized_upper_bound"]["rational"] == "29/44"
    assert payload["uniform_normalized_upper_bound"]["float"] < 2 / 3
    assert payload["uniform_normalized_upper_bound"]["float"] > 0.65
