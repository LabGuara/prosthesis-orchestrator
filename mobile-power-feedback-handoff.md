# Power command feedback — orchestrator → mobile app handoff

The orchestrator now listens to the communication bridge's power feedback and **republishes it
on a parsed topic** meant for the mobile app. This document is the contract the app needs to
implement against.

Nothing on the command side changed: the app keeps publishing power commands exactly as it does
today. What is new is that a reply always comes back.

## At a glance

| | |
| --- | --- |
| Feedback topic (app subscribes) | `prothesis/actions/feedback/parsed` |
| Orchestrator env var | `MQTT_POWER_FEEDBACK_PARSED_TOPIC` |
| Direction | orchestrator → mobile app |
| QoS | 1 |
| Retain | `false` |
| Broker | unchanged — same host, credentials and TLS settings already used for commands and logs |
| Triggered by | every power command (`16` / `17`) that reaches the prosthesis, without exception |

## Message flow

```
mobile app  --{"command_type":2,"value":16}-->  prothesis/actions
                                                     |
                                            orchestrator (stores command_log)
                                                     |
                                                 "16"  -->  prothesis/actions/parsed
                                                                  |
                                                          bridge on the Raspberry Pi
                                                        (starts/stops RoboticLegControl)
                                                                  |
                                        prothesis/actions/feedback  <--  {JSON feedback}
                                                     |
                                        orchestrator (stores a log row)
                                                     |
mobile app  <--{JSON feedback}--  prothesis/actions/feedback/parsed
```

The app only needs to touch the two ends: it publishes on `prothesis/actions` and subscribes to
`prothesis/actions/feedback/parsed`. The middle topics are bridge/orchestrator internals.

## Command side (unchanged, for reference)

Commands are published on `prothesis/actions` (orchestrator env `MQTT_COMMAND_LOGS_TOPIC`) as
JSON:

```json
{"timestamp":"2026-08-17T12:00:00Z","command_type":2,"value":16}
```

| `command_type` | Meaning | `value` | Feedback? |
| --- | --- | --- | --- |
| `1` | gait mode | `1`–`9` (walking, stair ascent, standing, stair descent, upslope, downslope, sitting, sit-to-stand, stand-to-sit) | **no** — fire and forget |
| `2` | power | `16` = on, `17` = off | **yes** — always answered |

## Feedback payload

A JSON object. All five fields are always present.

| Field | Type | Values |
| --- | --- | --- |
| `timestamp` | string | ISO 8601 UTC with `+00:00` offset and microsecond precision, e.g. `2026-08-17T12:04:30.552004+00:00` (**not** `Z`). This is the moment the bridge produced the feedback, not the moment the app receives it. |
| `command` | string | `"power_on"` or `"power_off"` — echoes which command this answers |
| `status` | string | `"success"` or `"failure"` |
| `state` | string | `"on"` or `"off"` — the prosthesis power state **after** the command |
| `message` | string | human-readable detail. Free text, **not a stable API**: log it, show it to the operator, never branch on it |

### JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ProsthesisPowerFeedbackParsed",
  "type": "object",
  "required": ["timestamp", "command", "status", "state", "message"],
  "properties": {
    "timestamp": { "type": "string", "format": "date-time" },
    "command": { "type": "string", "enum": ["power_on", "power_off"] },
    "status": { "type": "string", "enum": ["success", "failure"] },
    "state": { "type": "string", "enum": ["on", "off"] },
    "message": { "type": "string" }
  }
}
```

The orchestrator emits exactly these five fields — it normalizes the bridge payload and drops any
extra field the bridge might add later. Still parse leniently and ignore unknown fields, so a
future orchestrator version that forwards more data does not break the app.

## Status semantics — the part that matters

`status` describes **the resulting state, not the work performed**. A command that was already
satisfied is a success, because the prosthesis is in the state the app asked for.

| Scenario | `status` | `state` |
| --- | --- | --- |
| `power_on`, prosthesis already on | `success` | `on` |
| `power_on`, was off, started fine | `success` | `on` |
| `power_on`, was off, start failed | `failure` | `off` |
| `power_off`, prosthesis already off | `success` | `off` |
| `power_off`, was on, stopped fine | `success` | `off` |
| `power_off`, was on, stop failed | `failure` | `on` |

The invariant the app can rely on:

> `status == "success"` **if and only if** `state` equals the state the command asked for.

That makes `state` sufficient on its own to drive the toggle — `status` is there so error handling
reads naturally.

### Sample payloads

Real orchestrator output, byte for byte:

```json
{"timestamp": "2026-08-17T12:00:00.421870+00:00", "command": "power_on", "status": "success", "state": "on", "message": "started RoboticLegControl (sudo pid 4312)"}
{"timestamp": "2026-08-17T12:00:07.118240+00:00", "command": "power_on", "status": "success", "state": "on", "message": "RoboticLegControl is already running"}
{"timestamp": "2026-08-17T12:01:11.903115+00:00", "command": "power_on", "status": "failure", "state": "off", "message": "RoboticLegControl exited right after start with status ExitStatus(unix_wait_status(256))"}
{"timestamp": "2026-08-17T12:04:30.552004+00:00", "command": "power_off", "status": "success", "state": "off", "message": "stopped RoboticLegControl (pids 4312, 4313)"}
{"timestamp": "2026-08-17T12:06:02.774390+00:00", "command": "power_off", "status": "failure", "state": "on", "message": "RoboticLegControl is still running after kill (pids 4312): kill for pid 4312 exited with status ExitStatus(unix_wait_status(256))"}
```

Note the spaces after the colons and commas — this is `json.dumps` output, not compact JSON.
Never string-match the payload; parse it.

### Messages the bridge can send

Useful for test fixtures and for wording the UI. Again: display only, never branch on these.

**Success**

- `RoboticLegControl is already running`
- `started RoboticLegControl (sudo pid <pid>)`
- `RoboticLegControl is already stopped`
- `no running RoboticLegControl process found, already stopped`
- `stopped RoboticLegControl (pids <pid>, <pid>)`

**Failure**

- `failed to start RoboticLegControl: <os error>`
- `RoboticLegControl exited right after start with status <status>`
- `failed to check whether RoboticLegControl (sudo pid <pid>) stayed alive: <os error>`
- `failed to run pgrep to locate RoboticLegControl: <os error>`
- `RoboticLegControl is still running after kill (pids <pids>)` — optionally followed by the kill errors
- `could not confirm RoboticLegControl was stopped: <reason>`

## Timing and delivery

- The bridge verifies the outcome before answering: **500 ms** after spawning to confirm the
  process stayed alive, **500 ms** after killing to confirm the processes are gone. Feedback
  leaves the Pi roughly **0.5–1.5 s** after the command.
- Add the orchestrator hop (parse, one DB insert, republish) and two broker round trips. On a
  healthy setup the app sees the feedback in **1–2 s**.
- Use an **8 s timeout** in the app before declaring "no response from prosthesis". That covers
  the bridge's own 5 s ceiling plus the extra hop, with room to spare on mobile networks.
- Order is preserved: the bridge handles power commands sequentially and the orchestrator
  processes MQTT messages on a single loop, so feedback order always matches command order.
- Nothing is queued or retained. If the bridge, the orchestrator or the phone is offline when the
  feedback would have been produced, that feedback is lost — the timeout is the only recovery.
- Malformed feedback is dropped by the orchestrator (it logs an error and does not republish), so
  from the app's point of view it is indistinguishable from no answer at all.

## What to implement in the mobile app

1. **Subscribe** to `prothesis/actions/feedback/parsed` at QoS 1, on the same broker and
   credentials already used for commands. Re-subscribe on every reconnect.
2. **Parse** the JSON. Ignore unknown fields; treat a missing required field or an unknown enum
   value as malformed — log it and ignore the message, never crash the MQTT callback.
3. **Track** the prosthesis power state from `state`, and let feedback be the *only* writer of
   that state. Never optimistically flip the toggle when publishing a command — show a pending
   state instead and let the feedback settle it.
4. **Await** feedback after publishing `16` / `17`: keep the toggle pending, resolve it on the
   matching `command` value, and time out after ~8 s with a "no response from prosthesis" error
   that leaves the state *unknown* rather than guessing.
5. **Serialize** power commands — do not issue a new one while another is pending, and disable the
   toggle meanwhile. Feedback carries no request id, so matching relies on exactly one power
   command being in flight at a time.
6. **Surface** `message` verbatim on failure. It is the only diagnostic the operator gets without
   SSH access to the Pi. It is worth showing on success too, since it distinguishes "started" from
   "was already running".
7. **Handle the unknown startup state.** On app launch the prosthesis state is unknown and there is
   no way to query it. Render a third, neutral state instead of defaulting the toggle to off.

### Suggested state machine

| App state | Enter on | Leave on |
| --- | --- | --- |
| `unknown` | app start, feedback timeout, malformed feedback | any feedback received |
| `pending` | power command published | matching feedback, or 8 s timeout → `unknown` |
| `on` / `off` | feedback received | next power command published → `pending` |

Gait commands never enter this machine — they stay fire-and-forget.

## Also stored as a regular log

Every feedback message is also written to the orchestrator's `logs` table as an ordinary log row:

| Column | Value |
| --- | --- |
| `timestamp` | the feedback `timestamp` |
| `level` | `INFO` when `status == "success"`, `ERROR` when `status == "failure"` |
| `sensor_name` | `power_feedback` |
| `message` | `<command> <status> (state: <state>): <message>`, e.g. `power_off success (state: off): stopped RoboticLegControl (pids 4312, 4313)` |

Relevant only if the app renders log history from the database: power feedback now shows up there
alongside sensor logs, filterable by `sensor_name = 'power_feedback'`. It is **not** published on
`prothesis/logs/parsed` — that topic still carries only sensor log text.

## Known gaps — not in this version

Flagging these so the app design accounts for them rather than assuming they exist.

- **No state query.** The prosthesis only reports in response to a command. On app startup the
  state is unknown until the first power command completes.
- **No device identifier.** The payload and topic both assume a single prosthesis. Multiple devices
  would need a per-device topic or an added field.
- **No correlation id.** Matching is by the `command` field plus one-in-flight discipline. Two
  concurrent power commands cannot be told apart.
- **No feedback for gait commands** (`1`–`9`). Those remain fire-and-forget.
- **No retained state message.** A fresh subscriber receives nothing until the next command.

## Deployment note

The app should read the feedback topic from its own configuration rather than hardcoding it, and
the string must match the orchestrator's `MQTT_POWER_FEEDBACK_PARSED_TOPIC` (default
`prothesis/actions/feedback/parsed`).

## Orchestrator-side changes (reference)

| File | Change |
| --- | --- |
| `app/settings.py` | new `mqtt_power_feedback_topic` (env `MQTT_POWER_FEEDBACK_TOPIC`, default `prothesis/actions/feedback`) and `mqtt_power_feedback_parsed_topic` (env `MQTT_POWER_FEEDBACK_PARSED_TOPIC`, default `prothesis/actions/feedback/parsed`) |
| `app/models/power_feedback.py` | new — `PowerCommand`, `PowerFeedbackStatus`, `ProsthesisState`, the `PowerFeedback` parser/validator, the log row builder and the parsed payload builder |
| `app/services/mqtt_service.py` | subscribes to the bridge feedback topic on connect |
| `app/main.py` | new routing branch: validate the feedback, insert a log row, republish the normalized payload on the parsed topic; malformed payloads are logged and discarded |
| `.env.example`, `README.md` | document the new variables and the feedback flow |
