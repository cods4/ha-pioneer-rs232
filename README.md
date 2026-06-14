# Pioneer VSX-92TXH RS-232 control

A Home Assistant integration (and a standalone test CLI) for controlling a
Pioneer VSX-92TXH receiver over its RS-232 serial port.

All of the serial protocol logic lives in one reusable async library
(`pioneer_avr`). The Home Assistant integration and the `cli.py` test tool are
both thin consumers of it, so anything you confirm with the CLI is confirmed for
Home Assistant too.

## Layout

```
custom_components/pioneer_rs232/        Home Assistant integration
├── pioneer_avr/                        core async library (no HA dependency)
│   ├── const.py                        enums, volume/tone conversions
│   ├── modes.py                        listening-mode tables (generated from CSV)
│   ├── protocol.py                     command builders + reply parser
│   ├── models.py                       VSX-92TXH capabilities
│   └── receiver.py                     PioneerReceiver + zone players
├── __init__.py                         config-entry setup
├── media_player.py                     main + zone 2 + zone 3 entities
├── config_flow.py                      serial-port picker
├── manifest.json / strings.json / translations/en.json
cli.py                                  interactive / one-shot tester
```

## Testing against the receiver

This project uses [`uv`](https://docs.astral.sh/uv/).

```bash
uv venv
uv pip install serialx

# interactive REPL (local serial)
uv run python cli.py --port /dev/ttyS0

# one-shot: send raw commands and print decoded state
uv run python cli.py --port /dev/ttyS0 ?P ?V ?F

# over an ESPHome serial proxy (serialx dispatches on the URL scheme)
uv run python cli.py --port "esphome://192.168.1.42:6053/?port_name=RS232%20Proxy%20Port&key=YOUR_KEY"
```

In the REPL: `status`, `on`/`off`, `vol +`/`vol -`/`vol -20`, `mute on`,
`source dvd`, `modes`, `mode 001`, or any raw command (e.g. `05FN`).

## Connection

The integration uses [`serialx`](https://github.com/puddly/serialx), Home
Assistant's async serial driver (2026.5+). It connects to any port `serialx`
understands, selected from the standard serial-port dropdown:

- a **local serial device**, e.g. `/dev/ttyS0`, or
- an **ESPHome serial proxy** — an ESP32 running the
  [`serial_proxy`](https://esphome.io/components/serial_proxy/) component, which
  bridges a UART to the network over the ESPHome native API. The proxy appears
  in the serial-port dropdown by its friendly name alongside USB ports; no
  socket address or extra config is needed.

> **Requires Home Assistant 2026.5 or newer** (when `serialx` and ESPHome
> serial-proxy support were introduced).

## Installing in Home Assistant

This is a **custom integration**, distributed through
[HACS](https://hacs.xyz/) (not a Home Assistant add-on).

**Via HACS (recommended):**

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/cods4/ha-pioneer-rs232` with category **Integration**.
3. Install **Pioneer RS-232**, then restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → Pioneer RS-232**, and pick
   the serial port (your ESPHome `RS232 Proxy Port` or a local `/dev/tty…`).

**Manual:** copy `custom_components/pioneer_rs232/` into your Home Assistant
`config/custom_components/` directory and restart. The `pioneer_avr` library
ships inside the component; the only external requirement is `serialx`, which
Home Assistant 2026.5+ already provides.

## Protocol source

Command and listening-mode tables are derived from
`vsx92txh_rs232c_commands.csv` and `vsx92txh_listening_surround_modes.csv`.
Volume uses the documented mapping `dB = raw - 81` (01 = -80 dB, 81 = 0 dB,
93 = +12 dB).

## Known limitations

### Listening modes unsupported on the VSX-LX70

The mode tables come from the VSX-92TXH documentation. When tested on a
**VSX-LX70**, the following `SR` listening-mode codes are **not accepted** and
should be avoided (or removed from the model's mode list for that unit):

| Code | Mode |
| ---- | ---- |
| 022  | (Multi-Channel Source) + EX |
| 023  | (Multi-Channel Source) + PRO LOGIC IIx MOVIE |
| 024  | (Multi-Channel Source) + PRO LOGIC IIx MUSIC |
| 026  | DTS-ES matrix6.1 |
| 028  | XM HD SURROUND |
| 029  | NEURAL THX |
| 030  | DTS-ES 8ch discrete |
