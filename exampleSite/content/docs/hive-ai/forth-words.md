---
weight: 90
title: "Controlling the Hive from Forth"
description: "The ESPIDFORTH REPL vocabulary that drives the hive — display, provisioning, ruler, shared memory, lineage, and audio words."
icon: "terminal"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "forth", "repl"]
---

Every MagNET node runs an **ESPIDFORTH** interpreter with a serial REPL. Hardware features and hive operations are exposed as Forth words — so you can drive a node live over USB serial, and bundle authors get the same vocabulary to compose new roles. Stack effects use the standard `( before -- after )` notation.

{{< alert context="warning" text="ESPIDFORTH (the E4TH dialect) is <strong>lowercase and case-sensitive</strong> — use <code>do</code>/<code>loop</code>/<code>if</code>, not their uppercase forms, or words silently fail to parse. Also call <code>forth_init()</code> before NimBLE/WiFi/httpd, or the dictionary heap starves." />}}

## Display & app words (Dial)

| Word | Effect | Notes |
|---|---|---|
| `theme` | `( n -- )` | Switch display theme (6 available) |
| `brightness` | `( n -- )` | Set backlight |
| `ping` | `( -- )` | Ripple animation |
| `starburst` | `( -- )` | Starburst animation |
| `invert` | `( -- )` | Invert display colors |
| `mute` | `( -- )` | Toggle the buzzer |
| `appbeep` | `( -- )` | Beep via the LEDC buzzer |
| `appsleep` | `( -- )` | Sleep display until touch/encoder |
| `appshowmem` | `( -- )` | Dump memory state to the display |
| `appdevinfo` | `( -- )` | Dump CPU / device info to the display |

## Provisioning words (every node)

| Word | Effect |
|---|---|
| `prov-status` | Print BLE + WiFi + IP + hostname + hive state |
| `prov-reset` | Clear stored WiFi credentials and reboot into BLE provisioning |

```
boombox> prov-status
ble:    MagNET-biologic-XXXX
wifi:   connected
ip:     192.168.1.42
time:   synced
host:   magnet-boombox-XXXX.local
hive:   joined
```

## Ruler words (Dial)

| Word | Effect |
|---|---|
| `ruler-status` | Print ruler id, hive id, gen, gate state, and the peer table |
| `grant-role` | Send a `ROLE_GRANT` to a connected peer |
| `lineage-auth` | `( n -- )` — `1` enables the [lineage gate](/docs/hive-ai/generations-lineage/), `0` disables it (no reflash) |

```
ruler:   MagNET-ruler-XXXX
hive:    beehive-1
gen:     0.5.0-spore
gate:    lineage-auth=off
peers:   2
  [0] MagNET-biologic-aaaa  spawn   0.5.0-spore   12s ago
  [1] MagNET-biologic-bbbb  scribe  0.5.0-spore   8s ago
```

## Shared-memory (KV) words

| Word | Effect |
|---|---|
| `kv-set` | Write a key/value to the ruler's shared-memory table |
| `kv-get` | Read a key from shared memory (blocks up to ~3 s) |
| `kv-list` | List keys (Dial) |
| `kv-put` | Write (node side; fire-and-forget, no ACK) |

Because shared memory is the hive's universal substrate, KV words double as a remote-control channel. For example, writing a Forth phrase to the Boombox's command key triggers a sound on it from across the room:

```forth
s" siren" s" boombox:cmd" kv-set       \ play siren on the boombox
s" 1500 100 tone" s" boombox:cmd" kv-set    \ freeform Forth
```

## Audio words (Boombox)

The full audio vocabulary — primitives (`tone`, `sweep`, `am`, `sleep`), canned recipes (`alert`, `notify`, `warn`, `error`), the siren family (`siren`, `yelp`, `nee-naw`, `air-raid`), the `sunrise` boot sound, and volume/amp control (`vol`, `audio-on`, `audio-off`, `audio-stop`, `audio-status`) — is documented in detail on the [Boombox page](/docs/hive-ai/boombox-audio/).

## Redis-sidecar words (Capsule Redis variant)

`redis-on` / `redis-off`, `redis-status`, `redis-profile` / `redis-profile!`, `redis-bind` / `redis-port`, `redis-flush`, and the on-device `redis-do` client are covered on the [Scribe & Redis page](/docs/hive-ai/scribe-redis/). The same project also exposes `imu-on` / `imu-off` / `imu-status` / `imu-zero` / `imu-scan` for the BMI270 service.

## Defining new words

The REPL is a full Forth, so you can define words live and — once happy — ship them as a [role bundle](/docs/hive-ai/role-bundles/):

```forth
: dot   800 60  tone  60 sleep ;
: dash  800 180 tone  60 sleep ;
: sos   dot dot dot  100 sleep  dash dash dash  100 sleep  dot dot dot ;
sos
```

Wrapped in a signed bundle and installed via `ROLE_GRANT`, `sos` becomes a permanent word that survives reboots via the bundle's NVS persistence.
