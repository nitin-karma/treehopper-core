#!/bin/bash
# ============================================================================
# Chain 5: Multi-Channel Processing (WITH CONTEXT ENRICHER)
# ============================================================================
# 6-step chain with parallel processing and data normalization
# enricher placed BEFORE parallel step for proper input resolution
# ============================================================================

set -e

echo "🔗 Chain 5: Multi-Channel Processing (with enricher)"
echo "===================================================="

# Create workspace
th workspace create support_omnichannel
cd support_omnichannel

# Create agents
echo "📦 Creating agents..."
th agent create classifier_c5 --from-template intent_classifier
th agent create enricher_c5 --from-template context_enricher
th agent create urgency_c5 --from-template urgency_detector
th agent create searcher_c5 --from-template knowledge_search
th agent create responder_c5 --from-template llm_responder
th agent create sender_c5 --from-template response_sender

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier_c5
th agent build enricher_c5
th agent build urgency_c5
th agent build searcher_c5
th agent build responder_c5
th agent build sender_c5

th restart
sleep 2

th push-file searcher_c5 ../synthetic_data/kb.json
th push-file searcher_c5 ../synthetic_data/support_tickets.json
th push-file searcher_c5 ../synthetic_data/test_scenarios.json


# Build chain with parallel processing + enricher
echo "⛓️  Building omnichannel chain..."
th chain build-steps omnichannel \
  --step classify sequential classifier_c5 \
  --step enrich sequential enricher_c5 \
  --step analyze parallel urgency_c5 searcher_c5 \
    --merge-agent smart_data_aggregator \
  --step respond sequential responder_c5 \
  --step send sequential sender_c5

echo ""
echo "✅ Chain 5 built: omnichannel"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "  2. enrich(enricher) → outputs: query, customer_message, recipient ✅"
echo "  3. [urgency(text) + searcher(query) in PARALLEL] ✅"
echo "  4. smart_data_aggregator (merge)"
echo "  5. respond(customer_message) → outputs: response ✅"
echo "  6. send(sender) → inputs: recipient, message ✅"
echo ""
echo "🌉 Bridge Pattern:"
echo "  enricher provides:"
echo "  - query for searcher (parallel step)"
echo "  - customer_message for responder"
echo "  - recipient for sender"
echo ""
echo "Test with:"
echo "  th chain start omnichannel --bg --port 20500"
echo "  th chain run omnichannel --payload '{\"text\":\"Need assistance\"}' --detached --port 20500"
echo ""
