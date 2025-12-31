#!/bin/bash
# ============================================================================
# Chain 3: Parallel Intelligence
# ============================================================================
# 5-step chain with parallel analysis and data normalization
# enricher placed AFTER classify, BEFORE parallel step
# ============================================================================

set -e

echo "🔗 Chain 3: Parallel Intelligence"
echo "================================="

# Create workspace
th workspace create support_parallel
cd support_parallel

# Create agents
echo "📦 Creating agents..."
th agent create classifier_c3 --from-template intent_classifier
th agent create enricher_c3 --from-template context_enricher
th agent create urgency_c3 --from-template urgency_detector
th agent create searcher_c3 --from-template knowledge_search
th agent create responder_c3 --from-template llm_responder

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier_c3
th agent build enricher_c3
th agent build urgency_c3
th agent build searcher_c3
th agent build responder_c3

th restart
sleep 2

th push-file searcher_c3 ../synthetic_data/kb.json
th push-file searcher_c3 ../synthetic_data/support_tickets.json
th push-file searcher_c3 ../synthetic_data/test_scenarios.json


# Build chain with parallel step + merge
echo "⛓️  Building chain with parallel analysis..."
th chain build-steps parallel_intel \
  --step classify sequential classifier_c3 \
  --step enrich sequential enricher_c3 \
  --step analyze parallel urgency_c3 searcher_c3 \
    --merge-agent smart_data_aggregator \
  --step respond sequential responder_c3


echo ""
echo "✅ Chain 3 built: parallel_intel"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "  2. [urgency(text) + searcher(query) in PARALLEL] ✅"
echo "  3. smart_data_aggregator (merge)"
echo "  4. respond(customer_message)"
echo ""
echo "  urgency gets 'text', searcher gets 'query' ✅"
echo ""
echo "Key Feature:"
echo "  Parallel execution with proper input resolution "
echo ""
echo "Test with:"
echo "  th chain start parallel_intel --bg --port 20300"
echo "  th chain run parallel_intel --payload '{\"text\":\"URGENT: Need help now!\"}' --detached --port 20300"
echo ""
