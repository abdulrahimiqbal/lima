#!/usr/bin/env python3
"""
Script to create a new Collatz Conjecture campaign with detailed research brief.
"""

import os
import sys
import requests
import json


def create_campaign(base_url: str, api_key: str | None = None) -> dict:
    """Create a new Collatz campaign."""
    
    problem_statement = """Let T(n) be the Collatz map on positive integers:
- if n is even, T(n) = n / 2
- if n is odd,  T(n) = 3n + 1

Conjecture:
For every positive integer n, repeated iteration of T eventually reaches 1.

Research brief:
- Treat this as a top-down theorem-search problem, not a computation-first problem.
- I want a world invented, not just local lemmas.
- Do not assume the right ontology is residue-based, probabilistic, or finite-check driven unless earned.
- Look for hidden representations, accelerated dynamics, quotient descriptions, funnel structures, transfer principles, canonical reductions, minimal-counterexample worlds, balancing laws, or order structures.
- Micro-worlds matter: the winning move may be a slight shift of theorem, map, parameterization, or invariant, not a grand new framework.
- Avoid mistaking large finite verification for closure unless you also produce a valid finite reduction certificate.
- Use computation only to test or support a proposed reduction frontier, not as a substitute for a bridge to the full theorem.
- Prefer universes that compress the infinite statement into a small number of critical closure/bridge obligations.
- Avoid narrative speculation that does not reduce proof debt.

What I want:
1. A current candidate answer with stance and confidence.
2. A primary world program that could make Collatz tractable.
3. One or two alternative worlds.
4. A bridge back to the original conjecture.
5. A finite reduction certificate, even if speculative.
6. An explicit proof-debt ledger with roles:
   - closure
   - bridge
   - support
   - boundary
   - falsifier
7. The single next critical obligation to attack.
8. A bounded claim derived from that obligation.
9. A small set of formal obligations for Aristotle.
10. Clear update rules for:
    - if proved
    - if refuted
    - if blocked
    - if inconclusive

Hard constraints:
- Do not declare Collatz solved unless the active world has a valid bridge to the original conjecture and all critical proof debt for that bridge is discharged.
- Do not treat "verified for many n" as proof unless accompanied by a proved reduction from all n to those checked cases.
- Do not default to broad universal obligations like "prove Collatz for all integers" as the next move.
- Prefer the smallest high-value obligation implied by the chosen world.
- If the world fails, classify the failure structurally:
  - bad_world
  - bad_bridge
  - incomplete_closure
  - missing_support_lemma
  - formalization_failure
  - verifier_failure

Desired style:
- Be bold but disciplined.
- Think like a researcher inventing a world in which Collatz becomes easy, then compiling that world into checkable structure.
- Optimize for reduction of proof debt, not elegance alone.
- Start with the strongest plausible world, but keep one serious backup world alive.

Deliver the result as a world-first theorem campaign."""

    operator_notes = [
        "World-oriented approach: invent a universe where Collatz becomes tractable",
        "Focus on proof debt reduction, not just local lemmas",
        "Require explicit bridge to original conjecture before declaring solved",
        "Classify failures structurally to guide world refinement",
        "Prefer micro-worlds and small theorem perturbations over grand frameworks",
    ]
    
    payload = {
        "title": "Collatz Conjecture (World-First Campaign)",
        "problem_statement": problem_statement,
        "operator_notes": operator_notes,
        "auto_run": True,
    }
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    
    response = requests.post(
        f"{base_url}/api/campaigns",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main():
    base_url = os.getenv("LIMA_SERVICE_URL")
    if not base_url:
        print("Error: LIMA_SERVICE_URL environment variable not set")
        print("Usage: LIMA_SERVICE_URL=<url> python create_collatz_campaign.py")
        sys.exit(1)
    
    api_key = os.getenv("OPERATOR_API_KEY")
    
    try:
        print("🚀 Creating new Collatz Conjecture campaign...")
        print(f"   Service: {base_url}")
        
        campaign = create_campaign(base_url, api_key)
        
        print(f"\n✅ Campaign created successfully!")
        print(f"   ID: {campaign['id']}")
        print(f"   Title: {campaign['title']}")
        print(f"   Status: {campaign['status']}")
        print(f"   Auto-run: {campaign['auto_run']}")
        print(f"   Frontier nodes: {len(campaign.get('frontier', []))}")
        
        print(f"\n🔗 View campaign at:")
        print(f"   {base_url}/?campaign={campaign['id']}")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if e.response is not None:
            print(f"   Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
