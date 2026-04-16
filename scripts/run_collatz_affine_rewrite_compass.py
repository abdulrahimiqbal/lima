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
    modulus: int | None = None
    residue: int | None = None
    coeff_numerator: int | None = None
    coeff_denominator: int | None = None
    leaf_const: int | None = None

    def applies(self, family: Family) -> bool:
        a, b = family.coeff, family.const
        match self.name:
            case "even1":
                return a % 2 == 0 and b % 2 == 0 and b > 0
            case "odd2":
                return a % 2 == 0 and b % 2 == 1
            case _:
                if self.modulus is None or self.residue is None:
                    raise ValueError(f"Unknown rule {self.name}")
                if self.name == "one_mod_four":
                    return a % self.modulus == 0 and b % self.modulus == self.residue and b > 1
                return a % self.modulus == 0 and b % self.modulus == self.residue

    def apply(self, family: Family) -> Family:
        a, b = family.coeff, family.const
        match self.name:
            case "even1":
                return Family(a // 2, b // 2)
            case "odd2":
                return Family((3 * a) // 2, (3 * b + 1) // 2)
            case _:
                if (
                    self.modulus is None
                    or self.residue is None
                    or self.coeff_numerator is None
                    or self.coeff_denominator is None
                    or self.leaf_const is None
                ):
                    raise ValueError(f"Unknown rule {self.name}")
                return Family(
                    (self.coeff_numerator * a) // self.coeff_denominator,
                    (self.coeff_numerator * (b - self.residue)) // self.coeff_denominator
                    + self.leaf_const,
                )


DIRECT_RULES = [
    Rule("one_mod_four", 3, 4, 1, 3, 4, 1),
    Rule("three_mod_sixteen", 6, 16, 3, 9, 16, 2),
    Rule("eleven_mod_32", 8, 32, 11, 27, 32, 10),
    Rule("twentythree_mod_32", 8, 32, 23, 27, 32, 20),
    Rule("seven_mod_128", 11, 128, 7, 81, 128, 5),
    Rule("fifteen_mod_128", 11, 128, 15, 81, 128, 10),
    Rule("fiftynine_mod_128", 11, 128, 59, 81, 128, 38),
    Rule("twoeightyseven_mod_1024", 16, 1024, 287, 729, 1024, 205),
    Rule("eightfifteen_mod_1024", 16, 1024, 815, 729, 1024, 581),
    Rule("fiveseventyfive_mod_1024", 16, 1024, 575, 729, 1024, 410),
    Rule("fiveeightythree_mod_1024", 16, 1024, 583, 729, 1024, 416),
    Rule("threefortyseven_mod_1024", 16, 1024, 347, 729, 1024, 248),
    Rule("threesixtyseven_mod_1024", 16, 1024, 367, 729, 1024, 262),
    Rule("twentyfiveeightyseven_mod_4096", 19, 4096, 2587, 2187, 4096, 1382),
    Rule("sixfifteen_mod_4096", 19, 4096, 615, 2187, 4096, 329),
    Rule("threeeightythree_mod_4096", 19, 4096, 383, 2187, 4096, 205),
]


RULES = [
    Rule("even1", 1),
    Rule("odd2", 2),
    *DIRECT_RULES,
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
                "modulus": rule.modulus,
                "residue": rule.residue,
                "coeff_numerator": rule.coeff_numerator,
                "coeff_denominator": rule.coeff_denominator,
                "leaf_const": rule.leaf_const,
            }
            for rule in RULES
        ],
        "certificates": certificates,
        "interpretation": (
            "This is a compass, not a proof. It composes already Lean-proved family rewrite "
            "rules on affine families a*t+b and searches for a leaf family with strictly "
            "smaller coefficient and constant than the root."
        ),
        "note_on_refinement": (
            "Adding the new 1024 and 4096 direct-descent rules does not change the current "
            "mod-256 root frontier, because those rules only fire after dyadic residue refinement. "
            "The next missing object is therefore not just a longer rewrite list, but a "
            "well-founded rewrite-plus-refinement theorem."
        ),
        "next_signal": (
            "If a root remains unresolved under this rewrite search, the missing ingredient is "
            "not another isolated residue lemma but a new rewrite rule, a residue-splitting "
            "operator, or a well-founded termination theorem for the affine rewrite system."
        ),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
