#!/bin/bash
# ============================================================================
# USE CASE: Drug Discovery Screening
# ============================================================================

set -e
th workspace create ws_drug_discovery
cd ws_drug_discovery

th agent create dd_ingest --from-template json_transformer
th agent create dd_quality --from-template quality_evaluator
th agent create dd_confidence --from-template confidence_gate
th agent create dd_router --from-template decision_router

th agent build dd_ingest
th agent build dd_quality
th agent build dd_confidence
th agent build dd_router

th chain build-steps drug_discovery_screening \
  --step ingest sequential dd_ingest \
  --step evaluate sequential dd_quality \
  --step gate sequential dd_confidence \
  --step route sequential dd_router
