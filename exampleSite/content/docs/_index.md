---
weight: 1
title: "Project MagNET"
description: "An open, local-first platform for IoT data and hyperlocal, hive-centric AI."
icon: "menu_book"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
---

**Project MagNET** is an open-source effort to capture, sync, and act on IoT data **locally first** — without surrendering it to proprietary clouds. It pairs a cross-platform app and data-sink services with a growing fleet of reference-design firmware, and explores a distinctive idea: **hyperlocal, hive-centric AI**, where ordinary edge devices self-organize and share intelligence like cells in a nervous system.

## The idea

The goal is to let people — and companies — control how their IoT data is captured, stored, and used, and to define their own security posture. An open server stack makes it easy to keep data on your own subnet, or in a cloud you choose.

On top of that data substrate, MagNET investigates **distributed edge intelligence**: every device has *some* intelligence, storage, contextual awareness, and goals, but no device needs to be a brain on its own. Each can act as a cell, neuron, or synapse in a larger swarm.

## Pillars

- **Local-first** — data lives where you are; sync is opportunistic and under your control.
- **Hyperlocal context** — awareness scoped to *here and now*: locations, sightings, and nearby-compute offloading.
- **Hive-centric AI** — devices form a hive, take on roles, and share memory. See the [Hive AI](/docs/hive-ai/) section.
- **Every device a cloud of services** — discoverable over BLE or Wi-Fi; detect → connect → provision → control → collect.
- **You own your data & security** — secure transport and verified sessions, on by default.
- **Open & interoperable** — zeroconf/Bonjour, Thread, Zigbee, LoRa/Meshtastic, and open APIs.

## Sections

### 🐝 [Hive AI](/docs/hive-ai/)

The flagship reference design: a swarm of ESP32-class "biologic" nodes that discover a **ruler**, prove their lineage to join, hot-swap **roles** delivered as signed Forth bundles, and share memory across the hive. The most fully documented part of the project today.

### 🗺️ [Roadmap](/docs/roadmap/)

A themed view of where the project is headed, distilled from the public issue tracker — specs and architecture, the app, discovery and provisioning, data sink and sync, networking and mesh, spatial/WebXR, and hardware.

## Repository layout

| Path | What it is |
|---|---|
| `magnet_app/` | Cross-platform app (Flutter) — scanning, provisioning, and data views |
| `datasync-proto/` | Rust prototype of the data-sync framework / data sink |
| `reference-designs/` | Firmware for ESP32 / -S3 / -C3 / -C6 and nRF52 boards, including the Hive AI prototype |
| `specs/` | Design specs — Unified Device Model, device self-registration, and more |
| `tools/` | Repo utilities |

{{< alert context="info" text="This documentation is being actively built out. The <a href=\"/docs/hive-ai/\">Hive AI</a> section is complete; other areas are migrating from design notes and the issue tracker into full docs over time." />}}
