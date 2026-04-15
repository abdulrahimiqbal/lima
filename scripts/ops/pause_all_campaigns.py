#!/usr/bin/env python3
"""
Script to pause all running campaigns in Lima Learning.
Uses the Railway API to find the service URL and then pauses all campaigns.
"""

import os
import sys
import requests
from typing import Any


def get_railway_service_url(railway_token: str) -> str:
    """Get the service URL from Railway API."""
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json",
    }
    
    # GraphQL query to get projects and their services
    query = """
    query {
        me {
            projects {
                edges {
                    node {
                        id
                        name
                        services {
                            edges {
                                node {
                                    id
                                    name
                                    serviceInstances {
                                        edges {
                                            node {
                                                domains {
                                                    serviceDomains {
                                                        domain
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    try:
        response = requests.post(
            "https://backboard.railway.app/graphql/v2",
            headers=headers,
            json={"query": query},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        
        # Debug: print the response
        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
        
        # Find Lima project and extract service URL
        me_data = data.get("data", {}).get("me", {})
        if not me_data:
            raise ValueError("Could not authenticate with Railway API")
        
        projects = me_data.get("projects", {}).get("edges", [])
        
        for project_edge in projects:
            project = project_edge.get("node", {})
            project_name = project.get("name", "").lower()
            
            print(f"  Found project: {project.get('name')}")
            
            # Look for Lima-related project
            if "lima" in project_name or "learning" in project_name:
                for service_edge in project.get("services", {}).get("edges", []):
                    service = service_edge.get("node", {})
                    print(f"    Found service: {service.get('name')}")
                    instances = service.get("serviceInstances", {}).get("edges", [])
                    
                    if instances:
                        domains = instances[0].get("node", {}).get("domains", {}).get("serviceDomains", [])
                        if domains:
                            domain = domains[0].get("domain")
                            if domain:
                                return f"https://{domain}"
        
        raise ValueError("Could not find Lima service URL in Railway projects")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Railway API request failed: {e}")


def list_campaigns(base_url: str) -> list[dict[str, Any]]:
    """List all campaigns from the Lima API."""
    response = requests.get(f"{base_url}/api/campaigns", timeout=30)
    response.raise_for_status()
    return response.json()


def pause_campaign(base_url: str, campaign_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Pause a specific campaign."""
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    
    response = requests.post(
        f"{base_url}/api/campaigns/{campaign_id}/control",
        json={"action": "pause"},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main():
    # Check for direct service URL first
    base_url = os.getenv("LIMA_SERVICE_URL")
    
    if not base_url:
        railway_token = os.getenv("RAILWAY_TOKEN")
        if not railway_token:
            print("Error: Either LIMA_SERVICE_URL or RAILWAY_TOKEN must be set")
            print("Usage: LIMA_SERVICE_URL=<url> python pause_all_campaigns.py")
            print("   or: RAILWAY_TOKEN=<token> python pause_all_campaigns.py")
            sys.exit(1)
        
        try:
            print("🔍 Finding Lima service URL from Railway...")
            base_url = get_railway_service_url(railway_token)
            print(f"✅ Found service at: {base_url}")
        except Exception as e:
            print(f"❌ Could not find service URL from Railway: {e}")
            print("\nPlease provide the service URL directly:")
            print("  LIMA_SERVICE_URL=https://your-service.railway.app python pause_all_campaigns.py")
            sys.exit(1)
    else:
        print(f"🔗 Using service URL: {base_url}")
    
    # Optional API key for protected endpoints
    api_key = os.getenv("OPERATOR_API_KEY")
    
    try:
        print("\n📋 Fetching all campaigns...")
        campaigns = list_campaigns(base_url)
        print(f"✅ Found {len(campaigns)} campaigns")
        
        # Filter running campaigns with auto_run enabled
        running_campaigns = [
            c for c in campaigns 
            if c.get("status") == "running" and c.get("auto_run", False)
        ]
        
        if not running_campaigns:
            print("\n✅ No running campaigns to pause!")
            return
        
        print(f"\n⏸️  Pausing {len(running_campaigns)} running campaigns...")
        
        for campaign in running_campaigns:
            campaign_id = campaign["id"]
            title = campaign.get("title", "Untitled")
            tick_count = campaign.get("tick_count", 0)
            
            try:
                print(f"  - Pausing {campaign_id} ({title}) [tick: {tick_count}]...", end=" ")
                pause_campaign(base_url, campaign_id, api_key)
                print("✅")
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n✅ All campaigns paused successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
