from pathlib import Path

from scripts.run_collatz_critical_q1_base_coverage_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_base_coverage_tracks_kernel_bound_and_key_witnesses() -> None:
    payload = build_payload()

    assert payload["kernel_bound"] == 256
    assert payload["witness_count"] == 256
    assert payload["max_witness"] == 96
    assert payload["sample_witnesses"] == {
        "2": 1,
        "27": 96,
        "31": 91,
        "127": 24,
        "255": 21,
    }


def test_base_coverage_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "theorem baseWitness_sound_fin" in source
    assert "theorem kernel_bound_has_finite_base_coverage" in source
    assert Path(LEAN_PATH).read_text() == source
