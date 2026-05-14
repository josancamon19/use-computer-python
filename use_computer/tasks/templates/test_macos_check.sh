# Check {{N}}
_r=$(mktemp)
perl -e 'alarm 15; exec @ARGV' -- bash -c '{{CMD}}' > "$_r" 2>>"$GRADER_LOG"
if grep -qi "true" "$_r" 2>/dev/null; then
  rm -f "$_r"
  echo "1" > "$REWARD"
  echo "Score: 1"
  exit 0
fi
rm -f "$_r"
