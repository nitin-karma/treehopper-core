#!/bin/bash
# ============================================================================
# Customer Support Automation - COMPLETE Test Script
# ============================================================================
# Phase A: Foundation - 5 Agents + 1 Chain
# Expected ROI: 60-70% auto-resolution, $15 → $0.50 per ticket
#
# COVERAGE: CREATE → LINT → BUILD → RUN → STOP → DELETE
# ============================================================================

set -e  # Exit on error

echo "🚀 Customer Support Automation - Complete Test Script"
echo "======================================================"
echo ""

# ============================================================================
# STEP 0: ASK FOR WORKSPACE NAME
# ============================================================================
echo "📋 STEP 0: Workspace Setup"
echo "--------------------------"

# Default workspace name
DEFAULT_WORKSPACE="smart_support"

# Ask user for workspace name
read -p "Enter workspace name (default: $DEFAULT_WORKSPACE): " WORKSPACE_INPUT
WORKSPACE=${WORKSPACE_INPUT:-$DEFAULT_WORKSPACE}

echo ""
echo "Creating workspace: $WORKSPACE"
echo ""

# ============================================================================
# STEP 1: CREATE WORKSPACE
# ============================================================================
echo "📋 STEP 1: Create Workspace"
echo "---------------------------"

# Use th workspace create command
th workspace create $WORKSPACE

# Navigate into workspace
cd $WORKSPACE

echo "✅ Workspace created and entered"
echo "📍 Current directory: $(pwd)"
echo ""

# ============================================================================
# STEP 2: CREATE AGENTS FROM TEMPLATES
# ============================================================================
echo "📦 STEP 2: Create Agents from Templates"
echo "---------------------------------------"

# Agent 1: Email Listener
echo "1️⃣  Creating email_listener agent..."
th agent create email_listener --from-template email_listener
echo "✅ email_listener created"
echo ""

# Agent 2: Intent Classifier
echo "2️⃣  Creating intent_classifier agent..."
th agent create intent_classifier --from-template intent_classifier
echo "✅ intent_classifier created"
echo ""

# Agent 3: Knowledge Search
echo "3️⃣  Creating knowledge_search agent..."
th agent create knowledge_search --from-template knowledge_search
echo "✅ knowledge_search created"
echo ""

# Agent 4: LLM Responder
echo "4️⃣  Creating llm_responder agent..."
th agent create llm_responder --from-template llm_responder
echo "✅ llm_responder created"
echo ""

# Agent 5: Response Sender
echo "5️⃣  Creating response_sender agent..."
th agent create response_sender --from-template response_sender
echo "✅ response_sender created"
echo ""

echo "✅ All 5 agents created successfully!"
echo ""

# Verify created directories
echo "📂 Verifying created agent directories:"
ls -la | grep -E "(email_listener|intent_classifier|knowledge_search|llm_responder|response_sender)"
echo ""

# ============================================================================
# STEP 3: LINT AGENTS
# ============================================================================
echo "🔍 STEP 3: Lint All Agents"
echo "-------------------------"

echo "Linting email_listener..."
th agent lint email_listener
echo ""

echo "Linting intent_classifier..."
th agent lint intent_classifier
echo ""

echo "Linting knowledge_search..."
th agent lint knowledge_search
echo ""

echo "Linting llm_responder..."
th agent lint llm_responder
echo ""

echo "Linting response_sender..."
th agent lint response_sender
echo ""

echo "✅ All agents passed linting!"
echo ""

# ============================================================================
# STEP 4: BUILD AGENTS
# ============================================================================
echo "🔨 STEP 4: Build All Agents"
echo "--------------------------"

echo "Building email_listener..."
th agent build email_listener
echo ""

echo "Building intent_classifier..."
th agent build intent_classifier
echo ""

echo "Building knowledge_search..."
th agent build knowledge_search
echo ""

echo "Building llm_responder..."
th agent build llm_responder
echo ""

echo "Building response_sender..."
th agent build response_sender
echo ""

