# Vornado Transom (Infrared) for Home Assistant

Controls a Vornado Transom window fan over infrared, through an existing Home Assistant `infrared` emitter entity. The fan sends nothing back, so the integration keeps track of what it believes the fan is doing (see [How it works](#how-it-works)).

## Requirements

- Home Assistant 2026.11.0 or newer.
- A [Vornado Transom](https://vornado.com/products/transom-parent) window fan.
- Any Home Assistant `infrared` emitter entity.
- Line of sight from the emitter to the fan.

If your Transom is Alexa-enabled and you'd rather use that, [home-assistant-vornado-transom](https://github.com/d1vanloon/home-assistant-vornado-transom) controls it through your Amazon account and polls its state from the cloud.

### Tested hardware

Developed and tested with a Vornado Transom fan and a Moes UFO-R11 blaster (Zigbee2MQTT model TS1201) connected through Zigbee2MQTT. Other emitters should work, but their limits may differ (see [Options](#options) and [Known limits](#known-limits)).

## Installation

### Marketplace

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=danielmoore&repository=homeassistant-vornado-transom-infrared&category=integration)

Or add it by hand:

1. Go to **Settings > Marketplace** and select **Add from link**.
2. Under **GitHub link**, enter `https://github.com/danielmoore/homeassistant-vornado-transom-infrared` and select **Add**. Home Assistant asks you to connect GitHub if you haven't already.
3. Install **Vornado Transom (Infrared)**.

### Manual

Copy `custom_components/vornado_transom_infrared` into your Home Assistant `custom_components` directory and restart.

## Setup

Go to **Settings > Devices & services > Add integration > Vornado Transom (Infrared)** and pick the infrared emitter that points at the fan. Each emitter can be used by one Transom. To control several fans, use one emitter per fan.

### Options

Open the integration's **Configure** dialog to change:

| Option | Default | Range | Change it when |
|---|---|---|---|
| Frames per press | 5 | 1-10 | The fan misses presses (raise it), or you want shorter sends and presses are reliable (lower it). 3 frames missed about 1 press in 9 in testing. |
| Maximum timings per payload | 288 | 24-1000 | Your emitter plays more or fewer timings per command. The effective minimum is 2 x frames per press x 24 (48 at 1 frame), so the value must hold at least two presses. Longer sequences are split into several sends. |
| Throttle interval | 5 s | 0-60 s | You want changes to go out faster (lower) or batched more (higher). 0 disables throttling. |

## Entities

- **Fan**: on/off, speeds 1-4 (Low, Medium, High, Turbo) at 25% steps and direction. Forward is Direct (intake); reverse is Exhaust.
- **Mode** (select): `Auto` uses the fan's thermostat mode; `Manual` turns it off.
- **Setpoint** (number): the Auto target, 60-90 °F.
- Diagnostic entities showing what the integration assumes about the fan: power, speed, direction, mode, setpoint, assumed idle, and the time of the last command.

The fan, Mode and Setpoint entities show the state you asked for. The diagnostic entities show the state the integration believes the fan is actually in, which differs while changes are pending. The last-command time and assumed idle reset after a restart or an options reload.

## How it works

IR is one-way, so the integration dead-reckons the fan's state: it remembers what it last sent and works out which button presses move the fan from there to what you asked for. Speed and temperature use the same Up/Down buttons and Direct/Exhaust and Power are toggles, so every press is relative to the assumed state.

- The integration should be the only thing transmitting to the fan. The remote or the fan's panel changes the fan without the integration knowing.
- Sends are throttled to one per throttle interval. Changes made in between are combined and sent when the interval ends.
- The fan goes idle a few seconds after a button press, and the first press on an idle fan only wakes it. Every send to a running fan therefore starts with a wake press.
- A setpoint change while Auto is off is stored and applied the next time Auto is turned on.
- Changes made while the fan is off (direction, Auto, setpoint) are stored and applied when it is turned on.
- Setting any speed on an off fan turns it on.
- A speed change shortly after a setpoint change waits until the fan's 5 second setpoint window has passed, because Up/Down adjust the setpoint during that window.

## Resync

If someone used the remote or the panel, or the fan lost power, the assumed state drifts. Compare the diagnostic entities with the fan, then call `vornado_transom_infrared.set_assumed_state` with the real values. It only updates what the integration believes; nothing is sent. Fields you leave out keep their current assumed value. Any pending or stored change is discarded, and the fan, Mode and Setpoint entities jump to the resynced values.

```yaml
action: vornado_transom_infrared.set_assumed_state
target:
  entity_id: fan.vornado_transom_fan
data:
  power: true
  speed: 2
  direction: direct   # or exhaust
  auto: false
  setpoint: 72
```

`fan.vornado_transom_fan` is the default entity ID. Use your own if you renamed the fan.

## Thermostat use

There are two ways to control temperature:

- **The fan's own thermostat.** Set Mode to `Auto` and pick the target with the Setpoint number. The fan regulates itself.
- **Your own thermometer.** Set Mode to `Manual` and set up Home Assistant's [generic thermostat](https://www.home-assistant.io/integrations/generic_thermostat/) with your thermometer as its sensor and the fan entity as its switch. Home Assistant then manages the temperature.

## Known limits

- **Playback limit.** The UFO-R11 plays only about the first 288 timings of a command and drops the rest. A setpoint change needs many presses, so long changes are split into several sends about 2 seconds apart, which stays inside the fan's 5 second setpoint window.
- **Zigbee2MQTT transfer.** Zigbee2MQTT allows 8 seconds to transfer a command to the emitter and sends it uncompressed, so a weak Zigbee link (low link quality) causes timeouts. `IR transmission timed out` does not mean nothing was sent: a late transfer still plays. The integration logs the error, keeps its planned state and does not retry, because a retry could apply a press twice. Resync if the fan ends up elsewhere. Adding a Zigbee router near the emitter helps.
- **Wake press.** The integration assumes the fan is idle when a send starts. If the fan is awake (for example you just used the remote), the wake press counts as a real press and the first action happens twice.
- Manual use of the remote or panel and power loss are invisible; see [Resync](#resync).

## Development

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run ty check
uv run pytest
```

`docs/design.md` describes the fan's behavior and the design decisions, and `docs/signals.md` the IR protocol.
