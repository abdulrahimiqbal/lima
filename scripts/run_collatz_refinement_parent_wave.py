from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.schemas import (
    CampaignCreate,
    FormalObligationSpec,
    FormalProbe,
    FormalProbeBakeRequest,
    FormalProbeDigestRequest,
)
from app.service import CampaignService
from scripts.run_collatz_affine_rewrite_compass import Family


WORLD_ID = "W-0273193499"
DEFAULT_MEMORY_PATH = str(ROOT / "data" / "collatz_refinement_parent_wave.db")
POLL_SECONDS = 20
PARENT_FRONTIER = [27, 31, 47, 63, 71, 91, 103, 111, 127]
PARENT_MODULUS = 256
CHILD_MODULUS = 4096
CHILD_SCALE = CHILD_MODULUS // PARENT_MODULUS

LEAN_PREAMBLE = r"""import Std

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

def iterateNat (f : Nat -> Nat) : Nat -> Nat -> Nat
  | 0, n => n
  | k + 1, n => iterateNat f k (f n)

def PositiveDescentAt (n k : Nat) : Prop :=
  0 < iterateNat collatzStep k n ∧ iterateNat collatzStep k n < n

def FamilyDescends (a b : Nat) : Prop :=
  ∀ t, a * t + b > 1 -> ∃ k, PositiveDescentAt (a * t + b) k

theorem parent_descends_of_bit_children
    (a b : Nat)
    (hEven : FamilyDescends (2 * a) b)
    (hOdd : FamilyDescends (2 * a) (a + b)) :
    FamilyDescends a b := by
  intro t ht
  have hcases := Nat.mod_two_eq_zero_or_one t
  cases hcases with
  | inl hmod =>
      let q := t / 2
      have hrepr : t = 2 * q := by
        dsimp [q]
        have hdecomp : t % 2 + 2 * (t / 2) = t := by
          simpa [Nat.add_comm] using (Nat.mod_add_div t 2)
        omega
      have hEq : a * t + b = (2 * a) * q + b := by
        rw [hrepr]
        simp [Nat.mul_left_comm, Nat.mul_comm]
      have hgt : (2 * a) * q + b > 1 := by
        simpa [hEq] using ht
      obtain ⟨k, hk⟩ := hEven q hgt
      refine ⟨k, ?_⟩
      simpa [hEq] using hk
  | inr hmod =>
      let q := t / 2
      have hrepr : t = 2 * q + 1 := by
        dsimp [q]
        have hdecomp : t % 2 + 2 * (t / 2) = t := by
          simpa [Nat.add_comm] using (Nat.mod_add_div t 2)
        omega
      have hEq : a * t + b = (2 * a) * q + (a + b) := by
        rw [hrepr]
        rw [Nat.mul_add, Nat.mul_one]
        simp [Nat.mul_left_comm, Nat.mul_comm, Nat.add_assoc, Nat.add_left_comm, Nat.add_comm]
      have hgt : (2 * a) * q + (a + b) > 1 := by
        simpa [hEq] using ht
      obtain ⟨k, hk⟩ := hOdd q hgt
      refine ⟨k, ?_⟩
      simpa [hEq] using hk

theorem parent_descends_of_refined_children
    (a b m : Nat)
    (hChildren : ∀ r, r < 2 ^ m -> FamilyDescends (a * 2 ^ m) (a * r + b)) :
    FamilyDescends a b := by
  induction m generalizing a b with
  | zero =>
      intro t ht
      have hFam := hChildren 0 (by omega)
      have ht0 : a * 2 ^ 0 * t + (a * 0 + b) > 1 := by
        simpa using ht
      obtain ⟨k, hk⟩ := hFam t ht0
      refine ⟨k, ?_⟩
      simpa using hk
  | succ m ih =>
      apply parent_descends_of_bit_children a b
      · have hEvenChildren :
            ∀ r, r < 2 ^ m -> FamilyDescends ((2 * a) * 2 ^ m) ((2 * a) * r + b) := by
          intro r hr
          have hlt : 2 * r < 2 ^ Nat.succ m := by
            omega
          have hFam := hChildren (2 * r) hlt
          simpa [Nat.pow_succ, Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm] using hFam
        exact ih (2 * a) b hEvenChildren
      · have hOddChildren :
            ∀ r, r < 2 ^ m -> FamilyDescends ((2 * a) * 2 ^ m) ((2 * a) * r + (a + b)) := by
          intro r hr
          have hlt : 2 * r + 1 < 2 ^ Nat.succ m := by
            omega
          have hFam := hChildren (2 * r + 1) hlt
          simpa [Nat.pow_succ, Nat.mul_add, Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm,
            Nat.add_assoc, Nat.add_left_comm, Nat.add_comm] using hFam
        exact ih (2 * a) (a + b) hOddChildren
"""


