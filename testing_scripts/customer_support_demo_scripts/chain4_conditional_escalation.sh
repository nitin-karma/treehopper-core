#!/bin/bash
# ============================================================================
# Chain 4: Conditional Escalation (WITH CONTEXT ENRICHER)
# ============================================================================
# 7-step chain with routing, escalation logic, and data normalization
# enricher placed BEFORE search to provide proper inputs
# ============================================================================

set -e

echo "🔗 Chain 4: Conditional Escalation (with enricher)"
echo "=================================================="

# Create workspace
th workspace create support_escalation
cd support_escalation

# Create agents
echo "📦 Creating agents..."
th agent create classifier_c4 --from-template intent_classifier
th agent create urgency_c4 --from-template urgency_detector
th agent create router_c4 --from-template simple_router
th agent create analysis_c4 --from-template analysis_bridge
th agent create enricher_c4 --from-template context_enricher
th agent create searcher_c4 --from-template knowledge_search
th agent create responder_c4 --from-template llm_responder
th agent create alerter_c4 --from-template alert_manager

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier_c4
th agent build urgency_c4
th agent build router_c4
th agent build analysis_c4
th agent build enricher_c4
th agent build searcher_c4
th agent build responder_c4
th agent build alerter_c4

th restart
sleep 2

th push-file searcher_c4 ../synthetic_data/kb.json
th push-file searcher_c4 ../synthetic_data/support_tickets.json
th push-file searcher_c4 ../synthetic_data/test_scenarios.json

# Build chain with routing logic + enricher
echo "⛓️  Building chain with escalation routing..."

th chain build-steps escalation_flow \
  --step classify sequential classifier_c4 \
  --step detect sequential urgency_c4 \
  --step analysis sequential analysis_c4 \
  --step route sequential router_c4 \
    --route-on '[
      {"if":"output.route==\"escalate\"","goto":"alert"},
      {"if":"state.analysis.urgency==\"critical\"","goto":"alert"}
    ]' \
  --step enrich sequential enricher_c4 \
  --step search sequential searcher_c4 \
  --step respond sequential responder_c4 \
  --step alert sequential alerter_c4





echo ""
echo "✅ Chain 4 built: escalation_flow"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "  2. detect(urgency) → outputs: urgency, confidence, reasoning"
echo "  3. route(router) → outputs: route, reasoning"
echo "     IF route == 'escalate' OR urgency == 'critical' → GOTO alert"
echo "  4. enrich(enricher) → outputs: query, customer_message ✅"
echo "  5. search(searcher) → inputs: query ✅"
echo "  6. respond(responder) → inputs: customer_message ✅"
echo "  7. alert(alerter)"
echo ""
echo "🌉 Bridge Pattern:"
echo "  enricher placed AFTER routing, BEFORE search"
echo "  Ensures search and response agents get proper inputs"
echo ""
echo "Test with:"
echo "  th chain start escalation_flow --bg --port 20400"
echo "  th chain run escalation_flow --payload '{\"text\":\"System broken! Help!\"}' --detached --port 20400"
echo ""
