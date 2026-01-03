#!/bin/bash
# ============================================================================
# USE CASE: Data Engineering ETL + Validation
# ============================================================================

set -e
th workspace create ws_data_engineering_etl
cd ws_data_engineering_etl

th agent create etl_ingest --from-template json_transformer
th agent create etl_schema --from-template schema_normalizer
th agent create etl_quality --from-template quality_evaluator
th agent create etl_writer --from-template sqlite_state_writer

th agent build etl_ingest
th agent build etl_schema
th agent build etl_quality
th agent build etl_writer

th chain build-steps data_pipeline_etl \
  --step ingest sequential etl_ingest \
  --step normalize sequential etl_schema \
  --step validate sequential etl_quality \
  --step persist sequential etl_writer
