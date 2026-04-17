from scripts.run_collatz_scc_kernel_graph import build_payload


def test_kernel_graph_stays_nine_state_closed_through_8192() -> None:
    payload = build_payload()

    assert payload["state_count"] == 9
    assert payload["graph"]["Q1"] == ["Q1", "Q2"]
    assert payload["graph"]["Q2"] == ["Q1", "Q2", "Q3", "Q4"]
    assert payload["graph"]["Q3"] == ["Q2", "Q5"]
    assert payload["graph"]["Q4"] == ["Q3", "Q6"]
    assert payload["graph"]["Q5"] == ["Q4", "Q7"]
    assert payload["graph"]["Q6"] == ["Q5", "Q8"]
    assert payload["graph"]["Q7"] == ["Q6"]
    assert payload["graph"]["Q8"] == ["Q7"]
    assert payload["graph"]["Q9"] == ["Q9"]


def test_kernel_graph_has_one_nontrivial_scc_plus_trivial_one_state() -> None:
    payload = build_payload()

    assert payload["sccs"] == [
        ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"],
        ["Q9"],
    ]
