---
weight: 70
title: "Security Model"
description: "How Hanasu derives channel keys, encrypts and authenticates every frame, rejects replays, authorizes admins, gates the BLE host link, and what all of that does and does not protect against."
icon: "lock"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "security"]
---

Hanasu's security rests on two independent planes. The **channel plane** is symmetric: everyone holding a channel's credential shares its keys, and that keeps outsiders from reading or forging traffic. The **identity plane** is asymmetric: each node has its own key pair, which is how privileged commands are tied to a specific, authorized operator rather than to "anyone on the channel."

This page describes the cryptography as it is **implemented** in the Hanasu repo (`firmware-idf/components/magnet/magnet_crypto.c`, `magnet_core.c`, and the PSA port in `firmware-zephyr/src/magnet_crypto_psa.c`). Where the design document (`MAGNet_Protocol_DESIGN_PROPOSAL.md` §11) says something different, the differences are called out.

{{< alert context="warning" text="<strong>The Thread network is not the security boundary.</strong> Every node joins the same Thread network built from a fixed development dataset with a well-known network key. Anyone with that key can join the mesh and see frames. Confidentiality and integrity come from the per-channel encryption described below, not from Thread link-layer security." />}}

## Channel keys

### From credential to root secret

A channel is defined by its credential. `CHANNEL SET <cred>` (or `CHANNEL JOIN`, which does the same) accepts a credential of 4 to 512 bytes and detects which of three paths it is:

| Path | Detected when | Derivation of the 32-byte root secret |
|---|---|---|
| **A — pairing / QR** | The credential starts with `qr:` | Base64-decode the rest; it must be exactly 32 bytes and is used as-is |
| **C — seed phrase** | It contains 12 or more space-separated words | `HKDF-SHA256(ikm = phrase, salt = "MagNET/v2.1/chan-salt", info = "root")` |
| **B — passphrase** | Anything else | `salt = HKDF-SHA256(ikm = passphrase, salt = "MagNET/v2.1/chan-salt", info = "chan-salt-ikm")`, then `PBKDF2-HMAC-SHA256(passphrase, salt, 100,000 iterations, 32 bytes)` |

Path A is the intended route for private channels: a companion app generates 32 random bytes and shares them as a QR code, so no human-chosen secret is involved. Path C gets its strength from the number of words. Path B is a convenience for development and the weakest option: PBKDF2 raises the cost of guessing, but it is not memory-hard, and a short passphrase is still guessable offline. The stretch takes seconds on the node, and the loop yields the CPU every 5,000 iterations so the single-core C6's watchdog keeps getting fed.

The root secret is derived once and cached in non-volatile storage, so a reboot does not re-run the stretch.

{{< alert context="info" text="<strong>Implementation vs design.</strong> The design (§11.1.2) specifies 600,000 PBKDF2 iterations with a salt bound to a separate channel name, and a Path C salt of <code>MagNET/v2.2/seed-phrase</code> applied to a lowercased, BIP39-style word list. The firmware uses 100,000 iterations (tunable via <code>MN_PBKDF2_ITERS</code>), derives the Path B salt from the passphrase itself, uses the shared channel salt for Path C, and does not check words against a word list or normalize case. Two hosts must therefore send the phrase in exactly the same form." />}}

### From root secret to everything else

All public routing identifiers and the encryption key are derived from the root secret, never from the passphrase directly. An observer who sees the selector or multicast address on the air cannot use them to test passphrase guesses.

| Output | Derivation (HKDF-SHA256) | Size | Public? |
|---|---|---|---|
| Channel selector | `info = "selector"`, salt = channel salt | 16 bits | Yes, in every envelope |
| Multicast suffix | `info = "mcast"`, salt = channel salt | 4 bytes, group `ff05::<suffix>` | Yes |
| Channel base key | `info = "chan-base"`, salt = channel salt | 32 bytes | No |
| Epoch key *e* | From the base key, no salt, `info = "epoch"` followed by the epoch number | 16 bytes (AES-128) | No |

`CHANNEL SHOW` and `STATUS` report only public values (name, selector, multicast group, which credential path was used). The node never prints the credential, the root secret, an epoch key, or its private key on any host binding, and `CHANNEL SET` replies with the name and selector only.

### The default channel

