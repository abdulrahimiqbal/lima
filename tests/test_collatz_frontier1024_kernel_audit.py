from scripts.run_collatz_frontier1024_kernel_audit import build_payload


def test_open_mod1024_frontier_has_three_nontrivial_kernel_classes() -> None:
    payload = build_payload()

    assert payload["open_parent_count"] == 65

    coarse = {
        tuple(cluster["parents"]): tuple(cluster["resolved_child_signature"])
        for cluster in payload["coarse_clusters"]
    }

    assert coarse[(1,)] == (1, 3, 7)
    assert coarse[(159, 239, 447, 511, 639, 767, 795, 871, 1023)] == (0, 0, 0)
    assert coarse[(27, 31, 91, 103, 111, 127, 167, 251, 255, 283, 319, 327, 359, 415, 479, 495, 559, 667, 671, 703, 719, 743, 751, 895, 959)] == (0, 0, 1)
    assert coarse[(47, 63, 71, 155, 191, 207, 223, 231, 303, 383, 411, 463, 487, 539, 543, 603, 615, 623, 679, 763, 799, 831, 839, 859, 879, 927, 935, 991, 1007, 1019)] == (0, 1, 4)


def test_exact_profile_inventory_matches_three_nontrivial_shapes() -> None:
    payload = build_payload()
    profiles = {tuple(tuple(pair) for pair in item["profile"]): item["count"] for item in payload["exact_profiles"]}

    assert profiles[((1, 1), (1, 1), (1, 1), (1, 1))] == 1
    assert profiles[((0, 2), (0, 4), (0, 8), (0, 16))] == 9
    assert profiles[((0, 2), (0, 4), (1, 7), (0, 14))] == 25
    assert profiles[((0, 2), (1, 3), (2, 4), (0, 8))] == 30
