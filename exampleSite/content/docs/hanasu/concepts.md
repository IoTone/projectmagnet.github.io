---
weight: 20
title: "Concepts & Vocabulary"
description: "The words used throughout the Hanasu docs: nodes, channels, credentials, envelopes, the host link, identity, admin, transfer, mesh time, Forth and OTA."
icon: "menu_book"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "concepts"]
---

Hanasu is a chat and machine-to-machine messaging layer for small radios. Nodes form a Thread mesh (IEEE 802.15.4, 6LoWPAN, IPv6), exchange encrypted messages over CoAP, and expose everything to an attached host through a line protocol. The vocabulary below comes up on every other page in this section, so it is collected here once. Each entry links to the page that covers it in depth.

## The big picture in one table

| Term | One-line meaning | Covered in |
|---|---|---|
| **Node** | One Hanasu radio: an ESP32-C6 or XIAO MG24 running the MagNET core | [Architecture](/docs/hanasu/architecture/), [Boards](/docs/hanasu/boards/) |
| **Host** | Whatever is plugged into the node: a laptop, phone, cyberdeck, or script | [HCP](/docs/hanasu/hcp/) |
| **Channel** | A private conversation space, defined entirely by its credential | [Security Model](/docs/hanasu/security/) |
| **Envelope** | The 16-byte binary header every mesh message carries | [Wire Protocol](/docs/hanasu/protocol/) |
| **HCP** | The Host Control Protocol: the line-based text protocol on the host link | [HCP](/docs/hanasu/hcp/) |
| **Forth mode** | The same host link dropped into the embedded ESPIDFORTH REPL | [Forth & Bots](/docs/hanasu/forth-and-bots/) |
| **Admin** | An operator whose public key is on a node's allow-list | [Security Model](/docs/hanasu/security/) |
| **OTA package** | A signed firmware image that travels over the mesh | [OTA](/docs/hanasu/ota/) |

## Nodes and the mesh

**Node** — a single device running the Hanasu firmware. Every node runs the same unified Thread role: it is router-eligible and lets Thread decide whether it acts as leader, router, or child. There is no hard-coded "leader" node; if the leader disappears, Thread elects another. See [Architecture](/docs/hanasu/architecture/).

**Lifecycle state** — a node reports one of `BOOTING`, `CONFIGURING`, `ATTACHING`, `READY`, or `DEGRADED`. `READY` means it is attached to the mesh and can send. In `DEGRADED` (it was ready, then lost the mesh) a small queue holds up to four outgoing chats until it reattaches.

**ML-EID** — the mesh-local endpoint identifier, a stable IPv6 address every Thread node has. Unicast traffic (direct messages, transfers, OTA commands) is addressed to a peer's ML-EID. The node learns peers' addresses from the source of the frames it receives and lists them with `PEERS`.

**Multicast group** — each channel has its own IPv6 multicast address of the form `ff05::<suffix>`, where the 4-byte suffix is derived from the channel's secret. Group chat goes to that address; Thread's multicast forwarding (MPL) carries it across the mesh. See [Wire Protocol](/docs/hanasu/protocol/).

**Peer** — another node this node has heard from. The peer table records each peer's device ID, display name (learned from its announce message), and address.

## Channels and credentials

**Channel** — the unit of privacy. Everyone who holds the same credential derives the same keys, the same channel selector, and the same multicast group, so they can read each other's messages. Everyone else sees only ciphertext. A node is on exactly one channel at a time. Out of the box every node sits on a well-known channel named `magnet`, and it warns about that (`!WARN default-channel-insecure`) until a private channel is set.

**Credential** — the secret that names a channel. A node accepts it with `CHANNEL SET <cred>` and recognizes three forms automatically:

| Path | What the host sends | How the node turns it into a key |
|---|---|---|
| **A — pairing / QR** | `qr:` followed by base64 of 32 random bytes | Used directly as the root secret; no stretching needed |
| **B — passphrase** | Any other text | Stretched on the node with PBKDF2-HMAC-SHA256 (slow on purpose, so takes seconds) |
| **C — seed phrase** | Twelve or more space-separated words | Hashed with HKDF; the words already carry enough entropy, so no stretch |

