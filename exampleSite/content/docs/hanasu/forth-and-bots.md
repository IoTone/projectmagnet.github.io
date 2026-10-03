---
weight: 110
title: "Forth, Bundles & Bots"
description: "The Hanasu node's Forth control layer: the dual-mode link, the mn-* vocabulary, chat hooks, boot scripts, signed role bundles, and opt-in bot mode."
icon: "code"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "forth"]
---

Every Hanasu node, on the ESP32-C6 and on the [XIAO MG24 Zephyr build](/docs/hanasu/mg24-zephyr/), embeds the **ESPIDFORTH** engine, the same Forth used by the [Hive AI](/docs/hive-ai/forth-words/) nodes. Forth is the **control and scripting layer over a C core**: encryption, OpenThread, CoAP, the envelope and NVS all stay in reviewable C, and Forth reaches them only through FFI words. Forth never touches key material. Each `mn-*` word is a thin wrapper around the **same** C function the HCP dispatcher calls, so the two front-ends cannot drift apart (design proposal §12.0–§12.3).

{{< alert context="warning" text="ESPIDFORTH (the E4TH dialect) is <strong>lowercase and case-sensitive</strong>. Use <code>do</code>/<code>loop</code>/<code>if</code>, not uppercase forms. The node also calls <code>forth_init()</code> before NVS, the core and the radios, so the dictionary heap (64 KB on the C6) is claimed while RAM is unfragmented." />}}

## The dual-mode link

One link dispatcher task owns the host byte stream (USB serial, or BLE GATT on BLE builds) and reads it a line at a time. It never hands the stream to a blocking REPL, so mesh events keep flowing while Forth runs.

| Mode | Enter | Behavior |
|---|---|---|
| **HCP** (default) | Boot, or `.hcp` | Structured, sigil-framed lines. Every command gets exactly one `+`/`-` response. See [HCP](/docs/hanasu/hcp/) |
| **FORTH** | `FORTH` (answers `+OK entering forth; type .hcp to return`) | Each line goes to the engine, followed by an `ok>` prompt. A line containing only `.hcp` returns to HCP mode |

All output (responses, events and Forth output) goes through one serialized writer, and the dispatcher holds it for the whole of a Forth evaluation, so an asynchronous `!CHAT` can never split a line of Forth output. FORTH mode is for people and power use; the strict HCP framing guarantees do not apply there. There is no local echo in FORTH mode.

`FORTH`, `HOOK`, `SCRIPT` and `BUNDLE` are **privileged** verbs. Over BLE they return `E_NOT_BONDED` until the link is bonded and encrypted. The USB serial link is treated as physically trusted. Once the node is in FORTH mode, every line from an unbonded BLE link is refused the same way, whoever switched the mode on.

### Engine limits

The engine is deliberately small. Per `docs/BOT-MODE.md` it has arithmetic, stack words (`depth`, `pick`, `>r`, `r>`), comparisons, `variable`/`constant`, `s"`, `if`/`else`/`then`, `begin`/`until`/`again`/`while`/`repeat`, `do`/`loop`/`+loop`, memory access (`here`, `allot`, `!`, `@`, `c!`, `c@`), `type`, and colon definitions.

It has **no** `create`/`does>`, **no** `'`/`execute`, **no** `,`/`c,`, and no string words beyond MagNET's own `str=`. All compiled code shares one 4096-cell (16 KB) array, with at most 512 words and a 256-byte input line. Interpret-mode `s"` strings live in a 4-deep rotating buffer, so use them on the same line; `s"` strings compiled into a definition are permanent. Anything that has to take text apart belongs in C.

## The MagNET vocabulary

These words are registered in `magnet_forth.c` (`mn_register_forth_vocab()`), except the OTA words, which `magnet_ota_idf.c` registers. Strings are passed as `( c-addr u )`, usually built with `s"`. A flag result `f` is 0 on success.

### Messaging and identity

| Word | Stack effect | Purpose |
|---|---|---|
| `mn-chat` | ( c-addr u -- ) | Send multicast chat to the channel |
| `mn-dm` | ( addr-c-addr addr-u text-c-addr text-u -- ) | Send unicast chat to an IPv6 address, e.g. `s" fd00::1234" s" hi there" mn-dm` |
| `mn-hello` | ( -- ) | Send a fixed `hello from forth` chat; a smoke test that needs no `s"` |
| `mn-name!` | ( c-addr u -- ) | Set the display name (1–16 chars); persists and announces |
| `mn-set-channel` | ( c-addr u -- f ) | Derive, persist and switch to a channel from a credential |
| `mn-join` | ( c-addr u -- f ) | Alias of `mn-set-channel` |

