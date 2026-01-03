#!/bin/bash
# ============================================================================
# USE CASE: Supply Chain Disruption Monitoring
# ============================================================================

set -e
th workspace create ws_supply_chain
cd ws_supply_chain

th agent create sc_event_ingest --from-template json_transformer
th agent create sc_quality --from-template quality_evaluator
th agent create sc_cache --from-template ttl_cache
th agent create sc_router --from-template decision_router
th agent create sc_alerter --from-template alert_manager

th agent build sc_event_ingest
th agent build sc_quality
th agent build sc_cache
th agent build sc_router
th agent build sc_alerter

th chain build-steps supply_chain_monitor \
  --step ingest sequential sc_event_ingest \
  --step validate sequential sc_quality \
  --step cache sequential sc_cache \
  --step route sequential sc_router \
  --step alert sequential sc_alerter
