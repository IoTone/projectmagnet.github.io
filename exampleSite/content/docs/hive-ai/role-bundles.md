---
weight: 70
title: "Signed Role Bundles"
description: "How the hive teaches nodes new behavior at runtime — the envelope format, signing, install pipeline, and authoring."
icon: "deployed_code"
date: "2026-05-29T00:00:00-05:00"
lastmod: "2026-05-29T00:00:00-05:00"
draft: false
toc: true
tags: ["hive", "bundles", "forth", "spec"]
---

A **role bundle** is a signed JSON envelope carrying ESPIDFORTH source that a receiving node executes via `forth_eval_n()`. Bundles are how a hive teaches its nodes new behavior at runtime — **without reflashing**. Implementation lives in the `craw_role_bundle` component.

## Design goals

- **Self-contained** — everything a node needs to install and run a role (source, version, signature).
- **Verifiable** — the signature catches tampering and lets a node refuse an unauthorized publisher.
- **Portable** — any chip running ESPIDFORTH and the matching FFI words can install any bundle whose `caps_req` it satisfies.
- **Compact** — typical bundles are < 2 KB, fitting in a single hive `KV_DATA` frame (3 KB cap).

## Wire format

```json
{
  "name":      "spy",
  "version":   "1.0.3",
  "min_proto": 1,
  "author":    "iotone-dev",
  "caps_req":  ["camera", "jpeg"],
  "deps":      [],
  "crc32":     "a1b2c3d4",
  "sig_alg":   "hmac-sha256",
  "sig":       "f17b...",
  "src_b64":   "OiBzcHktbG9vcCAuLi4="
}
```

| Field | Purpose |
|---|---|
| `name` | Role name (≤ 32 chars) |
| `version` | SemVer; a node refuses a bundle older than the installed one (monotonic upgrade) |
| `min_proto` | Minimum hive-protocol version; future-proto bundles are refused |
| `author` | Selects which trusted key the signature must validate against |
| `caps_req` | Capabilities the role needs; refused if the node's caps don't cover them |
| `deps` | Bundles expected first (not enforced in v1) |
| `crc32` | CRC-32 of the *decoded* source; defends against base64 corruption |
| `sig_alg` | `hmac-sha256` in v1; `ed25519` planned for v2 |
| `sig` | Signature over the canonical signing input |
| `src_b64` | Base64 Forth source; decoded ≤ 4096 bytes for v1 |

### Canonical signing input

```
"<name>|<version>|<min_proto>|<author>|<crc32>|<src_b64>"
```

Pipe-delimited, that exact order, no whitespace. For `hmac-sha256`:

```
sig = HMAC-SHA256(shared_key, signing_input)   # 32 bytes hex
```

## Trust model

**v1 — HMAC with the hive secret.** Bundles are signed with the same 32-byte secret used for hive HMACs. This means *anyone who can verify can also sign* — the model is "nodes trust holders of the shared secret to publish." Adequate for demos; inadequate for production (a firmware leak leaks the publisher key).

{{< alert context="warning" text="<strong>Planned (v2): Ed25519 with per-author public keys.</strong> Each <code>author</code> gets a public key baked into firmware; private keys stay offline. The <code>sig_alg</code> field exists from v1 precisely so a node can verify both schemes during migration." />}}

## Install pipeline

`craw_role_bundle_install_from_json()` runs these steps; any failure aborts with a specific code:

| Step | Failure code | Catches |
|---|---|---|
| Parse JSON envelope | `BUNDLE_ERR_PARSE` | Malformed JSON / missing fields |
| Validate `min_proto` | `BUNDLE_ERR_PROTO` | Future-proto bundle |
| Look up author | `BUNDLE_ERR_AUTHOR` | Unknown publisher |
| Verify signature | `BUNDLE_ERR_SIG` | Tampering / wrong key |
| Base64-decode | `BUNDLE_ERR_BASE64` | Corrupt encoding |
| CRC32 of decoded source | `BUNDLE_ERR_CRC` | Source mutated after signing |
| `caps_req` ⊂ node caps | `BUNDLE_ERR_CAPS` | Spy bundle on a Scribe-only node |
| Version monotonic | `BUNDLE_ERR_VERSION` | Downgrade attempt |
| `forth_eval_n()` | `BUNDLE_ERR_EVAL` | Forth syntax / runtime fault |
| Persist to NVS | `BUNDLE_ERR_NVS` | NVS write failure |

On success the bundle's words are registered in the global vocabulary, its top-level body runs once, and the envelope is persisted so the role auto-resumes on next boot.

## NVS persistence

| Namespace | `craw_role_bundle` |
|---|---|
| Per-role keys | `n:<name>` → version, `b:<name>` → full envelope JSON |
| Size limit | 4 KB per blob (NVS hard limit) |

`craw_role_bundle_apply_saved()` runs early in boot and re-installs each persisted bundle. Useful pattern: install once, reboot, watch it auto-resume.

## Where bundles live

The architectural decision: **bundles live on the Scribe**. This collapses "download a role" (R8/R9) and "query shared memory" (R16/R17) into a single mechanism — a bundle is just a shared-memory value keyed `bundle:<name>`. The Ruler embeds bundles as a bootstrap fallback; once a [Scribe](/docs/hive-ai/scribe-redis/) joins, the Ruler seeds its bundles into the Scribe, which becomes authoritative.

Two distribution paths exist:

- **A — production/demo:** bundles are compiled into the Dial firmware via an auto-generated header; on boot the ruler `KV_PUT`s each into its table. Self-sufficient, no laptop needed.
- **B — dev/CI:** `scripts/push_bundles.py` discovers a running Dial over mDNS, joins as a transient client, and `KV_PUT`s each signed `*.json`. Update bundles without reflashing.

## Authoring a bundle

```bash
echo ': hello-spy ." Hello from the spy role" cr ;' > /tmp/spy.forth
python scripts/sign_bundle.py /tmp/spy.forth \
  --name spy --version 1.0.0 --author iotone-dev \
  --caps-req "camera,jpeg" > spy.json
```

The output is ready to `KV_PUT` to a Scribe or embed in ruler firmware.

### Forth role conventions

A bundle's source is regular ESPIDFORTH. Conventional structure:

```forth
\ Role: spy v1.0.0 — periodic camera snapshot loop.
: spy-snap-once   cam-snap drop ;
: spy-loop        begin spy-snap-once 5000 ms again ;

spy-snap-once   \ one-shot capture as install-time confirmation
```

{{< alert context="warning" text="Bundles should not block forever at top level — the install task is shared, and a runaway bundle blocks subsequent installs. Define words and return, or use cooperative yields." />}}

See [Controlling the Hive from Forth](/docs/hive-ai/forth-words/) for the vocabulary available to bundle authors, and the [Boombox cookbook](/docs/hive-ai/boombox-audio/) for audio-role examples.