### Status and diagnostics

| Word | Stack effect | Purpose |
|---|---|---|
| `mn-status` | ( -- ) | Print the status line |
| `mn-whoami` | ( -- ) | Print device id, name and identity |
| `mn-peers` | ( -- ) | Print known peers |
| `mn-state` | ( -- n ) | Push the lifecycle state enum |
| `mn-sysinfo` | ( -- ) | Chip, IDF, heap, Forth heap, uptime |
| `mn-mesh` | ( -- ) | Thread detail: partition, RLOC, ML-EID, neighbors with RSSI |
| `mn-bench` | ( -- ) | Envelope codec and radio TX-call latency |
| `mn-selftest` | ( -- f ) | Self-test; 0 = pass. The pump and loopback stages report skipped at `ok>`, so run `SELFTEST` from HCP for the full sweep |
| `mn-stats` | ( -- ) | Print TX/RX counters |
| `mn-heartbeat!` | ( secs -- ) | Set the `!HEARTBEAT` interval, 0 to 86400; 0 = off |
| `mn-stress` | ( secs len -- f ) | Start a saturation burst; 0 = started |

### Hooks and hardware

| Word | Stack effect | Purpose |
|---|---|---|
| `mn-on-chat` | ( c-addr u -- ) | Register a word, **by name**, to run on inbound chat |
| `mn-on-cmd` | ( c-addr u -- ) | Register a word, by name, to run on inbound M2M commands |
| `mn-hooks` | ( -- ) | Print the registered hooks |
| `str=` | ( c-addr1 u1 c-addr2 u2 -- f ) | String compare for hook bodies; true (−1) if equal |
| `gpio-output` | ( pin -- ) | Make GPIO 0–31 an output |
| `gpio-set` | ( pin level -- ) | Drive a GPIO high or low |
| `led!` | ( r g b -- ) | On-board LED, 0–255 per channel. `MN_ENABLE_LED` builds only |
| `led-pat!` | ( r g b period-ms -- ) | LED color with a 50%-duty strobe; 0 = solid. `MN_ENABLE_LED` builds only |

### Time, bots and OTA

| Word | Stack effect | Purpose |
|---|---|---|
| `mn-time!` | ( epoch -- f ) | Seed the wall clock (UTC, 32-bit cell, good until 2038). See [Mesh Time](/docs/hanasu/mesh-time/) |
| `mn-now` | ( -- ) | Print clock, offset, stratum, source and age |
| `mn-time-push` | ( -- f ) | Announce this node's clock to the mesh |
| `mn-time-sync` | ( -- f ) | Ask the mesh for the time |
| `botmode` | ( [n] -- ) | Arm bot *n*, or list bots with no argument. `MN_ENABLE_BOTS` builds only |
| `mn-bot!` | ( n -- ) | Arm bot *n*; negative = off. `MN_ENABLE_BOTS` builds only |
| `mn-bots` | ( -- ) | List bots in ascending id order. `MN_ENABLE_BOTS` builds only |
| `ota-status` | ( -- ) | Report the running image and any staged package. OTA builds only |
| `ota-apply` | ( -- ) | Boot the staged image in trial mode. OTA builds only. See [OTA](/docs/hanasu/ota/) |

{{< alert context="info" text="Design proposal §12.3 also lists <code>mn-leave</code>, <code>mn-channels</code>, <code>mn-cmd</code>, <code>mn-admin-add</code>, <code>mn-rotate</code> and <code>i2c-*</code>. These are <strong>not registered</strong> in the current firmware; use the HCP verbs (<code>CHANNEL</code>, <code>ADMIN</code>, <code>ROTATE</code>) instead." />}}

## Hooks

Hooks let a node react to mesh traffic in Forth while all protocol logic stays in C. Inbound frames are decrypted, verified and de-duplicated in C. The registered word then runs **on the pump task**, never in an OpenThread or lwIP callback, with the payload pushed as `( c-addr u )`.

| Hook | Fires on | Payload |
|---|---|---|
| chat | Inbound chat (multicast) and DMs | The message text |
| cmd | Inbound M2M commands that are not system commands | The command parameters |

Set them from Forth with `mn-on-chat` / `mn-on-cmd`, or from HCP:

| HCP | Effect |
|---|---|
| `HOOK CHAT <word>` / `HOOK CMD <word>` | Register a word (name up to 32 chars) |
| `HOOK LIST` | Print `# hook chat=<word> cmd=<word>` |
| `HOOK CLEAR` | Unregister both |

