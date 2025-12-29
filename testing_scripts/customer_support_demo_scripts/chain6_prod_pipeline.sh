#!/bin/bash
# ============================================================================
# Chain 6: Production Pipeline (WITH CONTEXT ENRICHER)
# ============================================================================
# 9-step complete production workflow with data normalization
# - Parallel analysis (urgency + sentiment)
# - Conditional routing
# - enricher for proper input resolution
# - Escalation + auto-response paths
# ============================================================================

set -e

echo "🔗 Chain 6: Production Pipeline (with enricher)"
echo "==============================================="

# Create workspace
th workspace create support_production
cd support_production

# Create all agents
echo "📦 Creating agents..."
th agent create classifier --from-template intent_classifier
th agent create urgency --from-template urgency_detector
th agent create sentiment --from-template sentiment_analyzer
th agent create router --from-template simple_router
th agent create enricher --from-template context_enricher
th agent create searcher --from-template knowledge_search
th agent create responder --from-template llm_responder
th agent create alerter --from-template alert_manager
th agent create sender --from-template response_sender

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier
th agent build urgency
th agent build sentiment
th agent build router
th agent build enricher
th agent build searcher
th agent build responder
th agent build alerter
th agent build sender

# Build complete production chain with enricher
echo "⛓️  Building production chain..."
th chain build-steps production_support \
  --step classify sequential classifier \
  --step analyze parallel urgency sentiment \
    --merge-agent smart_data_aggregator \
  --step route sequential router \
    --route-on '[
      {"if":"output.route==\"escalate\"","goto":"escalate"},
      {"if":"output.urgency==\"critical\"","goto":"escalate"}
    ]' \
  --step enrich sequential enricher \
  --step search sequential searcher \
  --step respond sequential responder \
  --step escalate sequential alerter \
  --step send sequential sender

echo ""
echo "✅ Chain 6 built: production_support"
echo ""
echo "Expected Flow:"
echo "  1. classify(text) → outputs: intent, confidence, urgency, sentiment"
echo "  2. [urgency(text) + sentiment(text) in PARALLEL]"
echo "  3. smart_data_aggregator (merge)"
echo "  4. route(router) → outputs: route, reasoning"
echo "     IF route == 'escalate' OR urgency == 'critical' → GOTO escalate"
echo "  5. enrich(enricher) → outputs: query, customer_message, recipient ✅"
echo "  6. search(searcher) → inputs: query ✅"
echo "  7. respond(responder) → inputs: customer_message ✅"
echo "  8. escalate(alerter) → inputs: message, priority ✅"
echo "  9. send(sender) → inputs: recipient, message ✅"
echo ""
echo "🌉 Bridge Pattern:"
echo "  enricher placed AFTER routing, BEFORE search/respond"
echo "  Provides proper inputs for all downstream agents"
echo ""
echo "Complete Production Workflow:"
echo "  ✅ Intent classification"
echo "  ✅ Parallel analysis (urgency + sentiment)"
echo "  ✅ Smart data aggregation"
echo "  ✅ Routing decision"
echo "  ✅ Data normalization (enricher)"
echo "  ✅ Knowledge search"
echo "  ✅ LLM response generation"
echo "  ✅ Alert management"
echo "  ✅ Multi-channel delivery"
echo ""
echo "Test with:"
echo "  th chain start production_support --bg --port 20600"
echo "  th chain run production_support --payload '{\"text\":\"URGENT: Cannot login!\"}' --detached --port 20600"
echo ""
