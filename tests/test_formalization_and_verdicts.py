"""Tests for honest formalization and fixed verdict semantics."""

from app.executor import AristotleSdkProofAdapter, _sanitize_theorem_name
from app.schemas import FormalObligationSpec


def test_structured_obligation_with_lean_declaration():
    """Test that lean_declaration is used directly."""
    spec = FormalObligationSpec(
        source_text="Test",
        lean_declaration="theorem test : True := trivial",
    )
    result = AristotleSdkProofAdapter._obligation_to_lean(spec)
    assert result["status"] == "ok"
    assert "theorem test : True := trivial" in result["lean_code"]


def test_structured_obligation_with_statement():
    """Test that statement generates real theorem."""
    spec = FormalObligationSpec(
        source_text="Test addition",
        statement="∀ n : ℕ, n + 0 = n",
        theorem_name="add_zero",
        goal_kind="theorem",
    )
    result = AristotleSdkProofAdapter._obligation_to_lean(spec)
    assert result["status"] == "ok"
    assert "theorem add_zero" in result["lean_code"]
    assert "∀ n : ℕ, n + 0 = n" in result["lean_code"]
    assert "sorry" in result["lean_code"]
    assert "True := by" not in result["lean_code"]


def test_structured_obligation_with_imports_and_variables():
    """Test that imports and variables are included."""
    spec = FormalObligationSpec(
        source_text="Test",
        statement="n + m = m + n",
        theorem_name="add_comm_test",
        imports=["Mathlib.Data.Nat.Basic"],
        variables=["(n m : ℕ)"],
        goal_kind="lemma",
    )
    result = AristotleSdkProofAdapter._obligation_to_lean(spec)
    assert result["status"] == "ok"
    assert "import Mathlib.Data.Nat.Basic" in result["lean_code"]
    assert "variable (n m : ℕ)" in result["lean_code"]
    assert "lemma add_comm_test" in result["lean_code"]


def test_structured_obligation_without_statement_fails_honestly():
    """Test that obligations without statements fail with formalization_failed."""
    spec = FormalObligationSpec(
        source_text="Prove that the Collatz conjecture is true",
        goal_kind="theorem",
    )
    result = AristotleSdkProofAdapter._obligation_to_lean(spec)
    assert result["status"] == "formalization_failed"
    assert "lacks formal statement" in result["notes"]
    assert "formalization_gap" in str(result.get("artifacts", []))


def test_string_obligation_with_lean_code_accepted():
    """Test that string obligations that look like Lean are accepted."""
    obligation = "theorem test : True := by trivial"
    result = AristotleSdkProofAdapter._obligation_to_lean(obligation)
    assert result["status"] == "ok"
    assert "theorem test" in result["lean_code"]


def test_string_obligation_natural_language_fails_honestly():
    """Test that natural language string obligations fail honestly."""
    obligation = "Prove that all even numbers are divisible by 2"
    result = AristotleSdkProofAdapter._obligation_to_lean(obligation)
    assert result["status"] == "formalization_failed"
    assert "Cannot formalize natural language" in result["notes"]
    assert "unstructured_natural_language" in str(result.get("artifacts", []))


def test_sanitize_theorem_name():
    """Test theorem name sanitization."""
    assert _sanitize_theorem_name("test theorem") == "test_theorem"
    assert _sanitize_theorem_name("123test") == "theorem_123test"
    assert _sanitize_theorem_name("test-with-dashes") == "test_with_dashes"
    assert _sanitize_theorem_name("") == "obligation"
    assert _sanitize_theorem_name("valid_name") == "valid_name"


def test_structured_obligation_with_assumptions():
    """Test that assumptions are included as comments."""
    spec = FormalObligationSpec(
        source_text="Test",
        statement="n > 0",
        theorem_name="positive_test",
        assumptions=["n is a natural number", "n is not zero"],
        goal_kind="lemma",
    )
    result = AristotleSdkProofAdapter._obligation_to_lean(spec)
    assert result["status"] == "ok"
    assert "-- Assumptions:" in result["lean_code"]
    assert "-- n is a natural number" in result["lean_code"]


def test_structured_obligation_with_tactic_hints():
    """Test that tactic hints are included as comments."""
    spec = FormalObligationSpec(
        source_text="Test",
        statement="True",
        theorem_name="trivial_test",
        tactic_hints=["use trivial", "try rfl"],
        goal_kind="theorem",
    )
    result = AristotleSdkProofAdapter._obligation_to_lean(spec)
    assert result["status"] == "ok"
    assert "-- Hint: use trivial" in result["lean_code"]
    assert "-- Hint: try rfl" in result["lean_code"]


def test_backward_compatibility_string_obligations():
    """Test that old string obligations are coerced properly."""
    from app.schemas import ManagerDecision, CandidateAnswer, UpdateRules, SelfImprovementNote
    
    decision = ManagerDecision(
        candidate_answer=CandidateAnswer(stance="undecided", summary="test", confidence=0.5),
        alternatives=[],
        target_frontier_node="F-1",
        world_family="direct",
        bounded_claim="test",
        formal_obligations=["Prove something", "theorem test : True := trivial"],
        expected_information_gain="test",
        why_this_next="test",
        update_rules=UpdateRules(
            if_proved="a", if_refuted="b", if_blocked="c", if_inconclusive="d"
        ),
        self_improvement_note=SelfImprovementNote(proposal="p", reason="r"),
    )
    
    normalized = decision.get_normalized_obligations()
    assert len(normalized) == 2
    assert all(isinstance(ob, FormalObligationSpec) for ob in normalized)
    assert normalized[0].source_text == "Prove something"
    assert normalized[1].source_text == "theorem test : True := trivial"
