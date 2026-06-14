"""Select platform for the Pioneer RS-232 integration.

Exposes the absolute-set, multi-value main-zone options: phase control,
surround-back (SBch) processing, and MCACC memory position.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PioneerConfigEntry
from .entity import PioneerEntity
from .pioneer_avr import MainPlayer, PioneerReceiver


@dataclass(frozen=True, kw_only=True)
class PioneerSelectDescription:
    """Describes one select entity: its options and how to read/write it."""

    key: str
    icon: str
    # Raw protocol code (as reported in state) -> option slug.
    options_map: dict[str, str]
    getter: Callable[[MainPlayer], str | None]
    setter: Callable[[MainPlayer, int], Awaitable[None]]


SELECTS: tuple[PioneerSelectDescription, ...] = (
    PioneerSelectDescription(
        key="phase_control",
        icon="mdi:sine-wave",
        options_map={"0": "off", "1": "on", "2": "full_band"},
        getter=lambda m: m.phase_control,
        setter=lambda m, v: m.set_phase_control(v),
    ),
    PioneerSelectDescription(
        key="sb_processing",
        icon="mdi:speaker-multiple",
        options_map={"0": "off", "1": "on", "2": "auto"},
        getter=lambda m: m.sb_processing,
        setter=lambda m, v: m.set_sb_processing(v),
    ),
    PioneerSelectDescription(
        key="mcacc",
        icon="mdi:equalizer",
        options_map={
            "0": "off",
            "1": "memory_1",
            "2": "memory_2",
            "3": "memory_3",
            "4": "memory_4",
            "5": "memory_5",
            "6": "memory_6",
        },
        getter=lambda m: m.mcacc,
        setter=lambda m, v: m.set_mcacc(v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PioneerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pioneer select entities."""
    receiver = config_entry.runtime_data
    async_add_entities(
        PioneerSelect(receiver, config_entry, desc) for desc in SELECTS
    )


class PioneerSelect(PioneerEntity, SelectEntity):
    """A main-zone option backed by an absolute-set command."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        receiver: PioneerReceiver,
        config_entry: PioneerConfigEntry,
        description: PioneerSelectDescription,
    ) -> None:
        super().__init__(receiver, config_entry, description.key)
        self._desc = description
        self._attr_icon = description.icon
        self._attr_options = list(description.options_map.values())
        # slug -> protocol code (int), for writing.
        self._slug_to_code = {
            slug: int(code) for code, slug in description.options_map.items()
        }

    def _update_attributes(self) -> None:
        code = self._desc.getter(self._receiver.main)
        self._attr_current_option = self._desc.options_map.get(code)

    async def async_select_option(self, option: str) -> None:
        await self._desc.setter(self._receiver.main, self._slug_to_code[option])
