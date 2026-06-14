"""Config flow for the Pioneer RS-232 integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.selector import SerialPortSelector

from .const import DOMAIN, LOGGER
from .pioneer_avr import VSX_92TXH, PioneerReceiver


async def _async_attempt_connect(port: str) -> str | None:
    """Try to open the receiver. Return an error key, or None on success."""
    receiver = PioneerReceiver(port)
    try:
        await receiver.connect()
    except (ValueError, ConnectionError, OSError, TimeoutError):
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return "unknown"
    else:
        await receiver.disconnect()
        return None


class PioneerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pioneer RS-232."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            error = await _async_attempt_connect(user_input[CONF_DEVICE])
            if not error:
                return self.async_create_entry(
                    title=VSX_92TXH.name,
                    data={CONF_DEVICE: user_input[CONF_DEVICE]},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_DEVICE): SerialPortSelector()}),
                user_input or {},
            ),
            errors=errors,
        )
