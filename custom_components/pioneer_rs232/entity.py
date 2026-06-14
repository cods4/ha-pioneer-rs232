"""Shared base entity for the Pioneer RS-232 integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PioneerConfigEntry
from .pioneer_avr import PioneerReceiver, ReceiverState


class PioneerEntity(Entity):
    """Base for non-media-player entities tied to the receiver's main zone."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        receiver: PioneerReceiver,
        config_entry: PioneerConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity. ``key`` is the unique-id / translation suffix."""
        self._receiver = receiver
        self._attr_translation_key = key
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Pioneer",
            model=receiver.model.name,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self.async_on_remove(self._receiver.subscribe(self._handle_state_update))
        self._update_attributes()

    @callback
    def _handle_state_update(self, state: ReceiverState | None) -> None:
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._update_attributes()
        self.async_write_ha_state()

    @callback
    def _update_attributes(self) -> None:
        """Refresh attributes from receiver state. Overridden by subclasses."""
