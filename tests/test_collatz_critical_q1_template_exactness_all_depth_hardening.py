from pathlib import Path

from scripts.run_collatz_critical_q1_template_exactness_all_depth_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_template_exactness_tracks_classifier_rows_and_threshold() -> None:
    payload = build_payload()

    assert payload["interface_names"] == [
        "CriticalQ1TemplateObservation",
        "critical_template_kernel_exactness_all_depth",
        "templateTwoBitLift",
        "templateStabilizationThreshold",
    ]
    assert payload["stabilization_threshold"] == 262144
    assert payload["classifier_rows"][0] == {
        "state": "T1",
        "classifier_key": {
            "residue_mod_256": 27,
            "source_count": 39,
            "one_child_sources": 0,
            "two_child_sources": 39,
        },
        "two_bit_return": {
            "numerator": 78,
            "denominator": 156,
        },
        "two_bit_successor": "T6",
    }
    assert payload["classifier_rows"][-1] == {
        "state": "T12",
        "classifier_key": {
            "residue_mod_256": 255,
            "source_count": 595,
            "one_child_sources": 273,
            "two_child_sources": 322,
        },
        "two_bit_return": {
            "numerator": 917,
            "denominator": 2380,
        },
        "two_bit_successor": None,
    }


def test_template_exactness_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def critical_template_kernel_exactness_all_depth : Prop" in source
    assert "def templateTwoBitLift : CriticalTemplateState → Option CriticalTemplateState" in source
    assert "def templateStabilizationThreshold : Nat := 262144" in source
    assert "theorem critical_template_kernel_checked_successor_law" in source
    assert "theorem critical_template_kernel_checked_stabilization_threshold" in source
    assert Path(LEAN_PATH).read_text() == source
