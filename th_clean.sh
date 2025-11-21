#!/bin/bash

TH_ROOT="$HOME/.treehopper"
RUNTIME_DIR="$TH_ROOT/runtime"
MAIN_PID_FILE="$RUNTIME_DIR/main_server.pid"
SERVER_LOG="$RUNTIME_DIR/server.log"

AUTO_YES=false

# ------------------------
# Parse flags
# ------------------------
for arg in "$@"; do
  case $arg in
    -y|--yes)
      AUTO_YES=true
      shift
      ;;
  esac
done

# ------------------------
# Confirmation prompt
# ------------------------
if [ "$AUTO_YES" = false ]; then
  echo "⚠️  This will:"
  echo "   • Kill running Treehopper/uvicorn servers"
  echo "   • Clear agents, chains, shared files, registry, server.log"
  echo "   • Keep subscription_id.txt"
  echo ""
  read -p "Proceed with cleanup? (y/N): " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "❎ Cleanup cancelled."
    exit 0
  fi
fi

echo "🧹 Cleaning Python, Treehopper & server processes..."
echo "---------------------------------------------------------"

# ------------------------
# Kill running servers
# ------------------------
echo "🔫 Killing running uvicorn / treehopper servers..."
pkill -f "uvicorn" 2>/dev/null
pkill -f "treehopper run" 2>/dev/null
pkill -f "treehopper" 2>/dev/null

# Force free port 1560 if still busy
if lsof -i :1560 > /dev/null 2>&1; then
    PID=$(lsof -t -i :1560)
    kill -9 "$PID" 2>/dev/null
    echo "🛑 Force killed PID on port 1560: $PID"
else
    echo "🟢 Port 1560 free"
fi

# ------------------------
# PID file sanity cleanup
# ------------------------
if [ -f "$MAIN_PID_FILE" ]; then
  PID=$(cat "$MAIN_PID_FILE")
  if ps -p "$PID" > /dev/null 2>&1; then
      echo "🛑 Killing orphaned main server PID: $PID"
      kill -9 "$PID" 2>/dev/null
  fi
  echo "🗑 Removing $MAIN_PID_FILE"
  rm -f "$MAIN_PID_FILE"
fi

# ------------------------
# Logs
# ------------------------
echo "🗑 Removing server.log"
rm -f "$SERVER_LOG" 2>/dev/null

# ------------------------
# Python caches
# ------------------------
echo "🗂 Removing Python caches..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml 2>/dev/null

# ------------------------
# Treehopper memory
# ------------------------
echo "🗑 Removing .treehopper_memory & .tmp_chroma_test..."
rm -rf .treehopper_memory .tmp_chroma_test 2>/dev/null

# ------------------------
# Registry cleanup
# ------------------------
echo "🗑 Cleaning ~/.treehopper registry"
rm -rf "$TH_ROOT/registry/agents"/* 2>/dev/null
rm -f "$TH_ROOT/registry/agents.json" 2>/dev/null
rm -rf "$TH_ROOT/registry/chains"/* 2>/dev/null
rm -f "$TH_ROOT/registry/chains.json" 2>/dev/null
rm -rf "$TH_ROOT/registry/shared"/* 2>/dev/null

# ------------------------
# Runtime chain PIDs
# ------------------------
echo "🗑 Removing chain runtime PID files"
rm -f "$RUNTIME_DIR"/chain_*.pid 2>/dev/null

echo "---------------------------------------------------------"
echo "🟡 subscription_id.txt preserved"
echo "✨ Cleanup completed successfully!"
echo "🚀 Treehopper system ready for new builds/tests"
