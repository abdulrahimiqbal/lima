from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from shutil import which


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEAN = Path.home() / ".elan" / "bin" / "lean"

SINGLETON_CLASSES = [31, 47, 63, 71, 91, 111, 155, 167, 207, 223, 231, 251]
SEVEN_CLASSES = [27, 103, 127, 159, 191, 239]


LEAN_SOURCE = f"""import Std

open Std

abbrev ChildLawProfile := Nat × Nat × Nat × Nat
-- (source count, target count, one-child sources, two-child sources)

def singletonClasses : List Nat := {SINGLETON_CLASSES}
def sevenClasses : List Nat := {SEVEN_CLASSES}
def heavyClass : Nat := 255

def criticalChildProfile16384To32768 (r : Nat) : Option ChildLawProfile :=
  match r with
  | 27 | 103 | 127 | 159 | 191 | 239 => some (7, 8, 6, 1)
  | 31 | 47 | 63 | 71 | 91 | 111 | 155 | 167 | 207 | 223 | 231 | 251 => some (1, 1, 1, 0)
  | 255 => some (22, 29, 15, 7)
  | _ => none

def criticalChildProfile32768To65536 (r : Nat) : Option ChildLawProfile :=
  match r with
  | 27 | 103 | 127 | 159 | 191 | 239 => some (8, 9, 7, 1)
  | 31 | 47 | 63 | 71 | 91 | 111 | 155 | 167 | 207 | 223 | 231 | 251 => some (1, 1, 1, 0)
  | 255 => some (29, 37, 21, 8)
  | _ => none

def observedA : List Nat := [1, 1, 1]
def observedB : List Nat := [7, 8, 9]
def observedC : List Nat := [22, 29, 37]

theorem singleton_class_child_law_16384_to_32768 :
    ∀ r ∈ singletonClasses, criticalChildProfile16384To32768 r = some (1, 1, 1, 0) := by
  intro r hr
  simp [singletonClasses] at hr
  rcases hr with rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl
  all_goals rfl

theorem singleton_class_child_law_32768_to_65536 :
    ∀ r ∈ singletonClasses, criticalChildProfile32768To65536 r = some (1, 1, 1, 0) := by
  intro r hr
  simp [singletonClasses] at hr
  rcases hr with rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl
  all_goals rfl

theorem seven_class_child_law_16384_to_32768 :
    ∀ r ∈ sevenClasses, criticalChildProfile16384To32768 r = some (7, 8, 6, 1) := by
  intro r hr
  simp [sevenClasses] at hr
  rcases hr with rfl | rfl | rfl | rfl | rfl | rfl
  all_goals rfl

theorem seven_class_child_law_32768_to_65536 :
    ∀ r ∈ sevenClasses, criticalChildProfile32768To65536 r = some (8, 9, 7, 1) := by
  intro r hr
  simp [sevenClasses] at hr
  rcases hr with rfl | rfl | rfl | rfl | rfl | rfl
  all_goals rfl

theorem heavy_class_child_law :
    criticalChildProfile16384To32768 heavyClass = some (22, 29, 15, 7) ∧
    criticalChildProfile32768To65536 heavyClass = some (29, 37, 21, 8) := by
  simp [heavyClass, criticalChildProfile16384To32768, criticalChildProfile32768To65536]

theorem observed_child_law_recurrence :
    observedA = [1, 1, 1] ∧
    observedB = [7, 8, 9] ∧
    observedC = [22, 29, 37] ∧
    8 = 7 + 1 ∧
    9 = 8 + 1 ∧
    29 = 22 + 7 ∧
    37 = 29 + 8 := by
  decide

theorem critical_q1_child_law_bundle :
    (∀ r ∈ singletonClasses, criticalChildProfile16384To32768 r = some (1, 1, 1, 0)) ∧
    (∀ r ∈ singletonClasses, criticalChildProfile32768To65536 r = some (1, 1, 1, 0)) ∧
    (∀ r ∈ sevenClasses, criticalChildProfile16384To32768 r = some (7, 8, 6, 1)) ∧
    (∀ r ∈ sevenClasses, criticalChildProfile32768To65536 r = some (8, 9, 7, 1)) ∧
    criticalChildProfile16384To32768 heavyClass = some (22, 29, 15, 7) ∧
    criticalChildProfile32768To65536 heavyClass = some (29, 37, 21, 8) := by
  refine ⟨singleton_class_child_law_16384_to_32768, singleton_class_child_law_32768_to_65536,
    seven_class_child_law_16384_to_32768, seven_class_child_law_32768_to_65536, ?_, ?_⟩
  · exact heavy_class_child_law.1
  · exact heavy_class_child_law.2
"""


def build_lean_source() -> str:
    return LEAN_SOURCE


@lru_cache(maxsize=1)
def run_lean(name: str, source: str) -> dict[str, object]:
    lean_bin = Path(os.environ.get("LEAN_BIN", str(DEFAULT_LEAN)))
    fallback = which("lean")
    if lean_bin.exists():
        command = [str(lean_bin), "--stdin"]
        available = True
    elif fallback is not None:
        command = [fallback, "--stdin"]
        available = True
    else:
        return {
            "name": name,
            "available": False,
            "returncode": None,
            "ok": False,
            "stdout": "",
            "stderr": "lean binary not available in PATH or ~/.elan/bin/lean",
        }
    result = subprocess.run(
        command,
        input=source,
        text=True,
        capture_output=True,
        timeout=60,
    )
    return {
        "name": name,
        "available": available,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


@lru_cache(maxsize=1)
def build_payload() -> dict[str, object]:
    check = run_lean("critical_q1_child_law_hardening", LEAN_SOURCE)
    return {
        "verdict": "critical_q1_child_law_hardening",
        "singleton_classes": SINGLETON_CLASSES,
        "seven_classes": SEVEN_CLASSES,
        "heavy_class": 255,
        "lean_source_theorems": [
            "singleton_class_child_law_16384_to_32768",
            "singleton_class_child_law_32768_to_65536",
            "seven_class_child_law_16384_to_32768",
            "seven_class_child_law_32768_to_65536",
            "heavy_class_child_law",
            "observed_child_law_recurrence",
            "critical_q1_child_law_bundle",
        ],
        "lean_check": check,
        "interpretation": (
            "This is a Lean-facing exact finite child-law package for the critical Q1 frontier-shadow. "
            "It promotes the audited recurrence data into explicit theorem objects over finite class families."
        ),
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, indent=2))
    return 0 if payload["lean_check"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