A factory-fresh node derives the well-known channel `magnet` (via Path B). Its traffic is encrypted, but because the passphrase is public, anyone can derive the key. The node says so on every boot with `!WARN default-channel-insecure` until a private channel is set.

## Per-frame encryption

Every frame on a channel is encrypted with **AES-128-CCM** and an **8-byte MIC** (authentication tag).

```
nonce (13 bytes) = device_id(4) ‖ counter(4, big-endian) ‖ epoch(1) ‖ selector(2, big-endian) ‖ 0x0000
AAD              = the 16-byte envelope header
key              = the epoch key named by the header's epoch byte
```

The header is authenticated but not encrypted, so a receiver can route on it, and any change to it breaks the MIC. On receive, the node decrypts and checks the MIC **before** any stateful processing. A plaintext frame arriving on an encrypted channel is dropped.

### The nonce rule and the persistent counter

AES-CCM fails catastrophically if a key is ever used twice with the same nonce. Hanasu guarantees uniqueness with the pair *(device ID, counter)*: the device ID is unique per node and the counter is a 32-bit value the node increments for every frame and never reuses, even across reboots.

To avoid a flash write per message, the counter is reserved in blocks of 1,024: the node writes "current + 1024" to storage, hands out values from RAM, and reserves the next block before the current one runs out. A crash wastes at most part of one block. If the node cannot persist a new block, it refuses to send rather than risk reusing a nonce (it **fails closed**).

## Replay protection

Because counters only ever go up, a receiver can reject replays and duplicates by remembering the highest counter it has accepted from each sender (its **high-water mark**). A frame whose counter is at or below that mark is dropped and counted as a duplicate.

The table is bounded at 40 senders with least-recently-used eviction, sized alongside the peer table for meshes of 32 or more nodes. An unknown sender is accepted and recorded (trust on first use). One consequence is accepted by design: if a long-idle sender's entry is evicted, one replay of an old frame from that sender can slip through. ADMIN frames are additionally signed, and the OTA commands are bound to specific staged images, which limits what such a replay could do.

The order of checks on every received frame is:

1. Parse the header; drop the node's own frames and frames whose selector does not match.
2. If the frame is ADMIN, verify its signature against the allow-list (before decrypting).
3. Decrypt and verify the MIC with the current or previous epoch key.
4. Drop frames that are signed but not ADMIN, except for the two OTA messages that are meant to be.
5. Check the counter against the sender's high-water mark.
6. Only then update the peer table, emit events, or run hooks.

## Epochs and rotation

The epoch byte lets an admin replace the channel's working key. `ROTATE` (Forth: `mn-rotate`) sends the system command `rotate` (namespace `0x00`, command `0x03`) to the channel, carrying the next epoch number. It is flagged ADMIN and SIGNED; nodes verify the signature against their allow-list and then switch to the new epoch key. Each node keeps the immediately previous epoch key as well, so frames in flight during a rotation still decrypt. Anything older is rejected.

{{< alert context="warning" text="<strong>Limits of rotation as built.</strong> (1) Each epoch key is computed deterministically from the channel's root secret, so anyone who holds the credential can derive every past and future epoch key; rotation does not give forward secrecy against a leaked credential, although design §11.1.8 aims for that. (2) The current epoch is kept in RAM only: a node that reboots returns to epoch 0. (3) The design's automatic daily rotation is not implemented; rotation happens only on an admin command." />}}

## Node identity

On first boot each node generates an **ECDSA P-256** key pair and stores the private scalar in non-volatile storage (`idkey`). Signatures are deterministic ECDSA over SHA-256, sent as raw `r ‖ s` (64 bytes).

The **device ID** is `SHA-256(65-byte uncompressed public key)[0:4]`. It is the sender field of every envelope and part of every nonce. `PUBKEY` prints the full public key and `WHOAMI` the device ID.

{{< alert context="info" text="<strong>Why P-256 and not Ed25519.</strong> Design §11.1 specifies Ed25519 identity keys. When identity was implemented, the target's mbedTLS (ESP-IDF 5.3.1) had no Ed25519, while P-256 is native and hardware-accelerated on the C6, so identity keys became deterministic ECDSA P-256. Read every Ed25519 identity reference in §11.1 as P-256. Ed25519 <em>is</em> used elsewhere: for signed role bundles and as the preferred algorithm for OTA release keys." />}}

## Admins and signed commands

