#!/usr/bin/env python3
"""Test if LLM is working by checking system status."""

import requests

base_url = "https://lima-backend-production.up.railway.app"

# Check system status
response = requests.get(f"{base_url}/api/system/status")
status = response.json()

print("🔍 System Status:")
print(f"   Manager backend: {status['manager']['backend']}")
print(f"   Manager model: {status['manager']['model']}")
print(f"   Executor backend: {status['executor']['backend']}")
print(f"   Executor connectivity: {status['executor']['connectivity']['status']}")

# Check if LLM is configured
if status['manager']['backend'] == 'llm':
    print("\n✅ LLM is configured as manager backend")
    print(f"   Model: {status['manager']['model']}")
else:
    print(f"\n⚠️  Manager backend is: {status['manager']['backend']}")

# Check the campaign
response = requests.get(f"{base_url}/api/campaigns/C-fe1ea35d2800")
campaign = response.json()

print(f"\n📊 Campaign C-fe1ea35d2800:")
print(f"   Manager backend used: {campaign['manager_backend']}")
print(f"   Last decision backend: {campaign.get('last_manager_decision', {}).get('manager_backend', 'N/A')}")

if campaign['manager_backend'] == 'rules_fallback':
    print("\n⚠️  Campaign used rules_fallback - LLM decision failed")
    print("   This means the LLM was attempted but threw an exception")
    print("   Common causes:")
    print("   - API timeout")
    print("   - Rate limiting")
    print("   - Invalid API response")
    print("   - Schema validation failure")
    print("   - JSON parsing error")
