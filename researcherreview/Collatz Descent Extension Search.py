from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Family:
    coeff: int
    const: int


def direct_deterministic_descent(root: Family, max_steps: int = 400):
    A0, B0 = root.coeff, root.const
    A, B = A0, B0
    path: list[tuple[str, int, int]] = []
    for _ in range(max_steps):
        if A % 2 != 0:
            return None, Family(A, B), path
        if B % 2 == 0:
            A, B = A // 2, B // 2
            path.append(("even", A, B))
        else:
            A, B = 3 * A, 3 * B + 1
            path.append(("odd", A, B))
        if A < A0 and B < B0:
            return len(path), Family(A, B), path
    return None, Family(A, B), path


if __name__ == "__main__":
    selected = [
        Family(1024, 287),
        Family(1024, 815),
        Family(1024, 575),
        Family(1024, 583),
        Family(1024, 347),
        Family(1024, 367),
        Family(4096, 2587),
        Family(4096, 615),
        Family(4096, 383),
    ]
    for fam in selected:
        steps, leaf, path = direct_deterministic_descent(fam)
        print(f"{fam.coeff}*t+{fam.const}: steps={steps}, leaf={leaf}, path={path}")

    odd_residues = list(range(3, 4096, 2))
    direct = [b for b in odd_residues if direct_deterministic_descent(Family(4096, b))[0] is not None]
    unresolved = [b for b in odd_residues if b not in direct]
    print()
    print(f"Directly descending odd residues modulo 4096: {len(direct)}")
    print(f"Unresolved odd residues modulo 4096: {len(unresolved)}")
    print(f"First 50 unresolved: {unresolved[:50]}")
