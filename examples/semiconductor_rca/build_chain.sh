#!/bin/bash
# ============================================================================
# USE CASE: Semiconductor Defect Classification & RCA
# ============================================================================

set -e
th workspace create ws_semiconductor_rca
cd ws_semiconductor_rca

th agent create sc_defect_cls --from-template intent_classifier
th agent create sc_pattern_analyzer --from-template analysis_bridge
th agent create sc_router --from-template decision_router
th agent create sc_alerter --from-template alert_manager

th agent build sc_defect_cls
th agent build sc_pattern_analyzer
th agent build sc_router
th agent build sc_alerter

th chain build-steps semiconductor_defect_rca \
  --step classify sequential sc_defect_cls \
  --step analyze sequential sc_pattern_analyzer \
  --step route sequential sc_router \
  --step escalate sequential sc_alerter
