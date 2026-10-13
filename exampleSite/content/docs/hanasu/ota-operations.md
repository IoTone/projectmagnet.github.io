---
weight: 130
title: "OTA Operator Guide"
description: "Generate release keys offline, build and sign a release, install it by cable once, then push, apply, monitor and roll back Hanasu firmware over the mesh."
icon: "admin_panel_settings"
date: "2026-10-03T00:00:00-05:00"
lastmod: "2026-10-03T00:00:00-05:00"
draft: false
toc: true
tags: ["hanasu", "ota"]
---

This is the operator procedure for Hanasu firmware updates: keys, release builds, signing, the first cable install, and day-to-day pushes over the mesh. For the design behind it (package format, checks, trial and rollback, threats), read [Over-the-Air Updates](/docs/hanasu/ota/) first. Every command here matches the tools in the Hanasu repo: `tools/keys/genkeys.sh`, `tools/mnpkg.py`, `tools/mcuboot_sign.py` and `tools/ota_push.py`.

## At a glance

Three machines are involved, and only **public keys and signed files** cross between them:

| Machine | Holds | Does |
|---|---|---|
| Signing machine (offline) | The private release keys and the MCUboot private key | Generates keys, signs MCUboot images, builds `.mnpkg` packages |
| Build machine | Public halves only | Builds release firmware that trusts the public keys |
| Nodes | Public halves, compiled in | Verify packages before staging; on the MG24, MCUboot verifies the image at every swap and boot |

There are two signatures:

| Signature | Key | Checked by | When |
|---|---|---|---|
| OTA package | OTA release key (Ed25519, or P-256) | The node | Before staging, on both chips |
| MCUboot image | MCUboot key (ECDSA P-256) | MCUboot | At every swap and boot, MG24 only |

{{< alert context="danger" text="The DEV keys committed in <code>tools/keys/</code> and MCUboot's own default key are public. Anyone with the repo can sign firmware for a node built with them. Replace both before any node leaves the bench." />}}

## Key setup

Generate keys **once, on the signing machine**, never on a development box. `genkeys.sh` is self-contained shell and needs only `openssl`; copy it over.

```sh
sh genkeys.sh release-keys/                  # Ed25519 OTA keys (OpenSSL >= 1.1.1)
sh genkeys.sh --ota-p256 release-keys/       # P-256 OTA keys (works with LibreSSL)
```

Ed25519 needs OpenSSL 1.1.1 or later. The stock macOS `openssl` is LibreSSL 3.3, which has no Ed25519; the script detects that and stops. Either install OpenSSL 3:

```sh
brew install openssl@3
OPENSSL=$(brew --prefix openssl@3)/bin/openssl sh genkeys.sh release-keys/
```

or use `--ota-p256`. P-256 package signatures (`sig_alg 1`) are fully supported; Ed25519 is only preferred. The MCUboot key is always P-256.

The script writes three key pairs:

| File | Purpose |
|---|---|
| `ota_release.pem` / `.pub.pem` | OTA package key, current |
| `ota_release_next.pem` / `.pub.pem` | OTA package key, next (rotation spare) |
| `mcuboot_release.pem` / `.pub.pem` | MG24 MCUboot image key |

Private keys are PKCS#8 PEM, mode 600, and are **never overwritten**: the script refuses to run if any of them exists. It prints each OTA key's `key_id`, the same value `mnpkg.py` and the nodes compute.

Back up the private files offline. **Hand over only the three `*.pub.pem` files.**

The Python tools can do the same if preferred:

```sh
mnpkg.py keygen --alg ed25519 -o ota_release.pem --pub-out ota_release.pub.pem
imgtool keygen -t ecdsa-p256 -k mcuboot_release.pem
imgtool getpub -k mcuboot_release.pem -e pem > mcuboot_release.pub.pem
```

## Build a release

On the build machine, wire in the public halves:

