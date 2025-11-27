#!/usr/bin/env bash
set -e

###############################################################################
# CONFIG
###############################################################################
LOG_FILE="./treehopper_full_parallel_test_$(date +%Y%m%d_%H%M%S).log"
AGENT_PORT=9111
CHAIN_PORT=9112

# FAST test mode (reduces retry/backoff). Set to 0 for "real" runs.
export TH_TEST_MODE=1
# Optional: use the mock LLM provider (superfast, no external calls)
# export TH_LLM_PROVIDER=mock

# Auto-throttle concurrency safety
export TH_AUTO_THROTTLE=1
export TH_SAFE_CONCURRENCY=3

echo ""
echo "🧪 Treehopper FULL Test (Agents + Chain + Detached + Parallel)"
echo "📝 Log file → $LOG_FILE"
if [ "${TH_TEST_MODE}" = "1" ]; then
  echo "⚡ FAST RETRY MODE ENABLED (TH_TEST_MODE=1)" | tee -a "$LOG_FILE"
fi
if [ "${TH_LLM_PROVIDER:-}" = "mock" ]; then
  echo "⚡ MOCK LLM PROVIDER ENABLED (TH_LLM_PROVIDER=mock)" | tee -a "$LOG_FILE"
fi
echo ""

# -------------------- timing helpers --------------------
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
start_timer() { STEP_START=$(date +%s); }
end_timer() {
    local end=$(date +%s)
    local diff=$((end - STEP_START))
    echo "⏱  Duration: ${diff}s" | tee -a "$LOG_FILE"
}
# --------------------------------------------------------

###############################################################################
# STEP 1 — WORKSPACE
###############################################################################
echo "STEP 1 — Workspace: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
read -p "📂 Enter workspace path (formatter/, summarizer/, test_file.txt): " WS

if [ ! -d "$WS" ]; then
  echo "❌ Workspace not found" | tee -a "$LOG_FILE"
  exit 1
fi
cd "$WS"
echo "➡ Using workspace: $WS" | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 2 — START MAIN SERVER
###############################################################################
echo "STEP 2 — Start Treehopper Main Server: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper run --bg > >(tee -a "$LOG_FILE") 2>&1 || true
sleep 3
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 3 — LINT AGENTS
###############################################################################
echo "STEP 3 — Lint Formatter & Summarizer Agents: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper lint formatter | tee -a "$LOG_FILE"
treehopper lint summarizer | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 4 — BUILD AGENTS
###############################################################################
echo "STEP 4 — Build Formatter & Summarizer: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper build formatter | tee -a "$LOG_FILE"
treehopper build summarizer | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 5 — PUSH FILE TO FORMATTER
###############################################################################
echo "STEP 5 — Push test_file.txt to formatter: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
PUSH=$(treehopper push-file formatter test_file.txt)
echo "$PUSH" | tee -a "$LOG_FILE"
FILE_PATH=$(echo "$PUSH" | sed -n 's/.*"file_path":[[:space:]]*"\(.*\)".*/\1/p')
if [ -z "$FILE_PATH" ]; then
  echo "❌ Could not extract FILE_PATH" | tee -a "$LOG_FILE"
  exit 1
