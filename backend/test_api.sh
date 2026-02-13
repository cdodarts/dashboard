#!/usr/bin/env bash
# =============================================================================
# CDO Vertex Dashboard - API Test Script
# =============================================================================
# Usage: bash scripts/test_api.sh [host]
# =============================================================================

HOST="${1:-http://localhost:5001}"
PASS=0
FAIL=0
TOTAL=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

test_endpoint() {
    local method="$1"
    local path="$2"
    local data="$3"
    local desc="$4"
    TOTAL=$((TOTAL + 1))

    if [ "$method" = "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "${HOST}${path}" 2>/dev/null)
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" "${HOST}${path}" 2>/dev/null)
    fi

    if [ "$response" -ge 200 ] && [ "$response" -lt 400 ]; then
        echo -e "  ${GREEN}✓${NC} [${response}] ${method} ${path} - ${desc}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗${NC} [${response}] ${method} ${path} - ${desc}"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== CDO Vertex Dashboard API Tests ==="
echo "  Target: ${HOST}"
echo ""

echo "--- Health Check ---"
test_endpoint GET "/api/health" "" "Health check"

echo ""
echo "--- System Monitoring ---"
test_endpoint GET "/api/system/status" "" "Full system status"
test_endpoint GET "/api/system/cpu" "" "CPU info"
test_endpoint GET "/api/system/memory" "" "Memory info"
test_endpoint GET "/api/system/disk" "" "Disk info"
test_endpoint GET "/api/system/temperature" "" "Temperature"
test_endpoint GET "/api/system/network" "" "Network info"
test_endpoint GET "/api/system/wifi" "" "WiFi info"
test_endpoint GET "/api/system/uptime" "" "Uptime"
test_endpoint GET "/api/system/hostname" "" "Hostname"

echo ""
echo "--- Autodarts Management ---"
test_endpoint GET "/api/autodarts/status" "" "Autodarts status"
test_endpoint GET "/api/autodarts/check-update" "" "Check for updates"
test_endpoint GET "/api/autodarts/logs?lines=10" "" "Service logs"

echo ""
echo "--- Settings ---"
test_endpoint GET "/api/settings" "" "Get all settings"
test_endpoint POST "/api/settings" '{"display":{"theme":"dark"}}' "Update settings"
test_endpoint GET "/api/settings/auto-update" "" "Get auto-update settings"
test_endpoint POST "/api/settings/auto-update" '{"enabled":false}' "Update auto-update"
test_endpoint POST "/api/settings/reset" "" "Reset settings"

echo ""
echo "=== Results ==="
echo -e "  ${GREEN}Passed: ${PASS}${NC}  ${RED}Failed: ${FAIL}${NC}  Total: ${TOTAL}"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
