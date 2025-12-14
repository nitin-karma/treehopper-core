#!/usr/bin/env bash
set -e

echo "======================================"
echo "Treehopper Cancel / Resume Test Suite"
echo "======================================"

PDF_PAYLOAD='{"file_path":"shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}'

echo ""
echo "1️⃣ Build sequential chain"
th chain build doc_flow pdf_extractor content_analyzer report_generator || true

echo ""
echo "2️⃣ Build multistep chain"
th chain build-steps doc_intel \
  --step extract sequential pdf_extractor \
  --step analyze parallel \
      --merge-agent smart_data_aggregator \
      content_analyzer keyword_extractor \
  --step report sequential report_generator || true

echo ""
echo "3️⃣ Build dynamic routed chain"
th chain build-steps dynamic_doc_intel \
  --step extract sequential pdf_extractor \
  --step analyze parallel \
      --merge-agent smart_data_aggregator \
      content_analyzer keyword_extractor \
      --route-on '[{"if":"output.sentiment==\"negative\"","goto":"alert_team"}]' \
  --step alert_team sequential teams_notifier || true

echo ""
echo "--------------------------------------"
echo "RUN + CANCEL + RESUME TEST"
echo "--------------------------------------"

echo ""
echo "▶ Running dynamic_doc_intel (detached)"
RUN_OUTPUT=$(th chain run dynamic_doc_intel \
  --payload "$PDF_PAYLOAD" \
  --detached --bg)

echo "$RUN_OUTPUT"

RUN_ID=$(echo "$RUN_OUTPUT" | grep "RUN_ID:" | awk '{print $2}')

echo ""
echo "⏳ Sleeping 2 seconds before cancel..."
sleep 2

echo ""
echo "🛑 Cancelling run_id=$RUN_ID"
th chain cancel --run "$RUN_ID"

echo ""
echo "📄 Checking status after cancel"
sleep 1
cat ~/.treehopper/registry/chains/*/runs/${RUN_ID}.json | jq .

echo ""
echo "▶ Resuming run_id=$RUN_ID"
th chain resume "$RUN_ID"

echo ""
echo "📄 Checking status after resume"
sleep 1
cat ~/.treehopper/registry/chains/*/runs/${RUN_ID}.json | jq .

echo ""
echo "--------------------------------------"
echo "SWEEP RESUME TEST"
echo "--------------------------------------"

echo "▶ Running sweep-resume"
th chain sweep-resume

echo ""
echo "✅ All tests completed"