Chat and routine M2M traffic carry no signature: channel membership is the trust boundary, and keeping them unsigned lets them fit in one frame. Commands that change what a node does are different.

| Command | Namespace / ID | Flags | Delivery |
|---|---|---|---|
| Rotate epoch | `0x00` / `0x03` | ENCRYPTED, ADMIN, SIGNED | Multicast |
| OTA apply | `0x00` / `0x06` | ENCRYPTED, ADMIN, SIGNED | CON unicast to one node |
| Admin revoke | `0x00` / `0x08` | ENCRYPTED, ADMIN, SIGNED | Multicast, repeated by the operator |

An ADMIN frame carries a 64-byte signature trailer over `header ‖ ciphertext ‖ MIC`. The receiver checks it against every key on its **admin allow-list** before decrypting or acting; a frame that fails is dropped silently and counted as an error. An unauthorized rotate, for example, changes nothing on the mesh.

**The allow-list** holds at most four 65-byte public keys in non-volatile storage. It starts empty, so a fresh node accepts no mesh-level admin commands at all. Keys are added locally with `ADMIN ADD <130 hex digits>` over a trusted host link, and `ADMIN LIST` shows each key's **fingerprint**, `SHA-256(public key)[0:8]` (its first four bytes are that key owner's device ID). The design's signed mesh-level `admin/grant` command is not implemented; enrolling an admin is always a local operation.

**Self-signed replies.** The OTA apply reply (Type 2) and the post-update report (`0x00`/`0x07`) are signed by the *target* node's own identity key, not an admin key, so the operator can trust which node said what. Because the admin does not already hold that node's key, the key travels in the message, and the receiver requires `SHA-256(key)[0:4]` to equal the sender's device ID. That is only a 32-bit binding: a channel member willing to grind roughly 2³² P-256 keys could impersonate one node's report (but not issue an apply, which needs an admin key). Signed-but-not-ADMIN frames are accepted for these two messages only. See [OTA Updates](/docs/hanasu/ota/).

### Revoking an admin

Added in design rev 2.4 (§13.11):

| Verb | Effect |
|---|---|
| `ADMIN REMOVE <n or fingerprint>` | Remove a key from this node only |
| `ADMIN REVOKE <fingerprint>` | Send a signed `admin_revoke` (`0x00`/`0x08`) to the whole channel, then remove the key here too |

Revocation is idempotent, so the operator repeats it to cover a lost multicast frame. An admin may revoke its own key, since the frame is signed before the local removal. The limits are real: a thief holding a still-valid admin key can revoke the others just as quickly, and a node that was offline during the revoke keeps the key until it is revoked again. There is no revocation list. Recovery is `ADMIN ADD` over a bonded or wired link.

## The host link

### Wired links are trusted

USB serial and UART are treated as physically trusted: whoever is plugged in can run any verb, including privileged ones. Physical access to a node is effectively administrative access to that node.

### BLE is privileged-but-pairable

BLE is reachable by anyone nearby, so the GATT binding enforces bonding **per verb**:

- Read-only verbs (`STATUS`, `CAPS`, `WHOAMI`, `PEERS`, `CHANNEL SHOW`, and so on) work on an unbonded link, so a phone can identify a node before pairing.
- **Privileged verbs** return `-ERR E_NOT_BONDED` until the link is encrypted with a bond: `NAME`, `CHANNEL SET`/`JOIN`, `ADMIN`, `ROTATE`, `SCRIPT`, `HOOK`, `BUNDLE`, `OTA`, `FORTH`, `STRESS`, and `FACTORY`.
- **FORTH mode** is node-wide; while it is on, every line from a BLE link that is not bonded is refused (`E_NOT_BONDED`), so a node left in FORTH from its USB console does not open the REPL to a stranger.

The node pairs with **LE Secure Connections, Just Works** (the node has no display or keypad, so MITM protection is off), with legacy pairing enabled as a fallback. An encryption-required characteristic is what prompts the phone to start pairing; only the phone operating system's own pairing prompt can complete a bond. `docs/BLE-PAIRING.md` in the Hanasu repo records the details, including which behaviors are verified and which are not yet (for example, iOS is untested).

**The pairing window is narrow by default.** A provisioning build advertises only while the node is still on the default channel, and shuts BLE down the moment a channel is set, so power-cycling a deployed node does not reopen a chance to re-provision it. A companion build (`esp32c6_ble_resident`) deliberately stays attachable and reopens the bonding window on every boot; privileged verbs still require a bond.

