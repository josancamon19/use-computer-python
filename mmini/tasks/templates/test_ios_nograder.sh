#!/bin/bash
REWARD="${HARBOR_REWARD_FILE:-./reward.txt}"
echo "0" > "$REWARD"
echo "Score: 0 (no DSL grader)"
