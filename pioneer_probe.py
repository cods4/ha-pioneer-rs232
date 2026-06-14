#!/usr/bin/env python3
"""Probe a Pioneer AVR over RS-232 (/dev/ttyS0) for status / capabilities.

Only sends READ-ONLY '?' query commands so no settings are changed.
Prints which queries return data, which return ERR, and which are silent.
"""
import time
import serial

PORT = "/dev/ttyS0"
BAUD = 9600

# Known / documented Pioneer query commands (read-only) with a label.
KNOWN_QUERIES = [
    ("?P",    "Power status (PWR0=on / PWR1=standby)"),
    ("?V",    "Master volume (VOL000-185)"),
    ("?M",    "Mute status (MUT0/1)"),
    ("?F",    "Input function (FN##)"),
    ("?L",    "Listening mode (set)"),
    ("?S",    "Listening mode (playback)"),
    ("?T",    "Tuner preset"),
    ("?FR",   "Tuner frequency"),
    ("?BA",   "Bass"),
    ("?TR",   "Treble"),
    ("?FL",   "Front-panel display text (hex)"),
    ("?RGB00","Input name 00"),
    ("?RGB05","Input name 05 (DVD)"),
    ("?RGB19","Input name 19 (HDMI1)"),
    ("?AST",  "Audio status"),
    ("?VST",  "Video status"),
    ("?HA",   "HDMI audio"),
    ("?HO",   "HDMI output"),
    ("?SSA",  "System status A"),
    ("?SSI",  "System info"),
    ("?SSL",  "Speaker/zone info"),
    ("?SVB",  "Software/version B"),
    ("?SDA",  "Display A"),
    ("?ZV",   "Zone2 volume"),
    ("?ZP",   "Zone2 power"),
    ("?ZM",   "Zone2 mute"),
    ("?ZS",   "Zone2 input"),
    ("?AP",   "Zone3 power"),
    ("?BP",   "HDZone power"),
    ("?TO",   "Tone control on/off"),
    ("?PKL",  "Panel key lock"),
    ("?SAB",  "Sleep timer"),
    ("?RML",  "Remote model / ID"),
]


def query(ser, cmd, wait=0.8):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode("ascii"))
    ser.flush()
    end = time.time() + wait
    buf = b""
    while time.time() < end:
        chunk = ser.read(128)
        if chunk:
            buf += chunk
            end = time.time() + 0.35
    lines = [l.decode("ascii", "replace")
             for l in buf.replace(b"\r", b"\n").split(b"\n") if l]
    return lines


def main():
    ser = serial.Serial(
        PORT, BAUD, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE, xonxoff=False, rtscts=False,
        dsrdtr=False, timeout=0.25,
    )
    time.sleep(0.2)
    ser.write(b"\r")
    ser.flush()
    time.sleep(0.2)
    ser.reset_input_buffer()

    print("=== Known Pioneer query commands ===")
    responded, errored, silent = [], [], []
    for cmd, label in KNOWN_QUERIES:
        lines = query(ser, cmd)
        joined = " | ".join(lines) if lines else ""
        up = joined.upper()
        if not lines:
            silent.append(cmd)
            status = "(silent)"
        elif "ERR" in up or up.startswith("E0"):
            errored.append(cmd)
            status = f"ERR -> {joined}"
        else:
            responded.append((cmd, joined, label))
            status = f"-> {joined}"
        print(f"  {cmd:<8} {label:<38} {status}")
        time.sleep(0.12)

    print("\n=== Brute-force ?A .. ?Z (single letter) ===")
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        cmd = "?" + c
        lines = query(ser, cmd, wait=0.5)
        if lines:
            joined = " | ".join(lines)
            up = joined.upper()
            if "ERR" not in up:
                print(f"  {cmd}  -> {joined}")
        time.sleep(0.1)

    ser.close()

    print("\n=== Summary ===")
    print(f"Responding queries: {len(responded)}")
    for cmd, val, label in responded:
        print(f"  {cmd:<8} {label:<38} = {val}")
    print(f"ERR (recognized but n/a): {', '.join(errored) or 'none'}")
    print(f"Silent (unknown/unsupported): {', '.join(silent) or 'none'}")


if __name__ == "__main__":
    main()
