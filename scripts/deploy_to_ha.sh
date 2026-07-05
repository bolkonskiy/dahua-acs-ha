#!/usr/bin/env bash
# Sync custom_components/dahua_acs to Home Assistant and restart core.
#
# Preferred: install via HACS and use "Update" after git push.
# This script is for direct deploy from a git checkout (e.g. CI / homelab).
#
# Env:
#   PROXMOX_HOST  default root@chprkv.by
#   PROXMOX_SSH_PORT default 2222
#   HA_VMID       default 1000
#   SSH_KEY       default ~/.ssh/anton.chuprakov

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROXMOX_HOST="${PROXMOX_HOST:-root@chprkv.by}"
PROXMOX_SSH_PORT="${PROXMOX_SSH_PORT:-2222}"
HA_VMID="${HA_VMID:-1000}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/anton.chuprakov}"
HA_CC="/mnt/data/supervisor/homeassistant/custom_components"

SSH=(ssh -i "$SSH_KEY" -p "$PROXMOX_SSH_PORT" "$PROXMOX_HOST")

echo "Packaging dahua_acs from $REPO_ROOT"
TARBALL="$(mktemp /tmp/dahua_acs.XXXXXX.tar.gz)"
tar -C "$REPO_ROOT/custom_components" -czf "$TARBALL" dahua_acs
B64="$(base64 < "$TARBALL" | tr -d '\n')"
rm -f "$TARBALL"

echo "Deploying to HA VM $HA_VMID..."
"${SSH[@]}" "qm guest exec $HA_VMID -- sh -c 'echo $B64 | base64 -d | tar -xzf - -C $HA_CC && ha core restart'"

echo "Done. Reload integration in HA if needed: Settings → Devices → Dahua ACS → Reload."
