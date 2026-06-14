"""The Pioneer RS-232 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER, PioneerConfigEntry
from .pioneer_avr import PioneerReceiver, ReceiverState

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: PioneerConfigEntry) -> bool:
    """Set up Pioneer RS-232 from a config entry."""
    port = entry.data[CONF_DEVICE]
    receiver = PioneerReceiver(port)

    try:
        await receiver.connect()
        await receiver.query_state()
    except (ConnectionError, OSError, TimeoutError) as err:
        LOGGER.error("Error connecting to Pioneer receiver at %s: %s", port, err)
        if receiver.connected:
            await receiver.disconnect()
        raise ConfigEntryNotReady from err

    entry.runtime_data = receiver

    @callback
    def _on_disconnect(state: ReceiverState | None) -> None:
        # Reload only if still loaded; disconnect() during removal fires this too.
        if state is None and entry.state is ConfigEntryState.LOADED:
            LOGGER.warning("Pioneer receiver disconnected, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(receiver.subscribe(_on_disconnect))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PioneerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.disconnect()
    return unload_ok
