from pathlib import Path

from scripts.run_collatz_critical_q1_template_kernel_hardening import (
    LEAN_PATH,
    build_lean_source,
    build_payload,
)


def test_template_kernel_state_order_is_deterministic() -> None:
    payload = build_payload()

    assert [row["state"] for row in payload["template_states"]] == [
        "T1",
        "T2",
        "T3",
        "T4",
        "T5",
        "T6",
        "T7",
        "T8",
        "T9",
        "T10",
        "T11",
        "T12",
    ]
    assert payload["template_states"][0] == {
        "state": "T1",
        "phase": "bifurcate",
        "residue_mod_256": 27,
        "source_count": 39,
        "target_count": 78,
        "one_child_sources": 0,
        "two_child_sources": 39,
        "weight_num": 39,
        "weight_den": 1,
        "two_bit_succ": ["T6"],
    }
    assert payload["template_states"][-1] == {
        "state": "T12",
        "phase": "mixed",
        "residue_mod_256": 255,
        "source_count": 595,
        "target_count": 917,
        "one_child_sources": 273,
        "two_child_sources": 322,
        "weight_num": 595,
        "weight_den": 1,
        "two_bit_succ": [],
    }


def test_template_kernel_checked_successor_map_matches_window() -> None:
    payload = build_payload()

    assert {row["state"]: row["two_bit_succ"] for row in payload["template_states"]} == {
        "T1": ["T6"],
        "T2": ["T9"],
        "T3": ["T12"],
        "T4": ["T5"],
        "T5": ["T6"],
        "T6": [],
        "T7": ["T8"],
        "T8": ["T9"],
        "T9": [],
        "T10": ["T11"],
        "T11": ["T12"],
        "T12": [],
    }


def test_template_kernel_generated_source_matches_repo_file_and_compiles() -> None:
    payload = build_payload()
    source = build_lean_source()

    assert payload["lean_check"]["ok"], payload["lean_check"]["stderr"]
    assert "inductive CriticalPhase" in source
    assert "inductive CriticalTemplateState" in source
    assert "theorem critical_template_kernel_partition_checked_window" in source
    assert "theorem critical_template_kernel_transition_checked_window" in source
    assert "theorem critical_template_kernel_weight_data_checked_window" in source
    assert Path(LEAN_PATH).read_text() == source
