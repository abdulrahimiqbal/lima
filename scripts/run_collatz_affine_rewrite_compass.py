from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Family:
    coeff: int
    const: int


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    cost: int

    def applies(self, family: Family) -> bool:
        a, b = family.coeff, family.const
        match self.name:
            case "even1":
                return a % 2 == 0 and b % 2 == 0 and b > 0
            case "odd2":
                return a % 2 == 0 and b % 2 == 1
            case "one_mod_four":
                return a % 4 == 0 and b % 4 == 1 and b > 1
            case "three_mod_sixteen":
                return a % 16 == 0 and b % 16 == 3
            case "eleven_mod_32":
                return a % 32 == 0 and b % 32 == 11
            case "twentythree_mod_32":
                return a % 32 == 0 and b % 32 == 23
            case "seven_mod_128":
                return a % 128 == 0 and b % 128 == 7
            case "fifteen_mod_128":
                return a % 128 == 0 and b % 128 == 15
            case "fiftynine_mod_128":
                return a % 128 == 0 and b % 128 == 59
            case _:
                raise ValueError(f"Unknown rule {self.name}")

    def apply(self, family: Family) -> Family:
        a, b = family.coeff, family.const
        match self.name:
            case "even1":
                return Family(a // 2, b // 2)
            case "odd2":
                return Family((3 * a) // 2, (3 * b + 1) // 2)
            case "one_mod_four":
                return Family((3 * a) // 4, (3 * (b - 1)) // 4 + 1)
            case "three_mod_sixteen":
                return Family((9 * a) // 16, (9 * (b - 3)) // 16 + 2)
            case "eleven_mod_32":
                return Family((27 * a) // 32, (27 * (b - 11)) // 32 + 10)
            case "twentythree_mod_32":
                return Family((27 * a) // 32, (27 * (b - 23)) // 32 + 20)
            case "seven_mod_128":
                return Family((81 * a) // 128, (81 * (b - 7)) // 128 + 5)
            case "fifteen_mod_128":
                return Family((81 * a) // 128, (81 * (b - 15)) // 128 + 10)
            case "fiftynine_mod_128":
                return Family((81 * a) // 128, (81 * (b - 59)) // 128 + 38)
            case _:
                raise ValueError(f"Unknown rule {self.name}")


RULES = [
    Rule("even1", 1),
    Rule("odd2", 2),
    Rule("one_mod_four", 3),
    Rule("three_mod_sixteen", 6),
    Rule("eleven_mod_32", 8),
    Rule("twentythree_mod_32", 8),
    Rule("seven_mod_128", 11),
    Rule("fifteen_mod_128", 11),
    Rule("fiftynine_mod_128", 11),
]


def search_descent_certificate(
    root: Family,
    *,
    max_total_cost: int = 40,
    max_rule_depth: int = 8,
) -> dict[str, object] | None:
    queue = deque([(root, 0, [])])
    seen = {(root, 0)}
    while queue:
        family, cost, path = queue.popleft()
        if path and family.coeff < root.coeff and family.const < root.const:
            return {
                "total_cost": cost,
                "leaf": {"coeff": family.coeff, "const": family.const},
                "path": path,
            }
        if cost >= max_total_cost or len(path) >= max_rule_depth:
            continue
        for rule in RULES:
            if not rule.applies(family):
                continue
            next_family = rule.apply(family)
            next_cost = cost + rule.cost
            state = (next_family, len(path) + 1)
            if next_cost > max_total_cost or state in seen:
                continue
            seen.add(state)
            queue.append(
                (
                    next_family,
                    next_cost,
                    path
                    + [
                        {
                            "rule": rule.name,
                            "cost": rule.cost,
                            "next": {
                                "coeff": next_family.coeff,
                                "const": next_family.const,
                            },
                        }
                    ],
                )
            )
    return None


def main() -> int:
    frontier_roots = [27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127]
    certificates: dict[str, object] = {}
    unresolved: list[int] = []
    for residue in frontier_roots:
        root = Family(256, residue)
        certificate = search_descent_certificate(root)
        if certificate is None:
            unresolved.append(residue)
        else:
            certificates[str(residue)] = certificate

    payload = {
        "verdict": "affine_rewrite_compass",
        "root_modulus": 256,
        "frontier_roots": frontier_roots,
        "resolved_roots": sorted(int(key) for key in certificates),
        "unresolved_roots": unresolved,
        "rule_inventory": [
            {
                "name": rule.name,
                "cost": rule.cost,
            }
            for rule in RULES
        ],
        "certificates": certificates,
        "interpretation": (
            "This is a compass, not a proof. It composes already Lean-proved family rewrite "
            "rules on affine families a*t+b and searches for a leaf family with strictly "
            "smaller coefficient and constant than the root."
        ),
        "next_signal": (
            "If a root remains unresolved under this rewrite search, the missing ingredient is "
            "not another isolated residue lemma but a new rewrite rule or a well-founded "
            "termination theorem for the affine rewrite system."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
