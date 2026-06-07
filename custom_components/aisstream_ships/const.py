DOMAIN = "aisstream_ships"
AISSTREAM_WS = "wss://stream.aisstream.io/v0/stream"

# Ship type range presets
SHIP_TYPE_PRESETS = {
    "passenger": set(range(60, 70)),
    "cargo": set(range(70, 80)),
    "tanker": set(range(80, 90)),
    "all": set(range(0, 100)),
}

PASSENGER_TYPES = set(range(60, 70))

# Human-readable AIS ship type labels
SHIP_TYPE_LABEL_MAP = {
    **{c: "Passenger" for c in range(60, 70)},
    **{c: "Cargo" for c in range(70, 80)},
    **{c: "Tanker" for c in range(80, 90)},
    **{c: "Fishing" for c in [30, 31, 32, 33, 34, 35]},
    **{c: "Service" for c in range(50, 60)},
    36: "Sailing", 37: "Sailing",
    **{c: "High Speed" for c in range(40, 50)},
    21: "SAR", 22: "SAR",
    31: "Towing", 32: "Towing",
    33: "Dredging", 34: "Diving",
    35: "Military",
    51: "Pilot", 52: "Rescue", 53: "Tug", 54: "Port Tender",
    55: "Anti-pollution", 58: "Medical",
    90: "Other", 91: "Other", 99: "Other",
}

CONF_API_KEY = "api_key"
CONF_MAX_SHIPS = "max_ships"
CONF_MIN_LENGTH = "min_length_m"
CONF_BOUNDING_BOX = "bounding_box"
CONF_BOUNDING_BOX_RAW = "bounding_box_raw"
CONF_SHIP_TYPE_PRESET = "ship_type_preset"
CONF_MMSI_LIST = "mmsi_watchlist"
CONF_STALE_HOURS = "stale_threshold_hours"

DEFAULT_MAX_SHIPS = 10
DEFAULT_MIN_LENGTH = 0
DEFAULT_SHIP_TYPE_PRESET = "passenger"
DEFAULT_STALE_HOURS = 1

# Minimal 1x1 degree dummy bbox used in fleet mode.
# BoundingBoxes is a required field in the AISstream subscription,
# but FiltersShipMMSI works globally regardless of bbox.
# Sending a tiny box avoids the firehose of a worldwide subscription.
FLEET_MODE_BBOX = [[[0, 0], [1, 1]]]

# Kept for reference but no longer sent
WORLDWIDE_BBOX = [[[-90, -180], [90, 180]]]

DEFAULT_BBOX_RAW = "[[53.25,-3.20],[53.50,-2.85]]"

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