@dataclass(frozen=True, slots=True)
class DirectCertificate:
    residue: int
    steps: int
    leaf: Family
    path: list[tuple[str, Family, Family]]


def emit(label: str, payload: object) -> None:
    print(json.dumps({label: payload}, indent=2, default=str), flush=True)


def value(item: object, key: str) -> object:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key)


def build_service() -> CampaignService:
    api_key = os.environ.get("ARISTOTLE_API_KEY")
    if not api_key:
        raise SystemExit("ARISTOTLE_API_KEY is required for submit/poll mode")
    memory_path = Path(os.environ.get("COLLATZ_PARENT_WAVE_MEMORY_PATH", DEFAULT_MEMORY_PATH))
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    return CampaignService(
        Settings(
            executor_backend="aristotle",
            aristotle_api_key=api_key,
            aristotle_timeout_seconds=180,
            memory_db_path=str(memory_path),
            worker_poll_seconds=5,
        )
    )


def local_service() -> CampaignService:
    return CampaignService(
        Settings(memory_db_path="/tmp/lima_collatz_refinement_parent_wave_local.db")
    )


def affine_expr(family: Family) -> str:
    return f"{family.coeff}*t + {family.const}"


def theorem_token(modulus: int, residue: int) -> str:
    return f"fam_{modulus}_{residue}"


