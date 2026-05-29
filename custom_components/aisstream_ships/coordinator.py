import asyncio
import json
import logging
import ssl
from datetime import datetime, timezone
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import (
    AISSTREAM_WS, PASSENGER_TYPES, STATUS_MAP, SIGNAL_UPDATE,
    CONF_API_KEY, CONF_MAX_SHIPS, CONF_MIN_LENGTH,
    CONF_BOUNDING_BOX, DEFAULT_BBOX, DEFAULT_MAX_SHIPS, DEFAULT_MIN_LENGTH
)

_LOGGER = logging.getLogger(__name__)

RECONNECT_DELAY = 30  # seconds between reconnect attempts


class AisstreamShipsCoordinator:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self._entry = entry
        self.ships: dict = {}
        self._ws_task: asyncio.Task | None = None

    async def async_start(self) -> None:
        self._ws_task = self.hass.loop.create_task(self._connect_stream())

    async def async_stop(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

    def get_passenger_ships(self, min_length: int = 0, max_results: int = 4) -> list:
        ships = [
            s for s in self.ships.values()
            if s["ship_type"] in PASSENGER_TYPES
            and s["name"] not in ("Unknown", "")
            and s["length_m"] >= min_length
        ]
        ships.sort(key=lambda s: s.get("last_seen") or "", reverse=True)
        return ships[:max_results]

    def format_ship_line(self, ship: dict) -> str:
        name = ship["name"][:18]
        dest = (ship.get("destination") or "Unknown")[:12]
        status = STATUS_MAP.get(ship.get("status", -1), "Unknown")
        return f"{name} ({status} > {dest})"

    async def _connect_stream(self) -> None:
        try:
            import websockets
        except ImportError:
            _LOGGER.error("Aisstream Ships: websockets library not installed")
            return

        api_key = self._entry.data[CONF_API_KEY]
        bbox = self._entry.data.get(CONF_BOUNDING_BOX, DEFAULT_BBOX)

        while True:
            try:
                # Build SSL context off the event loop to avoid blocking call
                # (load_default_certs is a blocking I/O operation)
                ssl_context = await self.hass.async_add_executor_job(
                    ssl.create_default_context
                )

                async with websockets.connect(AISSTREAM_WS, ssl=ssl_context) as ws:
                    await ws.send(json.dumps({
                        "APIKey": api_key,
                        "BoundingBoxes": bbox,
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
                    }))
                    _LOGGER.info("Aisstream Ships: connected to AISstream.io")
                    async for raw in ws:
                        self._handle_message(json.loads(raw))
                        async_dispatcher_send(
                            self.hass,
                            f"{SIGNAL_UPDATE}_{self._entry.entry_id}"
                        )
            except asyncio.CancelledError:
                return
            except Exception as exc:
                _LOGGER.error(
                    "Aisstream Ships: connection error: %s — retrying in %ss",
                    exc, RECONNECT_DELAY
                )
                await asyncio.sleep(RECONNECT_DELAY)

    def _handle_message(self, msg: dict) -> None:
        mmsi = msg.get("MetaData", {}).get("MMSI", 0)
        if not mmsi:
            return
        msg_type = msg.get("MessageType")

        if mmsi not in self.ships:
            self.ships[mmsi] = {
                "mmsi": mmsi, "name": "Unknown", "ship_type": 0,
                "speed": 0.0, "lat": 0.0, "lon": 0.0,
                "destination": "", "status": -1, "length_m": 0,
                "last_seen": None,
            }

        ship = self.ships[mmsi]
        ship["last_seen"] = datetime.now(timezone.utc).isoformat()

        if msg_type == "ShipStaticData":
            data = msg["Message"]["ShipStaticData"]
            ship["name"] = (data.get("Name") or "Unknown").strip()
            ship["ship_type"] = data.get("Type", 0)
            ship["destination"] = (data.get("Destination") or "").strip()
            dim = data.get("Dimension") or {}
            ship["length_m"] = (dim.get("A") or 0) + (dim.get("B") or 0)

        elif msg_type == "PositionReport":
            data = msg["Message"]["PositionReport"]
            ship["speed"] = round(data.get("Sog") or 0.0, 1)
            ship["lat"] = data.get("Latitude", 0.0)
            ship["lon"] = data.get("Longitude", 0.0)
            ship["status"] = data.get("NavigationalStatus", -1)
