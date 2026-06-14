"""Constants, enums and conversions for the Pioneer VSX-92TXH RS-232 protocol.

All values are taken from vsx92txh_rs232c_commands.csv. The receiver speaks
ASCII commands terminated with a carriage return at 9600 baud, 8N1.
"""

from __future__ import annotations

from enum import Enum

# --- Serial defaults --------------------------------------------------------

DEFAULT_PORT = "/dev/ttyS0"
DEFAULT_BAUD = 9600

# --- Volume -----------------------------------------------------------------
#
# The master volume command/status uses a 2-digit value:
#   00 = Mute, 01 = -80 dB, 81 = 0 dB, 93 = +12 dB   (1 dB per step)
# so the decibel value of a raw step `v` is simply (v - 81).
VOLUME_RAW_MIN = 1            # 01 = -80 dB (00 is the mute sentinel)
VOLUME_RAW_MAX = 93           # 93 = +12 dB
MIN_VOLUME_DB = -80.0
MAX_VOLUME_DB = 12.0
VOLUME_DB_RANGE = MAX_VOLUME_DB - MIN_VOLUME_DB  # 92.0


def raw_to_db(raw: int) -> float:
    """Convert a raw 2-digit volume step into decibels."""
    return float(raw - 81)


def db_to_raw(db: float) -> int:
    """Convert decibels into the nearest raw 2-digit volume step (clamped)."""
    raw = round(db + 81)
    return max(VOLUME_RAW_MIN, min(VOLUME_RAW_MAX, raw))


# --- Input sources (FN / Z2F / Z3F function codes) --------------------------


class InputSource(Enum):
    """Selectable input function. Value is the 2-digit FN code."""

    PHONO = "00"
    CD = "01"
    TUNER = "02"
    CDR = "03"
    DVD = "04"
    TV = "05"
    VIDEO_1 = "10"
    MULTI_CH = "12"
    VIDEO_2 = "14"
    DVR_1 = "15"
    DVR_2 = "16"
    IPOD = "17"
    XM = "18"
    HDMI_1 = "19"
    HDMI_2 = "20"
    HDMI_3 = "21"
    BDP = "25"
    SIRIUS = "27"
    HDMI_CYCLIC = "31"


# Map FN code -> InputSource for fast reply parsing.
INPUT_BY_CODE: dict[str, InputSource] = {src.value: src for src in InputSource}

# Human-friendly slug used as the Home Assistant `source` string.
INPUT_SOURCE_SLUGS: dict[InputSource, str] = {
    InputSource.PHONO: "phono",
    InputSource.CD: "cd",
    InputSource.TUNER: "tuner",
    InputSource.CDR: "cdr",
    InputSource.DVD: "dvd",
    InputSource.TV: "tv",
    InputSource.VIDEO_1: "video_1",
    InputSource.MULTI_CH: "multi_ch",
    InputSource.VIDEO_2: "video_2",
    InputSource.DVR_1: "dvr_1",
    InputSource.DVR_2: "dvr_2",
    InputSource.IPOD: "ipod",
    InputSource.XM: "xm",
    InputSource.HDMI_1: "hdmi_1",
    InputSource.HDMI_2: "hdmi_2",
    InputSource.HDMI_3: "hdmi_3",
    InputSource.BDP: "bdp",
    InputSource.SIRIUS: "sirius",
    InputSource.HDMI_CYCLIC: "hdmi_cyclic",
}
SLUG_TO_INPUT: dict[str, InputSource] = {
    slug: src for src, slug in INPUT_SOURCE_SLUGS.items()
}


# --- Simple on/off style enums ----------------------------------------------


class Power(Enum):
    """Power reply digit (0 = ON, 1 = OFF/standby) per the protocol."""

    ON = "0"
    OFF = "1"


# --- Tone / bass / treble ---------------------------------------------------
#
# BA/TR use a 2-digit code: 00 = +6, 06 = 0 (flat), 12 = -6.
def tone_code_to_db(code: int) -> int:
    """Convert a BA/TR code (00..12) to decibels (+6 .. -6)."""
    return 6 - code


def tone_db_to_code(db: int) -> int:
    """Convert a bass/treble decibel value (+6 .. -6) to a BA/TR code."""
    return max(0, min(12, 6 - db))
