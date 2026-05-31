---
weight: 100
title: "Scribe & the Redis Sidecar"
description: "The Scribe role's NVS-backed key-value store, and the RESP2-compatible Redis server that exposes it to any standard client."
icon: "database"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "scribe", "redis", "storage"]
---

The **Scribe** (Role 4) is the hive's memory keeper — *"its only job is to save data to its internal memory and recall it from shared memory if asked."* It runs on the M5Capsule, whose 8 MB flash and oversized 64 KB NVS partition make it the natural store for hive shared memory and [role bundles](/docs/hive-ai/role-bundles/).

The **Redis variant** (`M5Capsule_Hive_Scribe_Redis`) keeps every Scribe behavior and adds a **RESP2-compatible TCP server** so a laptop `redis-cli` — or any Redis client library — can read and write the same NVS-backed store the Scribe already manages.

{{< alert context="info" text="Both the Redis server and the BMI270 IMU service on this board are <strong>sidecars</strong>, off by default at boot. Bring them up explicitly with <code>redis-on</code> / <code>imu-on</code>. Every existing scribe behavior — BLE provisioning, hive join, role-bundle install, MQTT bridge — keeps working alongside them." />}}

## Why Redis on a microcontroller

The hive already has a key-value substrate (`KV_GET`/`KV_PUT`), but it only speaks the MagNET wire protocol. Wrapping the same store in RESP2 means **standard tooling just works**: `redis-cli`, client libraries, dashboards. It turns the Scribe into something a laptop or another service can inspect and script without learning the hive protocol.

## Wire format

RESP2. Both inline (`PING\r\n`) and array (`*1\r\n$4\r\nPING\r\n`) forms are accepted, so telnet and standard clients are equally happy. Frames cap at 16 KB; up to 4 concurrent clients (per-client task pattern, mirroring the hive ruler).

## Commands implemented

```
PING [msg]      ECHO msg        QUIT            SELECT 0
AUTH pw (stub)  CLIENT ...       COMMAND [...]   INFO [section]
SET k v         GET k           DEL k [k...]    EXISTS k [k...]
TYPE k          KEYS pat        DBSIZE          FLUSHDB / FLUSHALL
LPUSH k v...    RPUSH k v...     LPOP k          RPOP k
LLEN k          LINDEX k idx     LRANGE k a b    (negative idx ok)
```

Unknown commands return `-ERR unknown command 'X'`. A list command on a string key (or vice versa) returns `-WRONGTYPE`.

## Storage limits (NVS backend, v1)

| Limit | Value |
|---|---|
| User key length | 14 chars |
| String value | 1024 bytes |
| List total per key | 4 KB |
| List entries per key | 64 |
| List entry length | 1024 bytes |
| Concurrent clients | 4 |

A future SD-FAT backend lifts each of these by roughly 1000×.

## Configuration profiles

```
0 redis-profile!   →  local    bind=127.0.0.1   port=6379
1 redis-profile!   →  lan      bind=0.0.0.0     port=6379   (default)
2 redis-profile!   →  quiet    bind=0.0.0.0     port=16379
3 redis-profile!   →  custom   (preserved across reboots)
```

`redis-bind <addr>` and `N redis-port` switch the active profile to `custom` automatically. Profiles and overrides persist in NVS namespace `scribe_redis`.

## Forth surface

| Word | Effect |
|---|---|
| `redis-on` | Start the listener on the active config |
| `redis-off` | Stop, close clients, clear `redis:status` |
| `redis-status` | State + bind/port + clients + command counter |
| `redis-profile` | Print active profile |
| `N redis-profile!` | Apply preset 0–3 and persist |
| `redis-bind` | Prompt for bind addr (→ custom) |
| `N redis-port` | Set port (→ custom) |
| `redis-flush` | FLUSHDB the local store |
| `redis-do` | On-device client — prompt for a command, send to localhost, print reply |

## Built-in client — `redis-do`

`redis-do` connects to `127.0.0.1:<active-port>` from the Capsule itself, so you can verify the loopback path without a laptop:

```
redis> SET foo bar
+OK
redis> LPUSH log first second
(integer) 2
redis> LRANGE log 0 -1
1) "second"
2) "first"
```

## Hive integration — the Dial indicator dot

While the server is up and the Scribe is joined, a 5 s heartbeat publishes `redis:status = <self-id>:<port>:<clients>` to the hive KV table. The Dial reads that key and lights a small **orange** dot (next to the purple MQTT-bridge dot), so you can confirm the server is reachable from across the room. The dot goes dark when `redis-off` clears the value.

## Security model — v1

{{< alert context="warning" text="Cleartext TCP, dev-only. The default <code>lan</code> profile binds <code>0.0.0.0</code>. Every start logs <code>[WARN] exposed on LAN, no encryption</code>. <code>AUTH</code> is parsed and answered <code>+OK</code> so <code>redis-cli -a</code> doesn't error, but the password is <strong>not</strong> checked. Real auth lands in v2." />}}

## The IMU sidecar

The Redis-variant Capsule also carries a Bosch **BMI270** 6-DoF IMU on the internal I2C bus (SDA = G8, SCL = G40, addr `0x69`). The `craw_imu` component samples at 50 Hz, runs a 6-DoF Madgwick AHRS, and serves fused orientation + raw accel/gyro at `GET /api/v1/sensor/imu` — the real-hardware swap for a simulated stream in the d3-spatial "airplane" dataspace.

{{< alert context="warning" text="No magnetometer means no true north — yaw is integrated from the gyro and drifts ~1–2°/min. <code>imu-zero</code> snaps the current heading as the 0 datum (the user-controlled equivalent of magnetic-north calibration)." />}}

{{< alert context="info" text="The BMI270 driver is <strong>vendored, not managed</strong>: the registry component's transitive <code>i2c_bus</code> dependency needs an ESP-IDF v5.4 API (<code>i2c_master_get_bus_handle</code>) that the pinned <code>espressif32@6.9.0</code> (IDF v5.3.1) doesn't have. Vendoring the v5.3-compatible driver sidesteps the v5.4 efuse build collision entirely." />}}

## Related work

The on-device RESP2 server design references the **ESP32RedisClient** project — [github.com/DankJugal/ESP32RedisClient](https://github.com/DankJugal/ESP32RedisClient) — as prior art for speaking Redis to/from ESP32-class hardware. MagNET's twist is the *server* side, backed by NVS and bridged into the hive's shared-memory model.