def next_family(family: Family) -> tuple[str, Family]:
    if family.const % 2 == 0:
        if family.coeff % 2 != 0:
            raise ValueError(f"even step reached odd coefficient in {family}")
        return "even", Family(family.coeff // 2, family.const // 2)
    return "odd", Family(3 * family.coeff, 3 * family.const + 1)


def direct_deterministic_descent(root: Family, max_steps: int = 400) -> DirectCertificate | None:
    start = root
    current = root
    path: list[tuple[str, Family, Family]] = []
    for step_index in range(max_steps):
        if current.coeff % 2 != 0:
            return None
        step_kind, nxt = next_family(current)
        path.append((step_kind, current, nxt))
        current = nxt
        if current.coeff < start.coeff and current.const < start.const:
            return DirectCertificate(
                residue=root.const,
                steps=step_index + 1,
                leaf=current,
                path=path,
            )
    return None


def child_residues(parent_residue: int) -> list[int]:
    return [parent_residue + PARENT_MODULUS * offset for offset in range(CHILD_SCALE)]


def direct_children(parent_residue: int) -> list[DirectCertificate]:
    found: list[DirectCertificate] = []
    for residue in child_residues(parent_residue):
        certificate = direct_deterministic_descent(Family(CHILD_MODULUS, residue))
        if certificate is not None:
            found.append(certificate)
    return found


def selected_parents() -> list[int]:
    raw = os.environ.get("COLLATZ_PARENT_WAVE_PARENTS", "").strip()
    if not raw:
        return PARENT_FRONTIER
    requested = [int(item.strip()) for item in raw.split(",") if item.strip()]
    invalid = [item for item in requested if item not in PARENT_FRONTIER]
    if invalid:
        raise SystemExit(
            f"Unsupported parent residues {invalid}; choose from {PARENT_FRONTIER}"
        )
    return requested


def render_direct_certificate(certificate: DirectCertificate) -> str:
    token = theorem_token(CHILD_MODULUS, certificate.residue)
    lines: list[str] = []
    for step_index, (step_kind, current, nxt) in enumerate(certificate.path, start=1):
        theorem_name = f"{token}_step_{step_index}_eq"
        lines.extend(
            [
                f"-- Deterministic Collatz evolution for {affine_expr(Family(CHILD_MODULUS, certificate.residue))}.",
                f"theorem {theorem_name} (t : Nat) :",
                f"    collatzStep ({affine_expr(current)}) = {affine_expr(nxt)} := by",
                "  unfold collatzStep",
            ]
        )
        if step_kind == "odd":
            lines.extend(
                [
                    f"  have hodd : ({affine_expr(current)}) % 2 ≠ 0 := by omega",
                    "  simp [hodd]",
                    "  omega",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"  have heven : ({affine_expr(current)}) % 2 = 0 := by omega",
                    "  simp [heven]",
                    "  omega",
                    "",
                ]
            )

    lines.extend(
        [
            f"theorem {token}_iterate_eq (t : Nat) :",
            f"    iterateNat collatzStep {certificate.steps} ({affine_expr(Family(CHILD_MODULUS, certificate.residue))}) = {affine_expr(certificate.leaf)} := by",
            "  simp [iterateNat,",
        ]
    )
    for step_index in range(1, certificate.steps + 1):
        suffix = "," if step_index < certificate.steps else "]"
        lines.append(f"    {token}_step_{step_index}_eq{suffix}")
    lines.extend(
        [
            "",
            f"theorem {token}_descends : FamilyDescends {CHILD_MODULUS} {certificate.residue} := by",
            "  intro t ht",
            f"  refine ⟨{certificate.steps}, ?_, ?_⟩",
            f"  · rw [{token}_iterate_eq]",
            "    omega",
            f"  · rw [{token}_iterate_eq]",
            "    omega",
            "",
        ]
    )
    return "\n".join(lines)


def render_unresolved_child(parent_residue: int, child_residue: int) -> str:
    token = theorem_token(CHILD_MODULUS, child_residue)
    return "\n".join(
        [
            f"-- Remaining child of 256*t+{parent_residue}; this is the genuine open branch for this probe.",
            f"theorem {token}_descends : FamilyDescends {CHILD_MODULUS} {child_residue} := by",
            "  sorry",
            "",
        ]
    )


def render_parent_theorem(parent_residue: int) -> str:
    parent_token = theorem_token(PARENT_MODULUS, parent_residue)
    disj = " ∨ ".join(f"r = {offset}" for offset in range(CHILD_SCALE))
    lines = [
        f"theorem {parent_token}_descends : FamilyDescends {PARENT_MODULUS} {parent_residue} := by",
        f"  apply parent_descends_of_refined_children {PARENT_MODULUS} {parent_residue} 4",
        "  intro r hr",
        f"  have hcases : {disj} := by",
        "    omega",
        f"  rcases hcases with {' | '.join(f'h{offset}' for offset in range(CHILD_SCALE))}",
    ]
    for offset, child_residue in enumerate(child_residues(parent_residue)):
        child_token = theorem_token(CHILD_MODULUS, child_residue)
        lines.append(f"  · simpa [h{offset}] using {child_token}_descends")
    lines.append("")
    return "\n".join(lines)


def render_probe_source(parent_residue: int) -> tuple[str, dict[str, object]]:
    direct = direct_children(parent_residue)
    direct_by_residue = {item.residue: item for item in direct}
    unresolved = [residue for residue in child_residues(parent_residue) if residue not in direct_by_residue]

    sections = [LEAN_PREAMBLE, ""]
    for residue in child_residues(parent_residue):
        if residue in direct_by_residue:
            sections.append(render_direct_certificate(direct_by_residue[residue]))
        else:
            sections.append(render_unresolved_child(parent_residue, residue))
    sections.append(render_parent_theorem(parent_residue))
    source = "\n".join(sections) + "\n"

    summary = {
        "parent_modulus": PARENT_MODULUS,
        "parent_residue": parent_residue,
        "child_modulus": CHILD_MODULUS,
        "direct_child_count": len(direct),
        "unresolved_child_count": len(unresolved),
        "direct_children": [
            {
                "residue": item.residue,
                "steps": item.steps,
                "leaf_coeff": item.leaf.coeff,
                "leaf_const": item.leaf.const,
            }
            for item in direct
        ],
        "unresolved_children": unresolved,
    }
    return source, summary


def build_probe(parent_residue: int) -> tuple[FormalProbe, dict[str, object]]:
    lean_source, summary = render_probe_source(parent_residue)
    probe_text = (
        f"Refinement-parent closure for {PARENT_MODULUS}*t+{parent_residue} from its "
        f"{CHILD_SCALE} mod-{CHILD_MODULUS} children."
    )
    probe = FormalProbe(
        world_id=WORLD_ID,
        probe_type="closure_probe",
        source_text=probe_text,
        formal_obligation=FormalObligationSpec(
            source_text=probe_text,
            channel_hint="proof",
            goal_kind="theorem",
            theorem_name=f"{theorem_token(PARENT_MODULUS, parent_residue)}_descends",
            lean_declaration=lean_source,
            tactic_hints=[
                "Use parent_descends_of_refined_children to reduce the parent to its 16 mod-4096 children.",
                "Reuse the fully checked direct child descent theorems already in the file.",
                "For unresolved mod-4096 children, recurse by dyadic refinement rather than introducing axioms.",
                "The current known obstruction is a self-feeding refinement class, so look for a finite closure tree, not a scalar rank on n.",
            ],
            requires_proof=True,
            metadata={
                "world_id": WORLD_ID,
                "probe_type": "closure_probe",
                "probe_family": "collatz_refinement_parent_wave",
                **summary,
            },
        ),
        status="compiled",
        notes=(
            "Compiled as a targeted dyadic parent-closure probe. "
            "This is not a Collatz proof unless every remaining child branch is discharged."
        ),
    )
    return probe, summary


def compile_probes(parents: list[int] | None = None) -> list[tuple[FormalProbe, dict[str, object]]]:
    parents = parents or selected_parents()
    return [build_probe(parent) for parent in parents]


def run_lean_check(name: str, source: str) -> dict[str, object]:
    result = subprocess.run(
        ["lean", "--stdin"],
        input=source,
        text=True,
        capture_output=True,
        timeout=90,
    )
    return {
        "name": name,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def create_campaign(service: CampaignService):
    return service.create_campaign(
        CampaignCreate(
            title="Collatz refinement parent closure wave",
            problem_statement=(
                "Attack the remaining Collatz refinement frontier by reducing each unresolved "
                "mod-256 parent family to its mod-4096 child families and asking Aristotle to "
                "fill the remaining child closures in Lean."
            ),
            operator_notes=[
                "This wave targets the actual remaining theorem bottleneck, not broad world invention.",
                "Each probe includes the general dyadic partition theorem plus direct child proofs already validated locally.",
                "A proved parent here would be theorem-level progress toward universal eventual descent, not yet full Collatz on its own.",
                f"World id carried over from production campaign: {WORLD_ID}.",
            ],
            auto_run=False,
        )
    )


def upsert_probes(service: CampaignService, campaign_id: str) -> list[dict[str, object]]:
    compiled = []
    parents = selected_parents()
    for probe, summary in compile_probes(parents):
        service.memory.upsert_research_node(
            campaign_id=campaign_id,
            node_id=probe.id,
            node_type="FormalProbe",
            title=f"{probe.probe_type}:{probe.world_id}",
            summary=probe.source_text,
            status=probe.status,
            payload=probe.model_dump(mode="json"),
        )
        compiled.append({"probe_id": probe.id, **summary})
    return compiled


def run_local() -> None:
    checks = []
    parents = selected_parents()
    for probe, summary in compile_probes(parents):
        check = run_lean_check(
            f"parent_{summary['parent_residue']}",
            probe.formal_obligation.lean_declaration or "",
        )
        check.update(summary)
        checks.append(check)
    emit(
        "local",
        {
            "world_id": WORLD_ID,
            "selected_parents": parents,
            "compiled_probe_count": len(checks),
            "all_sources_compile": all(item["ok"] for item in checks),
            "checks": checks,
        },
    )


def submit(service: CampaignService, campaign_id: str | None) -> None:
    if campaign_id:
        try:
            campaign = service.get_campaign(campaign_id)
        except KeyError:
            campaign = create_campaign(service)
    else:
        campaign = create_campaign(service)
    campaign_id = campaign.id

    compiled = upsert_probes(service, campaign_id)
    emit(
        "compiled",
        {
            "campaign_id": campaign_id,
            "world_id": WORLD_ID,
            "selected_parents": selected_parents(),
            "compiled_probe_count": len(compiled),
            "probes": compiled,
        },
    )

    bake = service.bake_formal_probes(
        campaign_id,
        FormalProbeBakeRequest(
            world_id=WORLD_ID,
            max_probes=len(compiled),
            submit_all_at_once=True,
            retry_failed_submissions=False,
        ),
    )
    emit(
        "submitted",
        {
            "bake_run_id": bake.id,
            "status": bake.status,
            "submitted_probe_count": bake.submitted_probe_count,
            "pending_job_count": bake.pending_job_count,
            "probe_ids": bake.probe_ids,
            "project_ids": bake.project_ids,
        },
    )


def poll_to_empty(service: CampaignService, campaign_id: str, max_polls: int = 50) -> None:
    last_pending = None
    for poll_index in range(max_polls):
        campaign = service.step_campaign(campaign_id)
        pending = [
            {
                "project_id": job.project_id,
                "status": job.status,
                "poll_count": job.poll_count,
                "debt_id": job.debt_id,
                "obligation_text": job.obligation_text,
            }
            for job in campaign.pending_aristotle_jobs
        ]
        pending_count = len(pending)
        if pending_count != last_pending or poll_index % 5 == 0:
            emit(
                "poll",
                {
                    "poll_index": poll_index,
                    "pending_count": pending_count,
                    "pending_jobs": pending,
                    "last_execution_result": campaign.last_execution_result,
                },
            )
            last_pending = pending_count
        if pending_count == 0:
            break
        time.sleep(POLL_SECONDS)


def digest(service: CampaignService, campaign_id: str) -> None:
    result = service.digest_formal_probe_results(
        campaign_id,
        FormalProbeDigestRequest(
            world_id=WORLD_ID,
            max_artifacts=260,
            attach_unmapped_artifacts=True,
            redownload_missing_artifacts=True,
        ),
    )
    emit(
        "digest",
        {
            "digest_id": result.id,
            "artifact_count": result.artifact_count,
            "probe_count": result.probe_count,
            "proved_count": result.proved_count,
            "blocked_count": result.blocked_count,
            "inconclusive_count": result.inconclusive_count,
            "reconciled_pending_job_count": result.reconciled_pending_job_count,
            "diagnostics": [
                {
                    "probe_id": value(diagnostic, "probe_id"),
                    "source_text": value(diagnostic, "source_text"),
                    "verdict": value(diagnostic, "verdict"),
                    "failure_type": value(diagnostic, "failure_type"),
                    "suggested_repair": value(diagnostic, "suggested_repair"),
                    "artifact_path": value(diagnostic, "artifact_path"),
                }
                for diagnostic in result.diagnostics
                if "Refinement-parent closure" in str(value(diagnostic, "source_text"))
            ],
        },
    )


def main() -> None:
    mode = os.environ.get("COLLATZ_PARENT_WAVE_MODE", "local")
    if mode == "local":
        run_local()
        return

    service = build_service()
    campaign_id = os.environ.get("COLLATZ_PARENT_WAVE_CAMPAIGN_ID")
    if mode == "submit":
        submit(service, campaign_id)
        return
    if mode == "poll":
        if not campaign_id:
            raise SystemExit("COLLATZ_PARENT_WAVE_CAMPAIGN_ID is required for poll mode")
        poll_to_empty(service, campaign_id)
        digest(service, campaign_id)
        return
    raise SystemExit(f"Unsupported COLLATZ_PARENT_WAVE_MODE={mode!r}; use local, submit, or poll")


if __name__ == "__main__":
    main()
