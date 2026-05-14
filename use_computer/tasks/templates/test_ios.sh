#!/bin/bash
# iOS test.sh — runs on the harbor host, evaluator runs server-side at /grade.
REWARD="${HARBOR_REWARD_FILE:-./reward.txt}"
GRADER_LOG="${HARBOR_GRADER_LOG:-./grader.log}"
: "${GATEWAY_URL:?GATEWAY_URL is required}"
: "${SANDBOX_ID:?SANDBOX_ID is required}"
: "${MMINI_API_KEY:?MMINI_API_KEY is required}"

SPECS='{{SPECS}}'
PAYLOAD=$(printf '{"specs": %s}' "$SPECS")
RESP=$(curl -sS -H "Authorization: Bearer $MMINI_API_KEY" -H "Content-Type: application/json" -X POST "$GATEWAY_URL/v1/sandboxes/$SANDBOX_ID/grade" --data-binary "$PAYLOAD")
echo "$RESP" >> "$GRADER_LOG"
if echo "$RESP" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get(\"passed\") else 1)"; then
  echo "1" > "$REWARD"
  echo "Score: 1"
  exit 0
fi

echo "0" > "$REWARD"
echo "Score: 0 — grader response: $(echo "$RESP" | head -c 500)"
