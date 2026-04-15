#!/bin/bash
# Disable self-improvement to conserve LLM credits

RAILWAY_TOKEN="e90c301d-7783-4823-bfd9-3d17ad8a71c3"

echo "🔧 Disabling self-improvement..."
railway variables --set ENABLE_SELF_IMPROVEMENT=false

echo "✅ Self-improvement disabled"
echo ""
echo "This will stop the continuous LLM calls for policy improvement."
echo "Manager decisions will still use LLM when campaigns step forward."
echo ""
echo "To re-enable later: railway variables --set ENABLE_SELF_IMPROVEMENT=true"