```sh
# OTA key store for both targets; refuses DEV keys
tools/mnpkg.py c-keys --release ota_release.pub.pem ota_release_next.pub.pem \
    > firmware-idf/components/magnet/include/magnet_pkg_keys_release.h
cp mcuboot_release.pub.pem tools/keys/        # public half only
```

### ESP32-C6

Add `-DMN_PKG_RELEASE_KEYS=1` to the OTA env's `build_flags` (the OTA env today is `esp32c6_xiao_ble_led_ota`). Without the release header the build stops with `#error`, and a header that holds DEV keys stops it too. The env's `MN_FW_VER_MAJOR/MINOR/REV/BUILD` flags are the version the image reports, and they must match the `--version` you give `mnpkg.py`.

### XIAO MG24

Add `release.conf` (it sets `CONFIG_MN_PKG_RELEASE_KEYS`; a plain `-D` does not reach the app image under sysbuild), point MCUboot at the **public** key, and turn on offline signing:

```sh
west build -p -b xiao_mg24 --sysbuild firmware-zephyr -d build/rel -- \
    -DEXTRA_CONF_FILE="ble.conf;ble-resident.conf;release.conf" \
    -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"$PWD/tools/keys/mcuboot_release.pub.pem\" \
    -DMN_SIGN_OFFLINE=1
```

MCUboot is built with the public key embedded, and `MN_SIGN_OFFLINE` leaves the application **unsigned** instead of letting sysbuild sign it with that same file. The image version comes from `firmware-zephyr/VERSION`.

Then package the unsigned image for the signing machine:

```sh
tools/mcuboot_sign.py job build/rel -o job/
```

`job` copies `zephyr.bin` and `zephyr.hex` and records the exact imgtool arguments the build would have used, plus a SHA-256 of each file. Carry `job/` to the signing machine.

{{< alert context="warning" text="An offline build's own <code>zephyr.signed.bin</code> is hash-only and unsigned, and MCUboot will not boot it. Never ship it: always sign with <code>mcuboot_sign.py</code>." />}}

## Sign a release

The signing machine needs Python 3 with the `cryptography` package, `imgtool` (`pip install imgtool`), and copies of `mnpkg.py` and `mcuboot_sign.py`.

**MG24:** sign the MCUboot image, then wrap it in a package.

```sh
python3 mcuboot_sign.py sign job/ --key mcuboot_release.pem -o signed/
python3 mnpkg.py build signed/zephyr.signed.bin --chip efr32mg24 --board xiao-mg24 \
    --variant <name> --version <X.Y.Z+N> --fw-version <tag> \
    --key ota_release.pem -o node.mnpkg
```

`sign` refuses a job whose files changed since `job` made it, signs both `.bin` and `.hex`, and runs `imgtool verify` against the key. `mnpkg.py build` refuses an MCUboot image whose embedded version differs from `--version`.

**C6:** package the IDF `firmware.bin` directly.

```sh
python3 mnpkg.py build firmware.bin --chip esp32c6 --board xiao-esp32c6 \
    --variant <name> --version <X.Y.Z+N> --fw-version <tag> \
    --key ota_release.pem -o node.mnpkg
```

The variant must not start with `dev` for a release; `mnpkg.py` refuses a DEV key with any other variant. Optional flags: `--min-running <version>`, `--clears-bundles`, `--requires-repartition`, and `--build-time <unix-seconds>` for reproducible builds.

Before shipping, inspect and verify the package offline:

```sh
python3 mnpkg.py inspect node.mnpkg                           # decode the header, check structure
python3 mnpkg.py verify node.mnpkg --pubkey ota_release.pub.pem   # checks 1-8 offline
```

## First install by cable

Every node needs one cable install of an OTA-capable release build. After that, updates go over the air.

**ESP32-C6:** flash the `_ota` env over USB. The OTA partition table keeps NVS at the same offset and size, so the node's identity, name, channel and BLE bonds survive.

