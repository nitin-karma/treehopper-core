#!/bin/bash
# ============================================================================
# TreehopperAI Customer Support - Complete Test Suite (UPDATED)
# ============================================================================
# This script demonstrates all 6 chains using synthetic test data
# UPDATED: Reflects individual agent builds (no batch build)
#
# Usage: ./COMPLETE_TEST_SUITE.sh [--quick|--full|--demo]
#   --quick: Test each chain once (10 min)
#   --full:  Test all scenarios (30 min)
#   --demo:  Run demo-ready scenarios for video (5 min)
# ============================================================================

set -e

MODE=${1:---quick}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SYNTHETIC_DATA_DIR="synthetic_data"
RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"

# Create results directory
mkdir -p $RESULTS_DIR

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  TreehopperAI Customer Support - Complete Test Suite      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Mode: $MODE${NC}"
echo -e "${YELLOW}Results will be saved to: $RESULTS_DIR${NC}"
echo ""

# ============================================================================
# Helper Functions
# ============================================================================

test_chain() {
  local chain_name=$1
  local test_name=$2
  local payload=$3
  local port=$4

  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}🧪 Testing: $test_name${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "   Chain: ${YELLOW}$chain_name${NC}"
  echo -e "   Port: ${YELLOW}$port${NC}"

  # Start timer
  START_TIME=$(date +%s)

  # Start chain runtime if not running
  echo -e "${YELLOW}   Starting chain runtime...${NC}"
  th chain start $chain_name --bg --port $port 2>&1 | head -5 || true
  sleep 2

  # Run chain
  echo -e "${YELLOW}   Running chain...${NC}"
  RUN_OUTPUT=$(th chain run $chain_name \
    --payload "$payload" \
    --detached \
    --port $port 2>&1)

  # Extract run_id
  RUN_ID=$(echo "$RUN_OUTPUT" | grep -oE 'run_[a-zA-Z0-9_-]+' | head -1 || echo "")

  if [ -z "$RUN_ID" ]; then
    echo -e "${RED}   ⚠️  Could not extract run_id (chain may still be running)${NC}"
    RUN_ID="unknown_$(date +%s)"
  fi

  echo -e "   Run ID: ${YELLOW}$RUN_ID${NC}"

  # Wait for completion
  echo -e "   Waiting for completion..."
  sleep 5

  # End timer
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))

  echo -e "   ⏱️  Duration: ${GREEN}${DURATION}s${NC}"

  # Save result
  echo "$RUN_OUTPUT" > "$RESULTS_DIR/${chain_name}_${RUN_ID}.log"

  # Record to summary
  echo "$(date +%Y-%m-%d\ %H:%M:%S) | $chain_name | $test_name | $RUN_ID | ${DURATION}s" >> "$RESULTS_DIR/summary.txt"

  echo -e "${GREEN}   ✅ Test completed${NC}"
  echo ""

  return 0
}

cleanup_chains() {
  echo -e "${YELLOW}🧹 Cleaning up chain runtimes...${NC}"

  for chain in basic_support smart_routing parallel_intel escalation_flow production_support; do
    th chain stop $chain 2>/dev/null || true
  done

  echo -e "${GREEN}✅ Cleanup complete${NC}"
  echo ""
}

# Trap to cleanup on exit
trap cleanup_chains EXIT

# ============================================================================
# QUICK MODE - One test per chain (10 minutes)
# ============================================================================

if [ "$MODE" == "--quick" ]; then
  echo -e "${YELLOW}Quick Mode: Testing each chain once${NC}"
  echo ""

  # Chain 1: Basic Auto-Reply
  test_chain "basic_support" \
    "Password Reset Query" \
    '{"query":"How do I reset my password?","text":"I forgot my password","customer_message":"I forgot my password"}' \
    20100

  # Chain 2: Smart Routing
  test_chain "smart_routing" \
    "Bug Report Routing" \
    '{"text":"CRITICAL: Production database down!"}' \
    20200

  # Chain 3: Parallel Intelligence
  test_chain "parallel_intel" \
    "Urgent Account Lock" \
    '{"text":"I need help urgently! My account is locked."}' \
    20300

  # Chain 4: Conditional Escalation
  test_chain "escalation_flow" \
    "Billing Issue Escalation" \
    '{"text":"I was charged twice this month!","customer_email":"test@example.com"}' \
    20400

  # Chain 6: Production Pipeline
  test_chain "production_support" \
    "Complete Production Flow" \
    '{"text":"URGENT: Cannot login, production impact!"}' \
    20600

# ============================================================================
# FULL MODE - All scenarios (30 minutes)
# ============================================================================

