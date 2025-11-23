#!/bin/bash
set +e

LOG_FILE="./chain_test_$(date +%Y%m%d_%H%M%S).log"
echo "🧪 Treehopper Full Chain Test Started" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 1 — WORKSPACE
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 1 — Workspace Directory" | tee -a "$LOG_FILE"
read -p "📂 Enter workspace directory (formatter/, summarizer/, test_file.txt): " WS

if [[ ! -d "$WS" ]]; then
  echo "❌ Invalid directory — exiting" | tee -a "$LOG_FILE"
  exit 1
fi
echo "➡ Using workspace: $WS" | tee -a "$LOG_FILE"
cd "$WS"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 2 — SERVER
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 2 — Start Treehopper Server" | tee -a "$LOG_FILE"
treehopper run --bg | tee -a "$LOG_FILE"
sleep 4

###############################################################################
# STEP 3 — LINT
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 3 — Lint Agents" | tee -a "$LOG_FILE"
treehopper lint formatter | tee -a "$LOG_FILE"
treehopper lint summarizer | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 4 — BUILD
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 4 — Build Agents" | tee -a "$LOG_FILE"
treehopper build formatter | tee -a "$LOG_FILE"
treehopper build summarizer | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 5 — PUSH FILE
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 5 — Push Input File" | tee -a "$LOG_FILE"

OUTPUT=$(treehopper push-file formatter test_file.txt | tee -a "$LOG_FILE")

# Extract shared file path
FILE_PATH=$(echo "$OUTPUT" | grep -oE '"file_path": "[^"]+"' | sed 's/"file_path": "//;s/"$//')

echo "📌 Extracted FILE_PATH: $FILE_PATH" | tee -a "$LOG_FILE"
if [[ -z "$FILE_PATH" ]]; then
  echo "❌ Failed to detect FILE_PATH — stopping" | tee -a "$LOG_FILE"
  exit 1
fi

echo "🔁 Restarting server to register shared state" | tee -a "$LOG_FILE"
treehopper restart | tee -a "$LOG_FILE"
sleep 4

###############################################################################
# STEP 6 — BUILD CHAIN
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 6 — Build Chain (exec_summ)" | tee -a "$LOG_FILE"
treehopper chain build exec_summ formatter summarizer | tee -a "$LOG_FILE"
echo "🔁 Restarting server to register chain endpoint" | tee -a "$LOG_FILE"
treehopper restart | tee -a "$LOG_FILE"
sleep 4

###############################################################################
# STEP 7 — RUN CHAIN (CLI)
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 7 — Execute Chain via CLI (explicit payload)" | tee -a "$LOG_FILE"

echo "{\"file_path\": \"$FILE_PATH\"}" > /tmp/payload.json
treehopper chain run exec_summ --payload-file /tmp/payload.json | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 8 — LOGS
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 8 — Show Chain Logs" | tee -a "$LOG_FILE"
treehopper chain logs exec_summ | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 9 — PYTHON (HTTP EXEC)
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 9 — Execute via Python HTTP POST" | tee -a "$LOG_FILE"

python3 - <<EOF | tee -a "$LOG_FILE"
import requests
url = "http://localhost:1560/api/v1/chains/exec_summ"
headers = {"x-api-key": "demo-key-123"}
payload = {"file_path": "$FILE_PATH"}
resp = requests.post(url, json=payload, headers=headers)
print("HTTP Response:", resp.text)
EOF
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 10 — LOGS AGAIN
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 10 — Show Logs Again" | tee -a "$LOG_FILE"
treehopper chain logs exec_summ | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 11 — AUTO PAYLOAD {}
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 11 — Execute with {} (auto path detection test)" | tee -a "$LOG_FILE"
python3 - <<EOF | tee -a "$LOG_FILE"
import requests
resp = requests.post("http://localhost:1560/api/v1/chains/exec_summ", json={}, headers={"x-api-key": "demo-key-123"})
print("Auto Payload Response:", resp.text)
EOF
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 12 — SAVE
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 12 — Logs Saved" | tee -a "$LOG_FILE"
echo "📝 Saved → $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 13 — HEALTH
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 13 — Check Health" | tee -a "$LOG_FILE"
curl -s http://localhost:1560/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 14 — STOP
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "STEP 14 — Stop Treehopper Server" | tee -a "$LOG_FILE"
treehopper stop | tee -a "$LOG_FILE"
echo "🎉 Chain Workflow Test Complete" | tee -a "$LOG_FILE"
