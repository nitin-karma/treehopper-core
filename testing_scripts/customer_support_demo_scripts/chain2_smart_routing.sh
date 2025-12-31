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
th agent create classifier_c2 --from-template intent_classifier
th agent create searcher_c2 --from-template knowledge_search
th agent create responder_c2 --from-template llm_responder
th agent create alerter_c2 --from-template alert_manager

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier_c2
th agent build searcher_c2
th agent build responder_c2
th agent build alerter_c2

th restart
sleep 2

th push-file searcher_c2 ../synthetic_data/kb.json
th push-file searcher_c2 ../synthetic_data/support_tickets.json
th push-file searcher_c2 ../synthetic_data/test_scenarios.json

# Build chain with routing + enricher
# Route-on MUST be applied to the step BEFORE the target
echo "⛓️  Building chain with routing..."
th chain build-steps smart_routing \
  --step classify sequential classifier_c2 \
    --route-on '[{"if":"output.intent==\"bug_report\"","goto":"respond"}]' \
  --step search sequential searcher_c2 \
  --step respond sequential responder_c2 \
    --route-on '[{"if":"output.intent==\"bug_report\"","goto":"escalate"}]' \
  --step escalate sequential alerter_c2

echo ""
echo "✅ Chain 2 built: smart_routing"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "     IF intent == bug_report → GOTO escalate"
echo "  2. search(searcher_c2) → inputs: query ✅"
echo "  3. respond(responder_c2) → inputs: customer_message ✅"
echo "  4. escalate(alerter_c2)"
echo ""
echo "Test with:"
echo "  th chain start smart_routing --bg --port 20200"
echo "  th chain run smart_routing --payload '{\"text\":\"CRITICAL BUG: System down!\"}' --detached --port 20200"
echo ""
