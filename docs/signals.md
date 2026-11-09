# Transom IR signals

What we know about the Vornado Transom remote's IR signals, and how much of it is verified. Update the status column and the checklist as tests are run.

Status values: **captured** (learned from the real remote), **verified** (transmitted by the blaster and the fan responded as expected).

## Capture setup

- Captured with a Moes UFO-R11 (Zigbee2MQTT model TS1201), friendly name `IR Blaster`, using its `learn_ir_code` expose.
- Z2M publishes the learned code in several messages. The last one carries `learned_ir_code` (Tuya format: base64 of FastLZ-compressed little-endian 16-bit µs durations) and `learned_ir_timings` (decoded signed µs: positive is a mark, negative a space).
- The same blaster sends with `ir_emitter` (timings) or `ir_code_to_send`. `ir_code_to_send` accepts both the base64 code and a JSON string `{"modulation":38000,"timings":[...]}` (verified).

## Protocol

- Carrier: 38 kHz.
- Pulse-distance encoding, one mark and one space per bit:
  - 1: ~1280 µs mark, ~427 µs space.
  - 0: ~427 µs mark, ~1280 µs space.
- No header or start pulse.
- Frame: 12 bits, MSB first as captured. The last bit's space is stretched into an inter-frame gap of ~7.8-8.9 ms. The final frame ends on the last mark with no gap.
- Repeats: 4-5 frames per press in the captures, identical bit pattern each time. The count appears to depend on how long the button was held.
- Timing varies slightly between captures (marks 417-1290 µs, gaps 7795-8880 µs). The blaster's capture resolution is the likely cause. Nominal values above are the averages.
- The protocol is **Symphony** (SM5021 encoder), as implemented in `infrared-protocols` (`infrared_protocols.commands.symphony.SymphonyCommand`, the library HA's `infrared` integration uses). Frame layout, MSB first: 3-bit frame head (`110`), 2-bit custom code (`11` = 3 for the Transom), 7-bit control word (the key). The library's nominal timings are 1265/420 µs bits with a 6740 µs footer gap added to the last bit's space, a 26.96 ms frame period, and a default of 6 frames per press. Its docstring notes that six frames worked every time on a real fan while fewer worked only occasionally, which matches what we found.

## Buttons

| Button | Frame | Control word | Frames in capture | Status |
|---|---|---|---|---|
| Power | `110110000100` | `0x04` | 5 | verified (exact replay of capture, off → on) |
| Up (speed up / temp up) | `110111000110` | `0x46` | 5 | verified for speed (exact replay; wake press then one press: speed 1 → 2) and for temperature (Auto wake, Auto, then Up: setpoint 68 → 69) |
| Down (speed down / temp down) | `110110000010` | `0x02` | 4 | verified for speed (exact replay; wake press then one press: speed 2 → 1) and for temperature (Auto wake, Auto, then Down: setpoint 69 → 68) |
| Direct/Exhaust | `110110000001` | `0x01` | 5 | verified (exact replay; wake press then one press: exhaust → direct/intake) |
| Auto | `110111000011` | `0x43` | 4 | verified (exact replay; wake press then one press from off: Auto on, setpoint flashes for a few seconds). Nominal 3-frame Auto after a wake: missed once, then worked |

Up and Down are the same physical buttons for speed and temperature. Their effect depends on the unit's state, see `design.md`.

## Raw captures (Z2M `learned_ir_code`)

```
power:          AwIFrAFAAwWsAQIFAgVABQOsAawBQAXgAQMFAgWsAawBQAUBmyJABUADBawBAgUCBUAFA6wBrAFABeABAwUCBawBrAFABeCELwIFrAE=
up:             DQEFqwEBBasBqwEBBQEFQAWAAwKrAQGgCQMBBQEFQAUGqwGrAT4iASAHAAEgAwWrAQEFAQVABYADAqsBAaAJAwEFAQVABQOrAasB4IQvAgGrAQ==
down:           AwUFpAFAAwKkAQUgAEAFBaQBpAEFBeAHAxIFBaQBpAGwIgUFpAEFBaQBpAEFIABABQWkAaQBBQXgBwMFBQWkAaQBwC8E3AGkAQUgAEAFgAtACeADAwUFBaQBpAHALwSkAaQBBSAAQAUFpAGkAQUF4AcDBQUFpAGkAQ==
direct_exhaust: AwoFoQFAAwWhAQoFCgVABQOhAaEBQAXgCQMFCgXfHgoFgBkFoQEKBQoFQAUDoQGhAUAF4AkDAQoF4IQvAgUKBQ==
auto:           A/4ErwFAAwWvAf4E/gRABYADAa8BwAmABwH+BEAJA3Me/gRABwevAa8B/gT+BIALBf4ErQGtAUAFgAMJ/gTfAf4E3wGtAQ==
```

Decoding the FastLZ payload by hand reproduced Z2M's `learned_ir_timings` for the Up capture, so the format is understood.

## Transmission

- One `ir_code_to_send` payload is played back as one continuous IR burst. Gaps between frames are spaces inside the payload, so the blaster times them accurately.
- Delay between separate payloads is not controlled. Each one goes through MQTT, Z2M and a multi-packet Zigbee transfer, which took about 1 s in testing and will vary.
- Bench tests sent each press as 5 frames of nominal timings (1280/427 µs bits, 8766 µs gap). 5 matches the remote. 3 frames missed about 1 press in 9, so 5 is used for margin.
- The integration sends `SymphonyCommand`'s timings instead (1265/420 µs bits, 6740 µs footer gap added to the last bit's space), with a configurable frame count that defaults to 5.
- Presses in one payload are separated by a 65 ms space, which replaces the last frame's gap.
- The blaster plays at most the first 288-318 timings of a code and silently drops the rest. Payloads must stay at or under 288 timings: 2 presses at 5 frames (240), or 4 presses at 3 frames (288).
- Presses in one payload are 65 ms apart, within the playback limit above. Verified for wake + action, several speed steps, double Auto, and Auto then Up. Longer sequences have to be split across payloads, whose arrival times are not controlled.
- The integration only treats a double Auto as inseparable. Every other press, including the wake press, can land in a separate payload, because split payloads arrive inside the fan's idle timeout.

