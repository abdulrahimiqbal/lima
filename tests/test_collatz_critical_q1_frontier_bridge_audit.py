from scripts.run_collatz_critical_q1_frontier_bridge_audit import build_payload


def test_critical_q1_projection_recovers_open_mod256_frontier_at_16384_and_32768() -> None:
    payload = build_payload()
    open_frontier = payload["open_mod256_frontier"]
    by_modulus = {
        level["source_modulus"]: level
        for level in payload["levels"]
    }

    assert by_modulus[16384]["projection_mod_256"] == open_frontier
    assert by_modulus[32768]["projection_mod_256"] == open_frontier


def test_critical_q1_projection_is_smaller_before_frontier_stabilization() -> None:
    payload = build_payload()
    by_modulus = {
        level["source_modulus"]: level
        for level in payload["levels"]
    }

    assert by_modulus[8192]["projection_mod_256"] == [27, 103, 127, 159, 191, 239, 255]
    assert by_modulus[8192]["critical_q1_count"] == 12
    assert by_modulus[16384]["critical_q1_count"] == 76
    assert by_modulus[32768]["critical_q1_count"] == 89
