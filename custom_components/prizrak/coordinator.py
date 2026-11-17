"""DataUpdateCoordinator for Prizrak integration."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .client import PrizrakClient
from .const import DOMAIN, SECURITY_FIELDS

_LOGGER = logging.getLogger(__name__)
_MISSING = object()


class PrizrakDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Prizrak data."""

    def __init__(self, hass: HomeAssistant, client: PrizrakClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # No update_interval - updates come via WebSocket
        )
        self.client = client
        self.devices: dict[int, dict[str, Any]] = {}

        # Throttling for frontend updates to prevent browser memory issues
        # Data is always up-to-date on HA server, but browser UI updates are throttled
        self.last_frontend_update: float = float("-inf")
        self.frontend_update_interval: float = 30.0  # seconds
        self.throttling_enabled: bool = True
        self.throttling_disable_task: Any | None = None

    @callback
    def handle_device_update(self, device_id: int, device_state: dict[str, Any]) -> None:
        """Handle device state update from WebSocket.

        Args:
            device_id: Device ID
            device_state: New device state (partial update)
        """
        full_device_state = self.client.device_states.get(device_id)
        if full_device_state is None:
            _LOGGER.warning("Device state missing from client cache")
            return

        if device_state:
            full_device_state["last_update"] = dt_util.utcnow()

        time_key = "last_device_exchange_time"
        if isinstance(full_device_state.get(time_key), str):
            try:
                full_device_state[time_key] = dt_util.parse_datetime(full_device_state[time_key])
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid device timestamp")
                full_device_state[time_key] = None

        # The client merges deltas in place. Compare against the last snapshot,
        # including absence of a field after a disconnection.
        previous = self.devices.get(device_id, {})
        security_changed = any(
            previous.get(key, _MISSING) != full_device_state.get(key, _MISSING)
            for key in SECURITY_FIELDS
        )
        self.devices[device_id] = full_device_state.copy()

        now = time.monotonic()
        if (
            security_changed
            or not self.throttling_enabled
            or now - self.last_frontend_update >= self.frontend_update_interval
        ):
            self.async_set_updated_data(self.devices)
            self.last_frontend_update = now

    def disable_throttling_temporarily(self, duration: float = 30.0) -> None:
        """Temporarily disable frontend update throttling.

        Used after sending commands (Guard, Autolaunch) to show immediate feedback.
        Throttling is re-enabled after specified duration.

        Args:
            duration: How long to disable throttling (seconds)
        """
        # Cancel previous task if exists
        if self.throttling_disable_task and not self.throttling_disable_task.done():
            self.throttling_disable_task.cancel()

        # Disable throttling
        self.throttling_enabled = False
        _LOGGER.info(f"Throttling disabled for {duration}s (command sent)")

        # Schedule re-enable
        async def re_enable_throttling():
            await asyncio.sleep(duration)
            self.throttling_enabled = True
            _LOGGER.info("Throttling re-enabled")

        self.throttling_disable_task = self.hass.async_create_task(re_enable_throttling())

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Update data via library.

        This is only used as a fallback. Real updates come via WebSocket callbacks.
        """
        return self.devices
