---
weight: 80
title: "Wire Protocol"
description: "The Hanasu v2.1 envelope byte by byte, frame types, the system command namespace, CoAP resources and delivery modes, size limits, and the scale figures the design and bench measurements support."
icon: "lan"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "protocol"]
---

Everything a Hanasu node sends over the mesh is one **envelope**: a fixed 16-byte binary header, a payload, and optional authentication trailers. The envelope rides as the payload of a CoAP request, which rides in UDP over IPv6, compressed by 6LoWPAN into IEEE 802.15.4 radio frames.

```
802.15.4 frame(s)
└─ 6LoWPAN (compressed IPv6 + UDP, fragmented if needed)
   └─ CoAP  PUT /magnet   (CON or NON)
      └─ MagNET envelope v2.1
         ├─ header      16 bytes   (authenticated, not encrypted)
         ├─ payload     N bytes    (AES-128-CCM ciphertext)
         ├─ MIC          8 bytes   (when ENCRYPTED)
         └─ signature   64 bytes   (when SIGNED)
```

The normative description is §11.1.4 of `MAGNet_Protocol_DESIGN_PROPOSAL.md` in the Hanasu repo; the implementation is `firmware-idf/components/magnet/include/magnet_envelope.h` and `magnet_envelope.c`. The original 10-byte envelope in design §4.4 and §9 is superseded and kept there only for history.

## The envelope header

All multi-byte fields are big-endian.

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 1 | Version (high 4 bits) ‖ Type (low 4 bits) | Version is `2` for the v2.1 format; frames with any other version are dropped |
| 1 | 1 | Flags | See below |
| 2 | 4 | Sender device ID | `SHA-256(sender public key)[0:4]` |
| 6 | 4 | Counter | Per-sender, persistent, strictly increasing; nonce input and replay check |
| 10 | 1 | Epoch | Which channel key epoch encrypted this frame |
| 11 | 2 | Channel selector | 16-bit public tag derived from the channel secret |
| 13 | 1 | Fragment: total (high 4 bits) ‖ index (low 4 bits) | Total 1–15, index below total |
| 14 | 2 | Message ID | Random; groups fragments of one message |
| 16 | N | Payload | Ciphertext when ENCRYPTED |
| 16+N | 8 | AES-CCM MIC | Present when ENCRYPTED |
| +8 | 64 | Signature, raw `r ‖ s` | Present when SIGNED; ECDSA P-256 over everything before it |

The whole 16-byte header is the AEAD's additional authenticated data, so tampering with any header field causes decryption to fail. Nonce construction and the replay rules are on [Security Model](/docs/hanasu/security/).

### Flags

| Bit | Name | Meaning |
|---|---|---|
| 0 | ENCRYPTED | Payload is AES-128-CCM ciphertext and the MIC is present |
| 1 | SIGNED | A 64-byte signature trailer is present |
| 2 | ADMIN | Privileged command; must also be SIGNED by an allow-listed key |
| 3 | REQUIRES_ACK | Sender expects a Type 4 acknowledgment (defined; not used by current senders) |
| 4 | IS_FRAGMENT | Application-layer fragment |
| 5 | IS_FINAL_FRAG | Last fragment of a group |
| 6 | AUTOMATED | Sent by an auto-responder; other auto-responders must not answer it. Advisory only; older firmware ignores it |
| 7 | reserved | Must be 0 |

**Application-layer fragmentation is not used in current firmware.** Every frame is sent with fragment total 1, index 0, and receivers reject inconsistent fragment fields. Payloads larger than one frame are carried either by 6LoWPAN fragmentation (transparently, below CoAP) or, for files, by Type 6 extended transfer.

## Frame types

| Type | Name | Status in firmware | Typical delivery |
|---|---|---|---|
| 0 | CHAT | Implemented | NON multicast for group chat; CON unicast for a direct message (reported as `!DM`) |
| 1 | M2M_CMD | Implemented | Depends on the command; see the system namespace below |
| 2 | M2M_RESP | Implemented for the OTA apply reply | CON unicast back to the requester |
| 3 | XFER | Reserved; superseded by Type 6 before it shipped | — |
| 4 | ACK | Defined in the design, not sent; CoAP's own acknowledgment covers CON delivery | — |
| 5 | PING | Used only by `SELFTEST`'s CoAP loopback to the node's own address | NON unicast to itself |
| 6 | XFER6 | Implemented: extended transfer | CON unicast only |

**Chat.** The payload is UTF-8 text. A receiver tells group chat from a direct message by whether the frame arrived on the channel's multicast address.

