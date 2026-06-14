"""Switch platform for the Pioneer RS-232 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PioneerConfigEntry
from .entity import PioneerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PioneerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pioneer switches."""
    receiver = config_entry.runtime_data
    async_add_entities([ToneSwitch(receiver, config_entry, "tone")])


class ToneSwitch(PioneerEntity, SwitchEntity):
    """Tone control on/off (bypass)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:tune-vertical"

    def _update_attributes(self) -> None:
        self._attr_is_on = self._receiver.main.tone

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._receiver.main.set_tone(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._receiver.main.set_tone(False)
