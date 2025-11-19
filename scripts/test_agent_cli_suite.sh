#!/bin/bash
set -euo pipefail

echo ""
echo "🧪 Treehopper Agent CLI + Name Validation Test Suite"
echo "==================================================="

ROOT_DIR="$(pwd)"
TEST_DIR="$ROOT_DIR/.tmp_agent_cli_tests"

# Clean test dir
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"

PASS=0
FAIL=0

# small helpers
ok()   { echo "   ✔️  $*"; }
bad()  { echo "   ❌ $*"; }
sep()  { echo "---------------------------------------------------"; }

# Run a command and expect success/failure
run_cmd_expect() {
  local EXPECT="$1"  # "pass" or "fail"
  shift
  local DESC="$1"
  shift

  local CMD=("$@")

  echo ""
  echo "▶️  $DESC"
  echo "    $ ${CMD[*]}"
  set +e
  OUTPUT="$("${CMD[@]}" 2>&1)"
  STATUS=$?
  set -e

  if [[ "$EXPECT" == "pass" ]]; then
    if [[ $STATUS -eq 0 ]]; then
      ok "PASSED (expected PASS)"
      PASS=$((PASS+1))
    else
      bad "FAILED (expected PASS, got exit $STATUS)"
      echo "   Output:"
      echo "   $OUTPUT"
      FAIL=$((FAIL+1))
    fi
  else
    if [[ $STATUS -ne 0 ]]; then
      ok "PASSED (expected FAIL, got exit $STATUS)"
      PASS=$((PASS+1))
    else
      bad "FAILED (expected FAIL, but command succeeded)"
      echo "   Output:"
      echo "   $OUTPUT"
      FAIL=$((FAIL+1))
    fi
  fi
}

# Clean up agent from registry + local dir if exists
cleanup_agent_everywhere() {
  local NAME="$1"

  set +e
  # delete from registry (answer yes automatically)
  printf "y\n" | treehopper agent delete "$NAME" >/dev/null 2>&1
  # delete any local scaffold in test dir
  rm -rf "$TEST_DIR/$NAME" 2>/dev/null
  set -e
}

sep
echo "🏁 Using test working dir: $TEST_DIR"
cd "$TEST_DIR"

# ---------------------------------------------
# 1️⃣ Pure name validation tests for `treehopper init`
# ---------------------------------------------

echo ""
echo "1️⃣ Name validation via 'treehopper init'"

# valid names
VALID_NAMES=(
  "alpha"
  "summarizer1"
  "auto_agent_1"
  "LLMcompare"
  "test_123"
)

for NAME in "${VALID_NAMES[@]}"; do
  cleanup_agent_everywhere "$NAME"
  run_cmd_expect "pass" "init valid agent name '$NAME'" \
    treehopper init "$NAME"
done


# names that should be auto-trimmed and accepted
TRIMMED_NAMES=(
  " namewithleading"
  "namewithtrailing "
)

# invalid names - should be blocked by validate_agent_name
INVALID_NAMES=(
  ""                          # empty
  "abc"                       # too short
  "thisnameiswaytoolongbeyond25chars"
  "agent name"                # space inside
  "agent-name"                # hyphen
  "123agent"                  # starts with digit
  "_agent"                    # starts with underscore
  "agent!"                    # symbol
  "white space inside"        # internal spaces
)

for NAME in "${INVALID_NAMES[@]}"; do
  run_cmd_expect "fail" "init invalid agent name '$NAME'" \
    treehopper init "$NAME"
done

# names with leading/trailing spaces should be trimmed and accepted
for RAW in "${TRIMMED_NAMES[@]}"; do
  EXPECTED_TRIMMED="$(echo "$RAW" | sed 's/^ *//; s/ *$//' )"
  cleanup_agent_everywhere "$EXPECTED_TRIMMED"

  run_cmd_expect "pass" "init name with outer spaces '$RAW' → '$EXPECTED_TRIMMED'" \
    treehopper init "$RAW"

  # verify directory actually created with trimmed name
  if [ -d "$TEST_DIR/$EXPECTED_TRIMMED" ]; then
    ok "Directory created with trimmed name '$EXPECTED_TRIMMED'"
  else
    bad "Expected directory '$TEST_DIR/$EXPECTED_TRIMMED' not found"
    FAIL=$((FAIL+1))
  fi
