#!/usr/bin/env bash
set -e

echo "🔧 Bootstrapping Treehopper test environment"

export TH_ROOT=${TH_ROOT:-/tmp/treehopper-test}
export TREEHOPPER_RUNTIME_DIR=$TH_ROOT/runtime
export TREEHOPPER_CANCEL_DIR=$TH_ROOT/runtime/cancels

rm -rf "$TH_ROOT"
mkdir -p "$TH_ROOT"

# Build agents
treehopper build examples/pdf_extractor
treehopper build examples/content_analyzer
treehopper build examples/report_generator
treehopper build examples/keyword_extractor
treehopper build examples/teams_notifier

# Build chains
treehopper chain build doc_flow pdf_extractor content_analyzer report_generator

treehopper chain build-steps dynamic_doc_intel \
  --step extract sequential pdf_extractor \
  --step analyze parallel \
      --merge-agent smart_data_aggregator \
      content_analyzer keyword_extractor \
      --route-on '[{"if":"output.sentiment==\"negative\"","goto":"alert_team"}]' \
  --step alert_team sequential teams_notifier

# Push file
treehopper push-file pdf_extractor examples/files/contract.pdf

# Start servers
treehopper restart
#treehopper chain start doc_flow --bg
#treehopper chain start dynamic_doc_intel --bg --port 20316

echo "✅ Treehopper test environment ready at $TH_ROOT"
