#!/bin/bash

set -e

YES=0
if [[ "$1" == "-y" || "$1" == "--yes" ]]; then
  YES=1
fi

echo "🧹 Treehopper Full Cleanup Utility"

if [[ $YES -ne 1 ]]; then
  echo ""
  echo "⚠️  This will delete:"
  echo "   • .treehopper_memory"
  echo "   • ~/.treehopper/registry/agents + agents.json"
  echo "   • ~/.treehopper/registry/chains + chains.json"
  echo "   • ~/.treehopper/registry/shared"
  echo "   • ~/.treehopper/runtime/*.pid"
  echo "   • ~/.treehopper/runtime/server.log"
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

# Kill running uvicorn / treehopper instances
pkill -f "uvicorn" 2>/dev/null
pkill -f "treehopper run" 2>/dev/null
pkill -f "treehopper" 2>/dev/null

# Force free port 1560 if still occupied
if lsof -i :1560 > /dev/null 2>&1; then
    PID=$(lsof -t -i :1560)
    echo "⚠️  Port 1560 still busy — force killing PID $PID"
    kill -9 $PID 2>/dev/null
else
    echo "🟢 Port 1560 already free"
fi

# Identify MAIN_SERVER PID and remove file if stale
TH_ROOT="$HOME/.treehopper"
MAIN_PID_FILE="$TH_ROOT/runtime/main_server.pid"

if [[ -f "$MAIN_PID_FILE" ]]; then
  PID=$(cat "$MAIN_PID_FILE" 2>/dev/null)
  if [[ -n "$PID" ]]; then
    if kill -0 $PID 2>/dev/null; then
      echo "🛑 Stopping running Treehopper (PID $PID)"
      kill -9 $PID 2>/dev/null
    else
      echo "🧹 Removing stale PID: $MAIN_PID_FILE"
    fi
  fi
  rm -f "$MAIN_PID_FILE" 2>/dev/null
fi

echo ""
echo "🗑 Removing runtime logs and PIDs..."
rm -f "$TH_ROOT/runtime/"*.pid 2>/dev/null
rm -f "$TH_ROOT/runtime/server.log" 2>/dev/null

echo "🗑 Removing .treehopper_memory..."
rm -rf .treehopper_memory 2>/dev/null

echo "🗑 Removing agent registry..."
rm -rf "$TH_ROOT/registry/agents" 2>/dev/null
rm -f "$TH_ROOT/registry/agents.json" 2>/dev/null

echo "🗑 Removing chain registry..."
rm -rf "$TH_ROOT/registry/chains" 2>/dev/null
rm -f "$TH_ROOT/registry/chains.json" 2>/dev/null

echo "🗑 Removing shared uploaded files..."
rm -rf "$TH_ROOT/registry/shared" 2>/dev/null

echo ""
echo "🚫 Preserved: subscription_id.txt"
echo ""
echo "✨ Cleanup complete — system ready for a fresh run!"