fi
echo "📌 FILE_PATH → $FILE_PATH" | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# FIXED RESTART BLOCK #1
###############################################################################
echo "Restarting Treehopper... $(timestamp)" | tee -a "$LOG_FILE"
start_timer
TMP_RESTART_LOG=$(mktemp)
treehopper restart >"$TMP_RESTART_LOG" 2>&1 || true
cat "$TMP_RESTART_LOG" | tee -a "$LOG_FILE"
rm "$TMP_RESTART_LOG"
sleep 2
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 6 — BUILD CHAIN
###############################################################################
echo "STEP 6 — Build chain exec_summ: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain build exec_summ formatter summarizer | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# FIXED RESTART BLOCK #2
###############################################################################
echo "Restarting Treehopper... $(timestamp)" | tee -a "$LOG_FILE"
start_timer
TMP_RESTART_LOG=$(mktemp)
treehopper restart >"$TMP_RESTART_LOG" 2>&1 || true
cat "$TMP_RESTART_LOG" | tee -a "$LOG_FILE"
rm "$TMP_RESTART_LOG"
sleep 2
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 7 — DIRECT AGENT TESTS
###############################################################################
echo "STEP 7 — Call formatter: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper call /api/v1/agents/formatter "{\"file_path\": \"$FILE_PATH\"}" | tee -a "$LOG_FILE"
end_timer
echo ""

echo "STEP 7.2 — Call summarizer: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper call /api/v1/agents/summarizer '{"formatted": "Test text"}' | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 8 — EXECUTE CHAIN (NORMAL MODE)
###############################################################################
echo "STEP 8 — Run exec_summ via CLI: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain run exec_summ --payload "{\"file_path\": \"$FILE_PATH\"}" | tee -a "$LOG_FILE"
end_timer
echo ""

echo "STEP 8.1 — Show chain logs: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain logs exec_summ | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 9 — DETACHED AGENT TEST
###############################################################################
echo "STEP 9 — DETACHED Formatter agent: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper agent run formatter --detached --bg --port $AGENT_PORT | tee -a "$LOG_FILE"
sleep 2

python3 - <<EOF | tee -a "$LOG_FILE"
import requests, sys
r=requests.post("http://localhost:$AGENT_PORT/api/v1/formatter/run",
    json={"file_path":"$FILE_PATH"},
    headers={"x-api-key":"demo-key-123"}
)
print("DETACHED-FORMATTER:", r.status_code, r.text)
EOF
treehopper agent stop formatter | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 10 — DETACHED CHAIN TEST
###############################################################################
echo "STEP 10 — DETACHED exec_summ chain: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain run exec_summ --payload "{\"file_path\": \"$FILE_PATH\"}" --detached --bg --port $CHAIN_PORT | tee -a "$LOG_FILE"
sleep 2

python3 - <<EOF | tee -a "$LOG_FILE"
import requests, sys
r=requests.post("http://localhost:$CHAIN_PORT/api/v1/exec_summ/run",
    json={"file_path":"$FILE_PATH"},
    headers={"x-api-key":"demo-key-123"}
)
print("DETACHED-CHAIN:", r.status_code, r.text)
EOF

treehopper chain stop exec_summ | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 11 — PARALLEL EXECUTION (5 RUNS)
###############################################################################
echo ""
echo "STEP 11 — PARALLEL (5 runs): $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain run exec_summ \
  --payload "{\"file_path\": \"$FILE_PATH\"}" \
  --parallel 5 | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 12 — PARALLEL WITH CONCURRENCY=3
###############################################################################
echo ""
echo "STEP 12 — PARALLEL (10 runs, concurrency=3): $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain run exec_summ \
  --payload "{\"file_path\": \"$FILE_PATH\"}" \
  --parallel 10 \
  --concurrency 3 | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 13 — PARALLEL DETACHED
###############################################################################
echo ""
echo "STEP 13 — PARALLEL DETACHED (6 runs): $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper chain run exec_summ \
  --payload "{\"file_path\": \"$FILE_PATH\"}" \
  --parallel 6 \
  --detached | tee -a "$LOG_FILE"
end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 14 — EDGE CASES
###############################################################################
echo ""
echo "STEP 14 — EDGE CASES: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

echo "EC1: parallel=1" | tee -a "$LOG_FILE"
treehopper chain run exec_summ --parallel 1 --payload "{\"file_path\": \"$FILE_PATH\"}" | tee -a "$LOG_FILE"

echo "EC2: invalid parallel" | tee -a "$LOG_FILE"
treehopper chain run exec_summ --parallel abc || echo "✔ Caught invalid parallel" | tee -a "$LOG_FILE"

echo "EC3: invalid concurrency" | tee -a "$LOG_FILE"
treehopper chain run exec_summ --parallel 5 --concurrency xyz || echo "✔ Caught invalid concurrency" | tee -a "$LOG_FILE"

echo "EC4: concurrency > parallel" | tee -a "$LOG_FILE"
treehopper chain run exec_summ --parallel 3 --concurrency 10 | tee -a "$LOG_FILE"

echo "EC5: large parallel=30 (throttled)" | tee -a "$LOG_FILE"
treehopper chain run exec_summ --parallel 30 --concurrency 4 | tee -a "$LOG_FILE"

end_timer
echo "" | tee -a "$LOG_FILE"

###############################################################################
# FINAL
###############################################################################
echo ""
echo "STEP 15 — Health check & stop: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
curl -s http://localhost:1567/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"
treehopper stop | tee -a "$LOG_FILE"
end_timer

echo ""
echo "🎉 ALL TESTS COMPLETED"
echo "📝 Log file → $LOG_FILE"
echo ""
