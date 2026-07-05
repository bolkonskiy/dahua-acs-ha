#!/usr/bin/env bash
# Point Dahua EventHttpUpload to the deflate relay (recommended) or HA webhook.
set -euo pipefail

HOST="${DAHUA_ACS_HOST:-192.168.1.80}"
USER="${DAHUA_ACS_USER:-admin}"
PASS="${DAHUA_ACS_PASSWORD:-}"

# Relay on LAN host (e.g. Proxmox) — panel cannot POST deflate JSON to HA directly.
RELAY_HOST="${RELAY_HOST:-192.168.1.10}"
RELAY_PORT="${RELAY_PORT:-8818}"
RELAY_PATH="${RELAY_PATH:-/}"

if [[ -z "$PASS" && -f "${DAHUA_SECRETS:-/config/secrets.yaml}" ]]; then
  SECRETS="${DAHUA_SECRETS:-/config/secrets.yaml}"
  PASS=$(grep -E '^dahua_acs_password:' "$SECRETS" | sed -E 's/^dahua_acs_password:\s*"?([^"#]+)"?.*/\1/' | tr -d ' ')
  USER=$(grep -E '^dahua_acs_user:' "$SECRETS" | sed -E 's/^dahua_acs_user:\s*"?([^"#]+)"?.*/\1/' | tr -d ' ' || true)
  HOST=$(grep -E '^dahua_acs_host:' "$SECRETS" | sed -E 's/^dahua_acs_host:\s*"?([^"#]+)"?.*/\1/' | tr -d ' ' || true)
  HOST="${HOST:-192.168.1.80}"
  USER="${USER:-admin}"
fi
[[ -n "$PASS" ]] || { echo "Need DAHUA_ACS_PASSWORD" >&2; exit 1; }

BASE="http://${HOST}/cgi-bin/configManager.cgi"
AUTH=(--digest -u "${USER}:${PASS}")

set_param() {
  local q="$1"
  echo ">>> $q"
  curl -s -m 15 -g "${AUTH[@]}" "${BASE}?${q}"
  echo
}

echo "Before:"
curl -s -m 10 "${AUTH[@]}" "${BASE}?action=getConfig&name=EventHttpUpload" | tr '\r' '\n'
echo

set_param "action=setConfig&EventHttpUpload.Enable=true"
set_param "action=setConfig&EventHttpUpload.UploadServerList[0].Address=${RELAY_HOST}"
set_param "action=setConfig&EventHttpUpload.UploadServerList[0].Port=${RELAY_PORT}"
set_param "action=setConfig&EventHttpUpload.UploadServerList[0].Uploadpath=${RELAY_PATH}"
set_param "action=setConfig&EventHttpUpload.UploadServerList[0].EventType[0]=AccessControl&EventHttpUpload.UploadServerList[0].EventType[1]=AlarmLocal"

echo "After:"
curl -s -m 10 "${AUTH[@]}" "${BASE}?action=getConfig&name=EventHttpUpload" | tr '\r' '\n'
