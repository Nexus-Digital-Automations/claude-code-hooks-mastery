#!/bin/bash
# Authorize a one-time stop
mkdir -p .claude/data
echo '{"authorized": true}' > .claude/data/stop_authorization.json
echo "✓ Stop authorized (one-time use)"
