DOMAIN = "zensehome"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_CODE = "code"

# Options
CONF_POLLING_MINUTES = "polling_minutes"
CONF_ENTITY_TYPES_JSON = "entity_types_json"

DEFAULT_PORT = 10001

# Interne defaults
DEFAULT_POLLING_MINUTES = 10
DEFAULT_CMD_GAP = 0.2          # lidt højere end 0.10 for mindre pres
DEFAULT_DEBOUNCE_S = 0.5        # øget fra 0.2

PLATFORMS = ["light", "switch"]

# Heuristik keywords til "switch" hvis ikke mappet
SWITCH_NAME_KEYWORDS = (
    "stik",
    "kontakt",
    "ventilation",
    "fan",
    "pump",
    "pumpe",
)