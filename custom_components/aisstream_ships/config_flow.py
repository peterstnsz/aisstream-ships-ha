import json
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector, TextSelectorConfig, TextSelectorType,
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
)
from .const import (
    DOMAIN, CONF_API_KEY, CONF_MAX_SHIPS, CONF_MIN_LENGTH,
    CONF_BOUNDING_BOX, CONF_BOUNDING_BOX_RAW,
    CONF_SHIP_TYPE_PRESET, CONF_MMSI_LIST, CONF_STALE_HOURS,
    DEFAULT_MAX_SHIPS, DEFAULT_MIN_LENGTH, DEFAULT_SHIP_TYPE_PRESET,
    DEFAULT_STALE_HOURS, DEFAULT_BBOX_RAW, SHIP_TYPE_PRESETS,
)


def _parse_mmsi_list(raw) -> list[int]:
    if isinstance(raw, list):
        return [int(m) for m in raw if str(m).strip().isdigit()]
    if not raw or not str(raw).strip():
        return []
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return [int(p) for p in parts if p.isdigit()]


def _mmsi_to_str(value) -> str:
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

    def _current(self, key, default):
        """Read from options first, fall back to data, then default."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    def _build_full_options(self, partial: dict) -> dict:
        """Merge partial submission with existing values into a complete options dict."""
        return {
            CONF_BOUNDING_BOX: partial.get(
                CONF_BOUNDING_BOX,
                self._current(CONF_BOUNDING_BOX, None)
            ),
            CONF_BOUNDING_BOX_RAW: partial.get(
                CONF_BOUNDING_BOX_RAW,
                self._current(CONF_BOUNDING_BOX_RAW, DEFAULT_BBOX_RAW)
            ),
            CONF_MAX_SHIPS: partial.get(
                CONF_MAX_SHIPS,
                self._current(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS)
            ),
            CONF_MIN_LENGTH: partial.get(
                CONF_MIN_LENGTH,
                self._current(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)
            ),
            CONF_SHIP_TYPE_PRESET: partial.get(
                CONF_SHIP_TYPE_PRESET,
                self._current(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET)
            ),
            CONF_MMSI_LIST: partial.get(
                CONF_MMSI_LIST,
                self._current(CONF_MMSI_LIST, [])
            ),
            CONF_STALE_HOURS: partial.get(
                CONF_STALE_HOURS,
                self._current(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)
            ),
        }

    # ------------------------------------------------------------------
    # Step 1 — MMSI entry (always shown first)
    # Routes to fleet_mode or area_mode depending on whether MMSIs are set
    # ------------------------------------------------------------------
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            mmsi_list = _parse_mmsi_list(user_input.get(CONF_MMSI_LIST, ""))
            self._mmsi_list = mmsi_list
            if mmsi_list:
                return await self.async_step_fleet_mode()
            else:
                return await self.async_step_area_mode()

        mmsi_default = _mmsi_to_str(self._current(CONF_MMSI_LIST, []))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_MMSI_LIST,
                    description={"suggested_value": mmsi_default},
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }),
            errors=errors,
            description_placeholders={
                "mmsi_hint": "Enter comma-separated MMSIs to track specific vessels worldwide, or leave blank for area mode."
            },
        )

    # ------------------------------------------------------------------
    # Step 2a — Fleet mode: only max ships + stale threshold
    # ------------------------------------------------------------------
    async def async_step_fleet_mode(self, user_input=None):
        if user_input is not None:
            partial = {
                CONF_MMSI_LIST: self._mmsi_list,
                CONF_MAX_SHIPS: user_input.get(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS),
                CONF_STALE_HOURS: user_input.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS),
            }
            return self.async_create_entry(title="", data=self._build_full_options(partial))

        return self.async_show_form(
            step_id="fleet_mode",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_MAX_SHIPS,
                    description={"suggested_value": self._current(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS)},
                ): NumberSelector(NumberSelectorConfig(min=2, max=20, mode=NumberSelectorMode.BOX)),
                vol.Optional(
                    CONF_STALE_HOURS,
                    description={"suggested_value": self._current(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)},
                ): NumberSelector(NumberSelectorConfig(min=0, max=72, mode=NumberSelectorMode.BOX)),
            }),
        )

    # ------------------------------------------------------------------
    # Step 2b — Area mode: bbox + ship type + min length + max ships + stale
    # ------------------------------------------------------------------
    async def async_step_area_mode(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                bbox_raw = user_input.get(CONF_BOUNDING_BOX_RAW, DEFAULT_BBOX_RAW)
                bbox = _parse_bbox(bbox_raw)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                errors[CONF_BOUNDING_BOX_RAW] = "invalid_bbox"
                bbox = None

            if not errors:
                partial = {
                    CONF_MMSI_LIST: [],
                    CONF_BOUNDING_BOX: bbox,
                    CONF_BOUNDING_BOX_RAW: user_input.get(CONF_BOUNDING_BOX_RAW, DEFAULT_BBOX_RAW),
                    CONF_MAX_SHIPS: user_input.get(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS),
                    CONF_MIN_LENGTH: user_input.get(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH),
                    CONF_SHIP_TYPE_PRESET: user_input.get(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET),
                    CONF_STALE_HOURS: user_input.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS),
                }
                return self.async_create_entry(title="", data=self._build_full_options(partial))

        stored_bbox = self._current(CONF_BOUNDING_BOX, None)
        bbox_default = _bbox_to_str(stored_bbox) if stored_bbox else DEFAULT_BBOX_RAW

        return self.async_show_form(
            step_id="area_mode",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_BOUNDING_BOX_RAW,
                    description={"suggested_value": bbox_default},
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_SHIP_TYPE_PRESET,
                    description={"suggested_value": self._current(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET)},
                ): SelectSelector(SelectSelectorConfig(
                    options=list(SHIP_TYPE_PRESETS.keys()),
                    mode=SelectSelectorMode.LIST,
                )),
                vol.Optional(
                    CONF_MIN_LENGTH,
                    description={"suggested_value": self._current(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)},
                ): NumberSelector(NumberSelectorConfig(min=0, max=500, mode=NumberSelectorMode.BOX)),
                vol.Optional(
                    CONF_MAX_SHIPS,
                    description={"suggested_value": self._current(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS)},
                ): NumberSelector(NumberSelectorConfig(min=2, max=20, mode=NumberSelectorMode.BOX)),
                vol.Optional(
                    CONF_STALE_HOURS,
                    description={"suggested_value": self._current(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)},
                ): NumberSelector(NumberSelectorConfig(min=0, max=72, mode=NumberSelectorMode.BOX)),
            }),
            errors=errors,
        )
