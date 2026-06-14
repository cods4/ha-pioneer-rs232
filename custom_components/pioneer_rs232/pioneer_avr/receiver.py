"""Asynchronous Pioneer VSX-92TXH receiver driver over RS-232.

``PioneerReceiver`` owns the serial connection, decodes the incoming reply
stream into a shared :class:`ReceiverState`, and notifies subscribers on every
change (``local_push``). Per-zone behaviour is exposed through lightweight
player views: ``receiver.main``, ``receiver.zone_2``, ``receiver.zone_3``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from serialx import open_serial_connection

from . import protocol
from .const import (
    DEFAULT_BAUD,
    InputSource,
    Power,
    db_to_raw,
    raw_to_db,
    tone_code_to_db,
    tone_db_to_code,
)
from .models import VSX_92TXH, ReceiverModel

_LOGGER = logging.getLogger(__name__)

# Minimum gap between commands; the receiver drops bytes if pushed too fast.
_COMMAND_GAP = 0.06

StateCallback = Callable[[Optional["ReceiverState"]], None]


@dataclass
class ReceiverState:
    """Snapshot of everything we decode from the receiver."""

    power: bool | None = None
    volume_raw: int | None = None
    mute: bool | None = None
    source: InputSource | None = None
    listening_mode: str | None = None
    listening_mode_set: str | None = None
    tone: bool | None = None
    bass_code: int | None = None
    treble_code: int | None = None
    phase_control: str | None = None
    sb_processing: str | None = None
    mcacc: str | None = None
    tuner_preset: str | None = None
    tuner_freq: str | None = None
    xm_channel: str | None = None
    sirius_channel: str | None = None
    zone2_power: bool | None = None
    zone2_volume_raw: int | None = None
    zone2_source: InputSource | None = None
    zone3_power: bool | None = None
    zone3_source: InputSource | None = None
    last_error: str | None = None

    @property
    def bass_db(self) -> int | None:
        """Bass level in dB (+6 .. -6), or None if unknown."""
        return None if self.bass_code is None else tone_code_to_db(self.bass_code)

    @property
    def treble_db(self) -> int | None:
        """Treble level in dB (+6 .. -6), or None if unknown."""
        return None if self.treble_code is None else tone_code_to_db(self.treble_code)


class PioneerReceiver:
    """Async driver for a Pioneer receiver on a serial port."""

    def __init__(
        self,
        port: str,
        model: ReceiverModel = VSX_92TXH,
        baud: int = DEFAULT_BAUD,
    ) -> None:
        """Initialise the driver. Call :meth:`connect` to open the port."""
        self.port = port
        self.model = model
        self.baud = baud
        self.state = ReceiverState()

        self.main = MainPlayer(self)
        self.zone_2 = ZonePlayer(self, "zone2", has_volume=True)
        self.zone_3 = ZonePlayer(self, "zone3", has_volume=False)

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._write_lock = asyncio.Lock()
        self._subscribers: list[StateCallback] = []
        self._raw_listeners: list[Callable[[str], None]] = []
        self._connected = False

    # --- Connection lifecycle ----------------------------------------------

    @property
    def connected(self) -> bool:
        """True while the serial port is open and the reader is running."""
        return self._connected

    async def connect(self) -> None:
        """Open the serial port and start reading replies.

        ``port`` may be a local device (``/dev/ttyS0``) or any URL serialx
        understands, including an ESPHome serial proxy
        (``esphome://host:6053/?port_name=...&key=...``). 8N1 is the default.
        """
        self._reader, self._writer = await open_serial_connection(
            url=self.port,
            baudrate=self.baud,
        )
        self._connected = True
        # Wake-up nudge: deep-standby CPUs drop the first byte(s) of a command.
        self._writer.write(b"\r")
        await self._writer.drain()
        await asyncio.sleep(0.15)
        self._read_task = asyncio.create_task(self._read_loop())

    async def disconnect(self) -> None:
        """Stop reading and close the serial port."""
        self._connected = False
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        self._reader = None
        self._notify(None)

    async def query_state(self) -> None:
        """Ask the receiver for its full current status."""
        for cmd in protocol.QUERIES.values():
            await self._send(cmd)

    async def send_and_collect(
        self, command: str, timeout: float = 1.0
    ) -> list[str]:
        """Send a raw command and return reply lines seen within ``timeout``.

        Intended for ad-hoc queries from the send_command service. Replies are
        still parsed into state as usual; this just also captures the raw text.
        """
        lines: list[str] = []

        def collector(line: str) -> None:
            lines.append(line)

        self._raw_listeners.append(collector)
        try:
            await self._send(command)
            await asyncio.sleep(timeout)
        finally:
            self._raw_listeners.remove(collector)
        return lines

    def set_optimistic_power(self, on: bool) -> None:
        """Update main power locally and notify subscribers.

        Used for write-only transitions the receiver does not confirm on its
        own (e.g. entering standby), where polling would wake it again.
        """
        self.state.power = on
        self._notify(self.state)

    # --- Subscriptions ------------------------------------------------------

    def subscribe(self, callback: StateCallback) -> Callable[[], None]:
        """Register a state-change callback. Returns an unsubscribe function."""
        self._subscribers.append(callback)

        def _unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return _unsubscribe

    # --- Low-level send -----------------------------------------------------

    async def send_raw(self, command: str) -> None:
        """Send a raw command string (carriage return added automatically)."""
        await self._send(command)

    async def _send(self, command: str) -> None:
        if self._writer is None:
            raise ConnectionError("Not connected")
        async with self._write_lock:
            self._writer.write((command + "\r").encode("ascii"))
            await self._writer.drain()
            await asyncio.sleep(_COMMAND_GAP)

    # --- Read loop ----------------------------------------------------------

    async def _read_loop(self) -> None:
        assert self._reader is not None
        buffer = b""
        try:
            while True:
                data = await self._reader.read(256)
                if not data:
                    break  # EOF / port closed
                buffer = (buffer + data).replace(b"\r", b"\n")
                *lines, buffer = buffer.split(b"\n")
                for raw in lines:
                    if raw:
                        self._handle_line(raw.decode("ascii", "replace"))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - any serial error means we lost the link
            _LOGGER.exception("Pioneer read loop failed")
        finally:
            if self._connected:
                # Unexpected drop (not a clean disconnect()).
                self._connected = False
                self._notify(None)

    def _handle_line(self, line: str) -> None:
        for listener in list(self._raw_listeners):
            listener(line)
        update = protocol.parse_reply(line)
        if update is None:
            _LOGGER.debug("Unparsed reply: %r", line)
            return
        field_name, value = update
        if field_name in ("power", "zone2_power", "zone3_power"):
            setattr(self.state, field_name, value is Power.ON if value else None)
        else:
            setattr(self.state, field_name, value)
        self._notify(self.state)

    def _notify(self, state: ReceiverState | None) -> None:
        for callback in list(self._subscribers):
            try:
                callback(state)
            except Exception:  # noqa: BLE001 - a bad subscriber must not kill us
                _LOGGER.exception("Error in state subscriber")


class _BasePlayer:
    """Shared power/volume/source behaviour for a single zone."""

    def __init__(self, receiver: PioneerReceiver, zone: str) -> None:
        self._receiver = receiver
        self._zone = zone

    @property
    def _state(self) -> ReceiverState:
        return self._receiver.state

    async def power_on(self) -> None:
        """Turn this zone on."""
        await self._receiver.send_raw(protocol.power(True, self._zone))

    async def power_standby(self) -> None:
        """Put this zone into standby."""
        await self._receiver.send_raw(protocol.power(False, self._zone))

    async def select_input_source(self, source: InputSource) -> None:
        """Select an input function for this zone."""
        await self._receiver.send_raw(protocol.select_source(source, self._zone))


class MainPlayer(_BasePlayer):
    """The main zone, with volume, mute, listening modes and tone."""

    # HA derives volume_level from module-level dB constants unless overridden.
    volume_min = None
    volume_max = None

    def __init__(self, receiver: PioneerReceiver) -> None:
        super().__init__(receiver, "main")

    @property
    def power(self) -> bool | None:
        return self._state.power

    @property
    def volume(self) -> float | None:
        raw = self._state.volume_raw
        return None if raw is None else raw_to_db(raw)

    @property
    def mute(self) -> bool | None:
        return self._state.mute

    @property
    def input_source(self) -> InputSource | None:
        return self._state.source

    @property
    def listening_mode(self) -> str | None:
        """Active decoded format (the LM status, e.g. 'DTS-HD MASTER AUDIO')."""
        return self._state.listening_mode

    @property
    def selected_listening_mode(self) -> str | None:
        """The listening mode currently selected (the SR setting)."""
        return self._state.listening_mode_set

    @property
    def tone(self) -> bool | None:
        return self._state.tone

    @property
    def bass_db(self) -> int | None:
        return self._state.bass_db

    @property
    def treble_db(self) -> int | None:
        return self._state.treble_db

    @property
    def phase_control(self) -> str | None:
        return self._state.phase_control

    @property
    def sb_processing(self) -> str | None:
        return self._state.sb_processing

    @property
    def mcacc(self) -> str | None:
        return self._state.mcacc

    async def power_on(self) -> None:
        """Turn the main zone on, robust against deep standby.

        From standby the receiver's CPU is asleep: the first command only wakes
        it (and is often dropped), and it does not reliably emit an unsolicited
        ``PWR0``. So send ``PO`` twice, then read back the real state with
        ``?P`` to drive a state update.
        """
        await self._receiver.send_raw("PO")
        await asyncio.sleep(0.5)
        await self._receiver.send_raw("PO")
        await asyncio.sleep(0.8)
        await self._receiver.send_raw("?P")

    async def power_standby(self) -> None:
        """Put the main zone into standby.

        Deliberately does *not* query ?P afterwards: polling the receiver as it
        enters standby can wake the amplifier straight back up (VSX-LX70). The
        unit also doesn't reliably emit an unsolicited PWR1, so update the
        state optimistically instead.
        """
        await self._receiver.send_raw("PF")
        self._receiver.set_optimistic_power(False)

    async def set_volume(self, db: float) -> None:
        """Set the master volume in decibels."""
        await self._receiver.send_raw(protocol.volume_set(db_to_raw(db), "main"))

    async def volume_up(self) -> None:
        await self._receiver.send_raw(protocol.volume_step(True, "main"))

    async def volume_down(self) -> None:
        await self._receiver.send_raw(protocol.volume_step(False, "main"))

    async def mute_on(self) -> None:
        await self._receiver.send_raw(protocol.mute(True))

    async def mute_off(self) -> None:
        await self._receiver.send_raw(protocol.mute(False))

    async def select_listening_mode(self, code: str) -> None:
        """Select a listening/surround mode by its 3-digit SR code."""
        await self._receiver.send_raw(protocol.listening_mode(code))

    async def set_tone(self, on: bool) -> None:
        """Enable or bypass tone control. The protocol only offers a toggle
        (``TO``), so toggle only when the current state differs."""
        if self._state.tone is None or self._state.tone != on:
            await self._receiver.send_raw(protocol.TONE_TOGGLE)

    async def set_bass_db(self, db: int) -> None:
        """Set bass to an absolute dB value (+6..-6) by stepping BI/BD.

        There is no absolute bass command, only increment/decrement, so we
        step from the current level. ``BI`` raises the level (and lowers the
        BA code); if your unit moves the opposite way, swap UP/DOWN here.
        """
        await self._step_tone(
            self._state.bass_code, db, protocol.BASS_UP, protocol.BASS_DOWN
        )

    async def set_treble_db(self, db: int) -> None:
        """Set treble to an absolute dB value (+6..-6) by stepping TI/TD."""
        await self._step_tone(
            self._state.treble_code, db, protocol.TREBLE_UP, protocol.TREBLE_DOWN
        )

    async def _step_tone(
        self, current_code: int | None, target_db: int, up: str, down: str
    ) -> None:
        if current_code is None:
            return
        target_code = tone_db_to_code(target_db)
        # Higher dB == lower code; `up` raises dB, i.e. lowers the code.
        steps = current_code - target_code
        cmd = up if steps > 0 else down
        for _ in range(abs(steps)):
            await self._receiver.send_raw(cmd)

    async def set_phase_control(self, value: int) -> None:
        """Set phase control (0=off, 1=on, 2=full band phase control)."""
        await self._receiver.send_raw(protocol.phase_control(value))

    async def set_sb_processing(self, value: int) -> None:
        """Set surround-back processing (0=off, 1=on, 2=auto)."""
        await self._receiver.send_raw(protocol.sb_processing(value))

    async def set_mcacc(self, value: int) -> None:
        """Set the MCACC memory position (0=off, 1..6=memory slot)."""
        await self._receiver.send_raw(protocol.mcacc(value))


class ZonePlayer(_BasePlayer):
    """A secondary zone. Zone 2 has volume; zone 3 does not."""

    volume_min = None
    volume_max = None

    def __init__(
        self, receiver: PioneerReceiver, zone: str, has_volume: bool
    ) -> None:
        super().__init__(receiver, zone)
        self.has_volume = has_volume

    @property
    def power(self) -> bool | None:
        return getattr(self._state, f"{self._zone}_power")

    @property
    def input_source(self) -> InputSource | None:
        return getattr(self._state, f"{self._zone}_source")

    @property
    def volume(self) -> float | None:
        if not self.has_volume:
            return None
        raw = getattr(self._state, f"{self._zone}_volume_raw")
        return None if raw is None else raw_to_db(raw)

    async def set_volume(self, db: float) -> None:
        if not self.has_volume:
            return
        await self._receiver.send_raw(protocol.volume_set(db_to_raw(db), self._zone))

    async def volume_up(self) -> None:
        if self.has_volume:
            await self._receiver.send_raw(protocol.volume_step(True, self._zone))

    async def volume_down(self) -> None:
        if self.has_volume:
            await self._receiver.send_raw(protocol.volume_step(False, self._zone))
