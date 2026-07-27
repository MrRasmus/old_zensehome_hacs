DOMAIN = "zensehome_old"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_CODE = "code"

# Options
CONF_POLLING_MINUTES = "polling_minutes"
CONF_ENTITY_TYPES_JSON = "entity_types_json"

DEFAULT_PORT = 10001

# Internal defaults
DEFAULT_POLLING_MINUTES = 10
DEFAULT_CMD_GAP_S = 0.2          # slightly higher than 0.10 for less bus pressure
DEFAULT_DEBOUNCE_S = 0.5         # debounce dimming changes
DEFAULT_PAUSE_SECONDS = 300      # 5 minutes
DEFAULT_RECONCILE_DELAY_S = 2.0 # delayed get_level after optimistic commands
BRIGHTNESS_SCALE = 100


PLATFORMS = ["light", "switch", "button"]

# Keywords for "switch" if not mapped in entity_types_json
SWITCH_NAME_KEYWORDS = (
    "stik",
    "kontakt",
    "ventilation",
    "fan",
    "pump",
    "pumpe",
)
