#!/bin/bash
# macOS test.sh — no grader saved for this task. Always 0.
PREFIX=""
[ -d "/tmp/harbor/logs" ] && PREFIX="/tmp/harbor"
REWARD="${PREFIX}/logs/verifier/reward.txt"
echo "0" > "$REWARD"
echo "Score: 0 (no grader)"