Path A is the preferred route for anything private: a companion app generates the secret and shares it as a QR code. Path B is the convenient fallback for development, and the weakest. Path C, the **seed phrase**, is meant to be read aloud or written on paper while still being high-entropy. Details and exact derivations are on [Security Model](/docs/hanasu/security/).

**Root secret** — the 32-byte value every credential path produces. The node caches it in non-volatile storage, so a passphrase is stretched once, not at every boot. The node never prints it.

**Channel selector** — a 16-bit public tag derived from the root secret and placed in every envelope. A receiver drops frames whose selector does not match its channel before trying to decrypt. Because it is derived from the secret rather than the passphrase, seeing it on the air does not help an outsider guess the passphrase.

**Epoch** — a one-byte counter naming which generation of the channel key encrypted a frame. An admin can advance it fleet-wide with a signed rotate command; receivers accept the current and the immediately previous epoch so traffic in flight during a rotation still decrypts. See [Security Model](/docs/hanasu/security/).

## Messages on the wire

**Envelope** — the binary wrapper every mesh message travels in: a 16-byte header (version, type, flags, sender ID, counter, epoch, selector, fragment and message-ID fields), then the payload, then an 8-byte authentication tag when encrypted and a 64-byte signature when signed. See [Wire Protocol](/docs/hanasu/protocol/).

**Frame type** — the 4-bit type field in the envelope:

| Type | Name | Used for |
|---|---|---|
| 0 | CHAT | Group chat (multicast) and direct messages (unicast) |
| 1 | M2M_CMD | Machine-to-machine commands, including the system commands |
| 2 | M2M_RESP | Replies to commands (currently the OTA apply reply) |
| 3 | XFER | Reserved; superseded by Type 6 before it shipped |
| 4 | ACK | Defined in the design; not sent by current firmware |
| 5 | PING | Used by the on-node self-test loopback |
| 6 | XFER6 | Extended transfer of files such as photos |

**Counter** — a 32-bit number every node increments for each frame it sends and persists across reboots. It makes each encryption nonce unique and lets receivers reject replays.

**System namespace** — M2M commands in namespace `0x00` are reserved for the protocol itself: announce, rotate, mesh time, OTA apply/report, and admin revocation. The full table is on [Wire Protocol](/docs/hanasu/protocol/).

## The host link

**Host link** — the byte stream between a node and its host. The firmware speaks the same grammar over USB serial (USB CDC or the C6's on-chip USB serial/JTAG), a UART (the MG24's bridged serial port), and BLE GATT. See [HCP](/docs/hanasu/hcp/).

**HCP (Host Control Protocol)** — the default mode of the host link: one command per line, and every line from the node starts with a sigil that says what it is. `+` is the single success reply to a command, `-` the single failure reply, `!` an unsolicited event (an incoming chat, a state change), and `#` a human-readable comment that parsers ignore. Commands can carry an `@tag` that the node echoes on the matching reply. The design target is a protocol equally usable by a person at a serial monitor, a chat app, and a small language-model driver. See [HCP](/docs/hanasu/hcp/).

**Forth mode** — the verb `FORTH` switches the same link into the embedded ESPIDFORTH interpreter (`ok>` prompt); a line containing only `.hcp` switches back. Forth mode is for people and scripts that want to program the node; it does not keep HCP's strict one-reply-per-command framing. See [Forth & Bots](/docs/hanasu/forth-and-bots/).

**Privileged verb** — an HCP command that changes configuration or behavior a stranger must not touch: `NAME`, `CHANNEL SET`/`JOIN`, `ADMIN`, `ROTATE`, `SCRIPT`, `HOOK`, `BUNDLE`, `OTA`, `FORTH`, `STRESS`, and `FACTORY`. A wired serial link is treated as physically trusted. Over BLE, privileged verbs are refused with `-ERR E_NOT_BONDED` until the phone has bonded with the node. Read-only verbs stay open so a host can identify a node first. See [Security Model](/docs/hanasu/security/).

**Companion mode** — by default a node advertises over BLE only while it is unprovisioned and shuts BLE down once a channel is set, giving the radio and RAM back to Thread. A companion build (`esp32c6_ble_resident` on the C6) keeps BLE up permanently so a phone app has a standing window into the mesh. See [Architecture](/docs/hanasu/architecture/) and [Getting Started](/docs/hanasu/getting-started/).

## Identity and authority

