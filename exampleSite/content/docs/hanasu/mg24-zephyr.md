---
weight: 140
title: "XIAO MG24 on Zephyr"
description: "How the unmodified Hanasu core runs on the Silicon Labs EFR32MG24 under Zephyr: compat layer, OpenThread, MCUboot, BLE, the host link, PSA crypto, and the traps found along the way."
icon: "memory"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "zephyr"]
---

Hanasu's second target is the **Seeed XIAO MG24**, a Silicon Labs EFR32MG24 running Zephyr with MCUboot. Its firmware lives in `firmware-zephyr/` of the Hanasu repo. It does not fork the protocol: it compiles the **unmodified** MagNET core and the ESPIDFORTH engine straight out of `firmware-idf/`, so the ESP32-C6 and MG24 builds cannot drift apart. Only the platform glue lives in `firmware-zephyr/`.

## Why a second chip

The MG24 brings a different vendor's 802.15.4 radio, a different RTOS, a different crypto stack (PSA on a Secure Engine instead of mbedTLS on the C6), and a bootloader that verifies its own image signatures. Running the same core on it keeps the protocol honest: every key derivation and signature must be byte-identical across the two chips, or the mesh does not interoperate.

The port was validated on hardware against the ESP32-C6 bench on 2026-09-28 and 29: a mixed mesh with encrypted chat in both directions, a 50 KB Type 6 transfer arriving SHA-256-identical in both directions, signed role bundles (Ed25519 and HMAC) with tamper rejection and boot re-apply, and BLE bonding, persistence and long writes with BLE and Thread running at the same time. Mesh OTA in both directions followed on 2026-09-29 and 30 (see [Over-the-Air Updates](/docs/hanasu/ota/#hardware-validation)).

## How the same core compiles on Zephyr

`firmware-zephyr/CMakeLists.txt` points straight at the IDF tree and compiles its sources into the Zephyr app:

| Source | From |
|---|---|
| `magnet_core.c`, `magnet_envelope.c`, `magnet_pkg.c`, `magnet_link.c`, `magnet_forth.c`, `magnet_xfer.c`, `magnet_bot.c`, `magnet_ot.c` | `firmware-idf/components/magnet/` |
| `forth_core.cpp` | `firmware-idf/components/forth/` |
| `craw_role_bundle.c`, TweetNaCl, cJSON | The role-bundle engine, as its own library (`mn_bundle`) |
| `src/main.c`, `src/magnet_crypto_psa.c`, `src/ota.c`, `src/magnet_ble_zephyr.c` | MG24-specific |
| `compat/` | The ESP-IDF and FreeRTOS APIs the shared sources call |

`compat/include` is the only source of `esp_*` and `freertos/*` headers on this target. Only what the shared files actually call is implemented; anything else fails to link, loudly.

| Compat piece | What it maps |
|---|---|
| `compat/src/freertos_zephyr.c` | Tasks, queues, semaphores, mutexes and timers on Zephyr kernel objects |
| `compat/src/nvs_zephyr.c` | The IDF NVS API over Zephyr settings, keys stored as `mn/<namespace>/<key>` |
| `compat/src/esp_misc_zephyr.c` | Time, randomness, reboot, heap, chip and flash queries, flat-numbered GPIO |
| `compat/include/esp_openthread_lock.h` | The OpenThread API lock, mapped to Zephyr's `openthread_mutex` |

The FreeRTOS shim closes the semantic gaps rather than hiding them:

| FreeRTOS behavior | On Zephyr |
|---|---|
| Ticks | `TickType_t` is milliseconds, so tick math means what it did at 1 kHz on IDF |
| Priorities | FreeRTOS is higher-number-wins, Zephyr lower-number-wins; `xTaskCreate` inverts the range |
| Stack sizes | In bytes, as on IDF |
| Timer callbacks | A raw `k_timer` expiry runs in ISR context, so expiries are bounced onto a work queue to keep thread context |
| Mutexes | `k_mutex` is always recursive, so plain and recursive mutexes are the same object |
| Self-deleting tasks | A thread cannot free its own stack, so it parks and the next `xTaskCreate` reaps it |

OpenThread keeps its dataset in the same settings store under `ot`, so `FACTORY RESET`, which erases MagNET namespaces as on IDF, leaves Thread alone.

The Forth engine is compiled with `ESP_PLATFORM=1` so it takes its re-entrancy lock (this target is multithreaded), and with `MAX_WORD_LEN=32`, which saves 16 KB of dictionary. The longest word any MagNET or bundle code registers is 14 characters.

## Building and flashing

Setup is a Zephyr workspace at `~/zephyrproject` (Zephyr `main`, pinned at `9f0253dc`, with a narrow project filter), Zephyr SDK 1.0.1, and the Silicon Labs blobs (`west blobs fetch hal_silabs` for RAIL and the BT controller). The Silabs 802.15.4 driver exists only on `main`, not in v4.4.x; stay past `a9f12d74`, which fixes SED/SSED MIC handling. The full setup is in `firmware-zephyr/README.md`.

Everything builds with `--sysbuild` (MCUboot plus the app signed for slot0):

| Variant | Command (`west build --sysbuild -b xiao_mg24 <app> -d <dir>` …) |
|---|---|
| Thread only | (no extra conf) |
| BLE provisioning only | `-- -DEXTRA_CONF_FILE=ble.conf` |
| Companion (BLE resident) | `-- -DEXTRA_CONF_FILE="ble.conf;ble-resident.conf"` |
| Crash reports on the console | add `debug.conf` (breaks HCP framing; bring-up only) |
| Release | add `release.conf` plus offline signing; see the [operator guide](/docs/hanasu/ota-operations/#build-a-release) |

App options are **Kconfig** (`firmware-zephyr/Kconfig`), not `-D`: sysbuild forwards conf files to the app image but silently drops arbitrary `-D` cache variables. The options are `MN_BLE_RESIDENT`, `MN_OTA_FORCE_UNHEALTHY` (test builds only) and `MN_PKG_RELEASE_KEYS`. The image version comes from `firmware-zephyr/VERSION`.

Flashing goes over SWD. Stock OpenOCD has no MG24 support and pyOCD's pack index lacks the part, so use the OpenOCD shipped with the Silicon Labs Arduino core:

```sh
OO=~/Library/Arduino15/packages/SiliconLabs/tools/openocd/0.12.0-arduino1-static
west flash -d build/mnota -r openocd --openocd $OO/bin/openocd --openocd-search $OO/share/openocd/scripts
```

`firmware-zephyr/tools/zephyr.p` wraps build, flash, RAM ranking, fault decoding and ESP-API inventory as Pop-11 procedures.

## OpenThread on the EFR32 radio

The MG24 runs OpenThread through Zephyr's OpenThread L2 as a full Thread device (FTD) with CoAP, started manually so MagNET configures the network first. The Silabs 802.15.4 driver only speaks Zephyr's `ieee802154` API, which is why the L2 is used.

| Setting | Why |
|---|---|
| `CONFIG_OPENTHREAD_MAX_STATECHANGE_HANDLERS=3` | OpenThread allows one state-changed handler by default and Zephyr's L2 takes it; without room for MagNET's, every `!ROLE` event silently disappears |
| Trimmed `NET_PKT` / `NET_BUF` counts | Zephyr's IP stack only ferries single 802.15.4 frames between the driver and OpenThread; MagNET's CoAP lives in OpenThread's own message pool |
| `CONFIG_OPENTHREAD_SECURITY_CUSTOM_CONFIG=y` | The default security profile makes every PSA and mbedTLS option unsettable and has no HKDF; the custom profile spells the list out |
| `CONFIG_SILABS_SISDK_RAIL_MULTIPROTOCOL=y` (BLE builds) | Concurrent BLE and 802.15.4 needs RAIL's multiprotocol library |

The XIAO MG24's RF switch (PB5 enable, PB4 antenna select) is set by gpio-hogs in the board devicetree, so unlike the XIAO C6 the firmware does nothing for it. Radios still come up last, in the same bring-up order as IDF: transport, Forth heap, storage, core and vocabulary, host link, then radios.

{{< alert context="warning" text="On Zephyr the OpenThread work queue is already running when MagNET configures the stack, and it is a cooperative thread that preempts the moment the lock drops. <code>magnet_ot.c</code> therefore publishes its instance pointer before releasing the OpenThread lock. Publishing after the unlock lets the state-changed callback run first and dereference NULL." />}}

## MCUboot and the flash map

`boards/mg24_partitions.dtsi` is shared by the app overlay and MCUboot's overlay, so the two can never disagree. The part has 1536 KB of flash in 8 KB pages:

| Partition | Offset | Size | Holds |
|---|---|---|---|
| `mcuboot` | `0x000000` | 48 KB | The bootloader |
| `slot0` | `0x00C000` | 712 KB | The running image |
| `slot1` | `0x0BE000` | 712 KB | OTA download and swap partner |
| `storage` | `0x170000` | 64 KB | Settings: identity key, bonds, channel, OpenThread dataset |

`storage` stays where the pre-MCUboot build put it, so moving a node to MCUboot keeps its identity and bonds.

`sysbuild.conf` enables MCUboot with ECDSA P-256 signatures and **swap-using-move**. MCUboot's console output is turned off in `sysbuild/mcuboot.conf`, because USART0 is the HCP link.

Sysbuild traps the port hit:

- **Swap mode.** The default swap-using-offset expects the upgrade image one sector into slot1, and silently ignores an image written at the slot start. Move mode takes images at the slot start; slot0 keeps one spare sector for the shuffle.
- **MCUboot's overlay.** Supplying `sysbuild/mcuboot.overlay` *replaces* MCUboot's default overlay, which is what points its code at the boot partition. Without `chosen { zephyr,code-partition = &boot_partition; }` MCUboot links at slot0 and never runs.
- **Signing key.** With `SB_CONFIG_BOOT_SIGNATURE_KEY_FILE` unset, MCUboot uses its public DEV key. For release builds, `-DMN_SIGN_OFFLINE=1` makes `sysbuild.cmake` append `sysbuild/sign_offline.cmake` to the app's image configuration, which leaves the app unsigned for `tools/mcuboot_sign.py`. It is appended rather than set, because sysbuild's own image defaults run after `sysbuild.cmake`.
- **`-D` variables.** Sysbuild does not forward arbitrary `-D` cache variables to the app image; use Kconfig and conf files.

The health policy (`src/ota.c`): a swapped-in image runs in MCUboot TEST state and is confirmed only once the node is healthy; if not within 10 minutes it reboots and MCUboot rolls back. Measured: swap, TEST boot, READY and confirm in about 11 seconds.

## BLE companion build

`ble.conf` adds the Zephyr BT host with the Silicon Labs controller and a BLE-GATT HCP binding (`src/magnet_ble_zephyr.c`) with the same service and UUIDs as the C6's NimBLE one. `ble-resident.conf` adds `CONFIG_MN_BLE_RESIDENT`: BLE stays up for the life of the node, so a phone can use it as its live window into the mesh. Without it, BLE advertises only while the node is still on the default channel.

| Choice | Reason |
|---|---|
| Just Works, not `BT_SMP_SC_ONLY` | SC-only demands authenticated (MITM) keys, which a screenless node can never produce |
| `BT_SMP_ALLOW_UNAUTH_OVERWRITE` | A phone that lost its bond may pair again |
| `BT_ATT_PREPARE_COUNT=4` | Long writes: `ADMIN ADD` with a 130-hex key exceeds one ATT payload |
| Subscription checked with `bt_gatt_is_subscribed()` at send time | Zephyr restores the stored CCC for a bonded peer, so a flag cleared on connect muted every reply after a reboot |
| Advertising restarts in the `recycled` callback | Restarting in `disconnected()` fails for lack of a free connection object |
| BT host callbacks only post notes | They run on the BT RX thread, which must never block |

Bonding is enforced per verb (`E_NOT_BONDED`), never at the ATT layer. The BT stack costs about 19 KB of RAM, paid from the malloc arena, so the BLE build halves the Forth heap to 16 KB.

## The host link

HCP runs on USART0 at 115200, bridged to USB by the board's SAMD11. USART0 is also Zephyr's default console, so console, logging, shell, printk and the boot banner are all off; any stray line would break HCP framing.

The bridge has rules every host tool must follow:

| Rule | Detail |
|---|---|
| **Assert DTR** | The bridge forwards, in both directions, only while DTR is asserted. pyserial asserts it by default; a DTR-low open looks exactly like a dead board |
| **Expect a NUL on open** | The bridge injects `0x00` when the port opens. The firmware drops NUL bytes; without that, the first command parsed as empty and was lost |
| **No reset on open** | Unlike the C6, opening the port does not reset the node |
| **Pace long writes** | 32 bytes per 5 ms, and never `flush()`: `tcdrain` can block forever under the bridge's backpressure. One unpaced 460-byte write once wedged the bridge until a USB replug |
| **One line in flight** | There is no flow control. Wait for each reply before sending the next line |
| **Nothing is buffered while closed** | Output emitted while no host has the port open is lost |

On the node side, USART0 receives by **LDMA**, not per-byte interrupts. The USART's receive FIFO is 2 bytes, and the CPU stalls longer than two character times whenever an 8 KB flash page is erased (about 15–20 ms) or BLE radio interrupts run. Interrupt-driven receive corrupted 0.9 % of lines with BLE up and lost an `XFER DATA` line during OTA. Two 384-byte buffers now ping-pong into a 1 KB ring with a 1 ms idle timeout: measured 0 of 1000 lines lost. If the host still outruns the dispatcher, the node reports `!WARN link-rx-overrun dropped=<n>`.

Transmit is polled. The SAMD11 drains the UART whether or not a host has the port open, so transmit cannot stall the way it could on the C6's on-die USB.

`tools/bundle_push.py`, `tools/ota_push.py` and `tools/ble_hcp.py` (which requires `--id`) follow these rules.

## PSA crypto

Zephyr `main` ships mbedTLS 4 / TF-PSA-Crypto, where the legacy CCM, HKDF and ECDSA APIs the C6 uses no longer exist. `src/magnet_crypto_psa.c` implements the same `magnet_crypto.h` contract on the PSA API, and on the MG24 hal_silabs dispatches PSA calls to the Secure Engine.

Interop is the point, and power-on known-answer tests check it at every boot: an RFC 6979 deterministic ECDSA P-256 signature, CRC-32, an RFC 4231 HMAC vector, Base64, and the software PBKDF2 path against PSA's one-shot PBKDF2. The well-known `magnet` channel must derive selector `82f7` on both chips.

| Issue | Resolution |
|---|---|
| The Secure Engine has no deterministic ECDSA | Signing falls back to software bignum math on the mbedTLS heap; the 1 KB default fails with `PSA_ERROR_INSUFFICIENT_MEMORY`, so `CONFIG_MBEDTLS_HEAP_SIZE=6144` |
| Each PSA call is a Secure Engine mailbox round trip (about 320 µs per HMAC) | The 100k-iteration PBKDF2 passphrase stretch took about 32 s; a software SHA-256 with pre-hashed HMAC pads, compiled `-O3`, brings it to **10.6 s** (C6: about 1 s) |
| `mbedtls_md_hmac()` is private in TF-PSA-Crypto 1.0 | The bundle engine's legacy HMAC check builds with `MBEDTLS_DECLARE_PRIVATE_IDENTIFIERS` |
| Two different headers named `magnet_crypto.h` | The core's (channel and AEAD) and TweetNaCl's (Ed25519) each get their own include path, so the bundle engine is its own Zephyr library |

Because of the PBKDF2 cost, prefer pairing or QR credentials over passphrase credentials for MG24 nodes.

## RAM budget

The MG24 has 256 KB of RAM, and every kilobyte is spoken for. Configured sizes, from `prj.conf`, `ble.conf` and `CMakeLists.txt`:

| | Thread | Thread + BLE |
|---|---|---|
| Static RAM (as built, per the README) | 97.9 % | 98.8 % |
| malloc arena | 76 KB | 52 KB |
| Kernel heap | 28 KB | 32 KB |
| Forth heap | 32 KB | 16 KB |
| mbedTLS heap | 6 KB | 6 KB |
| Main stack | 8 KB | 8 KB |

Knobs already turned: Forth `MAX_WORD_LEN=32` (dictionary 36 KB to 20 KB), trimmed net_buf counts, an 8 KB main stack (the boot bundle re-apply needs it; 4 KB smashed the stack), and a Forth heap at half the C6's 64 KB (it only backs `allot`/`create` data and showed 0 bytes used with two bundles installed). The pump task's stack is 8 KB because transfer sinks run on it and package signature checks overflowed 4 KB. Watch `SYSINFO` `min-ever`.

## Lessons learned

**Never allocate runtime objects from the kernel heap.** With BLE up, the Zephyr kernel heap is exhausted at runtime. Two bugs had this one root cause:

- The FreeRTOS shim allocated timer control blocks from the kernel heap. The OTA reboot timer came back NULL, and the fallback rebooted before the apply reply went out, so admins lost `accepted` replies, but only after the node had already sent an OTA report.
- The NVS shim allocated its key-list snapshot (about 800 bytes) from the kernel heap. A failed allocation looked exactly like "no keys": `BUNDLE LIST` came back empty and forgetting all bundles forgot nothing, at runtime only, while boot (before BLE) worked.

Both now allocate from the libc arena. Task, semaphore and timer control blocks and NVS iterators use libc; thread stacks (which need alignment and guards) and queue buffers stay on the kernel heap, allocated at init when there is room. If something on the MG24 works at boot but not later, check for kernel-heap allocation first.

**Every static buffer counts.** Timer callbacks share one event buffer, because they all run one at a time on the same timer-service thread (the FreeRTOS daemon on IDF, the compat work queue on Zephyr). A static buffer per callback cost 576 bytes each, which the BLE build cannot spare.

**Kconfig, not `-D`.** Under sysbuild, conf files reach the app image and `-D` cache variables do not. This is why `release.conf` exists.

**The image version lives in `firmware-zephyr/VERSION`.** `tools/mnpkg.py` refuses an MCUboot image whose embedded version differs from `--version`, because the post-update report compares the two.

## Known differences from the C6

| Area | MG24 |
|---|---|
| Passphrase stretch | 10.6 s instead of about 1 s |
| `esp_reset_reason` | Reports Zephyr hwinfo reset-cause bits, not IDF's enum |
| LED | No WS2812 (`MN_ENABLE_LED=0`); the XIAO's PA7 LED is reachable from Forth as `gpio` pin 7 (flat numbering: port × 16 + pin) |
| Bots | Built with `MN_ENABLE_BOTS=0` |
| Image authenticity | Two checks: the OTA package signature and MCUboot's own image signature |

One open observation: `BUNDLE CLEAR` once appeared not to persist across a reboot on the BLE build, right after `CHANNEL SET`. It has not reproduced since.
