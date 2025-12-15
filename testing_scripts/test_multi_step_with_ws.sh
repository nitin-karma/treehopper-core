#!/usr/bin/env bash
set -e

echo "======================================"
echo "Treehopper Cancel / Resume + WS Test"
echo "======================================"

PDF_PAYLOAD='{"file_path":"shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}'

echo ""
echo "▶ Running dynamic_doc_intel (detached)"
RUN_OUTPUT=$(th chain run dynamic_doc_intel \
  --payload "$PDF_PAYLOAD" \
  --detached --bg)

echo "$RUN_OUTPUT"

RUN_ID=$(echo "$RUN_OUTPUT" | grep "RUN_ID:" | awk '{print $2}')
echo "RUN_ID=$RUN_ID"

# -------------------------------
# Start WebSocket listener FIRST
# -------------------------------
CHAIN_PORT=$(ls ~/.treehopper/runtime | grep det_chain_dynamic_doc_intel | xargs -I{} \
  cat ~/.treehopper/runtime/{} | cut -d: -f2)

echo ""
echo "🔌 Connecting WebSocket (run_id=$RUN_ID, port=$CHAIN_PORT)"
wscat -c "ws://localhost:${CHAIN_PORT}/api/v1/ws/run/${RUN_ID}" > ws.log &

WS_PID=$!

sleep 1

echo ""
echo "⏳ Sleeping 1 second before cancel..."
sleep 1

echo ""
echo "🛑 Cancelling run_id=$RUN_ID"
th chain cancel --run "$RUN_ID"

sleep 2

echo ""
echo "📄 Run file after cancel:"
cat ~/.treehopper/registry/chains/*/runs/${RUN_ID}.json | jq .

echo ""
echo "▶ Resuming run_id=$RUN_ID"
th chain resume "$RUN_ID"

sleep 2

echo ""
echo "📄 Run file after resume:"
cat ~/.treehopper/registry/chains/*/runs/${RUN_ID}.json | jq .

echo ""
echo "🧹 Cleaning up WebSocket"
kill $WS_PID || true

echo ""
echo "✅ WS + Cancel + Resume test completed"
