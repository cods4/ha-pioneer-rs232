#!/usr/bin/env python3
"""Interactive Pioneer AVR control over RS-232 (/dev/ttyS0).

Usage:
  python3 avr.py            # interactive REPL: type commands like ?P, PO, VU
  python3 avr.py ?P         # one-shot: send a single command and exit
  python3 avr.py ?P ?V ?F   # send several in sequence

Inside the REPL:
  <command>   send a raw Pioneer command (CR is added automatically), e.g. ?P
  help        show the handy command che-sheet
  quit / q    exit
Anything you type is sent verbatim + '\r', so the full Pioneer set works.
"""
import sys
import time
import serial

PORT = "/dev/ttyS0"
BAUD = 9600

# Friendly decoders for replies we understand. Key = reply prefix.
INPUTS = {
    "04": "DVD", "05": "DVD", "06": "TV/SAT", "10": "Video",
    "19": "HDMI 1", "20": "HDMI 2", "21": "HDMI 3", "22": "HDMI 4",
}


def decode(reply):
    r = reply.strip()
    u = r.upper()
    if u == "PWR0":          return "Main power: ON"
    if u == "PWR1":          return "Main power: STANDBY"
    if u.startswith("VOL"):
        n = u[3:]
        try:
            v = int(n)
            # This unit: 0 = -81 dB, 93 = +12 dB, 1 dB per step => dB = v - 81.
            return f"Volume: {v} ({v - 81:+d} dB)"
        except ValueError:
            return f"Volume: {n}"
    if u == "MUT0":          return "Mute: ON (muted)"
    if u == "MUT1":          return "Mute: OFF (not muted)"
    if u.startswith("FN"):
        code = u[2:]
        return f"Input: {INPUTS.get(code, '?')} (FN{code})"
    if u.startswith("BA"):   return f"Bass: code {u[2:]} (06 = flat/0 dB)"
    if u.startswith("TR"):   return f"Treble: code {u[2:]} (06 = flat/0 dB)"
    if u == "TO0":           return "Tone control: OFF (bypass)"
    if u == "TO1":           return "Tone control: ON"
    if u.startswith("LM"):   return f"Listening mode (active): code {u[2:]}"
    if u.startswith("SR"):   return f"Surround mode (selected): code {u[2:]}"
    if u.startswith("ZV"):   return f"Zone 2 volume: {u[2:]}"
    if u.startswith("Z2F"):  return f"Zone 2 input: {INPUTS.get(u[3:], '?')} ({u[3:]})"
    if u.startswith("APR"):  return "Zone 3 power: " + ("ON" if u[3:] == "0" else "STANDBY")
    if u.startswith("BPR"):  return "HDZone power: " + ("ON" if u[3:] == "0" else "STANDBY")
    if u.startswith("E") and u[1:].isdigit():
        return "ERROR (E%s: command not recognized / unavailable)" % u[1:]
    return None


CHEAT = """\
Queries (read-only):   ?P power  ?V volume  ?M mute  ?F input
                       ?BA bass  ?TR treble ?TO tone  ?L mode
                       ?ZV zone2 vol  ?ZS zone2 input  ?AP zone3  ?BP hdzone
Commands:              PO power on   PF power off
                       VU vol up     VD vol down
                       MO mute on    MF mute off
                       05FN=DVD 06FN=TV/SAT 19FN..22FN=HDMI 1-4
"""


def send(ser, cmd, wait=0.8):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode("ascii"))
    ser.flush()
    end = time.time() + wait
    buf = b""
    while time.time() < end:
        chunk = ser.read(128)
        if chunk:
            buf += chunk
            end = time.time() + 0.3
    lines = [l.decode("ascii", "replace")
             for l in buf.replace(b"\r", b"\n").split(b"\n") if l]
    if not lines:
        print("  (no reply)")
        return
    for line in lines:
        meaning = decode(line)
        print(f"  {line}" + (f"   -> {meaning}" if meaning else ""))


def open_port():
    ser = serial.Serial(
        PORT, BAUD, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE, xonxoff=False, rtscts=False,
        dsrdtr=False, timeout=0.25,
    )
    time.sleep(0.15)
    ser.write(b"\r")            # wake-up nudge
    ser.flush()
    time.sleep(0.15)
    ser.reset_input_buffer()
    return ser


def main():
    args = sys.argv[1:]
    ser = open_port()

    # One-shot mode: commands given on the command line.
    if args:
        for cmd in args:
            print(f">>> {cmd}")
            send(ser, cmd)
        ser.close()
        return

    # Interactive REPL.
    print(f"Connected to Pioneer AVR on {PORT} @ {BAUD} 8N1.")
    print("Type a command (e.g. ?P), 'help' for a cheat-sheet, or 'quit'.")
    try:
        while True:
            try:
                line = input("avr> ").strip()
            except EOFError:
                break
            if not line:
                continue
            low = line.lower()
            if low in ("quit", "q", "exit"):
                break
            if low in ("help", "h", "?"):
                print(CHEAT)
                continue
            send(ser, line)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("\nClosed.")


if __name__ == "__main__":
    main()
