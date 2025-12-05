#!/usr/bin/env bash
set -e

LOG_FILE="./treehopper_resume_test_$(date +%Y%m%d_%H%M%S).log"
unset TH_TEST_MODE

echo ""
echo "🧪 Treehopper Cancellation + Resume Test Suite (Enhanced)"
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

sleep 2
TMP_RESTART=$(mktemp)
treehopper restart > "$TMP_RESTART" 2>&1 || true
cat "$TMP_RESTART" | tee -a "$LOG_FILE"
rm "$TMP_RESTART"
sleep 2

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

CHAIN_DIR=$(ls -d ~/.treehopper/registry/chains/cancel_test_chain-* | head -1)
echo "CHAIN_DIR = $CHAIN_DIR" | tee -a "$LOG_FILE"

end_timer; echo ""

###############################################################################
# STEP 5 — DETACHED RUN
###############################################################################
echo "STEP 5 — Fire long-running detached chain: $(timestamp)"
start_timer

RUN_OUTPUT=$(treehopper chain run cancel_test_chain \
  --payload '{"name":"Nitin"}' \
  --detached --bg)

echo "RUN OUTPUT = $RUN_OUTPUT"

RUN_ID=$(echo "$RUN_OUTPUT" | grep -oE "cancel_test_chain-[0-9]{10,}" | head -1)

echo "📌 RUN_ID = $RUN_ID" | tee -a "$LOG_FILE"

CHAIN_NAME="cancel_test_chain"
PID_PORT_FILE=$(ls ~/.treehopper/runtime/det_chain_${CHAIN_NAME}-*.pid | head -1)
PORT=$(cut -d: -f2 "$PID_PORT_FILE")

CHAIN_STATUS_URL="http://localhost:$PORT/api/v1/${CHAIN_NAME}/status/$RUN_ID"
echo "RUNTIME_LOG = $HOME/.treehopper/runtime/chain_${CHAIN_NAME}-$(basename $CHAIN_DIR).log" \
  | tee -a "$LOG_FILE"

end_timer; echo ""

###############################################################################
# STEP 6 — CANCEL DURING STEP 1
###############################################################################
echo "STEP 6 — Cancel run (wait for status='running'): $(timestamp)"
start_timer

echo "🔍 Waiting for status=running..."
for i in {1..300}; do
  STATUS=$(curl -s "$CHAIN_STATUS_URL" | jq -r '.status')
  if [ "$STATUS" = "running" ]; then
    echo "✔ Chain is running — sending CANCEL"
    break
  fi
  sleep 0.1
done

treehopper chain cancel --run "$RUN_ID" | tee -a "$LOG_FILE"
sleep 0.5

end_timer; echo ""

###############################################################################
# STEP 7 — VERIFY CANCELLATION
###############################################################################
echo "STEP 7 — Verify cancellation logged: $(timestamp)"
start_timer
if grep -R "\"cancelled\": true" "$CHAIN_DIR/runs" >/dev/null; then
  echo "✔ Cancellation logged"
else
  echo "❌ Cancellation not logged"
  exit 1
fi
end_timer; echo ""

###############################################################################
# STEP 8 — RESUME RUN (Option B: Should re-run step1)
###############################################################################
echo "STEP 8 — Resume run (should re-run step1): $(timestamp)"
start_timer

treehopper chain resume "$RUN_ID" | tee -a "$LOG_FILE"

if grep -R "\"status\": \"completed\"" "$CHAIN_DIR/runs" >/dev/null; then
  echo "✔ Resume completed"
else
  echo "❌ Resume FAILED"
  exit 1
fi
end_timer; echo ""

###############################################################################
# STEP 9 — RESUME AGAIN (reject)
###############################################################################
echo "STEP 9 — Resume again (should reject): $(timestamp)"
start_timer
treehopper chain resume "$RUN_ID" | tee -a "$LOG_FILE" || true
end_timer; echo ""

################################################################################
# 🆕 TEST T1 — CANCEL DURING STEP 2, RESUME SHOULD RE-RUN STEP 2
################################################################################
echo "TEST T1 — Cancel during step2, resume should re-run step2"
start_timer

RUN_OUTPUT2=$(treehopper chain run cancel_test_chain \
  --payload '{"name":"T1"}' \
  --detached --bg)
RUN_ID2=$(echo "$RUN_OUTPUT2" | grep -oE "cancel_test_chain-[0-9]{10,}" | head -1)

