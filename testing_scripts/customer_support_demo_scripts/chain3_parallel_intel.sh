#!/bin/bash
# ============================================================================
# Chain 3: Parallel Intelligence (WITH CONTEXT ENRICHER)
# ============================================================================
# 5-step chain with parallel analysis and data normalization
# enricher placed AFTER classify, BEFORE parallel step
# ============================================================================

set -e

echo "🔗 Chain 3: Parallel Intelligence (with enricher)"
echo "================================================="

# Create workspace
th workspace create support_parallel
cd support_parallel

# Create agents
echo "📦 Creating agents..."
th agent create classifier --from-template intent_classifier
th agent create enricher --from-template context_enricher
th agent create urgency --from-template urgency_detector
th agent create searcher --from-template knowledge_search
th agent create responder --from-template llm_responder

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier
th agent build enricher
th agent build urgency
th agent build searcher
th agent build responder

# Build chain with parallel step + enricher + merge
echo "⛓️  Building chain with parallel analysis..."
th chain build-steps parallel_intel \
  --step classify sequential classifier \
  --step enrich sequential enricher \
  --step analyze parallel urgency searcher \
    --merge-agent smart_data_aggregator \
  --step respond sequential responder

echo ""
echo "✅ Chain 3 built: parallel_intel"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "  2. enrich(enricher) → outputs: query, customer_message ✅"
echo "  3. [urgency(text) + searcher(query) in PARALLEL] ✅"
echo "  4. smart_data_aggregator (merge)"
echo "  5. respond(customer_message)"
echo ""
echo "🌉 Bridge Pattern:"
echo "  enricher prepares data BEFORE parallel step"
echo "  urgency gets 'text', searcher gets 'query' ✅"
echo ""
echo "Key Feature:"
echo "  Parallel execution with proper input resolution via enricher"
echo ""
echo "Test with:"
echo "  th chain start parallel_intel --bg --port 20300"
echo "  th chain run parallel_intel --payload '{\"text\":\"URGENT: Need help now!\"}' --detached --port 20300"
echo ""
