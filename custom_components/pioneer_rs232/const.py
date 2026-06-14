"""Constants for the Pioneer RS-232 integration."""

import logging

from homeassistant.config_entries import ConfigEntry

from .pioneer_avr import PioneerReceiver

LOGGER = logging.getLogger(__package__)
DOMAIN = "pioneer_rs232"

CONF_MODEL_NAME = "model_name"

type PioneerConfigEntry = ConfigEntry[PioneerReceiver]
