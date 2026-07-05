#!/usr/bin/env bash
# Configure ALARM IN zone 1 as silent doorbell input (NO button -> AlarmLocal Start).
set -euo pipefail

HOST="${DAHUA_ACS_HOST:-192.168.1.80}"
USER="${DAHUA_ACS_USER:-admin}"
PASS="${DAHUA_ACS_PASSWORD:-}"

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

echo "Configuring Alarm[0] (ALARM_1) as doorbell input..."
curl -s -m 15 -g "${AUTH[@]}" \
  "${BASE}?action=setConfig&Alarm%5B0%5D.Name=Doorbell&Alarm%5B0%5D.SensorType=NO&Alarm%5B0%5D.EventHandler.BeepEnable=false&Alarm%5B0%5D.EventHandler.AlarmOutEnable=false&Alarm%5B0%5D.EventHandler.Dejitter=1"
echo
curl -s -m 10 "${AUTH[@]}" "${BASE}?action=getConfig&name=Alarm" | tr '\r' '\n' | grep -E 'Alarm\[0\]\.(Name|SensorType|Beep|AlarmOut|Dejitter)'
