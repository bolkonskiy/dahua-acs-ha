"""Constants for Dahua ACS integration."""

DOMAIN = "dahua_acs"

CONF_CHANNEL = "channel"
CONF_ENABLE_EVENTS = "enable_events"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PASSWORD = "password"
CONF_USERNAME = "username"
CONF_WEBHOOK_ID = "webhook_id"

DEFAULT_CHANNEL = 1
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_USERNAME = "admin"
DEFAULT_WEBHOOK_ID = "dahua_acs_events"

MANUFACTURER = "Dahua"
MODEL = "DHI-ASI1212M-W"

DOORBELL_METHOD = 12

# AlarmLocal from external button on ALARM IN: Start=pressed, Stop=released.
ALARM_LOCAL_PRESS_ACTIONS = frozenset({"Start", "Pulse"})
ACCESS_CONTROL_PRESS_ACTIONS = frozenset({"Pulse", "Start", ""})
