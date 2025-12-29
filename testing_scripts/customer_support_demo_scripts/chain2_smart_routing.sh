#!/bin/bash
# ============================================================================
# Chain 2: Smart Routing (WITH CONTEXT ENRICHER)
# ============================================================================
# 5-step chain with conditional routing and data normalization
# enricher bridges: classifier outputs → query, customer_message
# ============================================================================

set -e

echo "🔗 Chain 2: Smart Routing (with enricher)"
echo "========================================="

# Create workspace
th workspace create support_routing
cd support_routing

# Create agents
echo "📦 Creating agents..."
th agent create classifier --from-template intent_classifier
th agent create enricher --from-template context_enricher
th agent create searcher --from-template knowledge_search
th agent create responder --from-template llm_responder
th agent create alerter --from-template alert_manager

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier
th agent build enricher
th agent build searcher
th agent build responder
th agent build alerter

# Build chain with routing + enricher
# Route-on MUST be applied to the step BEFORE the target
echo "⛓️  Building chain with routing..."
th chain build-steps smart_routing \
  --step classify sequential classifier \
    --route-on '[{"if":"output.intent==\"bug_report\"","goto":"escalate"}]' \
  --step enrich sequential enricher \
  --step search sequential searcher \
  --step respond sequential responder \
  --step escalate sequential alerter

echo ""
echo "✅ Chain 2 built: smart_routing"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "     IF intent == bug_report → GOTO escalate"
echo "  2. enrich(enricher) → outputs: query, customer_message ✅"
echo "  3. search(searcher) → inputs: query ✅"
echo "  4. respond(responder) → inputs: customer_message ✅"
echo "  5. escalate(alerter)"
echo ""
echo "🌉 Bridge Pattern:"
echo "  enricher ensures searcher and responder get properly formatted inputs"
echo ""
echo "Test with:"
echo "  th chain start smart_routing --bg --port 20200"
echo "  th chain run smart_routing --payload '{\"text\":\"CRITICAL BUG: System down!\"}' --detached --port 20200"
echo ""