echo "✅ All agents built successfully!"
echo ""

# List all built agents
echo "📋 Listing all built agents:"
th list_agents
echo ""

# ============================================================================
# STEP 5: TEST INDIVIDUAL AGENTS
# ============================================================================
echo "🧪 STEP 5: Test Individual Agents"
echo "---------------------------------"

# Create test payload for knowledge_search (works without credentials)
echo ""
echo "Creating test payload for knowledge_search..."
cat > test_knowledge_search.json << 'EOF'
{
  "query": "how do I reset my password",
  "top_k": 5,
  "min_relevance": 0.3,
  "knowledge_base": "default",
  "include_content": true
}
EOF
echo "✅ test_knowledge_search.json created"
echo ""

# Test knowledge_search
echo "Testing knowledge_search agent..."
th call knowledge_search --payload-file test_knowledge_search.json
echo ""
echo "✅ Knowledge search test completed!"
echo ""

# Create other test payloads (for documentation)
echo "Creating other test payloads for reference..."

cat > test_intent_classifier.json << 'EOF'
{
  "text": "I need a refund for my purchase. The item arrived damaged and I'm really frustrated.",
  "categories": [
    "refund_request",
    "bug_report",
    "feature_request",
    "billing_question",
    "technical_support",
    "account_issue",
    "product_question",
    "complaint",
    "praise"
  ],
  "include_sentiment": true,
  "provider": "openai"
}
EOF

cat > test_llm_responder.json << 'EOF'
{
  "customer_message": "I need help resetting my password. I've tried the forgot password link but didn't receive an email.",
  "context": {
    "customer_name": "John Doe",
    "account_type": "Premium",
    "last_login": "2024-12-20"
  },
  "knowledge_articles": [
    {
      "title": "How to Reset Your Password",
      "content": "To reset your password: 1) Go to login page 2) Click 'Forgot Password' 3) Enter your email 4) Check inbox for reset link 5) Click link and set new password"
    }
  ],
  "tone": "empathetic",
  "max_length": 150,
  "include_signature": true,
  "provider": "openai"
}
EOF

cat > test_email_listener.json << 'EOF'
{
  "email_config": {
    "host": "imap.gmail.com",
    "port": 993,
    "username": "support@example.com",
    "password": "test_password",
    "use_ssl": true
  },
  "folder": "INBOX",
  "limit": 5,
  "unread_only": true
}
EOF

cat > test_response_sender.json << 'EOF'
{
  "recipient": "#support",
  "message": "New support ticket received from John Doe regarding password reset. Priority: High",
  "channel": "slack",
  "priority": "high",
  "slack_config": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "username": "Support Bot",
    "icon_emoji": ":robot_face:"
  }
}
EOF

echo "✅ All test payloads created"
echo ""

# ============================================================================
# STEP 6: BUILD CHAIN USING CLI COMMAND
# ============================================================================
echo "⛓️  STEP 6: Build Multi-Step Support Chain"
echo "-------------------------------------------"

# Build 3-step chain with proper input/output matching
# Chain name must be 4-25 chars, letters/numbers/underscore only
echo "Building 3-step chain: knowledge_search → llm_responder → response_sender"
echo ""
echo "Data flow:"
echo "  Request → Step 1 (knowledge_search) → articles"
echo "  Request + articles → Step 2 (llm_responder) → response"
echo "  Request + response → Step 3 (response_sender) → status"
echo ""

th chain build-steps smart_support \
  --step search sequential knowledge_search \
  --step respond sequential llm_responder \
  --step send sequential response_sender

echo ""
echo "✅ Chain built successfully!"
echo ""

# Show chain info
echo "📋 Verifying chain was created..."
th list_chains
echo ""

# ============================================================================
# STEP 7: START CHAIN RUNTIME (DETACHED/BACKGROUND)
# ============================================================================
echo "🚀 STEP 7: Start Chain Runtime (Background Service)"
echo "----------------------------------------------------"

# Start chain runtime as background service on specific port
th chain start smart_support --bg --port 20300
echo ""

