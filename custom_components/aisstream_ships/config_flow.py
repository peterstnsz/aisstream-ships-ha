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


def _parse_mmsi_list(raw) -> list[int]:
    """Accept either a comma-separated string or an already-parsed list."""
    if isinstance(raw, list):
        return [int(m) for m in raw if str(m).strip().isdigit()]
    if not raw or not str(raw).strip():
        return []
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return [int(p) for p in parts if p.isdigit()]


def _mmsi_to_str(value) -> str:
    """Serialise a stored MMSI value (list or string) back to display string."""
    if isinstance(value, list):
        return ", ".join(str(m) for m in value)
    return str(value) if value else ""


def _parse_bbox(raw: str):
    parsed = json.loads(raw.strip())
    if isinstance(parsed[0][0], list):
        return parsed
    return [parsed]


def _bbox_to_str(bbox) -> str:
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
                user_input[CONF_MMSI_LIST] = _parse_mmsi_list(
                    user_input.get(CONF_MMSI_LIST, "")
                )
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

    def _current(self, key, default):
        """Always read the most recently saved value: options beats data."""
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
                user_input[CONF_MMSI_LIST] = _parse_mmsi_list(
                    user_input.get(CONF_MMSI_LIST, "")
                )
            except ValueError:
                errors[CONF_MMSI_LIST] = "invalid_mmsi"

            if not errors:
                # Write the FULL config into options so entry.data is never
                # consulted again — avoids stale fallback values on reopen.
                full_options = {
                    CONF_BOUNDING_BOX: user_input[CONF_BOUNDING_BOX],
                    CONF_BOUNDING_BOX_RAW: user_input.get(CONF_BOUNDING_BOX_RAW, DEFAULT_BBOX_RAW),
                    CONF_MAX_SHIPS: user_input.get(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS),
                    CONF_MIN_LENGTH: user_input.get(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH),
                    CONF_SHIP_TYPE_PRESET: user_input.get(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET),
                    CONF_MMSI_LIST: user_input[CONF_MMSI_LIST],
                    CONF_STALE_HOURS: user_input.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS),
                }
                return self.async_create_entry(title="", data=full_options)

        # Populate form with current saved values
        stored_bbox = self._current(CONF_BOUNDING_BOX, None)
        bbox_default = _bbox_to_str(stored_bbox) if stored_bbox else DEFAULT_BBOX_RAW

        mmsi_default = _mmsi_to_str(self._current(CONF_MMSI_LIST, []))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_BOUNDING_BOX_RAW, default=bbox_default): str,
                vol.Optional(CONF_MAX_SHIPS,
                    default=self._current(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS)):
                    vol.All(int, vol.Range(min=2, max=20)),
                vol.Optional(CONF_MIN_LENGTH,
                    default=self._current(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)):
                    vol.All(int, vol.Range(min=0, max=500)),
                vol.Optional(CONF_SHIP_TYPE_PRESET,
                    default=self._current(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET)):
                    vol.In(list(SHIP_TYPE_PRESETS.keys())),
                vol.Optional(CONF_MMSI_LIST, default=mmsi_default): str,
                vol.Optional(CONF_STALE_HOURS,
                    default=self._current(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)):
                    vol.All(int, vol.Range(min=0, max=72)),
            }),
            errors=errors,
        )
