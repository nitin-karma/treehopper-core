#!/bin/bash
set +e
LOG_FILE="./chain_test_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo "🧪 Treehopper Full Chain Test Started"
echo "Log file: $LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 1 — Workspace directory
###############################################################################
echo "STEP 1 — Workspace directory" | tee -a "$LOG_FILE"
read -p "📂 Enter workspace path (formatter/, summarizer/, test_file.txt): " WS

if [ ! -d "$WS" ]; then
  echo "❌ Workspace not found" | tee -a "$LOG_FILE"
  exit 1
fi
cd "$WS"
echo "➡ Using workspace: $WS" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 2 — Start Treehopper server
###############################################################################
echo "STEP 2 — Start main server" | tee -a "$LOG_FILE"
treehopper run --bg | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
sleep 4

###############################################################################
# STEP 3 — Lint agents
###############################################################################
echo "STEP 3 — Lint agents" | tee -a "$LOG_FILE"
treehopper lint formatter | tee -a "$LOG_FILE"
treehopper lint summarizer | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 4 — Build agents
###############################################################################
echo "STEP 4 — Build agents" | tee -a "$LOG_FILE"
treehopper build formatter | tee -a "$LOG_FILE"
treehopper build summarizer | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 5 — Push file into formatter & detect FILE_PATH
###############################################################################
echo "STEP 5 — Push file" | tee -a "$LOG_FILE"
PUSH=$(treehopper push-file formatter test_file.txt)
echo "$PUSH" | tee -a "$LOG_FILE"

FILE_PATH=$(echo "$PUSH" | sed -n 's/.*"file_path":[[:space:]]*"\(.*\)".*/\1/p' | head -n1)
if [ -z "$FILE_PATH" ]; then
  echo "❌ Could not extract FILE_PATH" | tee -a "$LOG_FILE"
  exit 1
fi
echo "📌 Extracted FILE_PATH: $FILE_PATH" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

treehopper restart | tee -a "$LOG_FILE"
sleep 4

###############################################################################
# STEP 6 — Build chain
###############################################################################
echo "STEP 6 — Build chain" | tee -a "$LOG_FILE"
treehopper chain build exec_summ formatter summarizer | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

treehopper restart | tee -a "$LOG_FILE"
sleep 4

###############################################################################
# STEP 7 — Test agents via CLI
###############################################################################
echo "STEP 7 — Call formatter agent directly" | tee -a "$LOG_FILE"
treehopper call /api/v1/agents/formatter "{\"file_path\": \"$FILE_PATH\"}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "STEP 8 — Call summarizer agent directly" | tee -a "$LOG_FILE"
treehopper call /api/v1/agents/summarizer '{"formatted": "dummy"}' | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 9 — Execute chain via CLI
###############################################################################
echo "STEP 9 — Execute chain via CLI" | tee -a "$LOG_FILE"
treehopper chain run exec_summ --payload "{\"file_path\":\"$FILE_PATH\"}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

tail -n 40 "$HOME/.treehopper/runtime/server.log" >> "$LOG_FILE" 2>/dev/null

###############################################################################
# STEP 10 — Chain logs
###############################################################################
echo "STEP 10 — Show chain logs" | tee -a "$LOG_FILE"
treehopper chain logs exec_summ | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 11 — Execute chain via Python HTTP
###############################################################################
echo "STEP 11 — Execute chain via Python HTTP" | tee -a "$LOG_FILE"
python3 - <<EOF | tee -a "$LOG_FILE"
import requests, json
url="http://localhost:1560/api/v1/chains/exec_summ"
headers={"x-api-key":"demo-key-123"}
payload={"file_path": "$FILE_PATH"}
print("POST", url, "→", json.dumps(payload))
r=requests.post(url, json=payload, headers=headers)
print("Status:", r.status_code)
print("Response:", r.text)
EOF
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 12 — Agent detached runtime test
###############################################################################
echo "STEP 12 — Agent detached runtime test" | tee -a "$LOG_FILE"

treehopper agent run formatter --detached | tee -a "$LOG_FILE"
PORT=$(treehopper agent port formatter)
URL="http://localhost:$PORT/api/v1/formatter/run"

python3 - <<EOF | tee -a "$LOG_FILE"
import requests
r=requests.post("$URL", json={"file_path": "$FILE_PATH"}, headers={"x-api-key":"demo-key-123"})
print("DETACHED-FORMATTER:", r.status_code, r.text)
EOF
treehopper agent stop formatter | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 13 — Chain detached runtime test
###############################################################################
echo "STEP 13 — Chain detached runtime test" | tee -a "$LOG_FILE"

treehopper chain run exec_summ --detached | tee -a "$LOG_FILE"
CHAIN_PORT=$(treehopper chain port exec_summ)
CURL_URL="http://localhost:$CHAIN_PORT/api/v1/chains/exec_summ/run"

python3 - <<EOF | tee -a "$LOG_FILE"
import requests
r=requests.post("$CURL_URL", json={"file_path": "$FILE_PATH"}, headers={"x-api-key":"demo-key-123"})
print("DETACHED-CHAIN:", r.status_code, r.text)
EOF
treehopper chain stop exec_summ | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

###############################################################################
# STEP 14 — Final health & cleanup
###############################################################################
echo "STEP 14 — Final health & stop" | tee -a "$LOG_FILE"
curl -s http://localhost:1560/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"
treehopper stop | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "🎉 Completed full chain + detached agent + detached chain test"
echo "📝 Log saved → $LOG_FILE"
