#!/bin/bash
# ============================================================================
# Master Chain Builder - Build All 6 Customer Support Chains (WITH ENRICHER)
# ============================================================================
# This script builds all 6 chains with context_enricher for data normalization
# Run this AFTER you've created all required templates
#
# Prerequisites:
#   - All agent templates created (including context_enricher)
#   - TreehopperAI installed and configured
#   - Workspaces ready to be created
#
# Usage: ./master_chain_builder.sh [--clean]
#   --clean: Delete existing workspaces first
# ============================================================================

set -e

CLEAN_MODE=${1:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  TreehopperAI - Build All Chains (WITH ENRICHER) 🌉       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Clean mode
if [ "$CLEAN_MODE" == "--clean" ]; then
  echo -e "${YELLOW}🧹 Cleaning existing workspaces...${NC}"
  rm -rf support_basic support_routing support_parallel support_escalation support_omnichannel support_production 2>/dev/null || true
  echo -e "${GREEN}✅ Cleanup complete${NC}"
  echo ""
fi

# Track success
SUCCESS_COUNT=0
TOTAL_CHAINS=6

# Function to build a chain
build_chain() {
  local chain_num=$1
  local chain_name=$2
  local script_file=$3

  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}Building Chain $chain_num: $chain_name${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  if [ -f "$script_file" ]; then
    chmod +x "$script_file"
    if bash "$script_file"; then
      echo -e "${GREEN}✅ Chain $chain_num completed${NC}"
      SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
      echo -e "${RED}❌ Chain $chain_num failed${NC}"
    fi
  else
    echo -e "${RED}❌ Script not found: $script_file${NC}"
  fi

  echo ""
}

# Build each chain (with enricher!)
build_chain 1 "Basic Auto-Reply (+ enricher)" "chain1_basic_cust_support.sh"
build_chain 2 "Smart Routing (+ enricher)" "chain2_smart_routing.sh"
build_chain 3 "Parallel Intelligence (+ enricher)" "chain3_parallel_intel.sh"
build_chain 4 "Conditional Escalation (+ enricher)" "chain4_conditional_escalation.sh"
build_chain 5 "Multi-Channel (+ enricher)" "chain5_multichannel.sh"
build_chain 6 "Production Pipeline (+ enricher)" "chain6_prod_pipeline.sh"

# Summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Build Summary                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Chains Built: ${GREEN}$SUCCESS_COUNT${YELLOW}/${TOTAL_CHAINS}${NC}"
echo ""

if [ $SUCCESS_COUNT -eq $TOTAL_CHAINS ]; then
  echo -e "${GREEN}🎉 All chains built successfully!${NC}"
  echo ""
  echo -e "${BLUE}🌉 Context Enricher Bridge Pattern Applied!${NC}"
  echo -e "   All chains now use enricher for data normalization:"
  echo -e "   - Transforms emails[] → query, customer_message"
  echo -e "   - Ensures proper input resolution"
  echo -e "   - No validation errors!"
  echo ""
  echo -e "${YELLOW}Next steps:${NC}"
  echo -e "  1. Test individual chains:"
  echo -e "     ${CYAN}th chain start basic_support --bg --port 20100${NC}"
  echo -e "     ${CYAN}th chain run basic_support --payload '{\"text\":\"password reset\"}' --detached --port 20100${NC}"
  echo ""
  echo -e "  2. Run complete test suite:"
  echo -e "     ${CYAN}./complete_test_suite.sh --quick${NC}"
  echo ""
  echo -e "  3. View chains:"
  echo -e "     ${CYAN}th chain vu basic_support${NC}"
  echo ""
  echo -e "  4. Check enricher is working:"
  echo -e "     ${CYAN}th call enricher --payload '{\"text\":\"test message\"}'${NC}"
  echo ""
else
  echo -e "${RED}⚠️  Some chains failed to build${NC}"
  echo -e "${YELLOW}Check error messages above and retry${NC}"
  echo ""
  echo -e "${YELLOW}Common issues:${NC}"
  echo -e "  - Missing context_enricher template"
  echo -e "  - Template not properly installed"
  echo -e "  - Agent build failures"
  echo ""
  exit 1
fi
