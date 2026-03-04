#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# check.sh - Network & service diagnostic for INN Image Steganography
#
# Run this on the SERVER when remote clients cannot reach the web UI.
#
# Usage:
#   bash check.sh [PORT]
#   PORT defaults to the value of the PORT env var, or 5000.
# ---------------------------------------------------------------------------

: "${PORT:=${1:-5000}}"
PASS=0; FAIL=0; WARN=0

ok()   { echo "[OK]   $*"; PASS=$((PASS+1)); }
fail() { echo "[FAIL] $*"; FAIL=$((FAIL+1)); }
warn() { echo "[WARN] $*"; WARN=$((WARN+1)); }
info() { echo "[INFO] $*"; }

echo "============================================================"
echo "  INN Steganography - Network Diagnostic"
echo "  Port under test: ${PORT}"
echo "============================================================"
echo ""

# ── 1. Is gunicorn / Python bound to the port? ─────────────────────────────
echo "── 1. Process binding ──────────────────────────────────────"
if command -v ss >/dev/null 2>&1; then
    BINDING=$(ss -tlnp 2>/dev/null | grep ":${PORT}")
elif command -v netstat >/dev/null 2>&1; then
    BINDING=$(netstat -tlnp 2>/dev/null | grep ":${PORT}")
else
    BINDING=""
fi

if [ -z "${BINDING}" ]; then
    fail "Nothing is listening on port ${PORT}."
    echo "       → Start the service first: bash start.sh"
else
    if echo "${BINDING}" | grep -qE "0\.0\.0\.0:${PORT}|:::${PORT}|\*:${PORT}"; then
        ok "Service is bound to 0.0.0.0:${PORT} (accessible from all interfaces)"
    elif echo "${BINDING}" | grep -q "127\.0\.0\.1:${PORT}"; then
        fail "Service is bound to 127.0.0.1:${PORT} (loopback only — not reachable remotely)"
        echo "       → Check gunicorn.conf.py: bind must be '0.0.0.0:${PORT}'"
    else
        warn "Service binding: ${BINDING}"
    fi
fi
echo ""

# ── 2. Local reachability (curl) ────────────────────────────────────────────
echo "── 2. Local HTTP reachability ──────────────────────────────"
if command -v curl >/dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout 3 "http://127.0.0.1:${PORT}/" 2>/dev/null || echo "000")
    if [ "${HTTP_CODE}" != "000" ]; then
        ok "Local request to http://127.0.0.1:${PORT}/ returned HTTP ${HTTP_CODE}"
    else
        fail "curl to http://127.0.0.1:${PORT}/ timed out or was refused"
        echo "       → Service may not be running"
    fi
else
    warn "curl not found; skipping local HTTP check"
fi
echo ""

# ── 3. UFW firewall ─────────────────────────────────────────────────────────
echo "── 3. UFW firewall ─────────────────────────────────────────"
if command -v ufw >/dev/null 2>&1; then
    UFW_STATUS=$(sudo ufw status 2>/dev/null || ufw status 2>/dev/null || echo "unknown")
    if echo "${UFW_STATUS}" | grep -qi "inactive"; then
        ok "UFW is inactive (no firewall blocking)"
    elif echo "${UFW_STATUS}" | grep -qi "Status: active"; then
        # Match port number anywhere in the line (e.g. "5000/tcp" or "5000 ")
        if echo "${UFW_STATUS}" | grep -qE "${PORT}/tcp|${PORT}[[:space:]]|${PORT}$"; then
            ok "UFW is active and port ${PORT} is allowed"
        else
            fail "UFW is active but port ${PORT} is NOT in the allow list"
            echo ""
            echo "  ┌─ FIX: Open port ${PORT} in UFW ─────────────────────────────"
            echo "  │  sudo ufw allow ${PORT}/tcp"
            echo "  │  sudo ufw reload"
            echo "  │"
            echo "  │  Or allow only a specific client subnet (replace <CLIENT_SUBNET>):"
            echo "  │  sudo ufw allow from <CLIENT_SUBNET> to any port ${PORT} proto tcp"
            echo "  └────────────────────────────────────────────────────────────"
        fi
    else
        warn "Could not determine UFW status (may need sudo)"
    fi
else
    info "UFW not found; checking iptables..."
    if command -v iptables >/dev/null 2>&1; then
        IPTABLES_DROP=$(sudo iptables -L INPUT -n 2>/dev/null | grep -c "DROP\|REJECT" || echo "0")
        if [ "${IPTABLES_DROP}" -gt 0 ]; then
            warn "iptables has DROP/REJECT rules. Check if port ${PORT} is allowed:"
            echo "       sudo iptables -L INPUT -n | grep ${PORT}"
        else
            ok "No obvious iptables DROP rules found"
        fi
    else
        ok "No firewall tool (ufw/iptables) detected"
    fi
fi
echo ""

# ── 4. Server IP addresses ──────────────────────────────────────────────────
echo "── 4. Server IP addresses ──────────────────────────────────"
IPS=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | grep -v '^::' || echo "unknown")
info "This server's IPs:"
echo "${IPS}" | while read -r ip; do
    echo "       ${ip}"
done
echo ""
echo "  Access URLs to try from a remote browser:"
echo "${IPS}" | grep -v '^127\.' | while read -r ip; do
    echo "       http://${ip}:${PORT}"
done
echo ""

# ── 5. Network routing ──────────────────────────────────────────────────────
echo "── 5. Default gateway reachability ────────────────────────"
GW=$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')
if [ -n "${GW}" ]; then
    if ping -c1 -W2 "${GW}" >/dev/null 2>&1; then
        ok "Default gateway ${GW} is reachable"
    else
        warn "Cannot reach default gateway ${GW} — check network configuration"
    fi
else
    warn "No default route found"
fi
echo ""

# ── Summary ─────────────────────────────────────────────────────────────────
echo "============================================================"
echo "  Summary: ${PASS} passed  |  ${WARN} warnings  |  ${FAIL} failed"
echo "============================================================"
if [ "${FAIL}" -gt 0 ]; then
    echo ""
    echo "  Fix the FAIL items above, then re-run: bash check.sh"
    echo ""
    echo "  If UFW was blocking, run on the server:"
    echo "    sudo ufw allow ${PORT}/tcp && sudo ufw reload"
    echo ""
    echo "  If the client is on a different subnet, use SSH port-forward:"
    echo "    ssh -L ${PORT}:127.0.0.1:${PORT} <user>@<server-ip>"
    echo "    Then open: http://localhost:${PORT}"
    exit 1
fi
