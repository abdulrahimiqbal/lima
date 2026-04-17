from scripts.run_collatz_critical_q1_child_law_hardening import build_lean_source, build_payload


def test_critical_q1_child_law_hardening_tracks_theorem_bundle() -> None:
    payload = build_payload()

    assert payload["lean_source_theorems"] == [
        "singleton_class_child_law_16384_to_32768",
        "singleton_class_child_law_32768_to_65536",
        "seven_class_child_law_16384_to_32768",
        "seven_class_child_law_32768_to_65536",
        "heavy_class_child_law",
        "observed_child_law_recurrence",
        "critical_q1_child_law_bundle",
    ]


def test_critical_q1_child_law_hardening_tracks_expected_class_partition() -> None:
    payload = build_payload()

    assert payload["singleton_classes"] == [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
    assert payload["seven_classes"] == [27, 103, 127, 159, 191, 239]
    assert payload["heavy_class"] == 255


def test_generated_source_contains_child_law_bundle() -> None:
    source = build_lean_source()

    assert "theorem singleton_class_child_law_16384_to_32768" in source
    assert "theorem seven_class_child_law_32768_to_65536" in source
    assert "theorem observed_child_law_recurrence" in source
    assert "theorem critical_q1_child_law_bundle" in source
