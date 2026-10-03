---
weight: 40
title: "Boards & Builds"
description: "The boards Hanasu runs on, the PlatformIO environments and Zephyr build variants for each, and what every build switches on."
icon: "developer_board"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "hardware"]
---

Hanasu has two firmware trees and one MagNET core. `firmware-idf/` builds the node for the **ESP32-C6** on ESP-IDF (through PlatformIO). `firmware-zephyr/` builds it for the **Seeed XIAO MG24** (Silicon Labs EFR32MG24) on Zephyr, and it compiles the *unmodified* MagNET core and ESPIDFORTH sources straight out of `firmware-idf/`, so the two targets cannot drift. Every board speaks the same [HCP](/docs/hanasu/hcp/) and joins the same Thread mesh.

## Supported boards

| Board | Chip | Firmware tree | Good for |
|---|---|---|---|
| **Seeed XIAO ESP32C6** | ESP32-C6, 4 MB flash | `firmware-idf/` | The general-purpose node. It is also the only C6 with an OTA-capable environment today. |
| **M5Stack M5NanoC6** | ESP32-C6, 4 MB flash | `firmware-idf/` | Bench and companion nodes. It has an on-board SK6812 RGB LED for the lighting build. |
| Other ESP32-C6 boards (for example DevKitC-1) | ESP32-C6 | `firmware-idf/` | Use the plain `esp32c6` environments. The image header is pinned to 4 MB, which is also safe on 8 MB parts. |
| **Seeed XIAO MG24** | EFR32MG24, 256 KB RAM | `firmware-zephyr/` | A second silicon vendor in the same mesh. It has MCUboot-based OTA. RAM is very tight. |

### XIAO ESP32C6

The XIAO routes its 802.15.4 radio through an RF switch. The `*_xiao` environments drive it before the radio starts: GPIO3 low enables the switch, and GPIO14 low selects the built-in ceramic antenna. **Without that, the XIAO meshes at near-zero range**, so always use a `xiao` environment on this board. The board has only a plain active-low LED on GPIO15. Forth can reach it through `gpio-output` / `gpio-set`. The `esp32c6_xiao_ble_led` build instead drives an external NeoPixel on GPIO2, which is the pixel the bench "xray" nodes carry.

### M5NanoC6

The NanoC6 has no RF switch, so it uses the plain `esp32c6*` environments. Its SK6812 LED (data G20, power-enable G19) is driven by the `esp32c6_ble_led` build. The README notes that the blue case muddies the hue, which is why the `LED` verb can also strobe: the blink rate carries meaning that the color alone does not.

### XIAO MG24

HCP runs on USART0, and the board's SAMD11 chip bridges it to USB. That bridge has rules of its own (DTR, pacing, one line in flight). They are covered on the [Getting Started](/docs/hanasu/getting-started/#open-the-host-link) page and in more depth on the [MG24 / Zephyr](/docs/hanasu/mg24-zephyr/) page. Differences from the C6 that the README lists:

- A Path B passphrase stretch (100k PBKDF2) takes **10.6 s**. Prefer `qr:` (Path A) credentials on MG24 nodes.
- There is no WS2812 LED (`MN_ENABLE_LED=0`), so the `LED` verb answers `E_UNSUPPORTED`. The XIAO's PA7 LED is reachable from Forth as `gpio` pin 7.
- Bot mode is compiled out (`MN_ENABLE_BOTS=0`).
- `esp_reset_reason` reports Zephyr hwinfo reset-cause bits, not IDF's enum.

## ESP32-C6: PlatformIO environments

All environments extend `magnet_base` from `MagNET_M5DialFiddlerCrab/magnet-common.ini`. That base pins `espressif32@6.9.0` with framework-espidf `3.50301.0` (IDF 5.3.1) and sets `monitor_speed = 115200`. Every environment also builds with `-DESPIDFORTH_ENABLE_TESTS=1` and `board_upload.flash_size = 4MB`. The default environment is `esp32c6`.

