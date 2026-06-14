"""Command builders and reply parser for the Pioneer VSX-92TXH.

Commands are plain ASCII strings; the carriage-return terminator is added by
the transport layer. Replies are decoded into ``(field, value)`` updates that
the receiver applies to its state.
"""

from __future__ import annotations

from typing import Any

from .const import INPUT_BY_CODE, InputSource, Power
from .modes import LISTENING_MODE_NAMES, SET_LISTENING_MODES

# --- Read-only status queries ----------------------------------------------
#
# Sent on connect (and on demand) to populate state. Order is roughly the
# order a human would read the front panel.
QUERIES: dict[str, str] = {
    "power": "?P",
    "volume": "?V",
    "mute": "?M",
    "source": "?F",
    "listening_mode": "?L",
    "listening_mode_set": "?S",
    "tone": "?TO",
    "bass": "?BA",
    "treble": "?TR",
    "tuner_preset": "?PR",
    "tuner_freq": "?FR",
    "phase_control": "?IS",
    "sb_processing": "?EX",
    "mcacc": "?MC",
    "zone2_power": "?AP",
    "zone2_source": "?ZS",
    "zone2_volume": "?ZV",
    "zone3_power": "?BP",
    "zone3_source": "?ZT",
}


# --- Command builders -------------------------------------------------------


def power(on: bool, zone: str = "main") -> str:
    """Build a power on/off command for the given zone."""
    return {
        "main": ("PO", "PF"),
        "zone2": ("APO", "APF"),
        "zone3": ("BPO", "BPF"),
    }[zone][0 if on else 1]


def volume_step(up: bool, zone: str = "main") -> str:
    """Build a single volume up/down step command."""
    return {"main": ("VU", "VD"), "zone2": ("ZU", "ZD")}[zone][0 if up else 1]


def volume_set(raw: int, zone: str = "main") -> str:
    """Build an absolute volume command from a raw 2-digit step."""
    suffix = {"main": "VL", "zone2": "ZV"}[zone]
    return f"{raw:02d}{suffix}"


def mute(on: bool) -> str:
    """Build a (main-zone) mute on/off command."""
    return "MO" if on else "MF"


def select_source(source: InputSource, zone: str = "main") -> str:
    """Build an input-function-select command for the given zone."""
    suffix = {"main": "FN", "zone2": "ZS", "zone3": "ZT"}[zone]
    return f"{source.value}{suffix}"


def listening_mode(code: str) -> str:
    """Build a listening-mode-set command from a 3-digit SR code."""
    return f"{code}SR"


# Tone controls (main zone only).
TONE_TOGGLE = "TO"
BASS_UP = "BI"
BASS_DOWN = "BD"
TREBLE_UP = "TI"
TREBLE_DOWN = "TD"
STATUS_DISPLAY = "STS"


# --- Reply parser -----------------------------------------------------------
#
# Each entry: prefix -> (field, value-length, decoder). Longest/most-specific
# prefixes must be tried first; the table below is ordered accordingly.
def parse_reply(line: str) -> tuple[str, Any] | None:
    """Decode one reply line into a ``(field, value)`` state update.

    Returns ``None`` for blank lines or replies we do not track.
    """
    r = line.strip().upper()
    if not r:
        return None

    # Error replies: E04, E06, B00, etc. (E + 2 digits, or B00).
    if (len(r) == 3 and r[0] == "E" and r[1:].isdigit()) or r == "B00":
        return ("error", r)

    # 3-character prefixes first so they win over their 2-char neighbours.
    if r.startswith("PWR"):
        return ("power", Power(r[3]))
    if r.startswith("VOL"):
        return ("volume_raw", _int(r[3:]))
    if r.startswith("MUT"):
        # 0 = mute ON (muted), 1 = mute OFF.
        return ("mute", r[3] == "0")
    if r.startswith("APR"):
        return ("zone2_power", Power(r[3]))
    if r.startswith("BPR"):
        return ("zone3_power", Power(r[3]))
    if r.startswith("Z2F"):
        return ("zone2_source", INPUT_BY_CODE.get(r[3:5]))
    if r.startswith("Z3F"):
        return ("zone3_source", INPUT_BY_CODE.get(r[3:5]))

    # 2-character prefixes.
    if r.startswith("FN"):
        return ("source", INPUT_BY_CODE.get(r[2:4]))
    if r.startswith("LM"):
        code = r[2:5]
        return ("listening_mode", LISTENING_MODE_NAMES.get(code, f"LM{code}"))
    if r.startswith("SR"):
        code = r[2:]
        return ("listening_mode_set", SET_LISTENING_MODES.get(code, f"SR{code}"))
    if r.startswith("TO"):
        return ("tone", r[2] == "1")
    if r.startswith("BA"):
        return ("bass_code", _int(r[2:]))
    if r.startswith("TR"):
        return ("treble_code", _int(r[2:]))
    if r.startswith("ZV"):
        return ("zone2_volume_raw", _int(r[2:]))
    if r.startswith("PR"):
        return ("tuner_preset", r[2:])
    if r.startswith("FR"):
        return ("tuner_freq", r[2:])
    if r.startswith("MC"):
        return ("mcacc", r[2:])
    if r.startswith("EX"):
        return ("sb_processing", r[2:])
    if r.startswith("IS"):
        return ("phase_control", r[2:])
    if r.startswith("XM"):
        return ("xm_channel", r[2:])
    if r.startswith("SI"):
        return ("sirius_channel", r[2:])

    return None


def _int(text: str) -> int | None:
    """Best-effort int parse; returns None on garbage."""
    try:
        return int(text)
    except ValueError:
        return None
