"""Sensor platform for the Pioneer RS-232 integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PioneerConfigEntry
from .entity import PioneerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PioneerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pioneer sensors."""
    receiver = config_entry.runtime_data
    async_add_entities([AudioFormatSensor(receiver, config_entry, "audio_format")])


class AudioFormatSensor(PioneerEntity, SensorEntity):
    """The audio format the receiver is currently decoding (LM status)."""

    _attr_icon = "mdi:surround-sound"

    def _update_attributes(self) -> None:
        self._attr_native_value = self._receiver.main.listening_mode
