# Dahua ACS for Home Assistant

Custom integration for **Dahua access control panels** (e.g. **DHI-ASI1212M-W**) over LAN HTTP API with Digest authentication.

All entities are grouped under a single device. Supports HTTP push events (EventHttpUpload) via webhook.

## Features

- **Lock** — remote open/close (`openDoor` / `closeDoor`, Type=Remote)
- **Sensor** — door status (`Open`, `Close`, `Break`)
- **Sensor** — last HTTP event from the panel
- **Binary sensor** — doorbell pulse (AccessControl method=12 or AlarmLocal)
- **Webhook** — compatible with existing URL `/api/webhook/dahua_acs_events`
- Config flow: host, username, password, channel
- Options: polling interval, enable/disable events

## Installation

### HACS (recommended)

1. Add this repository as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) (Integration).
2. Install **Dahua ACS** from HACS.
3. Restart Home Assistant.
4. **Settings → Devices & services → Add integration → Dahua ACS**
5. Enter panel IP (e.g. `192.168.1.80`), username and password.

### Manual

Copy `custom_components/dahua_acs` to your Home Assistant `config/custom_components/` directory and restart HA.

## Panel HTTP events

Configure **EventHttpUpload** on the panel to POST to:

```text
http://<ha-host>:8123/api/webhook/dahua_acs_events
```

The integration registers this webhook ID by default (same as the legacy YAML package).

## Migration from YAML package

If you used `packages/dahua_access_panel.yaml` and `packages/dahua_event_webhook.yaml`:

1. Install this integration and add the panel.
2. Assign the device to the desired area (e.g. **Прихожая**).
3. Disable or remove the YAML packages.
4. Entity IDs `lock.dahua_door` and `sensor.dahua_door_status` are preserved via matching `unique_id`.

## License

MIT
