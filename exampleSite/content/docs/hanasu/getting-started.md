---
weight: 50
title: "Getting Started"
description: "From zero to two Hanasu nodes chatting on a private channel: build, flash, open the host link, and run the first commands."
icon: "rocket_launch"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "getting-started"]
---

This walkthrough takes you from an empty bench to two nodes exchanging encrypted chat on a channel of your own. Two ESP32-C6 boards are the shortest path. An MG24 can stand in for either one. Paths are relative to the Hanasu reference design, `reference-designs/MagNET_Thread_COaP_hanasu_esp32c6/`, unless noted otherwise.

## Prerequisites

- **Two boards** from [Boards & Builds](/docs/hanasu/boards/): XIAO ESP32C6, M5NanoC6, or XIAO MG24, in any mix.
- **The whole `reference-designs/` tree, not just the Hanasu folder.** The C6 build reads `../../MagNET_M5DialFiddlerCrab/magnet-common.ini` and pulls the `forth` component from `../../MagNET_M5DialFiddlerCrab/ESPIDFORTH/components`. The role-bundle engine also comes from `MagNET_M5DialFiddlerCrab/components`.
- **For ESP32-C6:** PlatformIO. It installs the pinned toolchain itself (`espressif32@6.9.0`, IDF 5.3.1).
- **For XIAO MG24:** a Zephyr workspace set up as in `firmware-zephyr/README.md` (west, Zephyr SDK 1.0.1, `hal_silabs` blobs), plus the Silicon Labs Arduino core's OpenOCD for flashing.
- **Host tools:** Python 3 with `pyserial`. `tools/ble_hcp.py` also needs `bleak`, and `tools/mnpkg.py` needs `cryptography`.

## 1. Know which port is which

{{< alert context="warning" text="On a multi-board USB hub, choose ports by <strong>USB serial number</strong>, never by path or by &quot;the first usbmodem&quot;. Paths change with plug order and hub topology. Every ESP32 USB-JTAG board enumerates with the same VID/PID and description. And simply opening an ESP32's USB-JTAG port can reset that board, so opening the wrong one disturbs whatever it is running." />}}

1. List the attached devices with their hardware IDs:

   ```bash
   pio device list
   ```

   Each entry's `Hardware ID` line includes `SER=<serial>`. Write down which serial number belongs to which board, and map it to the current port path before each session.

2. If you use `tools/hcp.py`, its `list` and `all` commands skip ports whose path contains a substring from `MAGNET_HCP_SKIP` (comma-separated). Set it to keep the tools off boards that are not Hanasu nodes.

## 2. Build and flash an ESP32-C6

1. Go to the IDF tree:

   ```bash
   cd firmware-idf
   ```

2. Pick the environment for your board and build-and-flash it to the port you identified in step 1:

   ```bash
   # XIAO ESP32C6: always a *_xiao env (it enables the RF switch)
   pio run -e esp32c6_xiao -t upload --upload-port /dev/cu.usbmodemXXXX

   # M5NanoC6 / DevKit: the plain env
   pio run -e esp32c6 -t upload --upload-port /dev/cu.usbmodemYYYY

   # Want to provision from a phone instead of USB? Use a BLE env:
   pio run -e esp32c6_ble -t upload --upload-port /dev/cu.usbmodemYYYY
   ```

3. On first boot, a node with no peers self-promotes to Thread **leader**. The README's single-node bring-up saw this about 33 s after boot, followed by `!ROLE leader` and then `!STATE READY`. A second node attaches to it as a child and is then promoted to router.

{{< alert context="info" text="If you edit any <code>sdkconfig.defaults*</code> file, delete the cached <code>sdkconfig.&lt;env&gt;</code> before rebuilding, or PlatformIO silently keeps the old configuration." />}}

## 3. Build and flash a XIAO MG24 (optional)

1. Activate the Zephyr workspace and build. The Thread-only variant is shown here. Add `-- -DEXTRA_CONF_FILE=ble.conf` for BLE provisioning.

   ```sh
   cd ~/zephyrproject && . .venv/bin/activate && export ZEPHYR_SDK_INSTALL_DIR=~/zephyr-sdk-1.0.1
   APP=<path to>/firmware-zephyr
   west build --sysbuild -b xiao_mg24 $APP -d build/mnota
   ```

2. Flash MCUboot and the app. Stock OpenOCD has no MG24 support, so point west at the OpenOCD bundled with the Silicon Labs Arduino core:

   ```sh
   OO=~/Library/Arduino15/packages/SiliconLabs/tools/openocd/0.12.0-arduino1-static
   west flash -d build/mnota -r openocd --openocd $OO/bin/openocd --openocd-search $OO/share/openocd/scripts
   ```

