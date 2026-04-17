from scripts.run_collatz_pro_kernel_audit import build_payload


def test_frontier_split_matches_current_repo_signal() -> None:
    payload = build_payload()
    split = payload["frontier_split"]

    assert split["rewrite_descended"] == [39, 79, 95, 123]
    assert split["parent_frontier_256"] == [27, 31, 47, 63, 71, 91, 103, 111, 127]
    assert sorted(split["certificates"]) == ["123", "39", "79", "95"]


def test_kernel_candidates_capture_two_parent_archetypes() -> None:
    payload = build_payload()
    kernel = payload["kernel_candidates"]

    assert kernel["cluster_count"] == 2

    clusters = {
        tuple(cluster["parents"]): (
            cluster["resolved_child_signature"],
            cluster["unresolved_child_signature"],
        )
        for cluster in kernel["clusters"]
    }

    assert clusters[(27, 103, 127)] == ([0, 1, 6, 12], [4, 15, 26, 52])
    assert clusters[(31, 47, 63, 71, 91, 111)] == ([1, 6, 17, 34], [3, 10, 15, 30])


def test_frontier128_reduction_targets_all_land_in_k2() -> None:
    payload = build_payload()
    projection = payload["frontier128_kernel_projection"]

    assert projection["k1_roots_256"] == [27, 103, 127]
    assert projection["k2_roots_256"] == [31, 47, 63, 71, 91, 111]
    assert projection["all_reduction_targets_land_in_k2"] is True

    targets = {
        item["frontier_residue_128"]: (
            item["open_child_256"],
            item["resolved_child_signature"],
            item["unresolved_child_signature"],
        )
        for item in projection["frontier128_reduction_targets"]
    }

    assert targets[39] == (167, [1, 6, 17, 34], [3, 10, 15, 30])
    assert targets[47] == (47, [1, 6, 17, 34], [3, 10, 15, 30])
    assert targets[71] == (71, [1, 6, 17, 34], [3, 10, 15, 30])
    assert targets[79] == (207, [1, 6, 17, 34], [3, 10, 15, 30])
    assert targets[91] == (91, [1, 6, 17, 34], [3, 10, 15, 30])
    assert targets[95] == (223, [1, 6, 17, 34], [3, 10, 15, 30])
    assert targets[123] == (251, [1, 6, 17, 34], [3, 10, 15, 30])
