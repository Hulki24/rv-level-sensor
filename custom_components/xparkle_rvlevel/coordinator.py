"""BLE transport for RV Level Sensor - Alpha 2.

Alpha 2 stays read-only:
- no writes to FFF1/FFF3
- subscribes to FFF4/FFF8
- polls readable FFF1/FFF2/FFF6 every second
- records changing FFF2 packets so we can determine whether live angle data is
  available by READ without proprietary initialization.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import math
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .orientation import vehicle_angles
from .planner import plan_wedges, corner_heights

from .const import (
    CHAR_FFF1, CHAR_FFF2, CHAR_FFF4, CHAR_FFF6, CHAR_FFF8,
    CONF_ADDRESS, CONF_NAME, DOMAIN,
    CONF_LONGITUDINAL_LENGTH, CONF_TRANSVERSE_WIDTH,
    DEFAULT_LONGITUDINAL_LENGTH, DEFAULT_TRANSVERSE_WIDTH,
    CONF_SENSOR_ORIENTATION, DEFAULT_SENSOR_ORIENTATION,
    CONF_WEDGE_PROFILE, DEFAULT_WEDGE_PROFILE, WEDGE_PROFILES, track_widths,
)

_LOGGER = logging.getLogger(__name__)
SIGNAL_UPDATE = f"{DOMAIN}_update"
POLL_INTERVAL = 0.5

@dataclass
class RVLevelState:
    connected: bool = False
    auto_disconnect_remaining: int | None = None
    auto_disconnect_deadline: float | None = None
    raw_fff4: str | None = None
    raw_fff8: str | None = None
    read_fff1: str | None = None
    read_fff2: str | None = None
    read_fff6: str | None = None
    previous_fff2: str | None = None
    fff2_changed: bool = False
    fff2_change_count: int = 0
    notification_count: int = 0
    read_count: int = 0
    last_source: str | None = None
    last_error: str | None = None
    longitudinal_angle: float | None = None
    transverse_angle: float | None = None
    battery: int | None = None
    angle_diagnostics: dict[str, Any] | None = None
    longitudinal_lift_cm: float | None = None
    transverse_lift_cm: float | None = None
    front_left_lift_cm: float | None = None
    front_right_lift_cm: float | None = None
    rear_left_lift_cm: float | None = None
    rear_right_lift_cm: float | None = None
    front_left_high_cm: float | None = None
    front_right_high_cm: float | None = None
    rear_left_high_cm: float | None = None
    rear_right_high_cm: float | None = None
    level_status: str | None = None
    wedge_front_left_cm: float | None = None
    wedge_front_right_cm: float | None = None
    wedge_rear_left_cm: float | None = None
    wedge_rear_right_cm: float | None = None
    wedge_instruction: str | None = None
    wedge_plan: dict[str, Any] | None = None
    triple_front_left: str | None = None
    triple_front_right: str | None = None
    triple_rear_left: str | None = None
    triple_rear_right: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

class RVLevelCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.address = entry.data[CONF_ADDRESS]
        self.name = entry.data.get(CONF_NAME, "RVLevel")
        self.state = RVLevelState()
        self._client: BleakClient | None = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._io_lock = asyncio.Lock()
        self._connection_enabled = True
        self._connection_changed = asyncio.Event()
        self._auto_disconnect_task: asyncio.Task | None = None
        self._auto_disconnect_seconds = 300

    async def async_start(self) -> None:
        self._stop.clear()
        self._task = self.hass.async_create_background_task(
            self._connection_loop(), f"{DOMAIN}_{self.address}"
        )
        self._start_auto_disconnect_timer()

    async def async_stop(self) -> None:
        self._stop.set()
        self._cancel_auto_disconnect_timer()
        if self._task:
            self._task.cancel()
        await self._disconnect()

    async def _connection_loop(self) -> None:
        while not self._stop.is_set():
            if not self._connection_enabled:
                self.state.connected = False
                self.state.last_error = None
                self._notify()
                # Wait until Connect enables BLE. The short timeout prevents a
                # lost Event edge from ever requiring a second button press.
                while not self._connection_enabled and not self._stop.is_set():
                    try:
                        await asyncio.wait_for(self._connection_changed.wait(), timeout=0.25)
                    except asyncio.TimeoutError:
                        pass
                    self._connection_changed.clear()
                continue
            try:
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )
                if device is None:
                    self.state.connected = False
                    self.state.last_error = "device_not_reachable"
                    self._notify()
                    await asyncio.sleep(5)
                    continue

                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    device,
                    self.name,
                    disconnected_callback=self._on_disconnect,
                    max_attempts=3,
                    pair=False,
                )
                self.state.connected = True
                self.state.last_error = None
                if self.state.auto_disconnect_remaining is None:
                    self._start_auto_disconnect_timer()
                self._notify()

                # Subscribe first, matching what BLE apps commonly do.
                await self._subscribe_notifications()

                # Then continuously READ the characteristics which the real
                # RVLevel-410F has already proven to expose.
                while (
                    self._client
                    and self._client.is_connected
                    and not self._stop.is_set()
                    and self._connection_enabled
                ):
                    await self._read_cycle()
                    try:
                        await asyncio.wait_for(
                            self._connection_changed.wait(), timeout=POLL_INTERVAL
                        )
                        self._connection_changed.clear()
                    except asyncio.TimeoutError:
                        pass

            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.state.last_error = f"{type(err).__name__}: {err}"
                _LOGGER.debug("RVLevel connection error", exc_info=True)
            finally:
                await self._disconnect()
                self.state.connected = False
                self._notify()

            if not self._stop.is_set() and self._connection_enabled:
                try:
                    await asyncio.wait_for(self._connection_changed.wait(), timeout=5)
                    self._connection_changed.clear()
                except asyncio.TimeoutError:
                    pass

    @callback
    def _on_disconnect(self, client: BleakClient) -> None:
        self.state.connected = False
        self._notify()

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        if client and client.is_connected:
            try:
                await client.disconnect()
            except BleakError:
                pass

    async def async_read_now(self) -> None:
        """Request an immediate safe READ cycle; never writes to the device."""
        if self._client and self._client.is_connected:
            await self._read_cycle()

    @property
    def connection_enabled(self) -> bool:
        """Return whether Home Assistant should keep the BLE link active."""
        return self._connection_enabled

    def _cancel_auto_disconnect_timer(self) -> None:
        task = self._auto_disconnect_task
        self._auto_disconnect_task = None
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self.state.auto_disconnect_remaining = None
        self.state.auto_disconnect_deadline = None

    def _start_auto_disconnect_timer(self) -> None:
        self._cancel_auto_disconnect_timer()
        loop = asyncio.get_running_loop()
        self.state.auto_disconnect_remaining = self._auto_disconnect_seconds
        self.state.auto_disconnect_deadline = loop.time() + self._auto_disconnect_seconds
        self._auto_disconnect_task = self.hass.async_create_background_task(
            self._auto_disconnect_countdown(),
            f"{DOMAIN}_{self.address}_auto_disconnect",
        )
        # One HA update when timer starts; no update every second.
        self._notify()

    async def _auto_disconnect_countdown(self) -> None:
        try:
            await asyncio.sleep(self._auto_disconnect_seconds)
            self.state.auto_disconnect_remaining = 0
            self.state.auto_disconnect_deadline = None
            await self.async_disconnect()
        except asyncio.CancelledError:
            raise

    async def async_connect(self) -> None:
        """Enable BLE and trigger one immediate connection attempt."""
        self._connection_enabled = True
        self._stop.clear()
        self._connection_changed.set()

        if self._task is None or self._task.done():
            self._task = self.hass.async_create_background_task(
                self._connection_loop(), f"{DOMAIN}_{self.address}"
            )

        self.state.auto_disconnect_remaining = None
        self._notify()

        # Yield so the connection loop can leave its disabled wait immediately.
        await asyncio.sleep(0)
        self._connection_changed.set()

    async def async_disconnect(self) -> None:
        """Disable BLE reconnection and close the current link."""
        self._cancel_auto_disconnect_timer()
        self._connection_enabled = False
        self._connection_changed.set()
        await self._disconnect()
        self.state.connected = False
        self.state.last_error = None
        self._notify()

    async def _read_cycle(self) -> None:
        assert self._client is not None
        async with self._io_lock:
            await self._read_cycle_locked()

    async def _read_cycle_locked(self) -> None:
        assert self._client is not None
        for uuid, attr, label in (
            (CHAR_FFF1, "read_fff1", "FFF1"),
            (CHAR_FFF2, "read_fff2", "FFF2"),
            (CHAR_FFF6, "read_fff6", "FFF6"),
        ):
            try:
                value = bytes(await self._client.read_gatt_char(uuid))
            except (BleakError, EOFError) as err:
                _LOGGER.debug("Read %s failed: %s", label, err)
                continue

            text = value.hex(" ").upper()
            if attr == "read_fff2":
                old = self.state.read_fff2
                self.state.previous_fff2 = old
                self.state.fff2_changed = old is not None and old != text
                if self.state.fff2_changed:
                    self.state.fff2_change_count += 1
                    _LOGGER.debug("FFF2 changed: %s -> %s", old, text)
            setattr(self.state, attr, text)
            if attr == "read_fff2":
                self._decode_fff2(value)
            self.state.read_count += 1
            self.state.last_source = f"{label} read"

        self._notify()

    async def _subscribe_notifications(self) -> None:
        assert self._client is not None
        for uuid, label in ((CHAR_FFF4, "FFF4"), (CHAR_FFF8, "FFF8")):
            try:
                await self._client.start_notify(uuid, self._notification_handler)
                _LOGGER.debug("Subscribed to %s", label)
            except (BleakError, EOFError) as err:
                _LOGGER.debug("Subscribe %s failed: %s", label, err)

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        uuid = str(getattr(sender, "uuid", sender)).lower()
        raw = bytes(data)
        if uuid == CHAR_FFF4:
            self.state.raw_fff4 = raw.hex(" ").upper()
            self.state.last_source = "FFF4 notify"
        elif uuid == CHAR_FFF8:
            self.state.raw_fff8 = raw.hex(" ").upper()
            self.state.last_source = "FFF8 notify"
        else:
            self.state.last_source = f"{uuid} notify"
        self.state.notification_count += 1
        self.state.extra["last_notification_length"] = len(raw)
        self._notify()


    def _decode_fff2(self, data: bytes) -> None:
        """Decode the 7-byte live packet observed on FFF2.

        Observed reference:
          00 00 E8 00 00 2B 60
        while the original Xparkle app displayed approximately:
          longitudinal 2.3°, transverse 0.5°, battery 96%.

        This maps naturally to:
          bytes 1..2: signed big-endian hundredths of a degree
          bytes 4..5: signed big-endian hundredths of a degree
          byte 6: battery percentage

        Signed decoding is used so negative inclinations work when the high
        byte becomes FF. Alpha 4 keeps the raw packet visible for validation.
        """
        if len(data) < 7:
            return

        longitudinal_raw = int.from_bytes(data[1:3], byteorder="big", signed=True)
        transverse_raw = int.from_bytes(data[4:6], byteorder="big", signed=True)
        battery = int(data[6])

        longitudinal = longitudinal_raw / 100.0
        transverse = transverse_raw / 100.0

        # Keep the exact source values visible; no smoothing or hidden offsets.
        self.state.angle_diagnostics = {
            "raw_fff2": data.hex(" ").upper(),
            "raw_longitudinal_count": longitudinal_raw,
            "raw_transverse_count": transverse_raw,
            "raw_longitudinal_angle": longitudinal,
            "raw_transverse_angle": transverse,
            "sensor_orientation": self.entry.options.get(
                CONF_SENSOR_ORIENTATION, DEFAULT_SENSOR_ORIENTATION
            ),
            "decoder_scale_degrees_per_count": 0.01,
        }

        # Normalize once so every entity and card uses vehicle coordinates.
        longitudinal, transverse = vehicle_angles(
            longitudinal, transverse,
            self.entry.options.get(CONF_SENSOR_ORIENTATION, DEFAULT_SENSOR_ORIENTATION),
        )

        self.state.longitudinal_angle = round(longitudinal, 2)
        self.state.transverse_angle = round(transverse, 2)
        self.state.battery = battery if 0 <= battery <= 100 else None

        length_m = float(
            self.entry.options.get(
                CONF_LONGITUDINAL_LENGTH, DEFAULT_LONGITUDINAL_LENGTH
            )
        )
        width_m, rear_width_m = track_widths(self.entry.options)

        long_cm = abs(length_m * 100.0 * math.tan(math.radians(longitudinal)))
        trans_cm = abs(max(width_m, rear_width_m) * 100.0 * math.tan(math.radians(transverse)))

        self.state.longitudinal_lift_cm = round(long_cm, 1)
        self.state.transverse_lift_cm = round(trans_cm, 1)

        # Evaluate the actual four wheel positions; axle widths can differ.
        physical = corner_heights(longitudinal, transverse, length_m, width_m, rear_width_m)
        lowest, highest = min(physical.values()), max(physical.values())
        for corner, height in physical.items():
            setattr(self.state, f"{corner}_high_cm", round(height - lowest, 1))
            setattr(self.state, f"{corner}_lift_cm", round(highest - height, 1))

        # Human-readable status for dashboards.
        max_high = max(getattr(self.state, key) or 0.0 for key in (
            "front_left_high_cm", "front_right_high_cm",
            "rear_left_high_cm", "rear_right_high_cm",
        ))
        if max_high <= 0.5:
            self.state.level_status = "Nivelliert"
        elif max_high <= 2.0:
            self.state.level_status = "Fast nivelliert"
        else:
            self.state.level_status = "Korrektur erforderlich"

        # Theoretical four-wheel lifts above remain independent of the finite plan.
        profile = WEDGE_PROFILES.get(
            self.entry.options.get(CONF_WEDGE_PROFILE, DEFAULT_WEDGE_PROFILE),
            WEDGE_PROFILES[DEFAULT_WEDGE_PROFILE],
        )
        plan = plan_wedges(longitudinal, transverse, length_m, width_m, profile["stages_cm"], rear_width_m=rear_width_m)
        wedges = plan["heights_cm"]
        self.state.wedge_plan = plan
        labels = (("front_left", "vorne links"), ("front_right", "vorne rechts"),
                  ("rear_left", "hinten links"), ("rear_right", "hinten rechts"))
        needed = []
        for key, label in labels:
            cm = wedges[key]
            setattr(self.state, f"wedge_{key}_cm", cm)
            stage = plan["stages"][key]
            text = f"Stufe {stage} ({cm:g} cm)" if stage else "Kein Keil"
            # Retain legacy entity IDs, but use the configured wedge profile.
            setattr(self.state, f"triple_{key}", text)
            if stage:
                needed.append(f"{label}: {text}")
        advice = "; ".join(needed) if needed else "Keine Verbesserung mit den verfügbaren Keilstufen"
        if max_high <= 0.5:
            advice = "Keine Keile erforderlich"
        self.state.wedge_instruction = (
            advice + f" · Rest geschätzt: längs {plan['residual_longitudinal_angle']:+.2f}°, "
            f"quer {plan['residual_transverse_angle']:+.2f}°"
        )

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE, self.address)
