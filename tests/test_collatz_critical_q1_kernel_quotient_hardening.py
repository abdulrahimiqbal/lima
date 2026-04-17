from scripts.run_collatz_critical_q1_kernel_quotient_hardening import build_lean_source, build_payload


def test_kernel_quotient_tracks_three_explicit_states() -> None:
    payload = build_payload()

    assert payload["kernel_states"] == [
        {
            "state": "A",
            "residues_mod_256": [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251],
            "counts": [1, 1, 1],
        },
        {
            "state": "B",
            "residues_mod_256": [27, 103, 127, 159, 191, 239],
            "counts": [7, 8, 9],
        },
        {
            "state": "C",
            "residues_mod_256": [255],
            "counts": [22, 29, 37],
        },
    ]


def test_kernel_quotient_density_bounds_are_uniformly_subcritical() -> None:
    payload = build_payload()

    assert payload["density_bounds"] == {
        "A": {
            "16384_to_32768": {"rational": "1/2", "float": 0.5},
            "32768_to_65536": {"rational": "1/2", "float": 0.5},
        },
        "B": {
            "16384_to_32768": {"rational": "4/7", "float": 4 / 7},
            "32768_to_65536": {"rational": "9/16", "float": 9 / 16},
        },
        "C": {
            "16384_to_32768": {"rational": "29/44", "float": 29 / 44},
            "32768_to_65536": {"rational": "37/58", "float": 37 / 58},
        },
    }
    assert payload["density_bounds"]["C"]["32768_to_65536"]["float"] < payload["density_bounds"]["C"]["16384_to_32768"]["float"]


def test_generated_source_contains_kernel_theorem_bundle() -> None:
    source = build_lean_source()

    assert "inductive CriticalKernelState" in source
    assert "theorem critical_q1_kernel_partition" in source
    assert "theorem critical_q1_kernel_child_law" in source
    assert "theorem critical_q1_kernel_recurrence" in source
    assert "theorem critical_q1_kernel_uniform_subcritical" in source


def test_kernel_quotient_compiles_in_lean() -> None:
    payload = build_payload()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
