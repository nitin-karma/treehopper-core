#!/usr/bin/env bash

set -e

# export TREEHOPPER_DEV_MODE=1
# export TH_LLM_PROVIDER=mock
# export TREEHOPPER_FORCE_LOCAL=1
# export TREEHOPPER_SOURCE_ROOT="$(pwd)/../treehopper-core"
# export PYTHONPATH="$TREEHOPPER_SOURCE_ROOT:$PYTHONPATH"



LOG_FILE="./treehopper_resume_test_$(date +%Y%m%d_%H%M%S).log"
unset TH_TEST_MODE


echo ""
echo "🧪 Treehopper Cancellation + Resume Test Suite (2-Step Slow Chain)"
echo "📝 Log → $LOG_FILE"
echo ""

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
start_timer(){ STEP_START=$(date +%s); }
end_timer(){ echo "⏱ Duration: $(( $(date +%s) - STEP_START ))s" | tee -a "$LOG_FILE"; }


###############################################################################
# STEP 1 — WORKSPACE
###############################################################################
echo "STEP 1 — Workspace: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

read -p "📂 Enter workspace path (examples/): " WS
cd "$WS"
echo "➡ Workspace = $WS"

end_timer; echo ""


###############################################################################
# STEP 2 — START MAIN SERVER
###############################################################################
echo "STEP 2 — Start Main Server: $(timestamp)"
start_timer
treehopper run --bg | tee -a "$LOG_FILE"
sleep 3
end_timer; echo ""


###############################################################################
# STEP 3 — BUILD TWO AGENTS
###############################################################################
echo "STEP 3 — Build slow agents: $(timestamp)"
start_timer

treehopper lint slow_agent | tee -a "$LOG_FILE"
treehopper lint slow_agent_stage2 | tee -a "$LOG_FILE"

treehopper build slow_agent | tee -a "$LOG_FILE"
treehopper build slow_agent_stage2 | tee -a "$LOG_FILE"

# Restart to register new agents
sleep 2
TMP_RESTART=$(mktemp)
treehopper restart > "$TMP_RESTART" 2>&1 || true
cat "$TMP_RESTART" | tee -a "$LOG_FILE"
rm "$TMP_RESTART"
sleep 2

# Wait for main server
for i in {1..60}; do
  if curl -s -H "x-api-key: demo-key-123" http://localhost:1567/api/v1/sys/health \
      | grep -q '"status":"ok"'; then
    echo "✅ Main server healthy"
    break
  fi
  sleep 0.2
done

end_timer; echo ""


###############################################################################
# STEP 4 — BUILD CHAIN
###############################################################################
echo "STEP 4 — Build chain cancel_test_chain: $(timestamp)"
start_timer

treehopper chain build cancel_test_chain slow_agent slow_agent_stage2 \
    | tee -a "$LOG_FILE"

CHAIN_DIR=$(ls -d $HOME/.treehopper/registry/chains/cancel_test_chain-* | head -1)
echo "CHAIN_DIR = $CHAIN_DIR" | tee -a "$LOG_FILE"

end_timer; echo ""


###############################################################################
# STEP 5 — DETACHED RUN (background)
###############################################################################
echo "STEP 5 — Fire long-running detached chain: $(timestamp)"
start_timer

RUN_OUTPUT=$(treehopper chain run cancel_test_chain \
  --payload '{"name":"Nitin"}' \
  --detached --bg)

# Check CLI sees DB
#python3 -c "from treehopper.treehopper_cancellation import DB_PATH; print(f'CLI: {DB_PATH}')"

# Check runtime log
#grep "DB_PATH" ~/.treehopper/runtime/chain_*.log

echo "RUN OUTPUT = $RUN_OUTPUT"

RUN_ID=$(echo "$RUN_OUTPUT" | grep -oE "cancel_test_chain-[0-9]{10,}" | head -1)

if [ -z "$RUN_ID" ]; then
  echo "❌ ERROR: could not extract run_id"
  echo "$RUN_OUTPUT"
  exit 1
