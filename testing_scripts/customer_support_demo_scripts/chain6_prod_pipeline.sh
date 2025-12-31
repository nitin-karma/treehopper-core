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
th agent create classifier_c6 --from-template intent_classifier
th agent create urgency_c6 --from-template urgency_detector
th agent create sentiment_c6 --from-template sentiment_analyzer
th agent create router_c6 --from-template simple_router
th agent create enricher_c6 --from-template context_enricher
th agent create searcher_c6 --from-template knowledge_search
th agent create responder_c6 --from-template llm_responder
th agent create alerter_c6 --from-template alert_manager
th agent create sender_c6 --from-template response_sender

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build classifier_c6
th agent build urgency_c6
th agent build sentiment_c6
th agent build router_c6
th agent build enricher_c6
th agent build searcher_c6
th agent build responder_c6
th agent build alerter_c6
th agent build sender_c6

th restart
sleep 2

th push-file searcher_c6 ../synthetic_data/kb.json
th push-file searcher_c6 ../synthetic_data/support_tickets.json
th push-file searcher_c6 ../synthetic_data/test_scenarios.json

# Build complete production chain with enricher
echo "⛓️  Building production chain..."
th chain build-steps production_support \
  --step classify sequential classifier_c6 \
  --step analyze parallel urgency_c6 sentiment_c6 \
    --merge-agent smart_data_aggregator \
  --step route sequential router_c6 \
    --route-on '[
      {"if":"output.route==\"escalate\"","goto":"escalate"},
      {"if":"output.route==\"auto_respond\"","goto":"enrich"}
    ]' \
  --step enrich sequential enricher_c6 \
  --step search sequential searcher_c6 \
  --step respond sequential responder_c6 \
  --step send sequential sender_c6 \
  --step escalate sequential alerter_c6


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