elif [ "$MODE" == "--full" ]; then
  echo -e "${YELLOW}Full Mode: Testing all scenarios${NC}"
  echo ""

  if [ ! -f "$SYNTHETIC_DATA_DIR/test_scenarios.json" ]; then
    echo -e "${RED}❌ Synthetic data not found: $SYNTHETIC_DATA_DIR/test_scenarios.json${NC}"
    echo -e "${YELLOW}Please copy synthetic_data/ to current directory${NC}"
    exit 1
  fi

  TOTAL_SCENARIOS=$(cat $SYNTHETIC_DATA_DIR/test_scenarios.json | jq 'length')

  echo -e "${GREEN}Running $TOTAL_SCENARIOS test scenarios...${NC}"
  echo ""

  for i in $(seq 0 $(($TOTAL_SCENARIOS - 1))); do
    SCENARIO=$(cat $SYNTHETIC_DATA_DIR/test_scenarios.json | jq ".[$i]")

    SCENARIO_ID=$(echo $SCENARIO | jq -r '.scenario_id')
    NAME=$(echo $SCENARIO | jq -r '.name')
    CHAIN=$(echo $SCENARIO | jq -r '.chain_to_test')
    PAYLOAD=$(echo $SCENARIO | jq -c '.input_payload')

    echo -e "${BLUE}Test $((i+1))/$TOTAL_SCENARIOS: $SCENARIO_ID${NC}"

    test_chain "$CHAIN" "$NAME" "$PAYLOAD" $((20100 + i))

    sleep 2
  done

# ============================================================================
# DEMO MODE - Best scenarios for video (5 minutes)
# ============================================================================

elif [ "$MODE" == "--demo" ]; then
  echo -e "${YELLOW}Demo Mode: Running presentation-ready scenarios${NC}"
  echo ""

  echo -e "${GREEN}🎬 Scene 1: Auto-respond to common question${NC}"
  test_chain "basic_support" \
    "Password Reset (Auto-Respond)" \
    '{"query":"password reset","text":"How do I reset my password?"}' \
    20100

  sleep 3

  echo -e "${GREEN}🎬 Scene 2: Critical issue escalation${NC}"
  test_chain "escalation_flow" \
    "Production Down (Critical)" \
    '{"text":"CRITICAL: Production database returning 500 errors! Revenue impact!"}' \
    20200

  sleep 3

  echo -e "${GREEN}🎬 Scene 3: Parallel intelligence analysis${NC}"
  test_chain "parallel_intel" \
    "Multi-Analysis (Parallel)" \
    '{"text":"URGENT: Account locked and need immediate access for client presentation!"}' \
    20300

  sleep 3

  echo -e "${GREEN}🎬 Scene 4: Happy customer acknowledgment${NC}"
  test_chain "basic_support" \
    "Positive Feedback" \
    '{"text":"Just wanted to say the new update is AMAZING! Great work team!"}' \
    20100

  sleep 3

  echo -e "${GREEN}🎬 Scene 5: Refund request escalation${NC}"
  test_chain "escalation_flow" \
    "Refund Request" \
    '{"text":"I want a refund. The item arrived damaged.","customer_email":"customer@example.com"}' \
    20200

else
  echo -e "${RED}Unknown mode: $MODE${NC}"
  echo "Usage: $0 [--quick|--full|--demo]"
  exit 1
fi

# ============================================================================
# Summary Report
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Test Summary                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ -f "$RESULTS_DIR/summary.txt" ]; then
  echo -e "${GREEN}Results saved to: $RESULTS_DIR${NC}"
  echo ""
  cat "$RESULTS_DIR/summary.txt"
  echo ""

  # Calculate stats
  TOTAL_TESTS=$(wc -l < "$RESULTS_DIR/summary.txt")
  AVG_TIME=$(awk -F'|' '{gsub(/[^0-9.]/, "", $5); sum+=$5; count++} END {if(count>0) print sum/count; else print 0}' "$RESULTS_DIR/summary.txt")

  echo -e "${YELLOW}Statistics:${NC}"
  echo -e "  Total Tests: ${GREEN}$TOTAL_TESTS${NC}"
  echo -e "  Average Duration: ${GREEN}${AVG_TIME}s${NC}"
  echo ""
fi

echo -e "${GREEN}✅ All tests completed!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review logs in: ${BLUE}$RESULTS_DIR/${NC}"
echo -e "  2. Check chain outputs:"
echo -e "     ${CYAN}cat ~/.treehopper/registry/chains/*/runs/*.json${NC}"
echo -e "  3. View chain visualizations:"
echo -e "     ${CYAN}th chain vu basic_support${NC}"
echo ""
