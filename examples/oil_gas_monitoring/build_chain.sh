#!/bin/bash
# ============================================================================
# USE CASE: Oil & Gas Plant Monitoring
# ============================================================================

set -e
th workspace create ws_oil_gas_monitoring
cd ws_oil_gas_monitoring

th agent create og_sensor_ingest --from-template json_transformer
th agent create og_anomaly --from-template analysis_bridge
th agent create og_router --from-template decision_router
th agent create og_alerter --from-template alert_manager

th agent build og_sensor_ingest
th agent build og_anomaly
th agent build og_router
th agent build og_alerter

th chain build-steps plant_monitoring_pipeline \
  --step ingest sequential og_sensor_ingest \
  --step analyze sequential og_anomaly \
  --step route sequential og_router \
  --step alert sequential og_alerter
