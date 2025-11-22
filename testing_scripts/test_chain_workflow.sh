#!/bin/bash

set +e  # do NOT stop on error, we log everything

LOG_FILE="./chain_test_$(date +%Y%m%d_%H%M%S).log"
echo "🧪 Treehopper Full Chain Test Started" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE"

# 1. Ask for workspace directory
read -p "📂 Enter path of workspace directory (contains formatter/, summarizer/ & test_file.txt): " WS

if [ ! -d "$WS" ]; then
  echo "❌ Workspace does not exist: $WS" | tee -a "$LOG_FILE"
  exit 1
fi

cd "$WS"

echo "➡ Workspace: $WS" | tee -a "$LOG_FILE"

# 2. Start server (background)
echo "🚀 Starting Treehopper server..." | tee -a "$LOG_FILE"
treehopper run --bg
sleep 4

# 3. Lint both agents
echo "🔍 Linting formatter + summarizer" | tee -a "$LOG_FILE"
treehopper lint formatter | tee -a "$LOG_FILE"
treehopper lint summarizer | tee -a "$LOG_FILE"

# 4. Build agents
echo "🏗 Building agents" | tee -a "$LOG_FILE"
treehopper build formatter | tee -a "$LOG_FILE"
treehopper build summarizer | tee -a "$LOG_FILE"

# 5. Push file to formatter
echo "🗂 Pushing test_file.txt to formatter" | tee -a "$LOG_FILE"
treehopper push-file formatter test_file.txt | tee -a "$LOG_FILE"

# 6. Build chain
echo "🔗 Building chain exec_summ (formatter -> summarizer)" | tee -a "$LOG_FILE"
treehopper chain build exec_summ formatter summarizer | tee -a "$LOG_FILE"

# 7. Run chain
echo "▶ Running chain exec_summ" | tee -a "$LOG_FILE"
treehopper chain run exec_summ | tee -a "$LOG_FILE"

# 8. Show chain logs
echo "📜 Logs after first execution" | tee -a "$LOG_FILE"
treehopper chain logs exec_summ | tee -a "$LOG_FILE"

# 9. Python request to list chains
echo "🐍 Python request — list chains" | tee -a "$LOG_FILE"
python3 - <<EOF | tee -a "$LOG_FILE"
import requests
r = requests.get("http://localhost:1560/api/v1/dev/chains", headers={"x-api-key":"demo-key-123"})
print("Chains Response:", r.text)
EOF

# 10. View logs again
treehopper chain logs exec_summ | tee -a "$LOG_FILE"

# 11. Python request to run chain again
echo "🐍 Python request — execute chain" | tee -a "$LOG_FILE"
python3 - <<EOF | tee -a "$LOG_FILE"
import requests, json
payload = {}  # auto input — formatter will use pushed file
r = requests.post("http://localhost:1560/api/v1/chains/exec_summ", json=payload, headers={"x-api-key":"demo-key-123"})
print("Chain Execution Response:", r.text)
EOF

# 12. Log everything (already handled by tee)
echo "📝 All logs saved to $LOG_FILE"

# 13. Check server status
echo "💡 Checking Treehopper status" | tee -a "$LOG_FILE"
curl -s http://localhost:1560/api/v1/sys/health -H "x-api-key: demo-key-123" | tee -a "$LOG_FILE"

# 14. Stop server
echo "🛑 Stopping server" | tee -a "$LOG_FILE"
treehopper stop | tee -a "$LOG_FILE"

echo "🎉 Completed full chain workflow test" | tee -a "$LOG_FILE"