## Z2M transfer behavior

- From zigbee-herdsman-converters `src/lib/zosung.ts`: Z2M announces the code's length, then the blaster pulls it in 50-byte chunks of the encoded (compressed) code and signals completion at the end.
- Z2M allows 8 s for the whole transfer (hard-coded, not configurable) and then reports `IR transmission timed out`.
- The error doesn't mean nothing was sent: a transfer that finishes after 8 s still plays. The integration must treat a send error as an unknown outcome and must not retry automatically, since a retry could apply a press twice.
- The size limit depends on the compressed size and on link quality, not on a fixed number of timings.
- Z2M sets the Tuya envelope's `num` to `1 + repeat_count`. The UFO-R11 ignores it: an Up press ending in a 65 ms space, sent with `repeat_count: 2` (`num: 3`), registered once (verified twice, with and without the trailing space).

## Verification checklist

- [x] Each frame transmitted via the blaster produces the expected effect on the fan. All five buttons verified with exact replays of the captures.
- [x] Repeat count: decided on 5 frames per press, configurable. Single frames registered 1 of 3. 3 frames registered 3 of 3 in a counted Down trial but missed 1 of about 9 presses overall (an Auto press).
- [x] Whether one frame (no repeats) is enough. Not reliably: a single frame sometimes works (Up 2 of 2, captured Down 1 of 1) but a nominal single Down registered only 1 of 3 in a counted trial. Use at least 3 frames.
- [x] Inter-frame gap: 8766 µs in bench tests. A shorter gap would only save a few ms per press. The integration uses the library's footer gap (see Transmission).
- [x] Nominal mark/space values (1280/427 µs, gap 8766 µs) transmit reliably with 3 frames per press (3 of 3 Down presses). Single nominal frames were unreliable, as were some single frames of captured timings, so the cause appears to be the repeat count and not the values.
- [x] Wake press from idle has no other effect. Verified with Up: a single Up on an idle fan only woke it.
- [x] Double Auto in one transmission: verified. Auto, 65 ms, Auto in a single payload (after a separate wake) turned Auto off. Separate Zigbee sends can't reliably land within the fan's ~1 s double-press limit, so the integration always sends both presses in one payload.
- [x] The 5 s setpoint window is restarted by each Up/Down press. Verified by the split-payload test: the last Up played ~7 s after the Auto press and still changed the setpoint.
- [x] Press separation: the shortest pause between two frame groups in one payload that the fan counts as two presses, not one long press. 65 ms: two presses (Up, pause, Up in one payload: speed 1 → 3). 20 ms: one press (Down, pause, Down: speed 3 → 2). 40 ms: two presses (Up, pause, Up: speed 2 → 4). Threshold is between 20 and 40 ms. Decided on 65 ms (the longest single 16-bit space), for margin above 40 ms without needing chained spaces.
- [x] Long pauses: closed again, not the cause. Ups 130 ms and 1 s apart still registered only one step, while the physical remote registers ~4 presses/s. Two consecutive Up captures are bit-identical, so there is no toggle bit. The cause turned out to be payload length (see payload size).
- [x] Payload size: the largest payload the blaster and Z2M accept, in timings, so multi-press sequences can be sized or split. 360 timings: works. 1440 timings (wake + Auto + 10 Ups at 5 frames): Z2M error `IR transmission timed out` after ~12 s of transfer, and nothing was transmitted (fan unchanged). 720 timings (wake + Auto + 4 Ups): same timeout, nothing transmitted. 480 timings (wake + Auto + 2 Ups, Auto already on): no error, but setpoint rose by 1 instead of 2 (one Up missed). 360 timings (wake + Auto + 1 Up): Z2M reported `IR transmission timed out`, yet the setpoint rose 70 → 71, so the error does not mean nothing was sent. An Up 65 ms after Auto (with Auto already on) registers. The blaster reported Zigbee link quality of 7-10/255 during earlier captures, so failures may come from the weak link rather than a fixed size limit (unverified). After adding a router: a single press reported LQI 43-156 and transferred in ~1.6 s, but a 720-timing payload still timed out, nothing played, and LQI during that transfer fell to 0-14. The blaster reports 1500 mV supply voltage (battery reported as 100%). Self-compressed (real FastLZ) base64 codes sent via `ir_code_to_send` play correctly: a 720-timing sequence encoded to 88 chars, transferred in ~0.7 s with no error. Z2M's own encoder is literal-only (open upstream PR Koenkk/zigbee-herdsman-converters#13500 adds compression). Playback truncation: every payload over 360 timings dropped everything after roughly the first 360-480 timings (480, 482, 510 and 720 timings each registered only the first Up). wake + Auto + 2 Ups at 3 frames per press (288 timings) registered both Ups, twice (setpoint 70 → 74 over two sends). wake + Auto + 4 Ups at 3 frames (432 timings) registered 2 of 4 (74 → 76): playback stops somewhere between 288 and 360 timings, likely ~300-330 (consistent with all earlier results). Count, not duration: 318 timings with a 1 s pause and 318 timings with ~60 ms of short filler (100 µs marks, 4 ms spaces) both dropped the last Up, so the blaster plays only the first 288-318 timings of a code, whatever its length in time. Use at most 288 timings per payload (verified).
- [x] Combined sequences: whether wake + action, several speed steps, and Auto then Up/Down work as single payloads. Wake + action: verified (Down, 65 ms, Down in one payload from idle: speed 4 → 3). Several steps: verified (wake + 2 Downs, 360 timings, in one payload: speed 3 → 1). Auto then Up: verified (wake, Auto, Up in one payload from Auto off: Auto on, setpoint 68 → 69, speed unchanged at 1).
- [x] Split payloads: a setpoint change split into 2-press payloads stays inside the 5 s window. wake + Auto, then three payloads of Up + Up (240 timings each, uncompressed timings via Z2M as HA sends them, all published at once and queued by Z2M) took the setpoint 70 → 76. Transfers took ~2.2 s per payload (LQI ~156). An earlier identical run ended at 76 when 84 was expected from 78, most likely because the setpoint had been changed on the fan beforehand.
- [x] Turning Auto off and on, and turning power off and on, keeps the setpoint (checked by the user on the control panel).

## Verification through Home Assistant

The checks above used direct Zigbee2MQTT sends. These cover the integration's own timings and payloads on the real fan.

- [x] Power on and off.
- [x] Every speed.
- [x] Direction.
- [x] Auto on and off.
- [x] Setpoint change across a split payload (for example 60 → 90).
- [x] Resync.
- [x] Wake + double Auto packed into one payload at 3 frames per press (216 timings): Auto turned off.
