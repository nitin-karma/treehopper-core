#!/usr/bin/env bash
set -e

###############################################################################
# CONFIG
###############################################################################
LOG_FILE="./treehopper_slow_cancellation_test_$(date +%Y%m%d_%H%M%S).log"

export TH_TEST_MODE=1
export TH_LLM_PROVIDER=mock

echo ""
echo "🧪 Treehopper Slow-Agent Cancellation Test"
echo "📝 Log → $LOG_FILE"
echo "⚡ TH_TEST_MODE=1 (fast retries)"
echo "⚡ Using mock provider"
echo ""

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
start_timer(){ STEP_START=$(date +%s); }
end_timer(){
  local end=$(date +%s)
  echo "⏱ Duration: $((end-STEP_START))s" | tee -a "$LOG_FILE"
}

###############################################################################
# STEP 1 — WORKSPACE
###############################################################################
echo "STEP 1 — Workspace: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

read -p "📂 Enter workspace path (slow_agent/): " WS
if [ ! -d "$WS" ]; then
  echo "❌ Workspace not found" | tee -a "$LOG_FILE"
  exit 1
fi

cd "$WS"
echo "➡ Using workspace: $WS" | tee -a "$LOG_FILE"
end_timer ; echo ""

###############################################################################
# STEP 2 — START MAIN SERVER
###############################################################################
echo "STEP 2 — Start Main Server: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper run --bg | tee -a "$LOG_FILE"
sleep 3
end_timer ; echo ""

###############################################################################
# STEP 3 — BUILD SLOW AGENT + CHAIN
###############################################################################
echo "STEP 3 — Build slow_agent + chain: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper lint slow_agent | tee -a "$LOG_FILE"
treehopper build slow_agent | tee -a "$LOG_FILE"

treehopper chain build cancel_test_chain slow_agent | tee -a "$LOG_FILE" || true

end_timer ; echo ""

###############################################################################
# STEP 4 — RESTART MAIN SERVER
###############################################################################
echo "Restarting Treehopper main server... $(timestamp)" | tee -a "$LOG_FILE"
start_timer
TMP_RESTART=$(mktemp)
treehopper restart > "$TMP_RESTART" 2>&1 || true
cat "$TMP_RESTART" | tee -a "$LOG_FILE"
rm "$TMP_RESTART"
sleep 3
end_timer ; echo ""

###############################################################################
# STEP 5 — FIRE LONG-RUNNING CHAIN (DETACHED)
###############################################################################
echo "STEP 5 — Start slow chain (detached): $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain run cancel_test_chain \
  --payload '{"name":"Nitin"}' \
  --detached --bg \
  | tee -a "$LOG_FILE"

sleep 2   # give micro-app time to create last_run.json

CHAIN_DIR=$(ls -d $HOME/.treehopper/registry/chains/cancel_test_chain-* 2>/dev/null | head -1)
LAST_RUN="$CHAIN_DIR/last_run.json"

if [ ! -f "$LAST_RUN" ]; then
  echo "❌ last_run.json missing — micro-app did not start" | tee -a "$LOG_FILE"
  exit 1
fi

RUN_ID=$(grep -o '"run_id":[[:space:]]*"[^"]*"' "$LAST_RUN" | sed 's/"run_id":[[:space:]]*"//;s/"$//')

if [ -z "$RUN_ID" ]; then
  echo "❌ Unable to read run_id from last_run.json"
  cat "$LAST_RUN"
  exit 1
fi

echo "📌 DETECTED RUN_ID → $RUN_ID" | tee -a "$LOG_FILE"

end_timer ; echo ""

###############################################################################
# STEP 6 — CANCEL RUN-ID
###############################################################################
echo "STEP 6 — Cancel run: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain cancel --run "$RUN_ID" | tee -a "$LOG_FILE"
sleep 1

end_timer ; echo ""

###############################################################################
# STEP 7 — VERIFY CANCELLATION
###############################################################################
echo "STEP 7 — Verify cancellation: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain logs cancel_test_chain | tee -a "$LOG_FILE"

FOUND=$(grep -R "\"cancelled\"" ~/.treehopper/registry/chains/cancel_test_chain*/runs/*.json || true)

if [ -n "$FOUND" ]; then
  echo "✔ CANCEL CONFIRMED" | tee -a "$LOG_FILE"
else
  echo "❌ CANCELLATION NOT LOGGED" | tee -a "$LOG_FILE"
fi

end_timer ; echo ""

###############################################################################
# STEP 8 — PARALLEL BATCH
###############################################################################
echo "STEP 8 — Parallel batch test: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

TMP_BATCH=$(mktemp)

treehopper chain run cancel_test_chain \
  --payload '{"name":"BatchJob"}' \
  --parallel 4 --concurrency 2 \
  2>&1 | tee "$TMP_BATCH" | tee -a "$LOG_FILE"

sleep 1

BATCH_ID=$(grep -oE "batch-[0-9]+" "$TMP_BATCH" | head -1)
echo "📌 BATCH_ID → $BATCH_ID" | tee -a "$LOG_FILE"

end_timer ; echo ""

###############################################################################
# STEP 9 — CANCEL BATCH
###############################################################################
echo "STEP 9 — Cancel batch: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain cancel-batch "$BATCH_ID" | tee -a "$LOG_FILE"
sleep 1

end_timer ; echo ""

###############################################################################
# STEP 10 — ERROR CASES
###############################################################################
echo "STEP 10 — Error cases: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain cancel --run DOES_NOT_EXIST | tee -a "$LOG_FILE" || true
treehopper chain cancel --run "$RUN_ID" | tee -a "$LOG_FILE" || true

end_timer ; echo ""

###############################################################################
# STEP 11 — STOP
###############################################################################
echo "STEP 11 — Stop main server: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
curl -s http://localhost:1567/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"
treehopper stop | tee -a "$LOG_FILE"
end_timer ; echo ""

echo "🎉 SLOW-AGENT CANCELLATION TEST COMPLETE"
echo "📝 Log → $LOG_FILE"
