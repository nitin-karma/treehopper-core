#!/bin/bash
# ============================================================================
# USE CASE: Robotics Task Orchestration
# ============================================================================

set -e
th workspace create ws_robotics_orchestration
cd ws_robotics_orchestration

th agent create rb_task_ingest --from-template intent_classifier
th agent create rb_safety_gate --from-template confidence_gate
th agent create rb_planner --from-template decision_router
th agent create rb_state_writer --from-template sqlite_state_writer

th agent build rb_task_ingest
th agent build rb_safety_gate
th agent build rb_planner
th agent build rb_state_writer

th chain build-steps robot_task_controller \
  --step intake sequential rb_task_ingest \
  --step safety sequential rb_safety_gate \
  --step plan sequential rb_planner \
  --step persist sequential rb_state_writer
