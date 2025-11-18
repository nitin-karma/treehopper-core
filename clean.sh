#!/bin/bash

echo "🧹 Cleaning Python, Treehopper & server processes..."

# ----------------------------
# Kill running servers first
# ----------------------------
echo "🔫 Killing running uvicorn / treehopper servers..."

pkill -f "uvicorn" 2>/dev/null
pkill -f "treehopper run" 2>/dev/null
pkill -f "treehopper" 2>/dev/null

# ensure port 1560 is free
if lsof -i :1560 > /dev/null 2>&1; then
    echo "⚠️  Port 1560 still occupied — force killing process..."
    PID=$(lsof -t -i :1560)
    kill -9 $PID 2>/dev/null
    echo "🛑 Killed PID: $PID"
else
    echo "✅ Port 1560 free"
fi


# ----------------------------
# Python caches
# ----------------------------
echo "🗑 Removing Python caches..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml 2>/dev/null


# ----------------------------
# Treehopper memory
# ----------------------------
echo "🗑 Removing .treehopper_memory..."
rm -rf .treehopper_memory 2>/dev/null

# ----------------------------
# Treehopper testcases memory
# ----------------------------
echo "🗑 Removing .tmp_chroma_test..."
rm -rf .tmp_chroma_test 2>/dev/null


# ----------------------------
# Remove installed agents (keep subscription id)
# ----------------------------
TH_ROOT="$HOME/.treehopper"

if [ -d "$TH_ROOT/registry/agents" ]; then
    echo "🗑 Removing ~/.treehopper/registry/agents/*"
    rm -rf "$TH_ROOT/registry/agents"/* 2>/dev/null
fi

if [ -f "$TH_ROOT/registry/agents.json" ]; then
    echo "🗑 Removing ~/.treehopper/registry/agents.json"
    rm -f "$TH_ROOT/registry/agents.json" 2>/dev/null
fi

# DO NOT remove subscription_id.txt
# To reset subscription manually use:
#   rm -f "$HOME/.treehopper/subscription_id.txt"

echo "✨ Cleanup completed successfully!"
echo "🟢 System ready for fresh pytest run"
