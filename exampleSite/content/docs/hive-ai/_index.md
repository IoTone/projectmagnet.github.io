---
weight: 10
title: "Hive AI"
description: "A swarm of tiny ESP32 'biologics' that self-organize under a ruler, hot-swap roles over the air, and share memory — built on an embedded Forth."
icon: "hub"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "overview"]
---

**Hive AI** is the MagNET reference design for distributed edge intelligence on tiny hardware. A handful of ESP32-class boards — a knob with a screen, a camera, a battery-powered capsule, a speaker — power on knowing almost nothing, find each other on the local network, prove they belong, and self-organize into a working *hive* governed by a *ruler*. Once joined, a node can be handed a new **role** at runtime — a small program delivered, verified, and executed without reflashing — and can read and write a shared, hive-wide memory as if it were local.

The metaphor is biological, and the acronym is **DBOTS** — *Digital Biologic self-Organized Telepathic Sentients*:

| Letter | Stands for | What it means here |
|---|---|---|
| **D** | Digital | They run on modern RISC microcontrollers (ESP32 / -S3 / -C3 / -C6). |
| **B** | Biologic | Their behavior is code that can self-replicate and self-modify — roles are downloaded, validated, and executed. |
| **O** | Organized | They operate under a strict hierarchy and rule set — a ruler and well-defined roles. |
| **T** | Telepathic | They read each other's "minds" through shared memory and peer messaging. |
| **S** | Sentients | They act toward goals without operator intervention. |

In the demo, the "ruler" is partly software (an [M5Stack Dial](/docs/hive-ai/devices/) running the ruler firmware) and partly the human running the demo, who has physical control of the nodes.

## What's real today

{{< alert context="info" text="Current firmware generation: <strong>0.5.0-spore</strong>. Milestones A (BLE provisioning) and B (ruler discovery + HMAC join) are complete; Milestone C (signed role bundles) is through step 4. A three-chip, three-role hive was validated on the bench on 2026-04-25." />}}

This is a **research and demo prototype**. It is LAN-scoped, uses a development pre-shared secret, and is explicitly *not* hardened for hostile production environments — see the [protocol threat model](/docs/hive-ai/hive-protocol/#threat-model-v1) for what it does and does not defend against.

## Where to go next

**Read in order to understand the system:**

1. [Concepts & Vocabulary](/docs/hive-ai/concepts/) — the biology→engineering mapping and the core terms.
2. [Architecture & Topology](/docs/hive-ai/architecture/) — how the pieces fit and the load-bearing bring-up order.
3. [The 12 Roles](/docs/hive-ai/roles/) — the jobs a node can hold.

**Specifications (reference):**

- [Hive Protocol v1](/docs/hive-ai/hive-protocol/) — discovery, transport, authentication, message types.
- [Generations & the Lineage Gate](/docs/hive-ai/generations-lineage/) — versioning and the "you are not one of us" puzzle.
- [Signed Role Bundles](/docs/hive-ai/role-bundles/) — how the hive teaches nodes new behavior.

**Hands-on:**

- [The Cast: Devices & Boards](/docs/hive-ai/devices/)
- [Controlling the Hive from Forth](/docs/hive-ai/forth-words/)
- [Scribe & the Redis Sidecar](/docs/hive-ai/scribe-redis/) · [Boombox: Audio Notifications](/docs/hive-ai/boombox-audio/)
- [Bench Bring-Up & Verification](/docs/hive-ai/bring-up/)
