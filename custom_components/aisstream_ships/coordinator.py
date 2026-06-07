import asyncio
import json
import logging
import ssl
from datetime import datetime, timezone, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import (
    AISSTREAM_WS, SHIP_TYPE_PRESETS, STATUS_MAP, SIGNAL_UPDATE,
    CONF_API_KEY, CONF_MAX_SHIPS, CONF_MIN_LENGTH,
    CONF_BOUNDING_BOX, CONF_SHIP_TYPE_PRESET, CONF_MMSI_LIST, CONF_STALE_HOURS,
    DEFAULT_MAX_SHIPS, DEFAULT_MIN_LENGTH,
    DEFAULT_SHIP_TYPE_PRESET, DEFAULT_STALE_HOURS, WORLDWIDE_BBOX,
)

_LOGGER = logging.getLogger(__name__)

RECONNECT_BASE = 30
RECONNECT_MAX = 300
RECONNECT_429 = 600
# Connection must stay alive this long before backoff resets
STABLE_THRESHOLD = 60  # seconds
# WebSocket ping interval to keep the connection alive
WS_PING_INTERVAL = 20  # seconds
WS_PING_TIMEOUT = 10   # seconds


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

    def _get(self, key, default=None):
        return self._entry.options.get(
            key, self._entry.data.get(key, default)
        )

    def _active_ship_types(self) -> set:
        preset = self._get(CONF_SHIP_TYPE_PRESET, DEFAULT_SHIP_TYPE_PRESET)
        return SHIP_TYPE_PRESETS.get(preset, SHIP_TYPE_PRESETS[DEFAULT_SHIP_TYPE_PRESET])

    def _mmsi_watchlist(self) -> list[int]:
        return self._get(CONF_MMSI_LIST, [])

    def _fleet_mode(self) -> bool:
        return bool(self._mmsi_watchlist())

    def _is_stale(self, ship: dict) -> bool:
        stale_hours = self._get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)
        if stale_hours == 0:
            return False
        last_seen = ship.get("last_seen")
        if not last_seen:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
        try:
            return datetime.fromisoformat(last_seen) < cutoff
        except ValueError:
            return True

    def get_ships(self, min_length: int = 0, max_results: int = DEFAULT_MAX_SHIPS) -> list:
        if self._fleet_mode():
            watchlist = set(self._mmsi_watchlist())
            ships = [
                s for s in self.ships.values()
                if s["mmsi"] in watchlist and not self._is_stale(s)
            ]
        else:
            active_types = self._active_ship_types()
            ships = [
                s for s in self.ships.values()
                if s["ship_type"] in active_types
                and s["name"] not in ("Unknown", "")
                and s["length_m"] >= min_length
                and not self._is_stale(s)
            ]
        ships.sort(key=lambda s: s.get("last_seen") or "", reverse=True)
        return ships[:max_results]

    def get_passenger_ships(self, min_length: int = 0, max_results: int = DEFAULT_MAX_SHIPS) -> list:
        return self.get_ships(min_length=min_length, max_results=max_results)

    def format_ship_line(self, ship: dict) -> str:
        name = ship["name"][:18]
        dest = (ship.get("destination") or "Unknown")[:12]
        status = STATUS_MAP.get(ship.get("status", -1), "Unknown")
        heading = ship.get("true_heading")
        heading_str = f" hdg:{heading}\u00b0" if heading is not None else ""
        return f"{name} ({status} > {dest}){heading_str}"

    async def _connect_stream(self) -> None:
        try:
            import websockets
        except ImportError:
            _LOGGER.error("Aisstream Ships: websockets library not installed")
            return

        api_key = self._entry.data[CONF_API_KEY]

        if self._fleet_mode():
            bbox = WORLDWIDE_BBOX
        else:
            bbox = self._get(CONF_BOUNDING_BOX)
            if not bbox:
                _LOGGER.error(
                    "Aisstream Ships: no bounding box configured — "
                    "please set one in the integration options"
                )
                return

        delay = RECONNECT_BASE

        while True:
            connected_at = None
            try:
                ssl_context = await self.hass.async_add_executor_job(
                    ssl.create_default_context
                )
                async with websockets.connect(
                    AISSTREAM_WS,
                    ssl=ssl_context,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                ) as ws:
                    subscription: dict = {
                        "APIKey": api_key,
                        "BoundingBoxes": bbox,
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                    }
                    if self._fleet_mode():
                        subscription["FiltersShipMMSI"] = self._mmsi_watchlist()

                    await ws.send(json.dumps(subscription))
                    connected_at = asyncio.get_event_loop().time()
                    _LOGGER.info(
                        "Aisstream Ships: connected (mode=%s)",
                        "fleet" if self._fleet_mode() else "area",
                    )

                    async for raw in ws:
                        self._handle_message(json.loads(raw))
                        async_dispatcher_send(
                            self.hass,
                            f"{SIGNAL_UPDATE}_{self._entry.entry_id}"
                        )

            except asyncio.CancelledError:
                return

            except Exception as exc:
                exc_str = str(exc)
                uptime = (
                    asyncio.get_event_loop().time() - connected_at
                    if connected_at else 0
                )

                # Reset backoff only if we were connected long enough to be stable
                if uptime >= STABLE_THRESHOLD:
                    delay = RECONNECT_BASE

                if "429" in exc_str:
                    delay = RECONNECT_429
                    _LOGGER.warning(
                        "Aisstream Ships: rate limited (HTTP 429) — "
                        "backing off for %ss", delay,
                    )
                elif "no close frame" in exc_str.lower():
                    # Common server-side idle disconnect — not an error worth alarming on
                    _LOGGER.debug(
                        "Aisstream Ships: server closed connection without close frame "
                        "(uptime %.0fs) — retrying in %ss", uptime, delay,
                    )
                else:
                    _LOGGER.warning(
                        "Aisstream Ships: connection error: %s — retrying in %ss",
                        exc, delay,
                    )

                await asyncio.sleep(delay)

                if "429" not in exc_str:
                    delay = min(delay * 2, RECONNECT_MAX)

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
                "true_heading": None,
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
            raw_heading = data.get("TrueHeading")
            ship["true_heading"] = None if raw_heading in (511, None) else raw_heading

        if self._fleet_mode() and mmsi in set(self._mmsi_watchlist()):
            if self._is_stale(ship):
                _LOGGER.warning(
                    "Aisstream Ships: MMSI %s has not been seen within the stale threshold",
                    mmsi,
                )