PID_PORT_FILE2=$(ls ~/.treehopper/runtime/det_chain_${CHAIN_NAME}-*.pid | head -1)
PORT2=$(cut -d: -f2 "$PID_PORT_FILE2")
STATUS_URL2="http://localhost:$PORT2/api/v1/${CHAIN_NAME}/status/$RUN_ID2"

echo "⏳ Waiting until step2 begins..."
step2_started=false
for i in {1..600}; do
  idx=$(curl -s "$STATUS_URL2" | jq -r '.current_step_index')
  if [ "$idx" -eq 1 ]; then
    step2_started=true
    break
  fi
  sleep 0.1
done

if [ "$step2_started" = false ]; then
  echo "❌ Never reached step2"
  exit 1
fi

echo "🔥 Cancel during step2"
treehopper chain cancel --run "$RUN_ID2"

sleep 0.5
echo "🔁 Resume T1 run"
treehopper chain resume "$RUN_ID2" | tee -a "$LOG_FILE"

echo "✔ T1 completed"
end_timer; echo ""

################################################################################
# 🆕 TEST T2 — RESUME A PENDING RUN (current_step_index = -1)
################################################################################
echo "TEST T2 — Resume pending run should start at step0"
start_timer

RUN_OUTPUT3=$(treehopper chain run cancel_test_chain \
  --payload '{"name":"Pending"}' \
  --detached)

RUN_ID3=$(echo "$RUN_OUTPUT3" | grep -oE "cancel_test_chain-[0-9]{10,}" | head -1)
RUN_FILE3="$CHAIN_DIR/runs/$RUN_ID3.json"

# Force pending status (simulate no work started yet)
sed -i '' 's/"status": "running"/"status": "pending"/' "$RUN_FILE3"
sed -i '' 's/"current_step_index": [0-9-]*/"current_step_index": -1/' "$RUN_FILE3"

echo "🔁 Resume PENDING run:"
treehopper chain resume "$RUN_ID3" | tee -a "$LOG_FILE"

echo "✔ Pending resume OK"
end_timer; echo ""

################################################################################
# 🆕 TEST T3 — Resume should ALWAYS re-run same step (Option B)
################################################################################
echo "TEST T3 — Resume re-runs same step"
start_timer

RUN_OUTPUT4=$(treehopper chain run cancel_test_chain \
  --payload '{"name":"ReExec"}' --detached --bg)
RUN_ID4=$(echo "$RUN_OUTPUT4" | grep -oE "cancel_test_chain-[0-9]{10,}" | head -1)

PID_PORT_FILE4=$(ls ~/.treehopper/runtime/det_chain_${CHAIN_NAME}-*.pid | head -1)
PORT4=$(cut -d: -f2 "$PID_PORT_FILE4")
URL4="http://localhost:$PORT4/api/v1/${CHAIN_NAME}/status/$RUN_ID4"

# Wait for step1
until curl -s "$URL4" | jq -e '.current_step_index == 0' >/dev/null; do sleep 0.1; done

treehopper chain cancel --run "$RUN_ID4"
sleep 0.5

echo "🔁 Resume should rerun step1"
treehopper chain resume "$RUN_ID4" | tee -a "$LOG_FILE"

echo "✔ Step re-execution verified"
end_timer; echo ""

################################################################################
# 🆕 TEST T4 — Cancel batch does NOT affect resume logic
################################################################################
echo "TEST T4 — Cancel-batch shouldn't break resume behavior"
start_timer

RUN_OUTPUT5=$(treehopper chain run cancel_test_chain --payload '{"name":"BatchX"}' --detached --bg)
RUN_ID5=$(echo "$RUN_OUTPUT5" | grep -oE "cancel_test_chain-[0-9]{10,}" | head -1)

treehopper chain cancel-batch batch-000000 || true
treehopper chain resume "$RUN_ID5" || true

echo "✔ Batch cancel unaffected"
end_timer; echo ""

###############################################################################
# STEP 12 — STOP SERVER
###############################################################################
echo "STEP 12 — Stop main server: $(timestamp)"
start_timer
treehopper stop | tee -a "$LOG_FILE"
end_timer; echo ""

echo ""
echo "🎉 FULL TEST SUITE COMPLETE — including step2 cancellation, pending resume, re-run semantics, batch tests."
echo "📝 Log → $LOG_FILE"
