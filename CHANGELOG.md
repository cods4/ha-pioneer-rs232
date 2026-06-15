# Changelog

## 0.3.3
- Detect manual power-off: the receiver sends its power-off status without a
  CR/LF terminator, so the read loop never processed it. It now flushes a
  buffered partial line when the serial link goes idle, so unterminated
  messages (like the power-off `PWR1`) are handled.

## 0.3.2
- Tolerate leading line-noise on power-up: the receiver prepends junk to its
  first message as the RS-232 line settles (e.g. `P\x00PWR0`), which previously
  went unparsed so manual power-on wasn't detected. Control bytes are now
  stripped and a few bytes of leading noise are skipped. Parsing is also
  hardened against malformed power/tone tokens.

## 0.3.1
- Detect manual power-on: an unsolicited `PWR0` (front-panel button, remote)
  now flips the entity On and triggers a full status refresh.
- Log every received line at debug (`RX '...'`) to aid troubleshooting.

## 0.3.0
- New action `pioneer_rs232.send_command`: send a raw command and get the
  reply back (supports response data).

## 0.2.2
- Mark main power Off optimistically on standby (the receiver doesn't report
  standby over serial, and polling it would wake the amplifier).

## 0.2.1
- Fix power-off re-waking the amplifier (no longer polls `?P` after `PF`).
- Normalise the 4-digit `?S` sound-mode status code so scenes apply correctly.

## 0.2.0
- Add Audio format sensor; Tone switch; Bass/Treble numbers; Phase control,
  Surround-back processing and MCACC memory selects.

## 0.1.x
- Initial release: media_player for main + Zone 2/3, serialx transport
  (local serial and ESPHome serial proxy), config flow, HACS packaging.