## Factory reset

`FACTORY RESET CONFIRM` erases the node's entire storage namespace (channel root secret, name, admin allow-list, boot script, counter block, and identity key) and the BLE bond store, then reboots. Bare `FACTORY RESET` returns `-ERR E_CONFIRM_REQUIRED`. Over BLE it is a privileged verb.

Erasing the identity key is deliberate: a reset node is usually leaving its trust domain, and keeping its key pair would let it carry authority another node's allow-list still grants it. The node returns with a new key and therefore a new device ID. Erasing the whole namespace (rather than a list of keys) means a setting added later cannot be accidentally left behind. Because the node's BLE address does not change, a phone that still holds the old bond needs to forget it before pairing again (see `docs/BLE-PAIRING.md`).

## Code signing on the node

Two kinds of code can reach a node without a cable, and each has its own key, separate from channel and admin keys:

| What | Signed with | Checked |
|---|---|---|
| Role bundles (Forth) | Ed25519 (legacy HMAC-SHA256 entries still accepted during migration) against a compiled-in trust store | On install and when re-applied at boot |
| OTA packages (firmware) | Release key: Ed25519 preferred, ECDSA P-256 accepted | Before staging; on the MG24, MCUboot also checks its own image signature |

Holding one key grants none of the others: an admin key can *apply* an update but cannot sign one, and a release key can sign an image but cannot make a node boot it. The repository's DEV keys must be replaced before any node leaves the bench (design §13.8). See [Forth & Bots](/docs/hanasu/forth-and-bots/) and [OTA Updates](/docs/hanasu/ota/).

## What this protects, and what it doesn't

| Threat | Protected? | How, or why not |
|---|---|---|
| Outsider reads channel traffic | Yes | AES-128-CCM with keys only credential holders can derive |
| Outsider forges or alters a frame | Yes | MIC over header and payload; header is the AAD |
| Outsider confirms passphrase guesses from the air | Yes | Selector and multicast group derive from the root secret |
| Offline guessing of a weak Path B passphrase from captured traffic | Partly | PBKDF2 slows it; Path A or C credentials avoid it |
| Replay of a captured frame | Yes, with a caveat | Persistent counters and per-sender high-water marks; a sender evicted from the 40-entry table can be replayed once |
| Nonce reuse after a reboot or crash | Yes | Block-reserved persistent counter; refuses to send if it cannot persist |
| A channel member impersonating another member in chat | **No** | Chat is group-authenticated only: it proves "some channel member sent this" |
| A channel member rotating keys, updating firmware, or revoking admins | Yes | ADMIN commands need a signature from an allow-listed key, checked before decryption |
| Replaying a captured OTA apply | Yes | Counter check, plus the command is bound to the target's device ID and the hash of the image staged now |
| Forging a node's OTA reply or report | Partly | Signed by the node, but tied to its device ID by only 32 bits |
| Malicious firmware image | Yes, as strong as the release keys | Package signature checked before staging; the C6 has no secure boot, so this is its only check |
| Bricked radio after an update | Yes | TEST-mode trial, confirm only when healthy, automatic rollback after 10 minutes |
| Stolen admin key | Partly | Revocation removes it, but a thief can revoke other admins as fast |
| Leaked channel credential exposing past traffic | **No** | Every epoch key derives from the root secret; rotation is not forward secrecy in current firmware |
| Someone nearby pairing over BLE | Partly | Pairing is Just Works (no MITM protection) and possible only while the window is open: unprovisioned nodes, or companion builds |
| Physical access to a node | **No** | The wired link is trusted, and keys sit in the node's ordinary non-volatile storage |
| Traffic analysis (who talks, when, how much) | **No** | Device IDs, counters, selectors, and sizes are visible in every header |
| Mesh flooding / denial of service | **No** | Rate limits protect the node from its own host, not from a hostile radio |
| Thread-level intrusion | **No** | The Thread dataset and network key are fixed and well known |

Mesh time is deliberately outside the security model: it is channel-encrypted but not signed, so any channel member can set it, and nothing that matters for security depends on it. Replay defense uses counters, not timestamps. See [Mesh Time](/docs/hanasu/mesh-time/).
