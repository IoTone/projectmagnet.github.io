---
weight: 20
title: "Concepts & Vocabulary"
description: "The biology metaphor, the engineering reality it maps to, and the words used throughout the Hive AI docs."
icon: "biotech"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "concepts"]
---

The Hive AI design borrows its structure from social insects: a colony with a ruler, members that take on specialized roles, and a kind of shared awareness across the group. Every metaphor maps cleanly onto an engineering construct. This page defines both sides so the rest of the documentation can use the shorthand.

## The metaphor → the machinery

| Biology | In the hive | Engineering reality |
|---|---|---|
| **Hive / colony** | One MagNET deployment on a LAN | A set of nodes sharing a `hive_id` and a pre-shared secret |
| **Ruler / queen** | The coordinator | A device running the **ruler** firmware: advertises itself, accepts joins, holds the peer table and shared-memory store |
| **Biologic** | A hive member | A node running updatable Forth code over ESP-IDF |
| **Spawn** | A newborn with no job | A freshly joined node holding the default `spawn` role until promoted |
| **Role** | A member's specialization | A named behavior (worker, scribe, spy, …), delivered as a signed Forth **role bundle** |
| **DNA** | What proves family | A per-lineage secret key baked into firmware, used by the [lineage gate](/docs/hive-ai/generations-lineage/) |
| **Hive mind** | Shared awareness | A hive-wide key-value store queried transparently, regardless of where a value physically lives |
| **Telepathy** | Mind-to-mind | Peer messaging and shared-memory reads over the hive session |

## Core terms

**Node / biologic** — any participating device. It has a stable identity derived from its WiFi MAC: `MagNET-biologic-<MAC4>`.

**Ruler** — the single coordinator a node talks to at a time. Identity `MagNET-ruler-<MAC4>`. It advertises over mDNS, authenticates joiners, tracks live peers, and answers shared-memory requests. If no ruler exists, the design allows any node to request nomination (planned).

**Hive id** — a short slug (e.g. `beehive-1`) that lets multiple independent hives coexist on one LAN. A node ignores a ruler advertising a different hive id.

**Role** — the runtime function a node performs. See [The 12 Roles](/docs/hive-ai/roles/). A node's role can change at runtime via a `ROLE_GRANT`.

**Role bundle** — a signed JSON envelope carrying Forth source code that implements a role. The node verifies the signature, decodes, and executes it — teaching the node new behavior without a reflash. See [Signed Role Bundles](/docs/hive-ai/role-bundles/).

**Shared memory (hive mind)** — a key-value substrate exposed over the hive session (`KV_GET` / `KV_PUT`). A node doesn't need to know whether a value is held locally, on the ruler, or on a [Scribe](/docs/hive-ai/scribe-redis/) — only how fresh its cache is. This is the project's nod to **Named Data Networking** / Content-Centric Networking, where data is addressed by name rather than host.

**Shared secret** — a 32-byte key every member of a hive holds. It authenticates every message on the wire (HMAC) so a stranger cannot impersonate a node or the ruler. Distinct from a DNA key.

**DNA key (lineage key)** — a separate 32-byte secret tied to a firmware **lineage**. It proves a node descends from the same firmware family, gating membership independently of wire authentication.

## The three version axes

A single biologic carries **three orthogonal version concepts**. Conflating them causes grief whenever one of them moves, so MagNET keeps them strictly separate:

| Axis | Answers | Bumps when | Seen by peers as |
|---|---|---|---|
| `proto` | "What wire language do I speak?" | Message schemas change | mDNS TXT `ver=1` |
| `gen` | "What firmware family am I?" | Capabilities / NVS schemas evolve | `gen` field in HELLO/WELCOME |
| `role` | "What's my job right now?" | A node accepts a new role | `role_requested` in HELLO |

`proto` is the wire spec, `gen` is the firmware family, `role` is the runtime function. They move on different timelines, and a peer that mismatches one may still cooperate on the others. The full treatment — including the mycology-themed **lineages** that `gen` carries — is in [Generations & the Lineage Gate](/docs/hive-ai/generations-lineage/).
