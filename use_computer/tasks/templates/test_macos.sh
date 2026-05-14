#!/bin/bash
# macOS test.sh — runs inside the VM via Harbor.
PREFIX=""
[ -d "/tmp/harbor/logs" ] && PREFIX="/tmp/harbor"
REWARD="${PREFIX}/logs/verifier/reward.txt"
GRADER_LOG="${PREFIX}/logs/verifier/grader.log"

{{CHECKS}}
echo "0" > "$REWARD"
echo "Score: 0"
