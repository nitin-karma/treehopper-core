#!/bin/bash
set +e   # do NOT exit on failure (we are testing)
echo ""
LOG_FILE="./chain_test_$(date +%Y%m%d_%H%M%S).log"
echo "🧪 Treehopper Full Chain Test Started" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE"

##############################################
# STEP 1 — Ask for workspace
##############################################
echo -e "\nSTEP 1 — Workspace directory"
read -p "📂 Enter workspace path (formatter/, summarizer/, test_file.txt): " WS
if [ ! -d "$WS" ]; then
  echo "❌ Workspace not found: $WS" | tee -a "$LOG_FILE"
  exit 1
fi
cd "$WS"
echo "➡ Using workspace: $WS" | tee -a "$LOG_FILE"

##############################################
# STEP 2 — Start server
##############################################
echo -e "\nSTEP 2 — Start Treehopper server"
treehopper run --bg | tee -a "$LOG_FILE"
sleep 4

##############################################
# STEP 3 — Lint agents
##############################################
echo -e "\nSTEP 3 — Lint agents"
treehopper lint formatter | tee -a "$LOG_FILE"
treehopper lint summarizer | tee -a "$LOG_FILE"

##############################################
# STEP 4 — Build agents
##############################################
echo -e "\nSTEP 4 — Build agents"
treehopper build formatter | tee -a "$LOG_FILE"
treehopper build summarizer | tee -a "$LOG_FILE"

##############################################
# STEP 5 — Push file
##############################################
echo -e "\nSTEP 5 — Push input file"
OUTPUT=$(treehopper push-file formatter test_file.txt | tee -a "$LOG_FILE")

# Extract the shared/…/file.txt relative path safely
FILE_PATH=$(echo "$OUTPUT" | grep -o '"file_path":[^"]*' | sed -E 's/.*"file_path": "([^"]+)".*/\1/')
echo "📌 Extracted FILE_PATH: $FILE_PATH" | tee -a "$LOG_FILE"

# Restart server (so chain endpoints can load)
echo "🔁 Restarting server..."
treehopper restart | tee -a "$LOG_FILE"
sleep 4

##############################################
# STEP 6 — Build chain
##############################################
echo -e "\nSTEP 6 — Build chain"
treehopper chain build exec_summ formatter summarizer | tee -a "$LOG_FILE"

# Restart server again for new chain endpoint registration
echo "🔁 Restarting server..."
treehopper restart | tee -a "$LOG_FILE"
sleep 4

##############################################
# STEP 7 — Execute chain via CLI with explicit payload
##############################################
echo -e "\nSTEP 7 — Execute chain (explicit payload)"
echo "{\"file_path\": \"$FILE_PATH\"}" > /tmp/payload.json
treehopper chain run exec_summ --payload-file /tmp/payload.json | tee -a "$LOG_FILE"

echo -e "\n📜 Tail server.log" | tee -a "$LOG_FILE"
tail -n 40 "$HOME/.treehopper/runtime/server.log" >> "$LOG_FILE"

##############################################
# STEP 8 — Show chain logs
##############################################
echo -e "\nSTEP 8 — Show chain logs"
treehopper chain logs exec_summ | tee -a "$LOG_FILE"

##############################################
# STEP 9 — Execute via Python (HTTP)
##############################################
echo -e "\nSTEP 9 — Python HTTP exec"
python3 - <<EOF | tee -a "$LOG_FILE"
import requests
headers={"x-api-key":"demo-key-123"}
payload={"file_path": r"$FILE_PATH"}
resp=requests.post("http://localhost:1560/api/v1/chains/exec_summ", json=payload, headers=headers)
print("Response:", resp.text)
EOF

echo -e "\n📜 Tail server.log" | tee -a "$LOG_FILE"
tail -n 40 "$HOME/.treehopper/runtime/server.log" >> "$LOG_FILE"

##############################################
# STEP 10 — Logs again
##############################################
echo -e "\nSTEP 10 — Chain logs (2nd time)"
treehopper chain logs exec_summ | tee -a "$LOG_FILE"

##############################################
# STEP 11 — Execute with empty payload {}
##############################################
echo -e "\nSTEP 11 — HTTP auto payload test"
python3 - <<EOF | tee -a "$LOG_FILE"
import requests
resp=requests.post("http://localhost:1560/api/v1/chains/exec_summ",
                   json={}, headers={"x-api-key":"demo-key-123"})
print("Response:", resp.text)
EOF

##############################################
# STEP 12 — Final log summary
##############################################
echo -e "\nSTEP 12 — Logs saved"
echo "📝 Saved results → $LOG_FILE" | tee -a "$LOG_FILE"

##############################################
# STEP 13 — Check server health
##############################################
echo -e "\nSTEP 13 — Check health"
curl -s http://localhost:1560/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"

##############################################
# STEP 14 — Stop server
##############################################
echo -e "\nSTEP 14 — Stop server"
treehopper stop | tee -a "$LOG_FILE"

echo -e "\n🎉 Completed full chain workflow test"
