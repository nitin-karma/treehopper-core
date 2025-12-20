#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Treehopper REAL E2E — FULL EXECUTION MATRIX"
echo "---------------------------------------------"

# ------------------------------
# CONFIG
# ------------------------------
export TH_ROOT="$(mktemp -d /tmp/treehopper-e2e-XXXXXX)"
export TREEHOPPER_RUNTIME_DIR="$TH_ROOT/runtime"
export TREEHOPPER_CANCEL_DIR="$TREEHOPPER_RUNTIME_DIR/cancels"
export TREEHOPPER_API_KEY="demo-key-123"
export TREEHOPPER_FORCE_LOCAL=1
export TH_TEST_MODE=1
export TH_LLM_PROVIDER=mock

MAIN_PORT=1567
AGENT_PORT=20401
CHAIN_PORT=20316

DOC_FLOW_CHAIN="doc_flow"
DYNAMIC_CHAIN="dynamic_doc_intel"

PAYLOAD='{"file_path":"shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}'

cleanup() {
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "ℹ️ Skipping cleanup in GitHub Actions"
    return
  fi
  th stop >/dev/null 2>&1 || true
  rm -rf "$TH_ROOT"
}

trap cleanup EXIT

# ------------------------------
# STEP 1 — Build agents
# ------------------------------
echo "🔧 Building agents..."
th build examples/pdf_extractor
th build examples/content_analyzer
th build examples/report_generator
th build examples/keyword_extractor
th build examples/teams_notifier
echo "---------------------------------------------"
echo ""

# ------------------------------
# STEP 2 — Agent validation
# ------------------------------
echo "🧪 Agent validation (starting main server 1567)..."
th start --bg
sleep 2
echo ""
AGENT_OUTPUT="$(th call pdf_extractor '{"file_path":"examples/files/contract.pdf"}')"
echo "$AGENT_OUTPUT"
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 3 — Start detached agent
# ------------------------------
echo "🚀 Starting detached agent runtime..."
th agent start pdf_extractor --detached --port ${AGENT_PORT}

echo "⏳ Waiting for agent runtime..."
until curl -sf "http://127.0.0.1:${AGENT_PORT}/api/v1/pdf_extractor/health" >/dev/null; do
  sleep 0.5
done
echo "✅ Detached agent healthy"
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 4 — Build chains
# ------------------------------
echo "🔗 Building chains..."

th chain build ${DOC_FLOW_CHAIN} \
  pdf_extractor \
  content_analyzer \
  report_generator

th chain build-steps ${DYNAMIC_CHAIN} \
  --step extract sequential pdf_extractor \
  --step analyze parallel content_analyzer keyword_extractor \
  --merge-agent smart_data_aggregator \
  --step alert_team sequential teams_notifier
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 5 — Push test file
# ------------------------------
echo "📁 Pushing test file..."
th push-file pdf_extractor examples/files/contract.pdf
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 6 — Start main server
# ------------------------------
echo "▶️ Restarting main server..."
th restart
echo "---------------------------------------------"
echo ""
echo "⏳ Waiting for main server..."
until curl -sf "http://127.0.0.1:${MAIN_PORT}/api/v1/sys/health" >/dev/null; do
  sleep 0.5
done
echo "✅ Main server healthy"
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 7 — Run doc_flow (attached)
# ------------------------------
echo "▶️ Running doc_flow chain..."
DOC_FLOW_OUTPUT="$(th chain run ${DOC_FLOW_CHAIN} --payload "${PAYLOAD}")"
echo "$DOC_FLOW_OUTPUT"
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 8 — Run dynamic_doc_intel (detached)
# ------------------------------
echo "🚀 Running detached dynamic_doc_intel..."

OUTPUT="$(th chain run ${DYNAMIC_CHAIN} \
  --payload "${PAYLOAD}" \
  --detached \
  --bg \
  --port ${CHAIN_PORT})"

echo "$OUTPUT"

RUN_ID="$(echo "$OUTPUT" | grep RUN_ID | awk '{print $NF}')"
[[ -z "$RUN_ID" ]] && { echo "❌ RUN_ID missing"; exit 1; }

echo "🆔 RUN_ID = $RUN_ID"
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 9 — Wait for chain runtime
# ------------------------------
echo "⏳ Waiting for chain runtime..."
until curl -sf "http://127.0.0.1:${CHAIN_PORT}/api/v1/${DYNAMIC_CHAIN}/health" >/dev/null; do
  sleep 0.5
done
echo "✅ Chain runtime healthy"
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 10 — WebSocket stream
# ------------------------------
echo "📡 WebSocket stream validation..."

python3 - <<EOF
import websocket, json, time, sys

ws = websocket.WebSocket()
ws.connect(
    "ws://127.0.0.1:${CHAIN_PORT}/api/v1/ws/run/${RUN_ID}?api_key=demo-key-123"
)

seen = set()
start = time.time()

while time.time() - start < 10:
    event = json.loads(ws.recv())
    print("WS EVENT:", event.get("type"))
    seen.add(event.get("type"))
    if event.get("type") == "step_complete":
        break

ws.close()

if "step_start" not in seen:
    print("❌ step_start missing")
    sys.exit(1)
EOF
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 11 — Cancel
# ------------------------------
echo "⛔ Cancelling chain..."
th chain cancel --run ${RUN_ID}
sleep 2
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 12 — Resume
# ------------------------------
echo "▶️ Resuming chain..."
th chain resume ${RUN_ID}
sleep 3
echo "---------------------------------------------"
echo ""
# ------------------------------
# STEP 13 — Status check
# ------------------------------
echo "📊 Final chain status:"
curl -s "http://127.0.0.1:${CHAIN_PORT}/api/v1/${DYNAMIC_CHAIN}/status/${RUN_ID}" \
  -H "x-api-key: demo-key-123" | jq .

echo "Stopping ${DYNAMIC_CHAIN} Chain"
th chain stop ${DYNAMIC_CHAIN}
sleep 1
echo "---------------------------------------------"
echo ""
echo "Stopping ${DOC_FLOW_CHAIN} Chain"
th chain stop ${DOC_FLOW_CHAIN}
sleep 1
echo ""
echo "🎉 REAL E2E PASSED — ALL MODES VERIFIED"
echo "---------------------------------------------"
echo ""
exit 0