**M2M command.** The payload begins with a 4-byte command header:

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | Namespace (`0x00` system; design assigns `0x01` lighting, `0x02` sensor, `0x03`–`0xFF` user-defined) |
| 1 | 1 | Command ID within the namespace |
| 2 | 2 | Parameter length |
| 4 | n | Parameters |

The firmware handles namespace `0x00` itself. Any other command is surfaced to the host as `!CMD <channel> <sender> <ns> <id> len=<n>` and passed to a Forth `mn-on-cmd` hook if one is registered. The design's host verb for sending arbitrary commands (`CMD`, design §11.3.2) is not in the current firmware's verb list.

**M2M response.** Uses the same 4-byte header, echoing the namespace and command ID of the request, with a status byte as the first parameter byte. The only response the firmware currently sends is the OTA apply reply (status, the target's running version, and its public key; 74 bytes of parameters).

**Type 6 extended transfer.** The payload carries its own sub-header with a 16-bit chunk index, so transfers are not limited by the envelope's 4-bit fragment field. A data frame on the wire is 16 header + 5 sub-header + 336 chunk + 8 MIC = 365 bytes. The full format, windowing, and NACK recovery are on [Extended Transfer](/docs/hanasu/extended-transfer/); `docs/EXTENDED-TRANSFER.md` in the Hanasu repo is normative.

## The system namespace (`0x00`)

These commands are allocated in design §4.4 and §13. User commands belong in namespace `0x03` and above.

| Cmd | Name | Parameters | Flags and delivery | Implemented |
|---|---|---|---|---|
| `0x01` | set_channel | credential | Must be ADMIN and SIGNED | **No** (allocated; channels are set from the host with `CHANNEL SET`) |
| `0x02` | announce | display name, up to 16 bytes | NON multicast; sent on reaching READY after a 200–1700 ms random delay, and when the name changes | Yes |
| `0x03` | rotate | 1 byte: new epoch | ADMIN, SIGNED; multicast | Yes |
| `0x04` | time_announce | 11 bytes: Unix time `int64` ‖ time-zone offset in minutes `int16` ‖ sender stratum `u8` | NON multicast. Receivers adopt at stratum + 1, must not re-broadcast, and refuse stratum 4 or higher | Yes |
| `0x05` | time_request | none | NON multicast. Responders reply after a jittered delay and cancel on hearing any `0x04`, so one node answers | Yes |
| `0x06` | ota_apply | 30 bytes: target device ID (4) ‖ image SHA-256 prefix (16) ‖ version (8) ‖ mode (1) ‖ flags (1) | ADMIN, SIGNED; CON unicast to one node. Reply is Type 2 with the same namespace and command | Yes |
| `0x07` | ota_report | 83 bytes: outcome (1) ‖ running version (8) ‖ other version (8) ‖ bundles (1) ‖ public key (65) | SIGNED by the reporting node (not ADMIN); CON unicast to the admin that applied, falling back to NON multicast | Yes |
| `0x08` | admin_revoke | 8 bytes: key fingerprint | ADMIN, SIGNED; NON multicast, idempotent | Yes |

Details: mesh time in [Mesh Time](/docs/hanasu/mesh-time/); rotate and revoke in [Security Model](/docs/hanasu/security/); apply and report in [OTA Updates](/docs/hanasu/ota/).

## CoAP resources

OpenThread's CoAP service runs on its default port, and the node registers two resources:

| Resource | Method | What it does |
|---|---|---|
| `magnet` | PUT | Accepts one envelope of any type. A confirmable request gets a `2.04 Changed` acknowledgment immediately; the frame is then queued for the event pump |
| `magnet/recent` | GET | Returns the node's ring of up to 12 recently accepted multicast chat frames, still encrypted, as `[2-byte length][frame]…`, oldest first |

The catch-up resource exists because Thread does not deliver multicast to sleepy end devices, and because any node can miss traffic while detached. `RECENT <peer-ipv6>` fetches a peer's ring; each frame then goes through the normal decrypt and replay checks, so the node keeps exactly the frames it missed and drops the ones it already has. Serving ciphertext reveals nothing that was not already on the air.

The design's `GET /magnet` status resource and `/magnet/discover` (design §4.5) are not implemented; discovery happens through Thread attachment, announce messages, and the peer table.

## Multicast and unicast

| Mode | Destination | CoAP type | Used for |
|---|---|---|---|
| One to many | The channel's group `ff05::<suffix>` (suffix derived from the channel secret) | NON | Chat, announce, mesh time, rotate, admin revoke, the OTA report fallback |
| One to one | The peer's mesh-local IPv6 address (ML-EID) | CON | Direct messages, Type 6 transfers, OTA apply and its reply, OTA report, catch-up GET |

Each node subscribes to its current channel's multicast group and re-subscribes when the channel changes. Multicast is forwarded across the mesh by Thread's MPL, which is itself a Trickle algorithm, so Hanasu nodes never re-forward frames at the application layer; they only de-duplicate them. Unicast gets CoAP's acknowledgment and retransmission, plus a MAC-layer acknowledgment per radio frame.

The rule that falls out of the bench measurements below: **anything larger than one radio frame that must arrive goes by CON unicast**. Multicast is for short, best-effort traffic.

## Size limits

### Per frame

| Limit | Value | Source |
|---|---|---|
| Largest envelope accepted or produced | 512 bytes | `MN_ENV_MAX_FRAME` |
| Header | 16 bytes | v2.1 envelope |
| Encryption overhead | 8 bytes (MIC) | Every frame on a channel |
| Signature overhead | 64 bytes | ADMIN and SIGNED frames |
| Largest payload the sender accepts | 424 bytes (512 − 16 − 8 − 64; the signature space is always reserved) | `send_frame` |
| HCP line on the host side | 512 bytes | HCP; this is why Type 6 chunks are 336 bytes (448 characters of base64) |

### Radio frames and 6LoWPAN

An IEEE 802.15.4 frame is at most 127 bytes. After MAC, 6LoWPAN, UDP, and CoAP headers, the design (§3.1) estimates roughly 50–70 bytes of application payload fit in a single radio frame. The design's ~62-byte single-frame budget (§4.4) was computed for the older 10-byte header; the v2.1 header plus MIC is 24 bytes, so less text fits before a message spills into a second radio frame.

Anything larger is fragmented by 6LoWPAN, transparently to Hanasu. The first fragment carries a 4-byte header and each later one a 5-byte header, and OpenThread's default reassembly limit is 1280 bytes (design §3.2), comfortably above Hanasu's 512-byte frame cap. A full 496-byte payload takes about 5–6 radio frames, and a 365-byte Type 6 frame about 4. Each radio frame is a separate transmission, so more fragments mean more chances to lose the message.

## Throughput and loss, as measured

Four-node bench results from `firmware-idf/README.md` (July 2026, multicast unless noted):

| Scenario | Result |
|---|---|
| Steady chat, 62-byte payload, 1 msg/s per node | 0.00% loss |
| Steady traffic, 496-byte payload, 1 msg/s per node | 6.6% loss (one lost fragment kills the whole message) |
| One sender bursting, 496 bytes | ~50% delivery per receiver, ~4 KB/s goodput |
| All four nodes saturating, 496 bytes | Congestive collapse: almost nothing delivered; mesh self-healed, no crashes |
| Per-node send acceptance ceiling | ~13 msg/s at 496 bytes, ~48 msg/s at 62 bytes (OpenThread buffer backpressure) |
| Type 6 transfer, CON unicast, two nodes | ~5.4 KiB/s, byte-identical; completed byte-identical under a multicast flood at reduced speed |

To stay below the backpressure point, the node applies a token bucket to host-initiated multicast chat: a burst of 8, refilling at 10 messages per second. A host that exceeds it gets `-ERR E_RATE_LIMITED`.

## Scale

Thread itself sets the outer limits (design §3.3): at most 32 routers; up to 511 children per router in the specification but 64 in OpenThread's default; about 16,384 devices in theory; and Thread keeps 16–23 routers active on its own. The design's practical target is 32–250 nodes before multicast storms and routing overhead dominate.

Design §8 estimates practical limits by use case:

| Use case | Recommended maximum nodes | Bottleneck |
|---|---|---|
| Active chat, everyone sending | 30–50 | Multicast storm, radio collisions |
| Mixed chat, about 10% active | 200–300 | Router memory, routing table |
| Periodic M2M command and control | 500+ | Message frequency |
| Passive sensor reporting | 1000+ | Needs sleepy end devices and staggered reporting |

Its multicast arithmetic puts the ceiling at roughly **50 nodes each chatting at 1 message per second** before collisions degrade the channel. All channels share one Thread network, so they share that budget.

Design §11.6 and the E-G phase refined this: forwarding-level suppression is Thread's MPL; the application adds sender and counter de-duplication (tables sized at 40 entries for a 32+ node target) and a jittered announce so a healed partition does not announce in lockstep. The design suggests that above about 30 active senders, traffic should move to a border-router-backed publish/subscribe service (not built).

{{< alert context="info" text="These scale figures are design estimates. The largest bench so far has four nodes; the planned 32+ node soak (staggered boot, 24 hours of paced chat, hourly leader kills) is written up in <code>firmware-idf/README.md</code> but has not been run." />}}
