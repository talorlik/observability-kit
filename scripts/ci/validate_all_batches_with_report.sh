#!/usr/bin/env bash

set -u

REPORT_DIR="docs/reports/validation"
mkdir -p "$REPORT_DIR"

TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
REPORT_STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
MARKDOWN_REPORT="$REPORT_DIR/BATCH_VALIDATION_REPORT_${REPORT_STAMP}.md"
JSON_REPORT="$REPORT_DIR/BATCH_VALIDATION_REPORT_${REPORT_STAMP}.json"
LATEST_MARKDOWN="$REPORT_DIR/BATCH_VALIDATION_REPORT_LATEST.md"
LATEST_JSON="$REPORT_DIR/BATCH_VALIDATION_REPORT_LATEST.json"

declare -a BATCH_IDS=(
  "1"
  "2"
  "3"
  "4"
  "5"
  "6"
  "7"
  "8"
  "9"
  "9A"
  "10"
  "11"
  "12"
  "13"
  "14"
)

declare -a BATCH_NAMES=(
  "Delivery Foundation"
  "Compatibility and Modes"
  "Preflight and Discovery Engine"
  "Collector Core Topology"
  "Logs Pipeline"
  "Metrics and Traces Pipelines"
  "Onboarding and Subscription Model"
  "Security, Isolation, and Resilience"
  "Operator Experience and SLO Operations"
  "Visualization and Admin Access Plane"
  "Vector Foundations"
  "Graph Foundation"
  "Risk Scoring and Assisted RCA Readiness"
  "Core Adapter Integrations"
  "AI/MCP Runtime Validation and Productization"
)

declare -a VALIDATION_CRITERIA=(
  "Validate contract tests in CI, invalid fixture failure behavior, render checks for stubs, CI rejection of seeded invalid YAML or secrets, and runbook link validation."
  "Validate matrix grade mapping tests, profile fixture schema checks, and deterministic mode output tests."
  "Validate preflight test coverage for all check classes, full expected file generation from sample run, and smoke bundle pass on reference cluster profile."
  "Validate helm template plus cluster dry-run apply, required collector chains and export checks, and bounded-loss simulation metrics."
  "Validate single-line and multiline fixture tests, sensitive fixture redaction or drop behavior, and clean template and policy install with dashboard render checks."
  "Validate opted-in workload metrics indexing, trace ingest with sampling targets matching policy, and synthetic plus pilot correlation tests."
  "Validate one-block onboarding chart rendering, non-compliant onboarding rejection with clear output, and one-block onboarding CI smoke pass."
  "Validate expected cross-team access denials, CI security contract and audit tests, and successful non-production restore plus rollback drills."
  "Validate saved object import on test cluster, synthetic event alert routing, and drill evidence plus alert-noise trend checks."
  "Validate signal-to-UI ownership contract linting, core UI provisioning path rendering, admin-access profile schema checks, and admin GUI TLS plus login smoke results."
  "Validate versioned extraction snapshot bundle output, OpenSearch vector write and queryability, and quality baseline plus governance checks."
  "Validate healthy core platform behavior with graph on and off, convergent repeated sync runs, and stale-data freshness alert triggering."
  "Validate deterministic score reruns, backtest and evidence bundle contracts, and approval evidence before RCA suggestion release."
  "Validate adapter contract schema coverage, profile-driven activation safety, identity and secrets and network stub metadata, CI contract gating, CI/CD neutrality checks, and adapter operations guide completeness."
  "Validate AI agent boundary, governance, and state contracts; MCP catalog and tool response contracts; AI runtime base, MCP read-path, multi-agent, KHook trigger, and action-gate scaffolding; and KAgent/KHook release readiness."
)

declare -a SCRIPT_PATHS=(
  "scripts/ci/validate_batch1_smoke.sh"
  "scripts/ci/validate_batch2_smoke.sh"
  "scripts/ci/validate_batch3_smoke.sh"
  "scripts/ci/validate_batch4_smoke.sh"
  "scripts/ci/validate_batch5_smoke.sh"
  "scripts/ci/validate_batch6_smoke.sh"
  "scripts/ci/validate_batch7_smoke.sh"
  "scripts/ci/validate_batch8_smoke.sh"
  "scripts/ci/validate_batch9_smoke.sh"
  "scripts/ci/validate_batch9a_smoke.sh"
  "scripts/ci/validate_batch10_smoke.sh"
  "scripts/ci/validate_batch11_smoke.sh"
  "scripts/ci/validate_batch12_smoke.sh"
  "scripts/ci/validate_batch13_smoke.sh"
  "scripts/ci/validate_batch14_smoke.sh"
)