fi

echo "📌 RUN_ID = $RUN_ID" | tee -a "$LOG_FILE"

# Runtime log for synchronization
CHAIN_NAME=cancel_test_chain
CHAIN_ID=$(basename "$CHAIN_DIR")
RUNTIME_LOG="$HOME/.treehopper/runtime/chain_${CHAIN_NAME}-${CHAIN_ID}.log"
echo "RUNTIME_LOG = $RUNTIME_LOG" | tee -a "$LOG_FILE"

end_timer; echo ""

###############################################################################
# STEP 6 — CANCEL AS SOON AS slow_agent IS READY
###############################################################################
echo "STEP 6 — Cancel run (as soon as slow_agent is READY): $(timestamp)"
start_timer

echo "⏳ Waiting for slow_agent to enter READY state..."

# Wait for READY signal instead of 5/5
while ! grep -q "\[slow_agent\] READY" "$RUNTIME_LOG"; do
    sleep 0.02
done

echo "✔ slow_agent READY — SENDING CANCEL NOW"

treehopper chain cancel --run "$RUN_ID" | tee -a "$LOG_FILE"

# Give runtime a moment to process cancel marker
sleep 0.3

end_timer; echo ""


###############################################################################
# STEP 7 — VERIFY CANCELLATION
###############################################################################
echo "STEP 7 — Verify cancellation logged: $(timestamp)"
start_timer

FOUND=$(grep -R "\"cancelled\": true" "$CHAIN_DIR/runs" || true)

if [ -n "$FOUND" ]; then
  echo "✔ Cancellation logged" | tee -a "$LOG_FILE"
else
  echo "❌ Cancellation NOT logged" | tee -a "$LOG_FILE"
  exit 1
fi

end_timer; echo ""


###############################################################################
# STEP 8 — RESUME RUN
###############################################################################
echo "STEP 8 — Resume run: $(timestamp)"
start_timer

treehopper chain resume "$RUN_ID" | tee -a "$LOG_FILE"

UPDATED=$(grep -R "\"status\": \"completed\"" "$CHAIN_DIR/runs" || true)
if [ -n "$UPDATED" ]; then
  echo "✔ Resume completed" | tee -a "$LOG_FILE"
else
  echo "❌ Resume FAILED" | tee -a "$LOG_FILE"
  exit 1
fi

end_timer; echo ""


###############################################################################
# STEP 9 — RESUME AGAIN (Should reject)
###############################################################################
echo "STEP 9 — Resume again (should reject): $(timestamp)"
start_timer
treehopper chain resume "$RUN_ID" | tee -a "$LOG_FILE" || true
end_timer; echo ""


###############################################################################
# STEP 10 — Parallel Batch Test
###############################################################################
echo "STEP 10 — Parallel batch test: $(timestamp)"
start_timer

TMP=$(mktemp)
treehopper chain run cancel_test_chain \
  --payload '{"name":"Batch"}' \
  --parallel 4 --concurrency 2 \
  2>&1 | tee "$TMP"

BATCH_ID=$(grep -oE "batch-[0-9]+" "$TMP" | head -1)
echo "📌 BATCH_ID = $BATCH_ID" | tee -a "$LOG_FILE"

end_timer; echo ""


###############################################################################
# STEP 11 — Cancel Batch
###############################################################################
echo "STEP 11 — Cancel batch: $(timestamp)"
start_timer
treehopper chain cancel-batch "$BATCH_ID" | tee -a "$LOG_FILE"
end_timer; echo ""


###############################################################################
# STEP 12 — STOP SERVER
###############################################################################
echo "STEP 12 — Stop main server: $(timestamp)"
start_timer
treehopper stop | tee -a "$LOG_FILE"
end_timer; echo ""

echo ""
echo "🎉 RESUME + CANCELLATION TEST COMPLETE"
echo "📝 Log → $LOG_FILE"