**Identity key** — a per-node ECDSA P-256 key pair generated on first boot and stored in non-volatile storage. It signs admin commands and the node's own OTA replies and reports. (Earlier design text says Ed25519; the implementation uses P-256 because it is native and hardware-accelerated on the target's mbedTLS.)

**Device ID** — the first 4 bytes of SHA-256 of the node's 65-byte public key. It appears in every envelope as the sender, forms part of the encryption nonce, and is how peers, events, and the BLE name (`MagNET-xxxx`) refer to a node. A factory reset generates a new key and therefore a new device ID.

**Admin and allow-list** — each node keeps an allow-list of up to four admin public keys. Commands flagged ADMIN (channel key rotation, OTA apply, admin revocation) must carry a valid signature from one of those keys, or the node drops them before acting. The list starts empty, so no one has mesh-level authority over a fresh node until an operator enrolls a key over a trusted link with `ADMIN ADD`. A key's **fingerprint** is the first 8 bytes of SHA-256 of the public key. See [Security Model](/docs/hanasu/security/).

**Admin revocation** — `ADMIN REVOKE <fingerprint>` sends a signed command that removes that key from every node's allow-list that hears it; `ADMIN REMOVE` does the same locally only.

**Factory reset** — `FACTORY RESET CONFIRM` erases the channel, name, admins, saved script, counter block, identity key, and BLE bonds, then reboots. The node comes back as a blank part with a new identity.

## Larger payloads

**Type 6 extended transfer** — the mechanism for moving files (photos, firmware) between two nodes. The file is split into 336-byte chunks, sent by CON unicast only, with a windowed NACK bitmap for recovery; up to 4096 chunks (about 1.31 MB). The receiving node streams chunks up to its host rather than storing the file. See [Extended Transfer](/docs/hanasu/extended-transfer/).

## Time

**Mesh time and stratum** — a Hanasu mesh has no internet and no NTP. Instead one host seeds one node with `TIME SET`; that node becomes **stratum 0** and multicasts the time, and other nodes adopt it at stratum + 1. Nodes refuse a source at stratum 4 or above. Accuracy is about a second, and nothing security-related depends on it. See [Mesh Time](/docs/hanasu/mesh-time/).

## Forth and automation

**Hooks** — a Forth word registered with `mn-on-chat` or `mn-on-cmd` (or `HOOK CHAT|CMD <word>`) runs whenever chat or an M2M command arrives, so a node can react to the mesh with no host attached. Hooks are rate-limited to five firings per second to stop two nodes from triggering each other forever. See [Forth & Bots](/docs/hanasu/forth-and-bots/).

**Role bundle** — a signed package of Forth source that teaches a node new behavior without reflashing, installed through the `BUNDLE` verb using the same role-bundle engine as the [Hive AI](/docs/hive-ai/role-bundles/) firmware. Bundles are signed with Ed25519 (or a legacy HMAC). Saved bundles are re-applied at boot, and re-applying them successfully is part of what makes a newly updated node count as healthy. See [Forth & Bots](/docs/hanasu/forth-and-bots/).

**Bots** — opt-in auto-responders compiled in only with a build flag (`MN_ENABLE_BOTS`), used as a proof-of-life test: an armed bot answers chat by itself. Frames a bot sends carry the AUTOMATED envelope flag, and bots never answer a frame carrying it, so two bots cannot volley indefinitely. See [Forth & Bots](/docs/hanasu/forth-and-bots/).

## Firmware updates

| Term | Meaning |
|---|---|
| **OTA package** | A firmware image wrapped in a 256-byte header signed by a release key (Ed25519 preferred, ECDSA P-256 accepted). Release keys are separate from admin keys. |
| **Staging** | Sending the package to a node with a Type 6 transfer. The receiver verifies the signature and hash and writes it into the inactive firmware slot. Staging alone changes nothing that runs. |
| **Apply** | Telling the node to boot the staged image. Remotely, this is the `system/ota_apply` command, which must be signed by an allow-listed admin and sent unicast to one node. |
| **Trial** | By default the new image boots in TEST mode and confirms itself only once it reaches `READY` and its saved role bundles re-apply. If that does not happen within 10 minutes, the node rolls back and reports the rollback. |

See [OTA Updates](/docs/hanasu/ota/) for the design and [OTA Operations](/docs/hanasu/ota-operations/) for the operator workflow.
