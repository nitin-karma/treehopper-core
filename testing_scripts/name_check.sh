#!/bin/bash

echo ""
echo "🧪 Treehopper Agent Name Validation Test Suite"
echo "--------------------------------------------"

# track results
PASS=0
FAIL=0

run_test() {
  NAME="$1"
  EXPECT="$2" # "pass" or "fail"

  OUTPUT=$(treehopper init "$NAME" 2>&1)

  if [[ "$EXPECT" == "pass" ]]; then
      if echo "$OUTPUT" | grep -qE "✨ Scaffold created"; then
          echo "✔️  PASSED: '$NAME' (expected PASS)"
          PASS=$((PASS+1))
          rm -rf "$NAME" 2>/dev/null  # cleanup
      else
          echo "❌ FAILED: '$NAME' (expected PASS but got FAIL)"
          echo "   Output: $OUTPUT"
          FAIL=$((FAIL+1))
      fi
  else
      if echo "$OUTPUT" | grep -qE "Invalid agent name|already exists|cannot contain"; then
          echo "✔️  PASSED: '$NAME' (expected FAIL)"
          PASS=$((PASS+1))
      else
          echo "❌ FAILED: '$NAME' (expected FAIL but got PASS)"
          echo "   Output: $OUTPUT"
          FAIL=$((FAIL+1))
          rm -rf "$NAME" 2>/dev/null  # cleanup
      fi
  fi
}

echo ""
echo "🔍 Running tests..."

# -------------- VALID NAMES -------------------
run_test "alpha" pass
run_test "summarizer" pass
run_test "auto_agent_1" pass
run_test "LLMcompare" pass
run_test "test_123" pass


# -------------- INVALID NAMES -------------------
run_test "" fail
run_test "abc" fail                        # too short (<4)
run_test "thisnameiswaytoolongbeyond25chars" fail
run_test "agent name" fail                 # space not allowed
run_test "agent-name" fail                 # hyphen not allowed
run_test "123agent" fail                   # must start with letter
run_test "_agent" fail                     # must start with letter
run_test "agent!" fail                     # symbol not allowed
run_test "white space inside name" fail
run_test " namewithleading" fail           # leading space
run_test "namewithtrailing " fail          # trailing space


# Duplicate name check (existing agent test)
treehopper init sampleagent >/dev/null 2>&1
run_test "sampleagent" fail                # should block duplicates
rm -rf "sampleagent" 2>/dev/null


# -------------- CASE INSENSITIVITY -------------
treehopper init MixedCase >/dev/null 2>&1
run_test "mixedcase" fail                  # same name, diff case should fail
rm -rf "MixedCase" 2>/dev/null


# -------------- SUMMARY REPORT ---------------
echo ""
echo "--------------------------------------------"
echo "📌 TEST SUMMARY"
echo "   Passed: $PASS"
echo "   Failed: $FAIL"
echo "--------------------------------------------"

if [[ $FAIL -eq 0 ]]; then
  echo "🎉 All validation tests PASSED successfully!"
else
  echo "⚠️ $FAIL tests FAILED — validation not reliable yet."
fi

echo ""
