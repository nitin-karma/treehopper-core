#!/bin/bash
# ============================================================================
# USE CASE: Insurance Claims Processing
# ============================================================================
# This chain demonstrates a realistic insurance claims workflow using
# TreehopperAI with mocked agents.
#
# Capabilities shown:
# - Intent classification of claims
# - Parallel fraud & policy validation
# - Smart merge of analysis signals
# - Conditional routing (approve / reject / escalate)
# - Persistent state storage
# - Alerting for rejected or high-risk claims
#
# All agents are prefixed with `ic_` (insurance claims) to avoid collisions
# across other industry examples.
# ============================================================================

set -e

echo "🏥 Building Insurance Claims Processing Chain"
echo "============================================"

# Workspace
th workspace create ws_insurance_claims
cd ws_insurance_claims

echo "📦 Creating agents..."

th agent create ic_classifier --from-template intent_classifier
th agent create ic_fraud_gate --from-template confidence_gate
th agent create ic_policy_norm --from-template schema_normalizer
th agent create ic_router --from-template decision_router
th agent create ic_state_writer --from-template sqlite_state_writer
th agent create ic_alerter --from-template alert_manager

echo "🔨 Building agents..."

th agent build ic_classifier
th agent build ic_fraud_gate
th agent build ic_policy_norm
th agent build ic_router
th agent build ic_state_writer
th agent build ic_alerter

echo "⛓️ Building chain: insurance_claims_processing"

th chain build-steps insurance_claims_processing \
  --step intake sequential ic_classifier \
  --step analyze parallel ic_fraud_gate ic_policy_norm \
    --merge-agent smart_data_aggregator \
  --step route sequential ic_router \
    --route-on '[
      {"if":"output.route==\"reject\"","goto":"escalate"}
    ]' \
  --step persist sequential ic_state_writer \
  --step escalate sequential ic_alerter

echo ""
echo "✅ Insurance Claims Processing Chain Built"
echo ""
echo "Test with:"
echo "th chain run insurance_claims_processing --payload '{\"text\":\"Claim for accident reimbursement\"}'"
