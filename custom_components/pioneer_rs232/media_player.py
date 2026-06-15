"""Media player platform for the Pioneer RS-232 integration."""

from __future__ import annotations

import re
from typing import Any, Literal, cast

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

SERVICE_SEND_COMMAND = "send_command"
ATTR_COMMAND = "command"
ATTR_TIMEOUT = "timeout"

from .const import DOMAIN, PioneerConfigEntry
from .pioneer_avr import (
    INPUT_SOURCE_SLUGS,
    MIN_VOLUME_DB,
    SET_LISTENING_MODES,
    SLUG_TO_INPUT,
    VOLUME_DB_RANGE,
    MainPlayer,
    PioneerReceiver,
    ReceiverState,
    ZonePlayer,
)

# Selectable listening modes -> the 3-digit SR code that activates them.
# Several names share a code group; keep the first code seen for each name.
SOUND_MODE_TO_CODE: dict[str, str] = {}
for _code, _name in SET_LISTENING_MODES.items():
    SOUND_MODE_TO_CODE.setdefault(_name, _code)
SOUND_MODE_LIST = sorted(SOUND_MODE_TO_CODE)


def _resolve_sound_mode_code(sound_mode: str) -> str | None:
    """Resolve a sound-mode string to a 3-digit SR set code.

    Accepts a mode name from the list, or a raw ``SRxxxx`` / numeric value
    (as older scenes may have captured before the parser was fixed).
    """
    if (code := SOUND_MODE_TO_CODE.get(sound_mode)) is not None:
        return code
    if match := re.fullmatch(r"(?:SR)?(\d+)", sound_mode):
        code = f"{int(match.group(1)):03d}"
        if code in SET_LISTENING_MODES:
            return code
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PioneerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pioneer RS-232 media player(s)."""
    receiver = config_entry.runtime_data
    entities: list[PioneerMediaPlayer] = [
        PioneerMediaPlayer(receiver, receiver.main, config_entry, "main")
    ]
    if receiver.model.has_zone_2:
        entities.append(
            PioneerMediaPlayer(receiver, receiver.zone_2, config_entry, "zone_2")
        )
    if receiver.model.has_zone_3:
        entities.append(
            PioneerMediaPlayer(receiver, receiver.zone_3, config_entry, "zone_3")
        )
    async_add_entities(entities)

    # Action to send an arbitrary command to the receiver and return any reply.
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_TIMEOUT, default=1.0): vol.All(
                vol.Coerce(float), vol.Range(min=0.1, max=5.0)
            ),
        },
        "async_send_command",
        supports_response=SupportsResponse.OPTIONAL,
    )


class PioneerMediaPlayer(MediaPlayerEntity, RestoreEntity):
    """A Pioneer receiver zone controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_translation_key = "receiver"
    _attr_should_poll = False

    def __init__(
        self,
        receiver: PioneerReceiver,
        player: MainPlayer | ZonePlayer,
        config_entry: PioneerConfigEntry,
        zone: Literal["main", "zone_2", "zone_3"],
    ) -> None:
        """Initialize the media player."""
        self._receiver = receiver
        self._player = player
        self._is_main = zone == "main"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Pioneer",
            model=receiver.model.name,
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"

        self._attr_source_list = sorted(
            INPUT_SOURCE_SLUGS[source] for source in receiver.model.input_sources
        )

        features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )
        if zone == "main":
            self._attr_name = None
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            )
            self._attr_sound_mode_list = SOUND_MODE_LIST
        else:
            self._attr_name = "Zone 2" if zone == "zone_2" else "Zone 3"
            if getattr(player, "has_volume", False):
                features |= (
                    MediaPlayerEntityFeature.VOLUME_SET
                    | MediaPlayerEntityFeature.VOLUME_STEP
                )
        self._attr_supported_features = features

        self._async_update_from_player()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates and restore the last known power state.

        Nothing is queried at startup (that would wake the receiver). Instead
        the main zone restores its last power state and, only if it was on,
        requests a full refresh — safe, since an already-on unit won't wake.
        """
        await super().async_added_to_hass()
        self.async_on_remove(self._receiver.subscribe(self._async_on_state_update))

        if not self._is_main:
            return
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state not in (
            MediaPlayerState.ON,
            MediaPlayerState.OFF,
        ):
            return
        was_on = last_state.state == MediaPlayerState.ON
        self._receiver.set_optimistic_power(was_on)
        if was_on:
            self._receiver.request_refresh()

    @callback
    def _async_on_state_update(self, state: ReceiverState | None) -> None:
        """Handle a state update from the receiver."""
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_player()
        self.async_write_ha_state()

    @callback
    def _async_update_from_player(self) -> None:
        """Refresh entity attributes from the shared player view."""
        power = self._player.power
        if power is None:
            self._attr_state = None
        else:
            self._attr_state = (
                MediaPlayerState.ON if power else MediaPlayerState.OFF
            )

        source = self._player.input_source
        self._attr_source = INPUT_SOURCE_SLUGS.get(source) if source else None

        volume = self._player.volume
        if volume is not None:
            self._attr_volume_level = (volume - MIN_VOLUME_DB) / VOLUME_DB_RANGE
        else:
            self._attr_volume_level = None

        if self._is_main:
            main = cast(MainPlayer, self._player)
            self._attr_is_volume_muted = main.mute
            # The selected listening mode (SR), matching sound_mode_list.
            self._attr_sound_mode = main.selected_listening_mode

    async def async_turn_on(self) -> None:
        """Turn the zone on."""
        await self._player.power_on()

    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self._player.power_standby()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        db = volume * VOLUME_DB_RANGE + MIN_VOLUME_DB
        await self._player.set_volume(db)

    async def async_volume_up(self) -> None:
        """Volume up one step."""
        await self._player.volume_up()

    async def async_volume_down(self) -> None:
        """Volume down one step."""
        await self._player.volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute (main zone)."""
        main = cast(MainPlayer, self._player)
        if mute:
            await main.mute_on()
        else:
            await main.mute_off()

    async def async_select_source(self, source: str) -> None:
        """Select an input source by its slug."""
        input_source = SLUG_TO_INPUT.get(source)
        if input_source is None:
            raise HomeAssistantError(f"Invalid source: {source}")
        await self._player.select_input_source(input_source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a listening/surround mode (main zone)."""
        code = _resolve_sound_mode_code(sound_mode)
        if code is None:
            raise HomeAssistantError(f"Invalid sound mode: {sound_mode}")
        await cast(MainPlayer, self._player).select_listening_mode(code)

    async def async_send_command(
        self, command: str, timeout: float = 1.0
    ) -> dict[str, Any]:
        """Send a raw command to the receiver and return any reply lines."""
        replies = await self._receiver.send_and_collect(command, timeout)
        return {"command": command, "replies": replies}
