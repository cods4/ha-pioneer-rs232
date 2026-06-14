#!/usr/bin/env python3
"""Interactive / one-shot tester for the Pioneer RS-232 core library.

This is the async successor to avr.py: instead of poking the serial port
directly it drives the same ``pioneer_avr`` package that the Home Assistant
integration uses, so anything you confirm here is confirmed for HA too.

Usage:
  python3 cli.py                 # interactive REPL
  python3 cli.py ?P ?V ?F        # send raw commands and print decoded state
  python3 cli.py --port /dev/ttyUSB0 PO

REPL commands:
  <raw>        send a raw Pioneer command, e.g. ?P, PO, 05FN, 50VL
  status       re-query the receiver and print the full decoded state
  on / off     main power on / standby
  vol +/-      volume up / down        |  vol <dB>   set volume in dB
  mute on/off  mute control
  source <x>   select input by slug (e.g. dvd, hdmi_1) or FN code (e.g. 04)
  modes        list selectable listening-mode codes
  mode <code>  select listening mode by 3-digit SR code (e.g. 001)
  help         show this cheat-sheet      |  quit / q   exit
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Make the in-tree core library importable without installing it.
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_components", "pioneer_rs232")
)

from pioneer_avr import (  # noqa: E402
    DEFAULT_PORT,
    SET_LISTENING_MODES,
    SLUG_TO_INPUT,
    PioneerReceiver,
    ReceiverState,
)
from pioneer_avr.const import INPUT_BY_CODE, raw_to_db  # noqa: E402


def format_state(state: ReceiverState) -> str:
    """Render the populated parts of the receiver state as readable lines."""
    rows: list[tuple[str, str]] = []

    def add(label: str, value: object) -> None:
        if value is not None:
            rows.append((label, str(value)))

    add("Power", _onoff(state.power))
    if state.volume_raw is not None:
        rows.append(("Volume", f"{raw_to_db(state.volume_raw):+.0f} dB (raw {state.volume_raw})"))
    add("Mute", _onoff(state.mute))
    add("Source", state.source.name if state.source else None)
    add("Listening mode", state.listening_mode)
    add("Listening mode (set)", state.listening_mode_set)
    add("Tone", _onoff(state.tone))
    if state.bass_db is not None:
        rows.append(("Bass", f"{state.bass_db:+d} dB"))
    if state.treble_db is not None:
        rows.append(("Treble", f"{state.treble_db:+d} dB"))
    add("Phase control", state.phase_control)
    add("SB processing", state.sb_processing)
    add("MCACC", state.mcacc)
    add("Tuner preset", state.tuner_preset)
    add("Tuner freq", state.tuner_freq)
    add("Zone 2 power", _onoff(state.zone2_power))
    if state.zone2_volume_raw is not None:
        rows.append(("Zone 2 volume", f"{raw_to_db(state.zone2_volume_raw):+.0f} dB"))
    add("Zone 2 source", state.zone2_source.name if state.zone2_source else None)
    add("Zone 3 power", _onoff(state.zone3_power))
    add("Zone 3 source", state.zone3_source.name if state.zone3_source else None)
    add("Last error", state.last_error)

    if not rows:
        return "  (no state yet)"
    width = max(len(label) for label, _ in rows)
    return "\n".join(f"  {label:<{width}} : {value}" for label, value in rows)


def _onoff(value: bool | None) -> str | None:
    if value is None:
        return None
    return "ON" if value else "OFF"


async def repl(receiver: PioneerReceiver) -> None:
    """Run the interactive prompt."""
    loop = asyncio.get_running_loop()

    def on_update(state: ReceiverState | None) -> None:
        if state is None:
            print("\n[disconnected]")

    receiver.subscribe(on_update)

    print(f"Connected to Pioneer on {receiver.port} @ {receiver.baud} 8N1.")
    print("Type 'help' for commands, 'status' for a full read, 'quit' to exit.")

    while True:
        try:
            line = (await loop.run_in_executor(None, input, "avr> ")).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if not await handle_command(receiver, line):
            break


async def handle_command(receiver: PioneerReceiver, line: str) -> bool:
    """Execute one REPL line. Returns False to quit."""
    parts = line.split()
    cmd, args = parts[0].lower(), parts[1:]

    if cmd in ("quit", "q", "exit"):
        return False
    if cmd in ("help", "h", "?help"):
        print(__doc__)
    elif cmd == "status":
        await receiver.query_state()
        await asyncio.sleep(1.0)  # let replies stream in
        print(format_state(receiver.state))
    elif cmd == "on":
        await receiver.main.power_on()
    elif cmd == "off":
        await receiver.main.power_standby()
    elif cmd == "mute":
        await (receiver.main.mute_on() if args[:1] == ["on"] else receiver.main.mute_off())
    elif cmd == "vol":
        await _do_volume(receiver, args)
    elif cmd == "source":
        await _do_source(receiver, args)
    elif cmd == "modes":
        for code, name in SET_LISTENING_MODES.items():
            print(f"  {code}  {name}")
    elif cmd == "mode" and args:
        await receiver.main.select_listening_mode(args[0])
    else:
        # Treat anything else as a raw command (the avr.py behaviour).
        await receiver.send_raw(line)
        await asyncio.sleep(0.6)
        print(format_state(receiver.state))
    return True


async def _do_volume(receiver: PioneerReceiver, args: list[str]) -> None:
    if not args:
        print("  usage: vol +|- | vol <dB>")
        return
    if args[0] in ("+", "up"):
        await receiver.main.volume_up()
    elif args[0] in ("-", "down"):
        await receiver.main.volume_down()
    else:
        try:
            await receiver.main.set_volume(float(args[0]))
        except ValueError:
            print(f"  not a dB value: {args[0]!r}")


async def _do_source(receiver: PioneerReceiver, args: list[str]) -> None:
    if not args:
        print("  available:", ", ".join(sorted(SLUG_TO_INPUT)))
        return
    key = args[0].lower()
    source = SLUG_TO_INPUT.get(key) or INPUT_BY_CODE.get(key)
    if source is None:
        print(f"  unknown source: {args[0]!r}")
        return
    await receiver.main.select_input_source(source)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pioneer RS-232 tester")
    parser.add_argument("--port", default=DEFAULT_PORT, help="serial port path")
    parser.add_argument("commands", nargs="*", help="raw commands for one-shot mode")
    cli_args = parser.parse_args()

    receiver = PioneerReceiver(cli_args.port)
    try:
        await receiver.connect()
    except Exception as err:  # noqa: BLE001
        print(f"Failed to open {cli_args.port}: {err}")
        sys.exit(1)

    try:
        if cli_args.commands:
            for raw in cli_args.commands:
                print(f">>> {raw}")
                await receiver.send_raw(raw)
                await asyncio.sleep(0.6)
            print(format_state(receiver.state))
        else:
            await repl(receiver)
    finally:
        await receiver.disconnect()
        print("\nClosed.")


if __name__ == "__main__":
    asyncio.run(main())
