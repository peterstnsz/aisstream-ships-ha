from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import (
    DOMAIN, SIGNAL_UPDATE, CONF_MAX_SHIPS, CONF_MIN_LENGTH,
    DEFAULT_MAX_SHIPS, DEFAULT_MIN_LENGTH, STATUS_MAP, SHIP_TYPE_LABEL_MAP,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    max_ships = int(entry.options.get(CONF_MAX_SHIPS, entry.data.get(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS)))
    min_length = int(entry.options.get(CONF_MIN_LENGTH, entry.data.get(CONF_MIN_LENGTH, DEFAULT_MIN_LENGTH)))

    entities: list[SensorEntity] = [
        AisstreamShipCountSensor(coordinator, entry, min_length),
        AisstreamShipsHeaderSensor(coordinator, entry, min_length),
    ]
    for i in range(1, max_ships + 1):
        entities.append(AisstreamShipSlotSensor(coordinator, entry, i, min_length))
        entities.append(AisstreamShipLineSensor(coordinator, entry, i, min_length))

    async_add_entities(entities)


class _AisstreamBase(SensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator, entry, min_length: int) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._min_length = min_length

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATE}_{self._entry.entry_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    def _get(self, key, default):
        return self._entry.options.get(key, self._entry.data.get(key, default))

    def _ships(self) -> list:
        max_ships = int(self._get(CONF_MAX_SHIPS, DEFAULT_MAX_SHIPS))
        return self._coordinator.get_ships(
            min_length=self._min_length, max_results=max_ships
        )


class AisstreamShipCountSensor(_AisstreamBase):
    _attr_icon = "mdi:ferry"
    _attr_native_unit_of_measurement = "vessels"

    def __init__(self, coordinator, entry, min_length: int) -> None:
        super().__init__(coordinator, entry, min_length)
        self._attr_unique_id = f"{entry.entry_id}_count"
        self._attr_name = "Aisstream Ship Count"

    @property
    def native_value(self) -> int:
        return len(self._ships())


class AisstreamShipsHeaderSensor(_AisstreamBase):
    _attr_icon = "mdi:ferry"

    def __init__(self, coordinator, entry, min_length: int) -> None:
        super().__init__(coordinator, entry, min_length)
        self._attr_unique_id = f"{entry.entry_id}_header"
        self._attr_name = "Aisstream Ships Header"

    @property
    def native_value(self) -> str:
        n = len(self._ships())
        fleet_mode = self._coordinator._fleet_mode()
        if n == 0:
            return "No ships tracked" if fleet_mode else "No ships in area"
        label = "Fleet tracked" if fleet_mode else "Ships in area"
        return f"{label}: {n}"


class AisstreamShipSlotSensor(_AisstreamBase):
    _attr_icon = "mdi:ship-wheel"

    def __init__(self, coordinator, entry, slot: int, min_length: int) -> None:
        super().__init__(coordinator, entry, min_length)
        self._slot = slot
        self._attr_unique_id = f"{entry.entry_id}_ship_{slot}"
        self._attr_name = f"Aisstream Ship {slot}"

    def _ship(self) -> dict | None:
        ships = self._ships()
        return ships[self._slot - 1] if self._slot <= len(ships) else None

    @property
    def native_value(self) -> str:
        ship = self._ship()
        return ship["name"] if ship else ""

    @property
    def extra_state_attributes(self) -> dict:
        ship = self._ship()
        if not ship:
            return {}
        raw_status = ship.get("status", -1)
        ship_type_code = ship.get("ship_type", 0)
        return {
            "destination": ship.get("destination") or "Unknown",
            "status": STATUS_MAP.get(raw_status, "Unknown"),
            "status_code": raw_status,
            "ship_type": ship_type_code,
            "ship_type_label": SHIP_TYPE_LABEL_MAP.get(ship_type_code, "Vessel"),
            "speed_knots": ship.get("speed", 0),
            "true_heading": ship.get("true_heading"),
            "length_m": ship.get("length_m", 0),
            "mmsi": ship.get("mmsi"),
            "latitude": ship.get("lat"),
            "longitude": ship.get("lon"),
            "last_seen": ship.get("last_seen"),
        }


class AisstreamShipLineSensor(_AisstreamBase):
    _attr_icon = "mdi:text-short"

    def __init__(self, coordinator, entry, slot: int, min_length: int) -> None:
        super().__init__(coordinator, entry, min_length)
        self._slot = slot
        self._attr_unique_id = f"{entry.entry_id}_line_{slot}"
        self._attr_name = f"Aisstream Ship Line {slot}"

    @property
    def native_value(self) -> str:
        ships = self._ships()
        if self._slot > len(ships):
            return "—"
        return self._coordinator.format_ship_line(ships[self._slot - 1])
