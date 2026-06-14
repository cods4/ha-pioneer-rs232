"""Pioneer VSX-92TXH RS-232 control library.

A small async driver that speaks the Pioneer serial protocol and exposes a
push-based state model. Used both by the Home Assistant integration and by the
standalone ``cli.py`` test tool.
"""

from .const import (
    DEFAULT_BAUD,
    DEFAULT_PORT,
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    VOLUME_DB_RANGE,
    InputSource,
    INPUT_SOURCE_SLUGS,
    SLUG_TO_INPUT,
)
from .models import MODELS, VSX_92TXH, ReceiverModel
from .modes import LISTENING_MODE_NAMES, SET_LISTENING_MODES
from .receiver import (
    MainPlayer,
    PioneerReceiver,
    ReceiverState,
    ZonePlayer,
)

__all__ = [
    "DEFAULT_BAUD",
    "DEFAULT_PORT",
    "INPUT_SOURCE_SLUGS",
    "LISTENING_MODE_NAMES",
    "MAX_VOLUME_DB",
    "MIN_VOLUME_DB",
    "MODELS",
    "MainPlayer",
    "PioneerReceiver",
    "ReceiverModel",
    "ReceiverState",
    "SET_LISTENING_MODES",
    "SLUG_TO_INPUT",
    "VOLUME_DB_RANGE",
    "VSX_92TXH",
    "InputSource",
    "ZonePlayer",
]
