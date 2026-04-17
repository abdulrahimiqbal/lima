from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_collatz_scc_kernel_candidate_inventory import (
    child_states,
    is_resolved,
    local_profile,
)


STATE_MODULI = [1024, 2048, 4096, 8192, 16384, 32768]


def unresolved_states() -> list[tuple[int, int]]:
    states: list[tuple[int, int]] = []
    for modulus in STATE_MODULI:
        for residue in range(1, modulus, 2):
            if not is_resolved(modulus, residue):
                states.append((modulus, residue))
    return states


def build_payload() -> dict[str, object]:
    states = unresolved_states()
    profiles = sorted({local_profile(modulus, residue) for modulus, residue in states})
    profile_ids = {profile: f"Q{i + 1}" for i, profile in enumerate(profiles)}

    modulus_state_sets: dict[int, list[str]] = {}
    for modulus in STATE_MODULI:
        modulus_state_sets[modulus] = sorted(
            {
                profile_ids[local_profile(state_modulus, residue)]
                for state_modulus, residue in states
                if state_modulus == modulus
            }
        )

    transition_inventory: list[dict[str, object]] = []
    for modulus, residue in states:
        if modulus == max(STATE_MODULI):
            continue
        source_id = profile_ids[local_profile(modulus, residue)]
        children: list[str] = []
        for child_modulus, child_residue in child_states(modulus, residue):
            if not is_resolved(child_modulus, child_residue):
                children.append(profile_ids[local_profile(child_modulus, child_residue)])
        transition_inventory.append(
            {
                "source_modulus": modulus,
                "source_state_id": source_id,
                "children": sorted(children),
            }
        )

    profile_inventory = [
        {
            "state_id": profile_ids[profile],
            "profile": [list(pair) for pair in profile],
            "modulus_histogram": dict(
                Counter(
                    modulus
                    for modulus, residue in states
                    if local_profile(modulus, residue) == profile
                )
            ),
        }
        for profile in profiles
    ]

    return {
        "verdict": "scc_kernel_deep_extension_audit",
        "state_moduli": STATE_MODULI,
        "state_count": len(profiles),
        "modulus_state_sets": modulus_state_sets,
        "profile_inventory": profile_inventory,
        "transition_sample_count": len(transition_inventory),
        "interpretation": (
            "The 9-state local-profile kernel candidate stays coherent through modulus 16384, "
            "but one deeper dyadic extension refines it to 10 states by modulus 32768. So the "
            "current quotient has genuine periodic compression power, but it is not yet the final "
            "proof object. Any proof-closing kernel theorem will likely need either a deeper "
            "profile window or an explicitly phase-aware state definition."
        ),
    }


def main() -> int:
    print(json.dumps(build_payload(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
