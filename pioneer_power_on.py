#!/usr/bin/env python3
"""Power on a Pioneer AVR over RS-232C (Serial Port A = /dev/ttyS0).

Settings: 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control.
Commands are ASCII terminated with a carriage return (\r).
"""
import sys
import time
import serial

PORT = "/dev/ttyS0"
BAUD = 9600


def read_replies(ser, duration=2.0):
    """Collect any reply lines arriving within `duration` seconds."""
    end = time.time() + duration
    buf = b""
    while time.time() < end:
        chunk = ser.read(64)
        if chunk:
            buf += chunk
            end = time.time() + 0.5  # extend a bit while data flows
    lines = [l for l in buf.replace(b"\r", b"\n").split(b"\n") if l]
    return lines


def send(ser, cmd, wait=1.0):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode("ascii"))
    ser.flush()
    print(f">>> sent {cmd!r}")
    replies = read_replies(ser, wait)
    if replies:
        for l in replies:
            print(f"<<< {l.decode('ascii', 'replace')}")
    else:
        print("<<< (no reply)")
    return replies


def main():
    print(f"Opening {PORT} at {BAUD} 8N1 ...")
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=0.3,
    )
    time.sleep(0.2)

    # Wake-up nudge: deep-standby CPUs often drop the first byte(s).
    # Send a bare CR first to wake the parser, then the power-on command.
    ser.write(b"\r")
    ser.flush()
    time.sleep(0.2)

    # Query current power state (?P -> PWR0=on / PWR1=standby on most models)
    send(ser, "?P", wait=1.5)

    # Power On. Send twice with a short gap to cover deep-standby wake delay.
    send(ser, "PO", wait=1.5)
    time.sleep(0.3)
    send(ser, "PO", wait=1.5)

    # Re-query to confirm.
    time.sleep(0.5)
    replies = send(ser, "?P", wait=1.5)

    ser.close()

    text = b" ".join(replies).decode("ascii", "replace").upper()
    if "PWR0" in text:
        print("\nResult: receiver reports POWER ON (PWR0).")
    elif "PWR1" in text:
        print("\nResult: receiver still reports STANDBY (PWR1).")
    elif "ERR" in text:
        print("\nResult: receiver returned an ERROR (ERR).")
    else:
        print("\nResult: inconclusive — see replies above.")


if __name__ == "__main__":
    sys.exit(main())