```sh
cd firmware-idf && pio run -e esp32c6_xiao_ble_led_ota -t upload
```

**MG24:** copy the signed image into the build directory, then flash MCUboot and the signed app over SWD.

```sh
tools/mcuboot_sign.py install signed/ build/rel
west flash -d build/rel
```

Stock OpenOCD has no MG24 support; pass the Silicon Labs Arduino core's OpenOCD to `west flash` as described in [XIAO MG24 on Zephyr](/docs/hanasu/mg24-zephyr/#building-and-flashing).

Then check the node on its host link:

| Check | Expect |
|---|---|
| `WHOAMI` | The node's ID and name, unchanged from before |
| `WHOAMI` (or the app's node screen, "Build") | `ota=<version>/<slot>/confirmed`. Works over BLE without pairing |
| `FORTH`, then `ota-status` | `# ota: running v<version> … confirmed` and no staged image |
| Boot log | No `!WARN ota-dev-keys` line. If it appears, the build trusts the DEV keys |

On a bench with several boards, pick serial ports by **USB serial number**, not by port name: ports renumber when re-plugged, and different Espressif chips enumerate with the same product name.

## Admins

A remote apply must be signed by a key the **target** allow-lists. The admin key is the sending node's identity key.

| Command | Where | Does |
|---|---|---|
| `PUBKEY` | Admin node | Prints its 65-byte public key as 130 hex characters |
| `ADMIN ADD <130-hex pubkey>` | Target | Adds the key to the allow-list (up to 4 keys) |
| `ADMIN LIST` | Any | Lists keys by fingerprint, `SHA-256(pubkey)[0:8]` |
| `ADMIN REMOVE <n \| fp>` | Target | Removes a key from this node only |
| `ADMIN REVOKE <fp>` | Admin node | Signed revoke to the whole channel, then removes the key locally |

All `ADMIN` and `OTA` verbs are privileged: they work over serial, or over BLE only on a bonded link (otherwise `E_NOT_BONDED`). A fingerprint's first 4 bytes are the key owner's device ID, which makes `ADMIN LIST` easy to read.

## Push an update

From the host attached to the sending node:

```sh
python3 tools/ota_push.py <sender-port> <target-ml-eid> node.mnpkg --apply
```

The sender can be any Hanasu node on a host link; the target must allow-list the sender's key. Options:

| Option | Effect |
|---|---|
| (none) | Stage only. Apply later, or locally on the target |
| `--apply` | After staging, send `OTA APPLY` and wait for the result and the report |
| `--apply --perm` | PERMANENT: no trial, the image is confirmed at once |
| `--apply --downgrade` | Allow an older version than the one running |
| `--verbose` | Print everything the sender's port said |

What you see:

```
# package v0.7.0+2  chip 0x0002 board 0x0201  sha128 <32 hex>
# <bytes> B, <n> chunks, meta mnpkg:1
# sender: !XFER_SENT ... in <s>s
# apply: !OTA_RESULT <id> accepted v0.7.0+1
# report: !OTA_REPORT <id> confirmed v0.7.0+2 (was v0.7.0+1) bundles=1
```

`!XFER_SENT` means the target ran all nine package checks and staged the image. `!OTA_RESULT … accepted` means it armed the slot and is rebooting. The `!OTA_REPORT` arrives after the trial: `confirmed`, or `rolled-back v<old> (failed v<new>)`. The tool waits up to 12 minutes for the report and exits non-zero unless it is `confirmed`.

Timing: about 90 ms per 336-byte chunk, set by the node and radio round trip. A 557 KB MG24 package took 137–169 s (about 3 minutes); a 1.17 MB C6 package took 385 s (about 6.5 minutes).

Update **one node at a time**: start with a canary and move to the next only after its `confirmed` report. Never apply to many nodes at once.

### Package refusals

A refused package reads `!XFER_FAIL <xid> refused:<n>`, and `ota_push.py` adds the name. Checks 1–6 refuse at chunk 0, before the payload is sent.

| `refused:` | Code | Usual cause | Do |
|---|---|---|---|
| 1 | `E_PKG_FORMAT` | Not a v1 package, or a corrupted header | Rebuild with `mnpkg.py build`; check with `inspect` |
| 2 | `E_PKG_KEY` | Signed with a key the node does not trust (DEV vs release, or a rotated-out key) | Sign with a key in the node's store |
| 3 | `E_PKG_SIG` | Header changed after signing, or wrong key file | Rebuild the package; `verify` it offline |
| 4 | `E_PKG_TARGET` | Wrong chip or board, e.g. a C6 package sent to an MG24 | Build with the target's `--chip` and `--board` |
| 5 | `E_PKG_REPARTITION` | The build changed the partition table | USB only; reflash by cable |
| 6 | `E_PKG_SIZE` | Length mismatch, or the image does not fit the slot | Check the image; on a C6, confirm the node runs the OTA partition table |
| 7 | `E_PKG_SHA` | Payload corrupted in transit or in flash | Push again |
| 8 | `E_PKG_IMAGE` | The platform's own image check failed | Check the payload is a valid IDF or MCUboot image |
| 9 | `E_PKG_MIN` | The node runs older than the package's `min_running` | Install the intermediate release first |

### Apply results

| Status | Meaning | Do |
|---|---|---|
| `accepted` | Armed; the target reboots once the reply is acknowledged | Wait for the report |
| `E_NOT_TARGET` (2) | The command named a different device | Check the target address |
| `E_NOT_STAGED` (3) | Nothing staged, or still receiving. Also the answer to a repeated apply after success | Push the package again |
| `E_SHA_MISMATCH` (4) | A different package is staged now | Restage the intended package |
| `E_VERSION_MISMATCH` (5) | The version in the command differs from the staged header | Use the package's version |
| `E_DOWNGRADE` (6) | Version not newer than the running one | Add `--downgrade` if intended |
| `E_UNSUPPORTED` (7) | Build without OTA, or a bad mode or flag | Install an OTA-capable build by cable |

**No reply at all** means the target dropped the command: the sender's key is not on the target's allow-list, or the frame was lost. Check `ADMIN LIST` on the target.

### Local apply

Without `--apply`, apply on the target itself from a privileged link: `FORTH`, then `ota-status` to see what is staged, then `ota-apply`. A local apply always boots in TEST mode, and it sends no report because no admin asked for it.

## Health and rollback

After an apply the new image boots on a **10-minute trial**. It is healthy, and confirms itself, once:

1. the node is READY (attached to Thread), and
2. every saved Forth role bundle re-applied at boot without error.

If not, the node reboots and the bootloader restores the previous image, which then reports `rolled-back`.

The report's `bundles=` value:

| Value | Meaning |
|---|---|
| `0` | No bundles saved |
| `1` | All saved bundles re-applied |
| `2` | A re-apply failed, which blocks confirmation |
| `3` | Cleared by a `CLEARS_BUNDLES` image |

A package built with `--clears-bundles` is for firmware that breaks the Forth vocabulary on purpose. During the trial the node holds its saved bundles back, so health is READY alone. On confirm, it forgets them and you redeploy bundles for the new vocabulary. On rollback they are untouched and the old image re-applies them.

`--perm` (PERMANENT) skips the trial entirely: the image is confirmed at its first boot and never rolls back on its own. Use it only when you mean it.

## Rotation and compromise

### Rotating the OTA key

The firmware's store holds two OTA keys, current and next. To retire `current`:

1. On the signing machine, create a new spare. `genkeys.sh` will not overwrite existing files, so use openssl directly:

   ```sh
   openssl genpkey -algorithm ed25519 -out ota_release_new.pem && chmod 600 ota_release_new.pem
   openssl pkey -in ota_release_new.pem -pubout -out ota_release_new.pub.pem
   # P-256 instead:
   # openssl ecparam -name prime256v1 -genkey -noout | openssl pkcs8 -topk8 -nocrypt -out ota_release_new.pem
   ```

   Its `key_id` (use `tail -c 65` for a P-256 key):

   ```sh
   openssl pkey -pubin -in ota_release_new.pub.pem -outform DER | tail -c 32 |
       openssl dgst -sha256 -binary | od -An -tx1 | tr -d ' \n' | cut -c1-16
   ```

2. On the build machine, generate a store of `next` plus the new spare and build a release:

   ```sh
   tools/mnpkg.py c-keys --release ota_release_next.pub.pem ota_release_new.pub.pem \
       > firmware-idf/components/magnet/include/magnet_pkg_keys_release.h
   ```

3. Sign that release's package with `ota_release_next.pem`, which the fleet already trusts, and roll it out node by node.
4. Once every node runs it, destroy the old `current` private key. `next` is now current and the new spare is next.

The MCUboot key has no second slot: rotating it means reflashing the bootloader over SWD.

### If a key leaks

| Leaked | Exposure | Response |
|---|---|---|
| An OTA release key | Packages signed with it pass the node's checks and can be **staged**. Applying still needs an admin key or a privileged local link | Rotate it out as above, signing the new store with the other key in the store |
| An admin key | The holder can apply staged images and revoke other admins | From another admin: `ADMIN REVOKE <fp>`, repeated to cover lost frames. Nodes that were offline keep the key until revoked again. A thief can revoke other admins just as fast; recover with `ADMIN ADD` over a bonded link or serial |
| The MCUboot key (MG24) | Images signed with it will boot, but they still need a valid release-key package to be staged over the air | Generate a new MCUboot key and reflash the bootloader on every MG24 over SWD |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `!WARN ota-dev-keys` at boot | The build trusts the committed DEV release keys | Rebuild with release keys (C6 `-DMN_PKG_RELEASE_KEYS=1`, MG24 `release.conf`) |
| `refusing: DEV release key with a non-dev variant` | `mnpkg.py build` with a DEV key | Use the release key, or a `dev…` variant for bench work |
| `refusing: --version … but the MCUboot image says …` | The MG24 image was built with a different `firmware-zephyr/VERSION` | Rebuild with the version set, or pass the image's version |
| `this build signs the app itself` from `mcuboot_sign.py job` | The build was not made with `-DMN_SIGN_OFFLINE=1` | Rebuild with offline signing and the public MCUboot key |
| `refusing: … changed since the job was made` | Files in `job/` were modified | Recreate the job from the build |
| `not an OTA package (magic MNPK)` | `ota_push.py` was given a raw image | Build a `.mnpkg` with `mnpkg.py` |
| `sender refused XFER BEGIN` | The sender is not READY or the arguments are wrong | Check `STATUS`; rerun with `--verbose` |
| `!WARN ota: no update partition` on a C6 | The node runs the single-app partition table | Install the `_ota` env by cable |
| `-ERR E_UNKNOWN_PEER` from `OTA APPLY` | The target is not in the sender's `PEERS` | Wait until the sender has heard from the target |
| `-ERR E_NOT_BONDED` | Privileged verb over an unbonded BLE link | Pair first, or use serial |
| `-ERR E_BAD_STATE` from `OTA APPLY` | The sender is not READY | Wait for Thread to attach |
| `apply: no reply` | The target does not allow-list the sender's key, or the frame was lost | `ADMIN ADD <sender PUBKEY>` on the target; retry |
| No report within 12 minutes | The report was lost, or the target is off the mesh | Check the target's `WHOAMI` `ota=` (or `ota-status`); the 10-minute trial has settled by then |
| `!WARN link-rx-overrun` on an MG24 | The host wrote faster than the node could read | Keep one line in flight; use the provided tools |
| MG24 port seems dead | Opened with DTR low; the USB bridge forwards only while DTR is asserted | Reopen with DTR asserted (pyserial's default) |
