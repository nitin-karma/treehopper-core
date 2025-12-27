#!/bin/bash

# DO NOT USE set -e (it stops execution before cleanup completes)
set +e

YES=0
if [[ "$1" == "-y" || "$1" == "--yes" ]]; then
  YES=1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_MEM="$HOME/.treehopper_memory"
REPO_MEM="$REPO_ROOT/.treehopper_memory"
TH_ROOT="$HOME/.treehopper"

echo "🧹 Treehopper Full Cleanup Utility"

if [[ $YES -ne 1 ]]; then
  echo ""
  echo "⚠️  This will delete:"
  echo "   • $REPO_MEM"
  echo "   • $HOME_MEM"
  echo "   • ~/.treehopper/registry/agents + agents.json"
  echo "   • ~/.treehopper/registry/chains + chains.json"
  echo "   • ~/.treehopper/registry/shared"
  echo "   • ~/.treehopper/runtime/cancels"
  echo "   • ~/.treehopper/runtime/cancellation.db"
  echo "   • ~/.treehopper/runtime/*.pid"
  echo "   • ~/.treehopper/runtime/*.log"
  echo "   • ~/.treehopper/logs"
  echo "   • ~/.treehopper/dashboard_db"
  echo "🚫 subscription_id.txt will NOT be deleted"
  echo ""
  read -p "Proceed? (y/N): " yn
  case $yn in
    [Yy]* ) echo "➡️ Continuing...";;
    * ) echo "❎ Cancelled"; exit 0;;
  esac
fi

echo ""
echo "🔫 Stopping Treehopper Services..."

# 1. Kill processes by name/command pattern
# This stops the backend, active runs, and the UI launcher
pkill -f "uvicorn" 2>/dev/null
pkill -f "treehopper run" 2>/dev/null
pkill -f "treehopper launch ui" 2>/dev/null
pkill -f "th launch ui" 2>/dev/null
pkill -f "treehopper" 2>/dev/null

# 2. Clear Backend Server (Port 1567)
if lsof -i :1567 > /dev/null 2>&1; then
    PID=$(lsof -t -i :1567)
    echo "⚠️  Backend (1567) occupied — killing PID $PID"
    kill -9 "$PID" 2>/dev/null
fi

# 3. Clear UI Dashboard (Port 8090)
if lsof -i :8090 > /dev/null 2>&1; then
    PID=$(lsof -t -i :8090)
    echo "⚠️  UI Dashboard (8090) occupied — killing PID $PID"
    kill -9 "$PID" 2>/dev/null
fi

# 4. Cleanup Backend PID File
MAIN_PID_FILE="$TH_ROOT/runtime/main_server.pid"
if [[ -f "$MAIN_PID_FILE" ]]; then
  PID=$(cat "$MAIN_PID_FILE")
  kill -9 "$PID" 2>/dev/null
  rm -f "$MAIN_PID_FILE"
fi

# 5. Cleanup UI PID File
# Assuming your launch command saves a PID file here
UI_PID_FILE="$TH_ROOT/runtime/ui.pid"
if [[ -f "$UI_PID_FILE" ]]; then
  PID=$(cat "$UI_PID_FILE")
  echo "🧹 Cleaning up UI PID file"
  kill -9 "$PID" 2>/dev/null
  rm -f "$UI_PID_FILE"
fi
echo "✅ main server and ui services stopped."
echo ""
echo "🗑 Removing runtime logs and PIDs..."
rm -f "$TH_ROOT/runtime/"*.pid
rm -f "$TH_ROOT/runtime/"*.log

echo "🗑 Removing .treehopper_memory..."
rm -rf "$HOME_MEM"
rm -rf "$REPO_MEM"

echo "🗑 Removing agent registry..."
rm -rf "$TH_ROOT/registry/agents"
rm -f "$TH_ROOT/registry/agents.json"

echo "🗑 Removing chain registry..."
rm -rf "$TH_ROOT/registry/chains"
rm -f "$TH_ROOT/registry/chains.json"

echo "🗑 Removing shared uploads..."
rm -rf "$TH_ROOT/registry/shared"

echo "🗑 Removing cancels job logs..."
rm -rf "$TH_ROOT/runtime/cancels"

echo "🗑 Removing Treehopper main logs ..."
rm -rf "$TH_ROOT/logs"

echo "🗑 Removing cancellation.db ..."
rm -rf "$TH_ROOT/runtime/cancellation.db"

echo "🗑 Removing dashboard db uploads..."
rm -rf "$TH_ROOT/dashboard_db"

echo ""
echo "🚫 Preserved: $TH_ROOT/subscription_id.txt"
echo "✨ Cleanup complete — system ready for fresh run!"
