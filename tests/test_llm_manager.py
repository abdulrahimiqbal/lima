#!/usr/bin/env python3
"""Test LLM manager decision making."""

import requests
import json

# Get a campaign to test with
response = requests.get('https://lima-backend-production.up.railway.app/api/campaigns/C-c8b28d4eddc0')
campaign = response.json()

print("Campaign ID:", campaign['id'])
print("Manager backend:", campaign.get('manager_backend'))
print()

# Get manager context
response = requests.get(f'https://lima-backend-production.up.railway.app/api/campaigns/{campaign["id"]}/manager-context')
context = response.json()

print("=== MANAGER CONTEXT ===")
print(f"Problem statement: {context.get('problem', {}).get('statement', '')[:200]}...")
print(f"Frontier nodes: {len(context.get('frontier', []))}")
print(f"Memory state: {list(context.get('memory', {}).keys())}")
print()

# Check if there are any error logs
if campaign.get('last_execution_result'):
    result = campaign['last_execution_result']
    print("=== LAST EXECUTION RESULT ===")
    print(f"Status: {result.get('status')}")
    print(f"Failure type: {result.get('failure_type')}")
    print(f"Notes: {result.get('notes', '')[:300]}")
