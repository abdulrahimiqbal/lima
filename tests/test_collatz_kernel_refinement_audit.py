from scripts.run_collatz_kernel_refinement_audit import build_payload


def test_mod256_open_kernel_compresses_to_three_mod512_signature_classes() -> None:
    payload = build_payload()
    audit = payload["open_mod256_lift_signatures"]

    assert audit["cluster_count"] == 3

    clusters = {
        tuple(cluster["residues"]): (
            cluster["resolved_signature"],
            cluster["unresolved_signature"],
        )
        for cluster in audit["clusters"]
    }

    assert clusters[(127, 159, 239, 255)] == ([0, 0, 0, 1], [2, 4, 8, 15])
    assert clusters[(27, 31, 47, 91, 103, 111, 155, 167, 191, 207, 231, 251)] == (
        [0, 0, 1, 5],
        [2, 4, 7, 11],
    )
    assert clusters[(63, 71, 223)] == ([1, 2, 5, 12], [1, 2, 3, 4])


def test_mod512_open_kernel_compresses_to_four_mod1024_signature_classes() -> None:
    payload = build_payload()
    audit = payload["open_mod512_lift_signatures"]

    assert audit["cluster_count"] == 4

    clusters = {
        tuple(cluster["residues"]): (
            cluster["resolved_signature"],
            cluster["unresolved_signature"],
        )
        for cluster in audit["clusters"]
    }

    assert clusters[(159, 239, 447, 511)] == ([0, 0, 0, 0], [2, 4, 8, 16])
    assert clusters[(27, 31, 91, 103, 111, 127, 167, 251, 255, 283, 319, 327, 359, 415, 479, 495)] == (
        [0, 0, 1, 2],
        [2, 4, 7, 14],
    )
    assert clusters[(47, 63, 71, 155, 191, 207, 223, 231, 303, 383, 411, 463, 487)] == (
        [0, 1, 4, 8],
        [2, 3, 4, 8],
    )
    assert clusters[(287, 347, 367, 423, 507)] == ([2, 4, 8, 16], [0, 0, 0, 0])
