#!/bin/bash
set -e

echo "🔗 Chain: Basic Customer Support (3 agents)"
echo "==========================================="

th workspace create support_basic
cd support_basic

echo "📦 Creating agents..."
th agent create emailin --from-template email_listener
th agent create searcher --from-template knowledge_search
th agent create responder --from-template llm_responder


echo "🔨 Building agents..."
th agent build emailin
th agent build searcher
th agent build responder

th restart
sleep 2

th push-file searcher ../synthetic_data/kb.json
th push-file searcher ../synthetic_data/support_tickets.json
th push-file searcher ../synthetic_data/test_scenarios.json


echo "⛓️ Building chain..."
th chain build-steps basic_support \
  --step intake sequential emailin \
  --step search sequential searcher \
  --step respond sequential responder

echo ""
echo "✅ basic_support chain ready"
