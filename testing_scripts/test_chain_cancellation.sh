#!/usr/bin/env bash
set -e

###############################################################################
# CONFIG
###############################################################################
LOG_FILE="./treehopper_cancellation_test_$(date +%Y%m%d_%H%M%S).log"

export TH_TEST_MODE=1
export TH_LLM_PROVIDER=mock

echo ""
echo "🧪 Treehopper Cancellation Test Suite"
echo "📝  Log → $LOG_FILE"
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

read -p "📂 Enter workspace path (formatter/, summarizer/): " WS
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
echo "STEP 2 — Start Treehopper Main Server: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
treehopper run --bg | tee -a "$LOG_FILE"
sleep 3
end_timer ; echo ""

###############################################################################
# STEP 3 — BUILD AGENTS + CHAIN
###############################################################################
echo "STEP 3 — Prepare Agents + Chain: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper lint formatter | tee -a "$LOG_FILE"
treehopper lint summarizer | tee -a "$LOG_FILE"

treehopper build formatter | tee -a "$LOG_FILE"
treehopper build summarizer | tee -a "$LOG_FILE"

treehopper chain build cancel_test_chain formatter summarizer | tee -a "$LOG_FILE" || true

end_timer ; echo ""

###############################################################################
# STEP 4 — RESTART MAIN SERVER
###############################################################################
echo "Restarting Treehopper after agent/chain build... $(timestamp)" | tee -a "$LOG_FILE"
start_timer
TMP_RESTART=$(mktemp)
treehopper restart > "$TMP_RESTART" 2>&1 || true
cat "$TMP_RESTART" | tee -a "$LOG_FILE"
rm "$TMP_RESTART"
sleep 3
end_timer ; echo ""

###############################################################################
# STEP 5 — PUSH FILE
###############################################################################
echo "STEP 5 — Push test_file.txt: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

PUSH=$(treehopper push-file formatter test_file.txt)
echo "$PUSH" | tee -a "$LOG_FILE"

FILE_PATH=$(echo "$PUSH" | sed -n 's/.*"file_path":[[:space:]]*"\(.*\)".*/\1/p')
echo "📌 FILE_PATH = $FILE_PATH" | tee -a "$LOG_FILE"

end_timer ; echo ""

###############################################################################
# STEP 6 — RUN CHAIN (NON-DETACHED)
###############################################################################
echo "STEP 6 — Start long-running chain run: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain run cancel_test_chain \
  --payload "{\"file_path\": \"$FILE_PATH\"}" \
  | tee -a "$LOG_FILE"

sleep 1

CHAIN_DIR=$(ls -d $HOME/.treehopper/registry/chains/cancel_test_chain-* 2>/dev/null | head -1)
LAST_RUN="$CHAIN_DIR/last_run.json"

if [ ! -f "$LAST_RUN" ]; then
  echo "❌ last_run.json missing" | tee -a "$LOG_FILE"
  exit 1
fi

RUN_ID=$(grep -o '"run_id":[[:space:]]*"[^"]*"' "$LAST_RUN" | sed 's/"run_id":[[:space:]]*"//;s/"$//')

if [ -z "$RUN_ID" ]; then
  echo "❌ Unable to extract run_id"
  cat "$LAST_RUN"
  exit 1
fi

echo "📌 Detected RUN_ID → $RUN_ID" | tee -a "$LOG_FILE"
end_timer ; echo ""

###############################################################################
# STEP 7 — CANCEL RUN-ID
###############################################################################
echo "STEP 7 — Cancel run_id $RUN_ID: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain cancel --run "$RUN_ID" | tee -a "$LOG_FILE"
sleep 1

end_timer ; echo ""

###############################################################################
# STEP 8 — VERIFY CANCELLATION
###############################################################################
echo "STEP 8 — Verify cancellation logged: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain logs cancel_test_chain | tee -a "$LOG_FILE"

FOUND=$(grep -R "\"cancelled\"" ~/.treehopper/registry/chains/cancel_test_chain*/runs/*.json || true)

if [ -n "$FOUND" ]; then
  echo "✔ Cancellation recorded" | tee -a "$LOG_FILE"
else
  echo "❌ Cancellation NOT recorded" | tee -a "$LOG_FILE"
fi

end_timer ; echo ""

###############################################################################
# STEP 9 — PARALLEL BATCH
###############################################################################
echo "STEP 9 — Start parallel batch (parallel=4): $(timestamp)" | tee -a "$LOG_FILE"
start_timer

TMP_BATCH=$(mktemp)

treehopper chain run cancel_test_chain \
  --payload "{\"file_path\": \"$FILE_PATH\"}" \
  --parallel 4 --concurrency 2 \
  2>&1 | tee "$TMP_BATCH" | tee -a "$LOG_FILE"

sleep 1

BATCH_ID=$(grep -oE "batch-[0-9]+" "$TMP_BATCH" | head -1)

if [ -z "$BATCH_ID" ]; then
  echo "❌ Could not detect batch_id"
  cat "$TMP_BATCH"
  exit 1
fi

echo "📌 Detected BATCH_ID → $BATCH_ID" | tee -a "$LOG_FILE"
end_timer ; echo ""

###############################################################################
# STEP 10 — CANCEL BATCH
###############################################################################
echo "STEP 10 — Cancel batch $BATCH_ID: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

treehopper chain cancel-batch --batch "$BATCH_ID" | tee -a "$LOG_FILE"
sleep 1

end_timer ; echo ""

###############################################################################
# STEP 11 — ERROR CASES
###############################################################################
echo "STEP 11 — Error cases: $(timestamp)" | tee -a "$LOG_FILE"
start_timer

echo "❌ Cancel non-existent run:"
treehopper chain cancel cancel_test_chain --run-id DOES_NOT_EXIST | tee -a "$LOG_FILE" || true

echo "❌ Cancel finished run:"
treehopper chain cancel cancel_test_chain --run-id "$RUN_ID" | tee -a "$LOG_FILE" || true

end_timer ; echo ""

###############################################################################
# STEP 12 — HEALTH & STOP
###############################################################################
echo "STEP 12 — Health check & stop: $(timestamp)" | tee -a "$LOG_FILE"
start_timer
curl -s http://localhost:1567/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"
treehopper stop | tee -a "$LOG_FILE"
end_timer ; echo ""

echo "🎉 CANCELLATION TEST COMPLETE"
echo "📝 Log → $LOG_FILE"