| Environment | Board | Thread | BLE | Extras | Partition table |
|---|---|---|---|---|---|
| `esp32c6` | NanoC6 / devkit | yes | none | | `partitions.csv` |
| `esp32c6_xiao` | XIAO C6 | yes | none | RF-switch bring-up | `partitions.csv` |
| `esp32c6_ble` | NanoC6 / devkit | yes | provisioning only | | `partitions.csv` |
| `esp32c6_ble_resident` | NanoC6 / devkit | yes | resident (companion) | | `partitions.csv` |
| `esp32c6_ble_resident_bots` | NanoC6 / devkit | yes | resident (companion) | bot mode (`MN_ENABLE_BOTS=1`) | `partitions.csv` |
| `esp32c6_ble_led` | NanoC6 | yes | provisioning only | on-board SK6812 (`MN_ENABLE_LED=1`, G20/G19) | `partitions.csv` |
| `esp32c6_xiao_ble_led` | XIAO C6 | yes | provisioning only | RF switch + external NeoPixel on GPIO2 | `partitions.csv` |
| `esp32c6_xiao_ble_led_ota` | XIAO C6 | yes | provisioning only | everything above + mesh OTA (`MN_ENABLE_OTA=1`) | `partitions_ota.csv` |
| `esp32c6_noot` | any C6 | **compiled out** | none | footprint comparison only | `partitions.csv` |

What the flags mean:

- **Provisioning-only BLE** (`MN_ENABLE_BLE=1`). The node advertises the HCP GATT service only while it is still on the default `magnet` channel. `CHANNEL SET` tears the BLE controller down, which hands the radio and RAM back to Thread. A provisioned node skips BLE at boot, so a power cycle cannot re-open a bonding window. The environment layers `sdkconfig.defaults.ble` on top of the base defaults.
- **Resident BLE** (`MN_BLE_RESIDENT=1`). BLE stays up after provisioning, so a phone can use this one node as its live window into the mesh. The firmware README says to flash **exactly one** bench node with it. It re-opens the bonding window on every boot, so it is a bench/diagnostic anchor, not a fielded node. Privileged verbs still require a bonded link.
- **Bot mode** (`MN_ENABLE_BOTS=1`). This compiles in the opt-in auto-responder, the `BOTMODE` verb and the `botmode` Forth word. It has its own environment so that the soaked images stay bit-identical. Measured cost: +1,718 B flash, +220 B RAM. See [Forth & Bots](/docs/hanasu/forth-and-bots/).
- **LED** (`MN_ENABLE_LED=1`). This adds the `LED` verb and the `led!` / `led-pat!` Forth words.
- **OTA** (`MN_ENABLE_OTA=1`). This adds the `.mnpkg` package receiver (`magnet_ota_idf.c`), the dual-slot table and IDF app rollback (`sdkconfig.defaults.ota` sets `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`). The environment also sets `MN_PKG_BOARD=0x0102` and the 4-part version the image reports (`MN_FW_VER_*`, currently 0.7.0+1). That version **must match** the `--version` you give `tools/mnpkg.py` for the build.
- **No OpenThread** (`MN_ENABLE_OPENTHREAD=0`). Use this to measure what Thread costs. For a truly clean baseline, the README also says to set `CONFIG_OPENTHREAD_ENABLED=n` and rebuild from scratch.

The BLE environments pin `upload_speed = 115200`, because the on-die USB-serial-JTAG can refuse the 460800 re-baud after a hub replug.

{{< alert context="warning" text="PlatformIO caches <code>sdkconfig.&lt;env&gt;</code> in <code>firmware-idf/</code>. Edits to any <code>sdkconfig.defaults*</code> file are ignored until you delete that environment's cached file (for example <code>rm sdkconfig.esp32c6</code>) and rebuild." />}}

### Partition tables

The stock ESPIDFORTH table has a 1 MB factory app, and an OpenThread FTD + CoAP + mbedTLS + Forth image does not fit in it. Both Hanasu tables fit a 4 MB part:

`partitions.csv` (every environment except `_ota`):

| Partition | Size | Purpose |
|---|---|---|
| `nvs` | 24 KB | Thread dataset, identity key, counters, settings |
| `phy_init` | 4 KB | RF calibration |
| `factory` | 2.625 MB | firmware |
| `scripts` (LittleFS) | 960 KB | persisted Forth scripts |

`partitions_ota.csv` (`esp32c6_xiao_ble_led_ota`):

| Partition | Size | Notes |
|---|---|---|
| `nvs` | 24 KB | same offset as before, so identity and bonds survive the move |
| `otadata` | 8 KB | |
| `phy_init` | 4 KB | |
| `ota_0` / `ota_1` | 1792 KB each | dual app slots |
| `scripts` (LittleFS) | 384 KB | reserved, unused today |

A partition table cannot change over the air. Moving a node onto `partitions_ota.csv` therefore takes **one USB flash** of the `_ota` environment. After that, firmware arrives as signed `.mnpkg` packages over the mesh. See [OTA](/docs/hanasu/ota/) and [OTA Operations](/docs/hanasu/ota-operations/).

### Footprint (as reported in the firmware README)