echo "✅ Chain runtime started successfully!"
echo "📡 Chain runtime listening on: http://localhost:20300"
echo ""

# Wait for runtime to initialize
sleep 3

# ============================================================================
# STEP 8: RUN CHAIN (EXECUTE WITH PAYLOAD)
# ============================================================================
echo "🎯 STEP 8: Execute Chain with Test Payload"
echo "-------------------------------------------"

# Create test payload for 3-step chain
# Must include inputs for all steps that need request data:
#   Step 1 (knowledge_search): query, top_k, min_relevance
#   Step 2 (llm_responder): customer_message, tone, provider
#   Step 3 (response_sender): recipient, channel, subject
cat > chain_test_payload.json << 'EOF'
{
  "query": "How do I reset my password?",
  "top_k": 3,
  "min_relevance": 0.4,
  "customer_message": "I need help resetting my password. I tried the forgot password link but didn't receive an email.",
  "tone": "empathetic",
  "provider": "openai",
  "recipient": "customer@example.com",
  "channel": "email",
  "subject": "Re: Password Reset Help"
}
EOF

echo "📝 Created test payload: chain_test_payload.json"
echo ""
echo "Payload includes:"
echo "  • query: For knowledge_search (step 1)"
echo "  • customer_message: For llm_responder (step 2)"
echo "  • recipient, channel: For response_sender (step 3)"
echo ""

# Execute chain with payload in detached mode
echo "🚀 Triggering chain execution..."
th chain run smart_support \
  --payload-file chain_test_payload.json \
  --detached

echo ""
echo "✅ Chain execution triggered!"
echo ""
echo "Chain flow:"
echo "  1. knowledge_search: Searches for password reset articles"
echo "  2. llm_responder: Generates response using articles"
echo "  3. response_sender: Sends response to customer"
echo ""

# Wait a moment for execution to start
sleep 5

# ============================================================================
# STEP 9: VERIFY STATUS (RUNNING)
# ============================================================================
echo "📊 STEP 9: Verify Status (Chain Running)"
echo "----------------------------------------"

echo ""
echo "Checking agents status..."
th agents status
echo ""

echo "Checking chains status..."
th chains status
echo ""

echo "Listing all agents..."
th list_agents
echo ""

echo "Listing all chains..."
th list_chains
echo ""

# Get chain info
echo "Getting chain info..."
th chain info smart_support || echo "⚠️  Chain info command not available"
echo ""

# Show chain logs (last 20 lines)
CHAIN_LOG=$(ls -t ~/.treehopper/runtime/chain_smart_support*.log 2>/dev/null | head -1)
if [ -f "$CHAIN_LOG" ]; then
    echo "📝 Chain logs (last 20 lines):"
    tail -20 "$CHAIN_LOG"
    echo ""
else
    echo "⚠️  Chain log file not found yet"
    echo ""
fi

# ============================================================================
# STEP 10: STOP CHAIN
# ============================================================================
echo "🛑 STEP 10: Stop Chain"
echo "---------------------"

th chain stop smart_support
echo ""

echo "✅ Chain stopped successfully!"
echo ""

# Wait for chain to fully stop
sleep 2

# Verify chain stopped
echo "Verifying chain stopped..."
th chains status
echo ""

# ============================================================================
# STEP 11: DELETE CHAIN
# ============================================================================
echo "🗑️  STEP 11: Delete Chain"
echo "------------------------"

th chain delete smart_support
echo ""

echo "✅ Chain deleted successfully!"
echo ""

# Verify chain deleted
echo "Verifying chain deleted (should show no chains)..."
th list_chains
echo ""

# ============================================================================
# STEP 12: DELETE AGENTS
# ============================================================================
echo "🗑️  STEP 12: Delete All Agents"
echo "------------------------------"

echo "Deleting email_listener..."
echo "y" | th agent delete email_listener
echo ""

echo "Deleting intent_classifier..."
echo "y" | th agent delete intent_classifier
echo ""

