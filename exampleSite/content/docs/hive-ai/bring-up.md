---
weight: 120
title: "Bench Bring-Up & Verification"
description: "A sequential walkthrough to flash, provision, and verify a multi-node hive on the bench — including the lineage gate and the Redis sidecar."
icon: "rocket_launch"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "testing", "bring-up"]
---

This is a reader-facing adaptation of the project's bench test plan for the **`0.5.0-spore`** rev. Run it top to bottom; every step lists what to **do**, what to **expect**, and what a deviation means — so the first failure is itself the diagnostic.

## Prerequisites

- **On the bench:** a Dial (ruler), at least one peer (Echo / Matrix / C3U), a Capsule (Redis variant), optionally a Camera.
- **One 2.4 GHz SSID** for everything, with mDNS unblocked. On macOS, *System Settings → Privacy → Local Network* must allow Terminal/Python.
- **Laptop tools:** `redis-cli` (`brew install redis`), `nc`, Python 3.11+ for `scripts/fake_ruler.py`.
- **Two terminals:** one `pio device monitor` on the device under inspection, one for laptop scripts.

## 1. Flash everything (ruler first)

Flash the **ruler first** so a newer ruler can recognize older nodes during a transition (see the [compatibility matrix](/docs/hive-ai/generations-lineage/#compatibility-matrix)).

```bash
cd M5StackDial-m5gfx-demo-ESPIDFORTH  && pio run -t upload
cd ../M5Capsule_Hive_Scribe_Redis     && pio run -t upload
cd ../M5Atom_Echo_Hex_Hive_Test       && pio run -t upload
cd ../M5_Hive_Camera                  && pio run -t upload   # optional
```

**Expected** on each boot banner: `MagNET gen 0.5.0-spore`.

{{< alert context="warning" text="If a node crashes with <code>BLE_INIT: hci inits failed</code> then a <code>Guru Meditation</code> in <code>ble_host_task</code>: internal SRAM was exhausted before NimBLE could allocate HCI buffers. Read the <code>DRAM budget pre-NimBLE</code> log line first — if free is below ~50&nbsp;KB the fix is to free DRAM, not to erase NVS." />}}

DRAM-recovery knobs, in order of how much each frees:

1. Reduce the Forth heap (`forth_init(N * 1024)` in the Dial `main.cpp`) — currently 48 KB; each 1 KB cut frees 1 KB.
2. Reduce `KV_TABLE_SIZE` in `craw_hive_ruler.c` (~3 KB/entry).
3. Reduce `CRAW_HIVE_KV_VALUE_MAX` in `craw_hive.h`.
4. Set `CONFIG_BT_NIMBLE_MAX_CONNECTIONS=1` if provisioning is one-at-a-time.

## 2. Baseline hive — no gating

Provision WiFi on each device over BLE (nRF Connect → connect → write SSID + password → commit), then on the Dial run `ruler-status`:

```
ruler:   MagNET-ruler-XXXX
hive:    beehive-1
gen:     0.5.0-spore
gate:    lineage-auth=off
peers:   2
  [0] MagNET-biologic-aaaa  spawn   0.5.0-spore   12s ago
  [1] MagNET-biologic-bbbb  scribe  0.5.0-spore   8s ago
```

Every peer showing `0.5.0-spore` confirms the Layer 1 gen round-trip.

**If it fails:** a peer showing `(no-gen)` wasn't reflashed with gen-aware firmware. No peers at all → check WiFi, confirm `prov-status` shows a real IP, and check the macOS firewall / Local Network permission.

## 3. Verify the lineage gate (positive path)

On the Dial:

```
1 lineage-auth
ruler-status        → gate: lineage-auth=ON
```

Power-cycle a peer. **Expected** on the Dial:

```
craw_hive_ruler: tx CHALLENGE to MagNET-biologic-XXXX lineage=spore
craw_hive_ruler: lineage auth OK MagNET-biologic-XXXX lineage=spore
craw_hive_ruler: WELCOME node=... gen=0.5.0-spore
```

The peer rejoins within ~2 s. **If it loops on `BACKOFF (lineage_auth)`:** the `MAGNET_LINEAGES[]` key bytes weren't identical at compile time on both sides. Clean up with `0 lineage-auth`.

## 4. Verify the gate (negative path)

You can't easily flash a "wrong lineage" (every project pulls the same key table), so use the laptop ruler with the spore key disabled:

```bash
cd scripts
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python fake_ruler.py --require-lineage-auth     # power the Dial off first
```

Confirm a CHALLENGE/RESPONSE round-trip, then stop the script, comment out the spore entry in its `LINEAGE_KEYS`, restart, and power-cycle a peer.

**Expected:** `REJECT (lineage_unknown lineage='spore')` on the ruler; `state=4 (lineage-unknown)` on the peer. Restore the entry and power the Dial back on afterward.

## 5. Bring up the Redis sidecar

On the Capsule: confirm `hive-status` shows JOINED, then:

```
redis-on
redis-status
```

```
[redis] up on 0.0.0.0:6379
[WARN] exposed on LAN, no encryption
running:   yes
profile:   lan
bind:      0.0.0.0
port:      6379
```

Note the Capsule IP from `prov-status`. From the laptop:

```bash
redis-cli -h <capsule-ip> ping            # → PONG
redis-cli -h <capsule-ip> SET foo bar      # → OK
redis-cli -h <capsule-ip> GET foo          # → "bar"
redis-cli -h <capsule-ip> LPUSH log a b c  # → (integer) 3
redis-cli -h <capsule-ip> LRANGE log 0 -1  # → "c" "b" "a"
redis-cli -h <capsule-ip> INFO server      # → redis_version:0.5.0-spore
```

**Persistence:** power-cycle the Capsule, `redis-on`, then `GET foo` should still return `bar`.

**Dial dot:** while Redis is up, an **orange** dot lights on the Dial (outboard of the purple MQTT-bridge dot) and tracks `redis-on`/`redis-off`.

## What "all green" looks like

- Every boot banner shows `MagNET gen 0.5.0-spore`.
- `ruler-status` lists every peer with a populated gen column.
- One CHALLENGE/RESPONSE round-trip logs on each side when `lineage-auth` is on.
- `redis-cli` round-trips strings and lists; `INFO` reports `redis_version:0.5.0-spore`.
- The orange Redis dot on the Dial tracks the sidecar state.
- Power-cycling the Capsule and running `redis-on` returns previously-set keys.

{{< alert context="info" text="This walkthrough tracks the firmware test plan and is kept in sync with each gen-impacting rev. If your hardware reports a different <code>MAGNET_GEN_STR</code>, expect the steps to have moved — follow the test plan shipped with that rev." />}}
