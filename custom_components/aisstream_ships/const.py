DOMAIN = "aisstream_ships"
AISSTREAM_WS = "wss://stream.aisstream.io/v0/stream"

# Legacy default — passenger ships only (60–69)
PASSENGER_TYPES = set(range(60, 70))

# Ship type range presets available in the config flow
SHIP_TYPE_PRESETS = {
    "passenger": set(range(60, 70)),
    "cargo": set(range(70, 80)),
    "tanker": set(range(80, 90)),
    "all": set(range(0, 100)),
}

CONF_API_KEY = "api_key"
CONF_MAX_SHIPS = "max_ships"
CONF_MIN_LENGTH = "min_length_m"
CONF_BOUNDING_BOX = "bounding_box"
CONF_SHIP_TYPE_PRESET = "ship_type_preset"
CONF_MMSI_LIST = "mmsi_watchlist"
CONF_STALE_HOURS = "stale_threshold_hours"

DEFAULT_MAX_SHIPS = 10
DEFAULT_MIN_LENGTH = 0
DEFAULT_BBOX = [[[53.25, -3.20], [53.50, -2.85]]]
DEFAULT_SHIP_TYPE_PRESET = "passenger"
DEFAULT_STALE_HOURS = 1
WORLDWIDE_BBOX = [[[-90, -180], [90, 180]]]

STATUS_MAP = {
    0: "Underway",
    1: "Anchored",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Sailing",
    15: "Not defined",
    -1: "Unknown",
}

SIGNAL_UPDATE = f"{DOMAIN}_update"
