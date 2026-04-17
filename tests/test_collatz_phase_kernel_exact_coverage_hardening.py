from pathlib import Path

from scripts.run_collatz_phase_kernel_exact_coverage_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_phase_kernel_exact_coverage_classifies_entire_live_frontier() -> None:
    payload = build_payload()

    assert payload["frontier_classification"]["39"] == "descends"
    assert payload["frontier_classification"]["27"] == "kernelB"
    assert payload["frontier_classification"]["31"] == "kernelA"
    assert payload["frontier_classification"]["255"] == "kernelC"
    assert len(payload["frontier_classification"]) == 23
    assert payload["interface_names"] == [
        "FrontierCoverage",
        "LiveRecurrentFrontierResidue",
    ]


def test_phase_kernel_exact_coverage_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "def LiveRecurrentFrontierResidue (n : Nat) : Prop" in source
    assert "theorem phase_kernel_exact_coverage" in source
    assert "∀ n, LiveRecurrentFrontierResidue n →" in source
    assert Path(LEAN_PATH).read_text() == source
