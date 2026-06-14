"""Number platform for the Pioneer RS-232 integration (bass / treble)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PioneerConfigEntry
from .entity import PioneerEntity
from .pioneer_avr import MainPlayer, PioneerReceiver


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PioneerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pioneer bass / treble number entities."""
    receiver = config_entry.runtime_data
    async_add_entities(
        [
            ToneNumber(
                receiver, config_entry, "bass",
                lambda m: m.bass_db, lambda m, v: m.set_bass_db(v),
            ),
            ToneNumber(
                receiver, config_entry, "treble",
                lambda m: m.treble_db, lambda m, v: m.set_treble_db(v),
            ),
        ]
    )


class ToneNumber(PioneerEntity, NumberEntity):
    """A bass or treble level, -6..+6 dB in 1 dB steps."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = -6
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_icon = "mdi:tune"

    def __init__(
        self,
        receiver: PioneerReceiver,
        config_entry: PioneerConfigEntry,
        key: str,
        getter: Callable[[MainPlayer], int | None],
        setter: Callable[[MainPlayer, int], Awaitable[None]],
    ) -> None:
        super().__init__(receiver, config_entry, key)
        self._getter = getter
        self._setter = setter

    def _update_attributes(self) -> None:
        self._attr_native_value = self._getter(self._receiver.main)

    async def async_set_native_value(self, value: float) -> None:
        await self._setter(self._receiver.main, int(value))
