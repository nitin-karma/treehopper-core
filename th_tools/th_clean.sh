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
  echo "   • ~/.treehopper/runtime/*.pid"
  echo "   • ~/.treehopper/runtime/*.log"
  echo "🚫 subscription_id.txt will NOT be deleted"
  echo ""
  read -p "Proceed? (y/N): " yn
  case $yn in
    [Yy]* ) echo "➡️ Continuing...";;
    * ) echo "❎ Cancelled"; exit 0;;
  esac
fi

echo ""
echo "🔫 Stopping running services..."

pkill -f "uvicorn" 2>/dev/null
pkill -f "treehopper run" 2>/dev/null
pkill -f "treehopper" 2>/dev/null

if lsof -i :1560 > /dev/null 2>&1; then
    PID=$(lsof -t -i :1560)
    echo "⚠️  Port 1560 occupied — killing PID $PID"
    kill -9 "$PID" 2>/dev/null
fi

MAIN_PID_FILE="$TH_ROOT/runtime/main_server.pid"
if [[ -f "$MAIN_PID_FILE" ]]; then
  PID=$(cat "$MAIN_PID_FILE")
  kill -9 "$PID" 2>/dev/null
  rm -f "$MAIN_PID_FILE"
fi

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

echo ""
echo "🚫 Preserved: $TH_ROOT/subscription_id.txt"
echo "✨ Cleanup complete — system ready for fresh run!"