| Measurement | Value |
|---|---|
| Static RAM, fw 0.7.0-eh | 137.1 KB of 320 KB (41.8%) |
| Flash, fw 0.7.0-eh | 824.1 KB of the 2.625 MB factory partition (29.9%) |
| Free heap, resident-BLE build, worst case (E-G) | 161.7 KB free / 160.5 KB min-ever |
| Mesh time (all builds) | +2,790 B flash / +620 B RAM |

## XIAO MG24: Zephyr build variants

Everything builds with `--sysbuild`, which produces MCUboot plus the app signed for slot0. `sysbuild.conf` is always applied. It turns on MCUboot with ECDSA P-256 signatures and **swap-using-move**, and keeps MCUboot quiet on USART0. App options are Kconfig symbols set from conf files, not `-D` flags, because sysbuild forwards conf files to the app image but silently drops arbitrary `-D` cache variables.

| Conf file | Use it as | What it does |
|---|---|---|
| `prj.conf` | always (base) | Thread FTD + CoAP, §11.1 crypto on PSA, MCUboot image manager (confirm after a healthy swap), Forth via C++. Console, log, shell and printk are **off**, because USART0 is both the HCP link and Zephyr's console. |
| `ble.conf` | `-DEXTRA_CONF_FILE=ble.conf` | The BLE-GATT HCP binding, provisioning-only. One connection, Just Works bonding (up to 4 bonds), ATT MTU 247, long writes, RAIL multiprotocol so BLE and 802.15.4 run together. Shrinks the malloc arena to 52 KB to pay for the BT host. |
| `ble-resident.conf` | together with `ble.conf` | Sets `CONFIG_MN_BLE_RESIDENT=y`. This is the companion node: BLE survives provisioning. |
| `debug.conf` | add to `EXTRA_CONF_FILE` | Console + minimal logging, asserts, thread names, MPU stack guard, extra exception info. **Breaks HCP framing.** Bring-up only. Takes 4 KB off the malloc arena. |
| `release.conf` | add to `EXTRA_CONF_FILE`, with `-DMN_SIGN_OFFLINE=1` and the public MCUboot key | Sets `CONFIG_MN_PKG_RELEASE_KEYS=y`, so the node trusts the offline release OTA keys instead of the committed DEV keys. The app is left unsigned for `tools/mcuboot_sign.py` on the signing machine. |

The README's three standard builds:

```sh
west build --sysbuild -b xiao_mg24 $APP -d build/mnota                                                       # Thread only
west build --sysbuild -b xiao_mg24 $APP -d build/mnprov   -- -DEXTRA_CONF_FILE=ble.conf                      # + BLE provisioning-only
west build --sysbuild -b xiao_mg24 $APP -d build/mnbleota -- -DEXTRA_CONF_FILE="ble.conf;ble-resident.conf"  # companion
```

The Kconfig menu also has `CONFIG_MN_OTA_FORCE_UNHEALTHY`, a test-only switch that never confirms an OTA image. It exists to exercise rollback.

### MG24 memory and flash

256 KB of RAM, and "every KB is spoken for":

| | Thread | +BLE |
|---|---|---|
| Static RAM | 97.9% | 98.8% |
| malloc arena | 80 KB | 56 KB |
| Forth heap | 32 KB | 16 KB |
| malloc low-water (bundle re-apply + COMMIT) | 34 KB | 18.9 KB |

Flash map (`boards/mg24_partitions.dtsi`, shared with MCUboot): MCUboot 48 KB at 0, slot0 712 KB at 0xC000, slot1 712 KB at 0xBE000, storage 64 KB at 0x170000. The storage partition is unchanged from the pre-MCUboot layout, so identity and bonds survive the move to MCUboot.

{{< alert context="danger" text="The release keys committed in <code>tools/keys/</code> and MCUboot's default key are <strong>DEV keys</strong>. Anyone with the repository can sign firmware for a node built with them, and such nodes say so at boot with <code>!WARN ota-dev-keys</code>. Replace them before any node leaves the bench. See <a href='/docs/hanasu/security/'>Security</a>." />}}

## Choosing a build

- **First bench, no phone:** `esp32c6_xiao` on XIAO C6, `esp32c6` on NanoC6, or `mnota` on MG24. Provision over USB with `CHANNEL SET`.
- **Provision from a phone:** `esp32c6_ble` (or a `_ble_led` variant), or `mnprov` on MG24.
- **A phone's standing window into the mesh:** one `esp32c6_ble_resident` node (or `mnbleota`), and only one.
- **Mesh OTA on a C6:** `esp32c6_xiao_ble_led_ota`, flashed once over USB.
- **Bot experiments:** `esp32c6_ble_resident_bots`. Keep it off fielded nodes.
