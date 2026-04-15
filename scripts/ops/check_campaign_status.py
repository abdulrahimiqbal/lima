#!/usr/bin/env python3
"""Check campaign status in a readable format."""

import sys
import requests
from datetime import datetime


def check_campaign(base_url: str, campaign_id: str):
    """Get campaign status."""
    response = requests.get(f"{base_url}/api/campaigns/{campaign_id}", timeout=30)
    response.raise_for_status()
    campaign = response.json()
    
    print(f"📊 Campaign Status: {campaign['id']}")
    print(f"   Title: {campaign['title']}")
    print(f"   Status: {campaign['status']}")
    print(f"   Auto-run: {campaign['auto_run']}")
    print(f"   Tick: {campaign['tick_count']}")
    print(f"   Manager: {campaign['manager_backend']}")
    print(f"   Executor: {campaign['executor_backend']}")
    
    # Pending job status
    pending = campaign.get('pending_aristotle_job')
    if pending:
        print(f"\n⏳ Aristotle Job In Progress:")
        print(f"   Project ID: {pending['project_id']}")
        print(f"   Status: {pending['status']}")
        print(f"   Poll count: {pending['poll_count']}")
        print(f"   Submitted: {pending['submitted_at']}")
        print(f"   Last polled: {pending['last_polled_at']}")
        print(f"   Target node: {pending['target_frontier_node']}")
        print(f"   World family: {pending['world_family']}")
        print(f"   Bounded claim: {pending['bounded_claim'][:100]}...")
    
    # Last decision
    decision = campaign.get('last_manager_decision')
    if decision:
        print(f"\n🎯 Last Decision:")
        print(f"   Target node: {decision['target_frontier_node']}")
        print(f"   World family: {decision['world_family']}")
        print(f"   Bounded claim: {decision['bounded_claim'][:100]}...")
        
        candidate = decision.get('candidate_answer')
        if candidate:
            print(f"   Candidate stance: {candidate['stance']}")
            print(f"   Confidence: {candidate['confidence']}")
    
    # Last result
    result = campaign.get('last_execution_result')
    if result:
        print(f"\n✅ Last Execution Result:")
        print(f"   Status: {result['status']}")
        print(f"   Failure type: {result.get('failure_type', 'N/A')}")
        print(f"   Channel: {result.get('channel_used', 'N/A')}")
        print(f"   Notes: {result.get('notes', 'N/A')[:100]}...")
    
    # Frontier
    frontier = campaign.get('frontier', [])
    print(f"\n🌐 Frontier: {len(frontier)} nodes")
    open_nodes = [n for n in frontier if n['status'] == 'open']
    print(f"   Open: {len(open_nodes)}")
    
    # Memory
    memory = campaign.get('memory', {})
    print(f"\n🧠 Memory:")
    print(f"   Useful lemmas: {len(memory.get('useful_lemmas', []))}")
    print(f"   Blocked patterns: {len(memory.get('blocked_patterns', []))}")
    print(f"   Recent failures: {len(memory.get('recent_failures', []))}")


if __name__ == "__main__":
    base_url = "https://lima-backend-production.up.railway.app"
    campaign_id = sys.argv[1] if len(sys.argv) > 1 else "C-fe1ea35d2800"
    
    try:
        check_campaign(base_url, campaign_id)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