declare -a STATUSES=()
declare -a EXIT_CODES=()
declare -a LOG_PATHS=()

PASSED_COUNT=0
FAILED_COUNT=0

echo "Running all batch smoke validators with report output..."
echo "Reports will be written to $REPORT_DIR"
echo ""

for i in "${!BATCH_IDS[@]}"; do
  batch_id="${BATCH_IDS[$i]}"
  script_path="${SCRIPT_PATHS[$i]}"
  log_path="$REPORT_DIR/batch_${batch_id}_validation_${REPORT_STAMP}.log"

  if [ ! -f "$script_path" ]; then
    echo "[Batch $batch_id] MISSING SCRIPT: $script_path"
    STATUSES+=("missing")
    EXIT_CODES+=("127")
    LOG_PATHS+=("$log_path")
    FAILED_COUNT=$((FAILED_COUNT + 1))
    continue
  fi

  echo "[Batch $batch_id] Running $script_path"
  bash "$script_path" >"$log_path" 2>&1
  exit_code=$?

  if [ "$exit_code" -eq 0 ]; then
    echo "[Batch $batch_id] PASS"
    STATUSES+=("pass")
    PASSED_COUNT=$((PASSED_COUNT + 1))
  else
    echo "[Batch $batch_id] FAIL (exit code $exit_code)"
    STATUSES+=("fail")
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi

  EXIT_CODES+=("$exit_code")
  LOG_PATHS+=("$log_path")
done

OVERALL_STATUS="pass"
if [ "$FAILED_COUNT" -gt 0 ]; then
  OVERALL_STATUS="fail"
fi

{
  echo "# Batch Validation Report"
  echo ""
  echo "- Generated at (UTC): \`$TIMESTAMP_UTC\`"
  echo "- Scope: Batch smoke validation scripts (\`1-14\` + \`9A\`)"
  echo "- Source criteria: \`docs/auxiliary/task_execution/IMPLEMENTATION_BATCH_COMMAND_SHEET.md\`"
  echo "- Overall status: \`$OVERALL_STATUS\`"
  echo "- Passed: \`$PASSED_COUNT\`"
  echo "- Failed or missing: \`$FAILED_COUNT\`"
  echo ""
  echo "| Batch | Name | Validation Criteria | Script | Status | Exit Code | Log |"
  echo "| ---- | ---- | ---- | ---- | ---- | ---- | ---- |"

  for i in "${!BATCH_IDS[@]}"; do
    echo "| ${BATCH_IDS[$i]} | ${BATCH_NAMES[$i]} | ${VALIDATION_CRITERIA[$i]} | \`${SCRIPT_PATHS[$i]}\` | \`${STATUSES[$i]}\` | \`${EXIT_CODES[$i]}\` | \`${LOG_PATHS[$i]}\` |"
  done
} >"$MARKDOWN_REPORT"

{
  echo "{"
  echo "  \"generated_at_utc\": \"$TIMESTAMP_UTC\","
  echo "  \"overall_status\": \"$OVERALL_STATUS\","
  echo "  \"passed\": $PASSED_COUNT,"
  echo "  \"failed_or_missing\": $FAILED_COUNT,"
  echo "  \"criteria_source\": \"docs/auxiliary/task_execution/IMPLEMENTATION_BATCH_COMMAND_SHEET.md\","
  echo "  \"batches\": ["

  for i in "${!BATCH_IDS[@]}"; do
    comma=","
    if [ "$i" -eq "$((${#BATCH_IDS[@]} - 1))" ]; then
      comma=""
    fi
    cat <<EOF
    {
      "batch": "${BATCH_IDS[$i]}",
      "name": "${BATCH_NAMES[$i]}",
      "validation_criteria": "${VALIDATION_CRITERIA[$i]}",
      "script": "${SCRIPT_PATHS[$i]}",
      "status": "${STATUSES[$i]}",
      "exit_code": ${EXIT_CODES[$i]},
      "log_path": "${LOG_PATHS[$i]}"
    }$comma
EOF
  done

  echo "  ]"
  echo "}"
} >"$JSON_REPORT"

cp "$MARKDOWN_REPORT" "$LATEST_MARKDOWN"
cp "$JSON_REPORT" "$LATEST_JSON"

echo ""
echo "Report generated:"
echo "- $MARKDOWN_REPORT"
echo "- $JSON_REPORT"
echo "- $LATEST_MARKDOWN"
echo "- $LATEST_JSON"
echo ""
echo "Quick summary: $PASSED_COUNT passed, $FAILED_COUNT failed or missing."

if [ "$FAILED_COUNT" -gt 0 ]; then
  exit 1
fi

exit 0