Build variants and the memory budget are on [Boards & Builds](/docs/hanasu/boards/#xiao-mg24-zephyr-build-variants). The full MG24 story is on [MG24 / Zephyr](/docs/hanasu/mg24-zephyr/).

## 4. Open the host link

The host link is a plain line protocol at **115200** baud. Each command is one line, and each command gets exactly one `+OK…` or `-ERR…` reply.

- **ESP32-C6.** The C6's USB-serial-JTAG bridge is on the chip itself. The host must assert DTR. pyserial does this by default. A bare `open(2)` does not, and you then receive nothing (`tools/uartpipe.py` exists to work around this for non-Python hosts). **Opening the port usually resets the node**, and the peer table lives only in RAM, so `PEERS` reads empty right after you connect until traffic arrives.
- **XIAO MG24.** HCP runs on USART0, bridged to USB by a SAMD11. **The bridge forwards only while DTR is asserted**, in both directions. A DTR-low open looks exactly like a dead board. The bridge injects one `0x00` on open, which the firmware drops. It buffers nothing while the port is closed. Pace long writes (32 B every 5 ms), never call `flush()`, and **keep one line in flight**: wait for each reply before sending the next. Opening this port does not reset the node.

Any of these works:

```bash
pio device monitor -b 115200 -p /dev/cu.usbmodemXXXX          # interactive
python3 tools/hcp.py /dev/cu.usbmodemXXXX STATUS               # one line, print the reply
python3 tools/hcp.py /dev/cu.usbmodemXXXX --watch 20           # stream the console for 20 s
python3 host-sdk/python/magnet_cli.py /dev/cu.usbmodemXXXX     # terminal chat client
```

HCP mode does not echo what you type, so the reply line is the only feedback.

## 5. First commands

Run these on each node, one line at a time:

```text
CAPS         → +OK proto=2.1 fw=0.7.0-eh maxline=512 … verbs=STATUS,CAPS,HELP,… mode=HCP
STATUS       → +OK state=READY role=leader channel=magnet peers=1 name=- id=1fa5d82e ble=off
WHOAMI       → +OK id=1fa5d82e name=- fw=0.7.0-eh
NAME alice   → +OK
PEERS        → # peer 7c0e19a4 bob fd…:…  last-seen=4s ago
               +OK
MESH         → # mesh role=leader partition=0x… rloc16=0x… chan=24 pan=0x4d4e
               # mesh ml-eid=fd…:… mcast=ff05::…
               # mesh neighbor rloc16=0x… rssi=… lqi=… age=…s …
               +OK
CHAT hello   → +OK
```

The IDs, addresses and names above are illustrative. `NAME` takes 1–16 characters with no spaces and is announced on the mesh, so peers show `alice` instead of a hex ID. On the other node the chat arrives as an unsolicited event:

```text
!CHAT magnet 1fa5d82e alice hello
```

`CHAT` is accepted only in `READY` (or queued with `+QUEUED n` in `DEGRADED`). Otherwise it answers `-ERR E_BAD_STATE <state>`. For a direct message, take the peer's IPv6 address from `PEERS` and send `DM <ipv6> <text>`. The full verb list is on the [HCP](/docs/hanasu/hcp/) page.

## 6. Move to a private channel

A fresh node sits on the well-known **`magnet`** channel. Its traffic is readable by anyone nearby, and the node says so with `!WARN default-channel-insecure`. Give both nodes the same credential:

```text
CHANNEL SET correct-horse-battery-staple
# deriving channel key (Path B takes ~seconds)...
+OK correct-horse-ba selector=XXXX path=B
```

(The channel *name* is the first 16 characters of a passphrase, the first word of a seed phrase, or `qr-channel` for a `qr:` secret.)

The node detects the credential type automatically:

| Credential | Path | Cost |
|---|---|---|
| `qr:<base64 of 32 random bytes>` | A | no stretch. Preferred on MG24 |
| a phrase of 12 or more words | C | HKDF only |
| anything else (a passphrase) | B | PBKDF2, 100,000 iterations: ≈7.9 s on the C6, 10.6 s on the MG24 |

Run the same `CHANNEL SET` on the second node and confirm that both report the same `selector` with `CHANNEL SHOW`. The reply never echoes the secret. The channel persists across reboots. `CHANNEL SET` is a privileged verb: over USB, physical access is the trust boundary, and over BLE it needs a bonded link. How the keys are derived is covered under [Security](/docs/hanasu/security/).

If a node ends up on the wrong channel, `FACTORY RESET CONFIRM` erases every provisioned setting (channel, name, admin keys, script, identity key, BLE bonds) and reboots it as a fresh node.

## 7. Provision over BLE instead (optional)

A BLE build (`esp32c6_ble`, the `_ble_led` variants, or MG24 with `ble.conf`) advertises the HCP GATT service only while the node is still on the default channel. It prints `# ble: provisioning window open` at boot. The service UUID is `6d61676e-2d68-6370-0001-000000000000`: commands go to characteristic `…0001`, replies and events come back as notifications on `…0002`, and reading `…0003` (encryption required) is what makes a phone pair.

1. Read-only verbs (`STATUS`, `WHOAMI`, `CAPS`, `CHANNEL SHOW`) work before pairing. Privileged verbs answer `-ERR E_NOT_BONDED pair with this node first`.
2. Pair (Just Works). **Only the operating system's pairing prompt can complete a bond.** On Android it often shows up as a notification ("Tap to pair with MagNET-xxxx") rather than a dialog.
3. Send `NAME` and `CHANNEL SET` over the bonded link. On a provisioning-only build, BLE then shuts down and the node leaves BLE on purpose.

From a laptop, `tools/ble_hcp.py` drives the same binding:

```bash
python3 tools/ble_hcp.py --id 1fa5d82e --pair "WHOAMI" "NAME alice"
```

`--id` (the 8-hex device ID from `WHOAMI`) is required. Several bench nodes advertise the same service, and a host already bonded to one of them gets an encrypted link silently. Without `--id`, a privileged verb lands on whichever node answers first. Select nodes by service UUID or address, never by the `MagNET-xxxx` name: macOS and iOS cache the GAP name.

The Flutter companion app (`magnet_app`) does this flow on a phone: scan, connect, read `STATUS`/`WHOAMI`/`CHANNEL SHOW`, set a name, and provision with a passphrase, seed phrase or `qr:` secret. The pitfalls (stale bonds after a factory reset, OEM-specific prompts, untested iOS) are written up in `docs/BLE-PAIRING.md` and summarized under [Security](/docs/hanasu/security/).

## 8. Host tools

| Tool | What it does |
|---|---|
| `tools/hcp.py` | Talks to a node over USB serial: `list`, one-shot commands, `--reboot` (RTS pulse, waits for READY), `--watch SECS`, `--time` (time to response), `all <cmd>` across the bench, and `synctime` (seeds the [mesh clock](/docs/hanasu/mesh-time/) with `TIME SET`). Exits 1 on `-ERR`. |
| `host-sdk/python/magnet_hcp.py` | The Python SDK. `MagnetNode` matches replies by `@tag`, raises `HCPError` with the `E_*` code, and routes `!` events to `node.on(...)` callbacks. Needs only pyserial. |
| `host-sdk/python/magnet_cli.py` | A small terminal chat client on the SDK: `/status`, `/peers`, `/join <cred>`, `/dm`, `/raw`, `/quit`. |
| `tools/ble_hcp.py` | HCP over BLE-GATT with bleak. `--id` is required. `--pair` forces pairing. |
| `tools/xfer.py` | Reference driver for [Type 6 extended transfer](/docs/hanasu/extended-transfer/): `send`, `recv`, `loopback`. |
| `tools/chat-bench/` | `bridge.py` plus a browser page with one chat pane per attached node, per-message latency, and photo transfer. |
| `tools/bundle_push.py` | Installs a signed role bundle over HCP (`BUNDLE BEGIN/ADD/COMMIT`). |
| `tools/mnpkg.py` / `tools/ota_push.py` | Build and verify `.mnpkg` OTA packages, then send one across the mesh. See [OTA Operations](/docs/hanasu/ota-operations/). |
| `tools/soak.py` | Long-running whole-bench soak: holds every port open, drips chat, samples `STATS`/`SYSINFO`. |
| `tools/uartpipe.py` | Exposes one node's serial port as a FIFO pair for non-Python hosts. |

`tools/hcp.py` opens and closes the port for each call, which resets a C6 every time. For anything long-running, hold one connection open with the SDK, `soak.py` or `uartpipe.py`.

## Where to next

- [Host Control Protocol](/docs/hanasu/hcp/): every verb, event and error code.
- [Mesh Time](/docs/hanasu/mesh-time/): a Thread-only mesh has no NTP, so run `python3 tools/hcp.py synctime` once.
- [Forth & Bots](/docs/hanasu/forth-and-bots/): `FORTH` drops the link into the Forth REPL, and `.hcp` returns.