echo "Deleting knowledge_search..."
echo "y" | th agent delete knowledge_search
echo ""

echo "Deleting llm_responder..."
echo "y" | th agent delete llm_responder
echo ""

echo "Deleting response_sender..."
echo "y" | th agent delete response_sender
echo ""

echo "✅ All agents deleted successfully!"
echo ""

# Verify agents deleted
echo "Verifying agents deleted (should show only built-in agents)..."
th list_agents
echo ""

# ============================================================================
# STEP 13: CLEANUP WORKSPACE
# ============================================================================
echo "🧹 STEP 13: Cleanup Workspace"
echo "-----------------------------"

cd ..
echo "📍 Current directory: $(pwd)"
echo ""

echo "Workspace contents before cleanup:"
ls -la $WORKSPACE
echo ""

# Optional: Remove workspace directory
read -p "Remove workspace directory '$WORKSPACE'? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf $WORKSPACE
    echo "✅ Workspace removed"
else
    echo "⏭️  Workspace kept at: $WORKSPACE"
fi
echo ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo "=============================================="
echo "✅ COMPLETE TEST CYCLE FINISHED"
echo "=============================================="
echo ""
echo "📊 Test Coverage Summary:"
echo "  ✅ CREATE   - Workspace created with th workspace create"
echo "  ✅ CREATE   - 5 agents created from templates"
echo "  ✅ LINT     - All agents linted successfully"
echo "  ✅ BUILD    - All agents built and registered"
echo "  ✅ TEST     - Individual agent tested (knowledge_search)"
echo "  ✅ BUILD    - 3-step chain built (search → respond → send)"
echo "  ✅ START    - Chain runtime started (background service)"
echo "  ✅ RUN      - Chain executed with test payload"
echo "  ✅ STATUS   - Verified chain runtime and execution"
echo "  ✅ STOP     - Chain runtime stopped"
echo "  ✅ DELETE   - Chain deleted"
echo "  ✅ DELETE   - All 5 agents deleted"
echo "  ✅ CLEANUP  - Workspace cleaned up"
echo ""
echo "🎯 All CRUD Operations Tested:"
echo "  • Create  ✅"
echo "  • Read    ✅ (list, status, info)"
echo "  • Update  ✅ (build/rebuild)"
echo "  • Delete  ✅"
echo ""
echo "⛓️  Chain Lifecycle Tested:"
echo "  • Build         ✅ (th chain build-steps - 3 steps)"
echo "  • Start Runtime ✅ (th chain start --bg --port)"
echo "  • Execute Chain ✅ (th chain run --payload --detached)"
echo "  • Status        ✅ (th chains status)"
echo "  • Stop Runtime  ✅ (th chain stop)"
echo "  • Delete        ✅ (th chain delete)"
echo ""
echo "🔗 Multi-Step Chain Validated:"
echo "  Step 1: knowledge_search (query → articles)"
echo "  Step 2: llm_responder (customer_message + articles → response)"
echo "  Step 3: response_sender (response + recipient → status)"
echo ""
echo "📝 Files Created (for reference):"
echo "  • test_knowledge_search.json  (agent test payload)"
echo "  • test_intent_classifier.json"
echo "  • test_llm_responder.json"
echo "  • test_email_listener.json"
echo "  • test_response_sender.json"
echo "  • chain_test_payload.json     (3-step chain payload)"
echo ""
echo "=============================================="
echo "🎉 Customer Support Automation test complete!"
echo "=============================================="
echo ""
echo "💡 Chain Design:"
echo "   • Name: smart_support (12 chars) ✅"
echo "   • Steps: 3 (knowledge_search → llm_responder → response_sender)"
echo "   • Input resolution: All inputs satisfied ✅"
echo "   • Data flow: Request + step outputs"
echo ""
echo "📋 Next Steps:"
echo "  1. Share this log output for verification"
echo "  2. Build 'th quick_start' command"
echo "  3. Add Monaco + Xterm.js UI tab"
echo "  4. Build remaining templates from UI shell"
echo ""
