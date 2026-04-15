#!/usr/bin/env python3
"""
Force complete a stuck Aristotle job by manually updating the campaign.
"""

import requests
import sys

def force_complete_job(base_url: str, campaign_id: str):
    """Force complete the pending Aristotle job."""
    
    # Get current campaign
    response = requests.get(f"{base_url}/api/campaigns/{campaign_id}")
    response.raise_for_status()
    campaign = response.json()
    
    pending = campaign.get('pending_aristotle_job')
    if not pending:
        print("No pending job found")
        return
    
    print(f"Current job status: {pending['status']}")
    print(f"Project ID: {pending['project_id']}")
    print(f"Poll count: {pending['poll_count']}")
    
    # Update the campaign to clear the pending job and add a result
    # This requires direct database access or an admin API endpoint
    print("\nTo force complete this job, you need to:")
    print("1. Access the Railway Postgres database directly")
    print("2. Update the campaign payload to remove 'pending_aristotle_job'")
    print("3. Or restart the campaign with a new decision")
    
    print(f"\nAlternatively, cancel this campaign and create a new one:")
    print(f"  POST {base_url}/api/campaigns/{campaign_id}/cancel")


if __name__ == "__main__":
    base_url = "https://lima-backend-production.up.railway.app"
    campaign_id = "C-fe1ea35d2800"
    
    force_complete_job(base_url, campaign_id)
