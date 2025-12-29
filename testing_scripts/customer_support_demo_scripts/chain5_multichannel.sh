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
th agent create classifier --from-template intent_classifier
th agent create enricher --from-template context_enricher
th agent create urgency --from-template urgency_detector
th agent create searcher --from-template knowledge_search
th agent create responder --from-template llm_responder
th agent create sender --from-template response_sender

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier
th agent build enricher
th agent build urgency
th agent build searcher
th agent build responder
th agent build sender

# Build chain with parallel processing + enricher
echo "⛓️  Building omnichannel chain..."
th chain build-steps omnichannel \
  --step classify sequential classifier \
  --step enrich sequential enricher \
  --step analyze parallel urgency searcher \
    --merge-agent smart_data_aggregator \
  --step respond sequential responder \
  --step send sequential sender

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