Hooks bind by **word name**, not execution token, because the engine has no `'`. This is a standing deviation from §12.3, which specified `( xt -- )`. Hooks are not persisted, so re-arm them from a boot script or a bundle.

```forth
4 gpio-output
: maybe-light  s" lights on" str= if 4 1 gpio-set then ;
s" maybe-light" mn-on-chat
```

Any chat that reads exactly `lights on` now drives GPIO 4 high on this node. (Pin 4 is only an example; check your [board's pin map](/docs/hanasu/boards/).)

{{< alert context="warning" text="<strong>Hook amplification.</strong> A hook that sends chat triggers other nodes' hooks, whose replies trigger it again. The firmware caps hook firings at 5 per second and emits a one-time <code>!WARN hook-rate-limited (loop?) suppressing</code>. A deliberate two-node echo loop measured 0.6 msg/s with the cap in place, but avoid writing hooks that reply to everything." />}}

## Boot scripts (SCRIPT)

`SCRIPT` stores up to 1024 bytes of Forth source in NVS and runs it at every boot, after the vocabulary is registered and **before the radios start**, so hooks are armed before traffic arrives.

| HCP | Effect |
|---|---|
| `SCRIPT SET <src>` | Save the script. One HCP line cannot hold a newline, so `;;` separates source lines |
| `SCRIPT SHOW` | Print it as `# script| …` lines |
| `SCRIPT RUN` | Run it now (`E_SYNTAX` if none is saved) |
| `SCRIPT CLEAR` | Erase it |

```
SCRIPT SET 4 gpio-output;;: maybe-light s" lights on" str= if 4 1 gpio-set then ; ;;s" maybe-light" mn-on-chat
```

The script is evaluated one line at a time. When a line ends with a Forth `;`, put a space before the separator, as in `then ; ;;` above. Written as `then ;;;`, the first two semicolons are taken as the separator and the definition loses its closing `;`.

{{< alert context="info" text="SCRIPT is <strong>unsigned</strong> and meant for development. Signed role bundles are the trusted path; persisted bundles re-apply at boot <em>before</em> the script runs, so a script can build on bundle-defined words." />}}

## Signed role bundles

Hanasu installs the same signed **role bundles** as the Hive AI nodes, through the shared `craw_role_bundle` component (`firmware-idf/components/craw_role_bundle`, a symlink into `MagNET_M5DialFiddlerCrab`). The envelope format, canonical signing input and install pipeline are documented on the [Signed Role Bundles](/docs/hive-ai/role-bundles/) page. This section covers what is specific to Hanasu.

### BUNDLE verbs

There is no hive KV store on a Thread mesh, so bundles arrive point-to-point over HCP. The host sends the envelope JSON in pieces:

| HCP | Effect |
|---|---|
| `BUNDLE BEGIN` | Start a new envelope buffer |
| `BUNDLE ADD <chunk>` | Append a piece of the envelope (total up to 6144 bytes) |
| `BUNDLE COMMIT` | Verify, install and persist. Answers `+OK <name> v<version> installed`, or `-ERR E_BUNDLE rc=<n> field=<field> at=<detail>` |
| `BUNDLE LIST` | Print `# bundle <name> v<version>` for each persisted bundle |
| `BUNDLE STOP` | Stop the active role |
| `BUNDLE CLEAR` | Stop the active role and forget all persisted bundles |

Install details from the component code:

- **Signatures.** The trust store accepts both `hmac-sha256` and `ed25519` for the dev author `iotone-dev`, matched on (author, algorithm). Production deployments should carry only Ed25519 entries, since the HMAC secret proves hive membership, not authorship.
- **Capabilities.** A Hanasu C6 node advertises `thread`, `chat` and `gpio`; a bundle whose `caps_req` is not covered is refused with `BUNDLE_ERR_CAPS`.
- **Atomic eval.** The source is evaluated a line at a time behind a dictionary savepoint. On the first failing line the dictionary rolls back, and `E_BUNDLE … at=` reports that line. No partial definitions survive.
- **Role lifecycle.** A bundle may define `role-init`, `role-tick`, `role-stop` and `role-status`. `role-init` runs once at install, and if it fails the whole bundle rolls back. If `role-tick` exists, the component calls it every `tick_ms` (envelope field, default 1000, clamped to 100–60000) from its own task. A new install stops the current role first; one ticking role runs per node.
- **Persistence.** The envelope is saved to NVS (namespace `role_bundle`, keys `n:<name>` and `b:<name>`). Version upgrades must be monotonic.

### Re-apply at boot

The boot order in `firmware-idf/src/main.c` is: Forth heap, NVS, core, vocabulary, **persisted bundles re-applied**, boot script, host link, radios. A bundle that fails to re-apply counts against [OTA](/docs/hanasu/ota/) health, so a trial image that breaks a saved bundle is not confirmed. An image flagged `CLEARS_BUNDLES` holds saved bundles back during its trial boot and forgets them when it is confirmed.

### bundle_push.py

`tools/bundle_push.py` wraps the verb sequence:

```bash
python3 tools/bundle_push.py /dev/cu.usbmodemXXXX bundle.json --list
```

It minifies the JSON, sends `BUNDLE BEGIN`, then `BUNDLE ADD` in 200-byte pieces, then `BUNDLE COMMIT` (and `BUNDLE LIST` with `--list`), and prints each response and any role output that follows. It works for both the ESP32-C6 build and the [XIAO MG24 Zephyr](/docs/hanasu/mg24-zephyr/) build. Sign bundles with `scripts/sign_bundle.py` in `MagNET_M5DialFiddlerCrab` (`--alg hmac-sha256` or `--alg ed25519`).

Broadcasting one bundle to the whole mesh in a single commit is future work; today each node is updated individually.

## Bot mode

Bot mode arms one auto-responder that answers inbound chat by itself. It is a **test mode** for proof of life: a node that replies shows in one line that it is awake, attached, holding the right channel key, and able to transmit. Spec: `docs/BOT-MODE.md`; code: `magnet_bot.c`.

It is compiled only with `MN_ENABLE_BOTS=1`, which only the `esp32c6_ble_resident_bots` PlatformIO environment sets. That keeps the validated builds identical to what was soaked. Other builds answer `BOTMODE` with `-ERR E_UNSUPPORTED`.

| Intent | Forth | HCP |
|---|---|---|
| List bots | `botmode` | `BOTMODE` |
| Arm bot 0 | `0 botmode` | `BOTMODE 0` |
| Turn off | `-1 botmode` | `BOTMODE OFF` |

| Id | Name | Status |
|---|---|---|
| 0 | `proofoflife` | Replies `Hey <id>, it's <time>.` |
| 1 | `eliza` | Reserved, not built. Selecting it returns `E_NO_BOT` |

`botmode` is a colon definition (`: botmode depth 0> if mn-bot! else mn-bots then ;`) rather than a primitive, because an FFI word cannot tell an empty stack from a pushed 0. A bare `botmode` will consume any leftover stack item, so check with `.s` if unsure. Bot mode is **not persisted**: after a power cycle the node is silent again.

### Loop guards

A responder that answers every chat would volley forever with another one. Four independent guards prevent that:

1. **`MN_F_AUTOMATED`** (envelope flag bit 6). Bot replies are marked, and bots never answer a marked frame. Older firmware ignores the bit.
2. **Never answer ourselves.**
3. **Per-peer cooldown** of 30 s.
4. **Global budget** of 6 replies per minute, with a one-time `!WARN bot-budget-exhausted`.

Guards 2–4 exist because guard 1 trusts the sender. Replies also pay the normal host rate limit. On the bench (2026-08-04), two armed bots each answered one stimulus once and never answered each other. The global budget has not been driven to exhaustion on hardware.

## Nekobot

**Nekobot** is a cat chatbot that drives one Hanasu node from the host, written in Pop-11 (`tools/catbot.p`, spec `docs/NEKOBOT.md`). It is **implemented and validated**, but it is a host program, not firmware: it needs no special build and is separate from `MN_ENABLE_BOTS`.

- **Purpose.** It adds organic, irregular chat traffic to soak testing, alongside the mechanical traffic from `tools/soak.py`.
- **Design.** A small template model (intent, mood, reply tables) feeds a "catify" text DSL that caps every message at 30 characters. That keeps each frame in the 62-byte single-frame class, the only multicast class measured lossless. Host-side throttles mirror the firmware bot's: a 20 s minimum gap, a 45 s per-sender cooldown, and 6 sends per minute.
- **Validation.** On 2026-08-15 a 5-minute proof session and a run of about 6 hours alongside a 6-hour gated soak, which passed (668/668 delivery). Version 2 (`tools/catbot_run.sh`, over the `tools/chat-bench/` bridge) adds LED moods on `MN_ENABLE_LED` builds and Type 6 photo turns; its 2026-08-16 reference run lasted 4 h 50 m with 888/888 deliveries.
- **Still future work** per the spec: a second persona so long runs become dialogues, and refreshing peer names after mid-run reboots.