done

# duplicate name (within same test dir)
DUP_NAME="sampleagent"
cleanup_agent_everywhere "$DUP_NAME"
run_cmd_expect "pass" "init first '$DUP_NAME'" \
  treehopper init "$DUP_NAME"
run_cmd_expect "fail" "init duplicate '$DUP_NAME'" \
  treehopper init "$DUP_NAME"

# case-insensitive duplicate
MIXED="MixedCase"
cleanup_agent_everywhere "$MIXED"
run_cmd_expect "pass" "init '$MIXED'" \
  treehopper init "$MIXED"
run_cmd_expect "fail" "init 'mixedcase' (case-insensitive duplicate)" \
  treehopper init "mixedcase"

# ---------------------------------------------
# 2️⃣ init + lint + build happy-path for valid names
# ---------------------------------------------

echo ""
sep
echo "2️⃣ Full lifecycle: init → lint → build"

# Use fresh, clearly test-only names
LIFECYCLE_NAMES=(
  "summarizer"
  "formatter"
  "riskanalyzer"
)

for NAME in "${LIFECYCLE_NAMES[@]}"; do
  cleanup_agent_everywhere "$NAME"

  run_cmd_expect "pass" "init lifecycle agent '$NAME'" \
    treehopper init "$NAME"

  # lint should pass
  run_cmd_expect "pass" "lint lifecycle agent '$NAME'" \
    treehopper lint "$NAME"

  # build should pass
  run_cmd_expect "pass" "build lifecycle agent '$NAME'" \
    treehopper build "$NAME"

  # agent info should work
  run_cmd_expect "pass" "agent info '$NAME'" \
    treehopper agent info "$NAME"

  # cleanup after verifying
  cleanup_agent_everywhere "$NAME"
done

# ---------------------------------------------
# 3️⃣ CLI arg validation for lint/build with bad names
# ---------------------------------------------

echo ""
sep
echo "3️⃣ CLI argument validation for lint/build"

BAD_CLI_NAMES=(
  "bad name"
  "bad-name"
  "3bad"
  " bad"
  "bad "
)

for NAME in "${BAD_CLI_NAMES[@]}"; do
  run_cmd_expect "fail" "lint invalid CLI name '$NAME'" \
    treehopper lint "$NAME"

  run_cmd_expect "fail" "build invalid CLI name '$NAME'" \
    treehopper build "$NAME"
done

# ---------------------------------------------
# 4️⃣ Yaml-level name tampering test for build
# ---------------------------------------------
echo ""
sep
echo "4️⃣ Tampering agent.yaml: invalid name in yaml should make build fail"

TAMPER_NAME="tampertest"
cleanup_agent_everywhere "$TAMPER_NAME"
run_cmd_expect "pass" "init '$TAMPER_NAME' (will tamper yaml)" \
  treehopper init "$TAMPER_NAME"

# overwrite agent.yaml with invalid name
cat > "$TAMPER_NAME/agent.yaml" <<EOF
agent_name: "bad name with space"
agent_id: "${TAMPER_NAME}-deadbeef"
subscription_id: "dummy-sub-id"
entrypoint: "/${TAMPER_NAME}"
chain_ids: []
description: "tampered bad name"
EOF

run_cmd_expect "fail" "build '$TAMPER_NAME' with invalid agent_name in yaml" \
  treehopper build "$TAMPER_NAME"

cleanup_agent_everywhere "$TAMPER_NAME"

# ---------------------------------------------
# 5️⃣ Summary
# ---------------------------------------------
echo ""
sep
echo "📊 TEST SUITE SUMMARY"
echo "   Passed: $PASS"
echo "   Failed: $FAIL"
sep

if [[ $FAIL -eq 0 ]]; then
  echo "🎉 All agent name + CLI tests PASSED!"
  exit 0
else
  echo "⚠️  Some tests FAILED — please inspect above output."
  exit 1
fi
