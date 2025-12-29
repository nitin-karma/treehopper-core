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
th agent create classifier --from-template intent_classifier
th agent create urgency --from-template urgency_detector
th agent create router --from-template simple_router
th agent create enricher --from-template context_enricher
th agent create searcher --from-template knowledge_search
th agent create responder --from-template llm_responder
th agent create alerter --from-template alert_manager

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier
th agent build urgency
th agent build router
th agent build enricher
th agent build searcher
th agent build responder
th agent build alerter

# Build chain with routing logic + enricher
echo "⛓️  Building chain with escalation routing..."
th chain build-steps escalation_flow \
  --step classify sequential classifier \
  --step detect sequential urgency \
  --step route sequential router \
    --route-on '[
      {"if":"output.route==\"escalate\"","goto":"alert"},
      {"if":"output.urgency==\"critical\"","goto":"alert"}
    ]' \
  --step enrich sequential enricher \
  --step search sequential searcher \
  --step respond sequential responder \
  --step alert sequential alerter

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
