#!/bin/bash
# ============================================================================
# Chain : Production Pipeline (WITH CONTEXT ENRICHER)
# ============================================================================
# 9-step complete production workflow with data normalization
# - Parallel analysis (urgency + sentiment)
# - Conditional routing
# - enricher for proper input resolution
# - Escalation + auto-response paths
# ============================================================================

set -e

echo "🔗 Chain: Customer Support"
echo "==========================="

# Create workspace
th workspace create ws_customer_support
cd ws_customer_support

# Create all agents
echo "📦 Creating agents..."
th agent create cs_classifier --from-template intent_classifier
th agent create cs_urgency --from-template urgency_detector
th agent create cs_sentiment --from-template sentiment_analyzer
th agent create cs_router --from-template simple_router
th agent create cs_enricher --from-template context_enricher
th agent create cs_searcher --from-template knowledge_search
th agent create cs_responder --from-template llm_responder
th agent create cs_alerter --from-template alert_manager
th agent create cs_sender --from-template response_sender

# Build agents ONE BY ONE
echo "🔨 Building agents..."
th agent build cs_classifier
th agent build cs_urgency
th agent build cs_sentiment
th agent build cs_router
th agent build cs_enricher
th agent build cs_searcher
th agent build cs_responder
th agent build cs_alerter
th agent build cs_sender

th restart
sleep 2

th push-file cs_searcher ../synthetic_data/kb.json
th push-file cs_searcher ../synthetic_data/support_tickets.json
th push-file cs_searcher ../synthetic_data/test_scenarios.json

# Build complete production chain with enricher
echo "⛓️  Building production chain..."
th chain build-steps customer_support \
  --step classify sequential cs_classifier \
  --step analyze parallel cs_urgency cs_sentiment \
    --merge-agent smart_data_aggregator \
  --step route sequential cs_router \
    --route-on '[
      {"if":"output.route==\"escalate\"","goto":"escalate"},
      {"if":"output.route==\"auto_respond\"","goto":"enrich"}
    ]' \
  --step enrich sequential cs_enricher \
  --step search sequential cs_searcher \
  --step respond sequential cs_responder \
  --step send sequential cs_sender \
  --step escalate sequential cs_alerter


echo ""
echo "✅ Chain built: customer_support"
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
echo "Complete Customer Support Workflow:"
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
echo "  th chain start customer_support --bg --port 20601"
echo "  th chain run customer_support --payload '{\"text\":\"URGENT: Cannot login!\"}' --detached --port 20600"
echo ""
