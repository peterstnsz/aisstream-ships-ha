import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN, CONF_API_KEY, CONF_MAX_SHIPS, CONF_MIN_LENGTH,
    CONF_SHIP_TYPE_PRESET, CONF_MMSI_LIST, CONF_STALE_HOURS,
    DEFAULT_MAX_SHIPS, DEFAULT_MIN_LENGTH, DEFAULT_SHIP_TYPE_PRESET,
    DEFAULT_STALE_HOURS, SHIP_TYPE_PRESETS,
)


def _parse_mmsi_list(raw: str) -> list[int]:
    """Parse a comma-separated string of MMSI numbers into a list of ints."""
    if not raw or not raw.strip():
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts if p.isdigit()]


class AisstreamShipsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
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
        """Read from options first, fall back to data, then default."""
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                mmsi_raw = user_input.get(CONF_MMSI_LIST, "")
                user_input[CONF_MMSI_LIST] = _parse_mmsi_list(mmsi_raw)
            except ValueError:
                errors[CONF_MMSI_LIST] = "invalid_mmsi"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Re-serialise stored MMSI list back to a comma-separated string for the form
        stored_mmsi = self._get(CONF_MMSI_LIST, [])
        mmsi_default = ", ".join(str(m) for m in stored_mmsi)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
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
