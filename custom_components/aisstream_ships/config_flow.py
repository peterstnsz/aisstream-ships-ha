import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN, CONF_API_KEY, CONF_MAX_SHIPS, CONF_MIN_LENGTH,
    CONF_BOUNDING_BOX, CONF_BOUNDING_BOX_RAW,
    CONF_SHIP_TYPE_PRESET, CONF_MMSI_LIST, CONF_STALE_HOURS,
    DEFAULT_MAX_SHIPS, DEFAULT_MIN_LENGTH, DEFAULT_SHIP_TYPE_PRESET,
    DEFAULT_STALE_HOURS, DEFAULT_BBOX_RAW, SHIP_TYPE_PRESETS,
)


def _parse_mmsi_list(raw: str) -> list[int]:
    if not raw or not raw.strip():
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts if p.isdigit()]


def _parse_bbox(raw: str):
    """Parse a bounding box string like [[lat1,lon1],[lat2,lon2]] into nested list."""
    parsed = json.loads(raw.strip())
    # Accept either [[lat,lon],[lat,lon]] or [[[lat,lon],[lat,lon]]]
    if isinstance(parsed[0][0], list):
        return parsed
    return [parsed]


def _bbox_to_str(bbox) -> str:
    """Serialise stored bbox back to a compact string for the form."""
    # Unwrap outer list if it's a single-box list of lists
    inner = bbox[0] if isinstance(bbox[0][0], list) else bbox
    return json.dumps(inner, separators=(",", ":"))


class AisstreamShipsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                bbox_raw = user_input.get(CONF_BOUNDING_BOX_RAW, DEFAULT_BBOX_RAW)
                user_input[CONF_BOUNDING_BOX] = _parse_bbox(bbox_raw)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                errors[CONF_BOUNDING_BOX_RAW] = "invalid_bbox"
            try:
                mmsi_raw = user_input.get(CONF_MMSI_LIST, "")
                user_input[CONF_MMSI_LIST] = _parse_mmsi_list(mmsi_raw)
            except ValueError:
                errors[CONF_MMSI_LIST] = "invalid_mmsi"
            if not errors:
                return self.async_create_entry(title="Aisstream Ships", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_BOUNDING_BOX_RAW, default=DEFAULT_BBOX_RAW): str,
                vol.Optional(CONF_MAX_SHIPS, default=DEFAULT_MAX_SHIPS):
                    vol.All(int, vol.Range(min=2, max=20)),
                vol.Optional(CONF_MIN_LENGTH, default=DEFAULT_MIN_LENGTH):
                    vol.All(int, vol.Range(min=0, max=500)),
                vol.Optional(CONF_SHIP_TYPE_PRESET, default=DEFAULT_SHIP_TYPE_PRESET):
                    vol.In(list(SHIP_TYPE_PRESETS.keys())),
                vol.Optional(CONF_MMSI_LIST, default=""): str,
                vol.Optional(CONF_STALE_HOURS, default=DEFAULT_STALE_HOURS):
                    vol.All(int, vol.Range(min=0, max=72)),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AisstreamShipsOptionsFlow(config_entry)


class AisstreamShipsOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    def _get(self, key, default):
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                bbox_raw = user_input.get(CONF_BOUNDING_BOX_RAW, DEFAULT_BBOX_RAW)
                user_input[CONF_BOUNDING_BOX] = _parse_bbox(bbox_raw)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                errors[CONF_BOUNDING_BOX_RAW] = "invalid_bbox"
            try:
                mmsi_raw = user_input.get(CONF_MMSI_LIST, "")
                user_input[CONF_MMSI_LIST] = _parse_mmsi_list(mmsi_raw)
            except ValueError:
                errors[CONF_MMSI_LIST] = "invalid_mmsi"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Re-serialise stored bbox and MMSI list for the form
        stored_bbox = self._get(CONF_BOUNDING_BOX, None)
        bbox_default = _bbox_to_str(stored_bbox) if stored_bbox else DEFAULT_BBOX_RAW

        stored_mmsi = self._get(CONF_MMSI_LIST, [])
        mmsi_default = ", ".join(str(m) for m in stored_mmsi)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_BOUNDING_BOX_RAW, default=bbox_default): str,
                vol.Optional(CONF_MAX_SHIPS,
                    default=self._get(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS)):
                    vol.All(int, vol.Range(min=2, max=20)),
                vol.Optional(CONF_MIN_LENGTH,
                    default=self._get(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)):
                    vol.All(int, vol.Range(min=0, max=500)),
                vol.Optional(CONF_SHIP_TYPE_PRESET,
                    default=self._get(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET)):
                    vol.In(list(SHIP_TYPE_PRESETS.keys())),
                vol.Optional(CONF_MMSI_LIST, default=mmsi_default): str,
                vol.Optional(CONF_STALE_HOURS,
                    default=self._get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)):
                    vol.All(int, vol.Range(min=0, max=72)),
            }),
            errors=errors,
        )
