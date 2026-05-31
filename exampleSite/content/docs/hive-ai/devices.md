---
weight: 80
title: "The Cast: Devices & Boards"
description: "The physical hardware that makes up a MagNET hive — what each board is, its chip, and the role it plays."
icon: "developer_board"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "hardware", "devices"]
---

Each node type is a separate PlatformIO project assembled from the [shared component stack](/docs/hive-ai/architecture/#the-shared-component-stack). All join the hive through the same protocol; they differ in hardware and the role-specific work they do.

## The ruler — M5Stack Dial

| | |
|---|---|
| Project | `M5StackDial-m5gfx-demo-ESPIDFORTH` |
| MCU | ESP32-S3 (no PSRAM) |
| Distinguishing hardware | 1.28" round touch LCD, rotary encoder, LEDC buzzer |
| Role | **Ruler** (Role 1) |

The Dial runs the ruler firmware: it advertises `_magnet-ruler._tcp` over mDNS, maintains up to 8 peer sessions (one FreeRTOS task per client), and shows BLE / WiFi / hive status plus a live peer count as colored dots on the round display. A serial REPL exposes `ruler-status`, `grant-role`, `lineage-auth`, and the KV words. It began life as the Pharkie m5gfx playground, reimplemented atop ESP-IDF + ESPIDFORTH.

{{< alert context="warning" text="DRAM on the no-PSRAM S3 is razor-thin (~320&nbsp;KB SRAM, shared by Forth heap, the KV table, WiFi, and the BLE HCI). New BSS or a larger Forth heap can silently break BLE init with <code>hci inits failed</code>. The bring-up page lists the recovery knobs." />}}

## The spawn — M5Atom Echo + Unit Hex

| | |
|---|---|
| Project | `M5Atom_Echo_Hex_Hive_Test` |
| MCU | ESP32-PICO-D4 (classic dual-core LX6) |
| Distinguishing hardware | 37 × SK6812 hex LED panel, NS4168 I2S speaker, button |
| Role | **Spawn** (Role 10) |

The first node with both visual status (the hex panel) and audible feedback (I2S chirps on state transitions). It was the bring-up target for BLE provisioning and hive join, and is the canonical "minimal node" reference.

## The eye / spy — Hive Camera

| | |
|---|---|
| Project | `M5_Hive_Camera` (two envs) |
| MCU | ESP32 classic (AI-Thinker ESP32-CAM) **or** ESP32-S3 (M5Stack Unit CamS3) |
| Distinguishing hardware | OV2640 camera + PSRAM frame buffer |
| Role | **Eye / Spy** (Roles 11 / 7) |

Preserves the stock ESP32-CameraWebServer HTTP behavior (`/stream`, `/capture`, `/control`, `/status`) on top of hive bring-up — one source tree, two PlatformIO envs, one shared `craw_camera` component with per-board pin maps.

{{< alert context="info" text="On classic ESP32 the camera DMA and BT controller contend for internal RAM, so the camera must initialize <em>after</em> BLE is fully torn down — the same teardown step the bring-up sequence already requires." />}}

## The scribe — M5Capsule

| | |
|---|---|
| Projects | `M5Capsule_Hive_Scribe` and `M5Capsule_Hive_Scribe_Redis` |
| MCU | ESP32-S3FN8 (8 MB flash, no PSRAM, 250 mAh LiPo) |
| Distinguishing hardware | 64 KB NVS partition, BMI270 IMU, BM8563 RTC, microSD, buzzer |
| Role | **Scribe** (Role 4) |

Battery-powered persistent KV store — the natural home for hive shared memory and bundle storage. The **Redis variant** adds a RESP2-compatible TCP server (any `redis-cli` can read/write the same NVS store) plus a BMI270 IMU HTTP service. Both surfaces are off by default. See [Scribe & the Redis Sidecar](/docs/hive-ai/scribe-redis/).

## The boombox — Seeed ReSpeaker Lite

| | |
|---|---|
| Project | `MagNET_ReSpeaker_Boombox` |
| MCU | XIAO ESP32-S3 socketed on the ReSpeaker Lite Voice Kit |
| Distinguishing hardware | TLV320AIC3204 codec + XMOS XU316 router, I2S audio |
| Role | **Boombox** (Role 12) |

A software-synth audio node: a sine-LUT engine over I2S (ESP32 as I2S *slave*; the XU316 supplies the clocks) plays multi-segment patterns with gain envelopes. Built-in `alert` / `notify` / `warn` / `error` / siren recipes, composable `tone` / `sweep` / `am` primitives, and a remote-trigger channel via a shared-memory key. See [Boombox: Audio Notifications](/docs/hive-ai/boombox-audio/).

## The vitals node — MagNET Vitals

| | |
|---|---|
| Project | `MagNET_Vitals_E4TH` |
| MCU | XIAO ESP32-C6 |
| Distinguishing hardware | MR60BHA2 60 GHz mmWave radar (heart/breathing/presence), BH1750 lux, WS2812 |
| Role | Personal-scale sensor node |

A health/presence dataspace device serving radar vitals over HTTP. Its WS2812 status LED uses semantic modes — including a rapid yellow blink (4 Hz) that preempts the display whenever WiFi is offline or all join attempts fail, so a network problem is unmistakable at a glance.

## The dev harness — fake_ruler.py

Not hardware: `scripts/fake_ruler.py` is a laptop script that speaks the full protocol — useful for isolating node-side bugs when no real ruler is flashed, and the only practical way to test the lineage gate's *negative* path (a deliberately wrong lineage key). It mirrors the firmware's `magnet_lineages.c` key table.

## Cross-board gotchas worth knowing

- **DRAM budget on no-PSRAM S3** — the Dial and Capsule are tight; watch the pre-NimBLE budget log.
- **ESP-IDF v5.4 efuse build collision** — every project pins `espressif32@6.9.0` (IDF v5.3.1). Building the Capsule Redis variant with the BMI270 *managed* component silently upgrades framework-espidf to v5.4 and breaks the next build; the project vendors the BMI270 driver to avoid this. (Both issues are documented in the reference-design repo's `docs/` and the project memory.)
