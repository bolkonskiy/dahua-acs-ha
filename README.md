# Dahua ACS for Home Assistant

Custom integration for **Dahua access control panels** (e.g. **DHI-ASI1212M-W**) over LAN HTTP API with Digest authentication.

All entities are grouped under a single device. Supports HTTP push events (EventHttpUpload) via webhook.

## Features

- **Lock** — remote open/close (`openDoor` / `closeDoor`, Type=Remote)
- **Sensor** — door status (`Open`, `Close`, `Break`)
- **Sensor** — last HTTP event from the panel
- **Binary sensor** — doorbell pulse on **press only** (`AlarmLocal` `Start` or `AccessControl` method=12)
- **Webhook** — `/api/webhook/dahua_acs_events`
- Config flow: host, username, password, channel
- Options: polling interval, enable/disable events

## Installation & updates (HACS)

This integration is installed and updated **only through HACS** — do not copy files over SSH or guest-agent scripts; that bypasses HACS version tracking.

### First install

1. **HACS → Integrations → ⋮ → Custom repositories** → add `https://github.com/bolkonskiy/dahua-acs-ha` (category: Integration).
2. **HACS → Integrations → Dahua ACS → Download**.
3. **Restart Home Assistant**.
4. **Settings → Devices & services → Add integration → Dahua ACS** — panel IP, username, password.

### After code changes (release workflow)

1. Bump `version` in `custom_components/dahua_acs/manifest.json`.
2. `git commit` + `git push` to `main` on GitHub.
3. Create a GitHub Release (tag format: `vX.Y.Z`) from that commit.
4. On HA: **HACS → Integrations → Dahua ACS → Update** (pulls latest release).
5. **Restart Home Assistant** (HACS may offer this automatically).

No SSH, no `qm guest exec`, no manual `custom_components` overwrite on the server.

## Doorbell via ALARM IN (ASI1212)

The panel **Doorbell Out** port is a dry contact only — it does not send network events.  
Wire the external button to **ALARM_1 + GND** (NO) and use `AlarmLocal` HTTP push.

1. **Panel zone** (silent, no 15s buzzer):

   ```bash
   DAHUA_ACS_PASSWORD=... ./scripts/configure_alarm_doorbell.sh
   ```

2. **Deflate relay** on a LAN host (Proxmox, NAS, etc.):

   ```bash
   sudo cp scripts/dahua_event_relay.py /usr/local/bin/
   sudo cp systemd/dahua-event-relay.service /etc/systemd/system/
   sudo systemctl enable --now dahua-event-relay
   ```

3. **EventHttpUpload** on the panel → relay:

   ```bash
   DAHUA_ACS_PASSWORD=... RELAY_HOST=192.168.1.10 ./scripts/dahua_enable_http_upload.sh
   ```

4. Relay forwards JSON to HA webhook (registered by this integration).

The integration fires `binary_sensor.*_doorbell` only on **press** (`AlarmLocal` `Action=Start`), not on release (`Stop`).

## Panel HTTP events

Configure **EventHttpUpload** to POST to the relay (port **8818**), not directly to HA — ASI1212 sends `Content-Encoding: deflate` bodies.

HA webhook URL (used by relay):

```text
http://<ha-host>:8123/api/webhook/dahua_acs_events
```

## Entities

| Entity | Description |
|--------|-------------|
| `lock.dahua_door` | Open / close |
| `sensor.dahua_door_status` | `Open` / `Close` / `Break` |
| `sensor.dahua_last_http_event` | Last HTTP push (all events) |
| `binary_sensor.*_doorbell` | Pulse on doorbell **press** |

## Migration from YAML package

If you used `packages/dahua_access_panel.yaml` and `packages/dahua_event_webhook.yaml`:

1. Install this integration and add the panel.
2. Remove or disable the YAML packages.
3. Entity IDs `lock.dahua_door` and `sensor.dahua_door_status` are preserved via matching `unique_id`.

## License

MIT
