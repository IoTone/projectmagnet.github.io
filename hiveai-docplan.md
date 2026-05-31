# Hive AI — Documentation Plan

**Purpose:** propose a complete "Hive AI" section for the ProjectMagNET Hugo doc site, derived from a review of the `MagNET_M5DialFiddlerCrab` reference-design folder (the ESPIDFORTH/hive code base).

**Status:** proposal for review. No content pages written yet — this document is the design for them.

**Author/date:** drafted 2026-05-29.

---

## 1. What I reviewed

Source tree: `ProjectMagNET/reference-designs/MagNET_M5DialFiddlerCrab/`.

Primary material (authoritative, already well-written — the doc section is largely a *re-presentation* of these for a public audience, not new invention):

| Source | Covers |
|---|---|
| `README.md` (top level) | The DBOTS concept, R1–R18 requirements, Role 1–12 roster, the phase plan (Janet → ESPIDFORTH → hive), component map, current-checkpoint topology |
| `docs/MagNET-HiveProtocol-v1.md` | mDNS discovery, length-prefixed JSON/TCP transport, HMAC-SHA256 auth, all 12 message types, node state machine, threat model |
| `docs/MagNET-Generations.md` | The three version axes (proto/gen/role), mycology lineages, the CHALLENGE/RESPONSE "you are not one of us" puzzle gate, compatibility matrix, MAJOR-bump migration playbook |
| `docs/MagNET-RoleBundle-v1.md` | Signed Forth role-bundle envelope, signing input, install pipeline, NVS persistence, authoring with `sign_bundle.py` |
| `test-plan.md` | Bench bring-up + verification walkthrough |
| `components/craw_hive/craw_hive.h` | Public API surface, message-type + reject-reason enums (verified against the protocol doc) |
| `M5StackDial-…-ESPIDFORTH/src/main.cpp`, `MagNET_ReSpeaker_Boombox/src/main.c` | The Forth word vocabulary actually registered on hardware |
| Subproject `README.md` files | The "cast" of devices: Dial ruler, Atom Echo spawn, Hive Camera spy, Capsule Scribe (+ Redis variant), ReSpeaker Boombox, Vitals |

**Key finding:** the design docs in `docs/*.md` are high quality and internally consistent (I cross-checked the protocol doc's message/reject enums against `craw_hive.h` — they match: 12 message types `HELLO…RESPONSE`, reject reasons including the three lineage ones at 6/7/8). The doc-site work is mostly *editorial* — restructure for a reader who has never seen the repo, convert ASCII diagrams to Mermaid, add narrative glue, and link the pieces — not a fresh authoring effort.

---

## 2. Target site context (important — affects where files go)

The repo `projectmagnet.github.io` is **not a plain content repo**. It is a clone of the **LotusDocs** Hugo theme (`github.com/colinwilson/lotusdocs`), and the *live site content* is built from the **`exampleSite/`** subdirectory:

- `netlify.toml` → `publish = "exampleSite/public"`, `command = "cd exampleSite && hugo --gc --minify --themesDir ../.."`. So **content lives under `exampleSite/content/`** and is served at `/docs/...`.
- Current `exampleSite/content/docs/` still contains only the stock LotusDocs **demo** pages (`quickstart.md`, `example-content/`, `section folder/`). No ProjectMagNET content has been migrated into Hugo yet.
- A **legacy mkdocs** site exists at the top-level `docs/` (`mkdocs.yml`, `readthedocs` theme) with `architecture/` and `use_cases/` stubs. This is the old IA being superseded by the Hugo/LotusDocs site.

**Implication:** "Hive AI" will be the *first real content section* on the Hugo site. I propose we treat it as a self-contained section now and let it set the pattern for migrating the rest of ProjectMagNET later (the user has already flagged "we will scan other parts of ProjectMagnet and do more documentation").

### LotusDocs conventions to follow (confirmed from existing pages)

- **Sections** = a folder with `_index.md`. **Pages** = `*.md`. Sidebar + ordering are **auto-generated** from folder structure + `weight`.
- **Front matter is YAML**, fields in use:
  ```yaml
  ---
  weight: 100
  title: "Quickstart"
  description: "A quickstart guide…"
  icon: "rocket_launch"        # Material Symbols Outlined name; sidebarIcons + titleIcon are enabled
  toc: true
  date: "2023-05-03T22:37:22+01:00"
  lastmod: "2023-05-03T22:37:22+01:00"
  draft: false
  tags: ["Beginners"]
  ---
  ```
- **Shortcodes available** (enabled in `exampleSite/hugo.toml`, `unsafe = true` for raw HTML):
  - `{{< mermaid >}} … {{< /mermaid >}}` — diagrams (there is an `example-content/mermaid.md` proving it works). **Use this for every ASCII diagram.**
  - `{{< tabs tabTotal="N" >}}{{% tab tabName="…" %}}…{{% /tab %}}{{< /tabs >}}` — used in `quickstart.md` for per-OS instructions; good for per-board / per-chip variants.
  - `{{< alert >}}` (LotusDocs note/warning callouts), `{{< prism >}}` (Prism is enabled, theme `solarized-light`) for syntax highlighting; fenced code blocks already get highlighting.
- **Images:** prefer **page bundles** — co-locate the image with the page (`hive-ai/architecture/topology.svg` next to an `index.md`), or drop site-wide assets in `exampleSite/static/`. `enableGitInfo`, `editPage`, and `lastMod` are on, so pages show edit links and last-modified dates.
- **TOC** depth is levels 1–3 (`markup.tableOfContents`). Keep headings ≤ H3 for the in-page TOC to look right.

---

## 3. Proposed section structure

Create **`exampleSite/content/docs/hive-ai/`** as a section (page-bundle style so diagrams co-locate). Proposed pages and weights:

```
exampleSite/content/docs/hive-ai/
├── _index.md                  weight  10   icon hub            "Hive AI"  (section landing)
├── concepts.md                weight  20   icon biotech        Concepts & Vocabulary (DBOTS)
├── architecture.md            weight  30   icon account_tree   Architecture & Topology
├── roles.md                   weight  40   icon diversity_3    The 12 Roles
├── hive-protocol.md           weight  50   icon lan            Hive Protocol v1 (wire spec)
├── generations-lineage.md     weight  60   icon fingerprint    Generations & the Lineage Gate
├── role-bundles.md            weight  70   icon deployed_code  Signed Role Bundles
├── devices.md                 weight  80   icon developer_board The Cast: Devices & Boards
├── forth-words.md             weight  90   icon terminal       Controlling the Hive from Forth
├── scribe-redis.md            weight 100   icon database       Scribe & the Redis Sidecar
├── boombox-audio.md           weight 110   icon volume_up      Boombox: Audio Notifications
└── bring-up.md                weight 120   icon rocket_launch  Bench Bring-Up & Verification
```

Grouped by intent:

- **Narrative core (read in order):** `_index` → `concepts` → `architecture` → `roles`. Tells the story: what a hive is, the vocabulary, how the pieces fit, what jobs nodes do.
- **Specifications (reference):** `hive-protocol`, `generations-lineage`, `role-bundles`. These map almost 1:1 to the three `docs/*.md` design docs.
- **Hands-on / per-subsystem:** `devices`, `forth-words`, `scribe-redis`, `boombox-audio`, `bring-up`.

If we want a lighter first cut, the **minimum viable section** is the five bold pages: `_index`, `concepts`, `architecture`, `hive-protocol`, `roles`. The rest can land as a second pass. I recommend doing the full set since the source material already exists.

---

## 4. Page-by-page outline

### `_index.md` — Hive AI (landing)
- One-paragraph hook: a hive of tiny ESP32 "biologics" that self-organize under a ruler, hot-swap roles over the air, and share memory — built on an embedded Forth.
- The **DBOTS** acronym expanded (Digital, Biologic, Organized, Telepathic, Sentients) from the README.
- "What's real today" callout: current generation `0.5.0-spore`, Milestones A/B done, C steps 1–4 done; multi-node validated 2026-04-25.
- Card links into the four narrative pages + the three specs.
- `{{< alert >}}` noting this is a research/demo prototype, LAN-scoped, not production-hardened.

### `concepts.md` — Concepts & Vocabulary
- The biology metaphor → engineering mapping table: **ruler/queen** = controller, **biologic** = node running updatable Forth, **hive mind** = shared memory (NDN/CCN-style, cache + freshness), **telepathy** = peer messaging, **spawn** = unprovisioned newcomer.
- The **three orthogonal version axes** intro (proto / gen / role) — full treatment deferred to `generations-lineage.md`.
- Glossary: ruler, node, spawn, role, role bundle, lineage, gen, hive id, shared secret, DNA key, scribe, KV.

### `architecture.md` — Architecture & Topology
- **Mermaid** redraw of the README "current checkpoint" topology (Dial ruler ⇄ Echo / Camera / Capsule / fake_ruler).
- The shared-`components/` map table (`craw_serial`, `craw_nvs`, `craw_wifi`, `craw_ble_provision`, `craw_hive`, `craw_camera`, `craw_role_bundle`, `craw_mdns`, …).
- The **load-bearing post-WiFi bring-up order**: BLE teardown → SNTP full-sync → hive start, with the *why* (mDNS OOM ~55 KB; HMAC `ts_skew`). This is hard-won knowledge worth a prominent callout.
- The phase history (Phase 0 Janet → Phase 2 ESPIDFORTH → Phase 4 hive) as a short timeline.

### `roles.md` — The 12 Roles
- Table of Role 1–12 (Ruler, Worker, Parrot, Scribe, Beeper, Warrior, Spy, Pet, ML PhD, Spawn, Eye, Boombox) with: function, intended display sprite, and **implementation status** (which exist as firmware vs bundles vs not-yet).
- Note the architectural split: most roles ship as **signed Forth bundles**; **Boombox** is its own firmware project (needs I2S compiled in) — forward-link to `role-bundles.md` and `boombox-audio.md`.

### `hive-protocol.md` — Hive Protocol v1
- Faithful re-presentation of `docs/MagNET-HiveProtocol-v1.md`: goals/non-goals, mDNS (`_magnet-ruler._tcp`, port 7447, TXT `ver`/`hive`), length-prefixed JSON framing, HMAC-SHA256 canonical `type|nonce|ts|payload`, the message envelope, all message types, **Mermaid** state machine, threat-model table.
- Verified message-type table against `craw_hive.h` (HELLO=1 … RESPONSE=12) — include the numeric enum so it doubles as an implementer reference.

### `generations-lineage.md` — Generations & the Lineage Gate
- The three-axes table; mycology lineage ladder (spore→hyphae→mycelium→fruiting→sporocarp); SemVer bump rules.
- The **CHALLENGE/RESPONSE puzzle gate** — the "you are not one of us" mechanic: `HMAC-SHA256(dna_key, puzzle|node_id|chal_ts)`, why HMAC-over-nonce beats a static key, where DNA keys live, default-OFF + the `lineage-auth` runtime toggle.
- Compatibility matrix + the MAJOR-bump migration playbook (flash rulers first — forward asymmetry).

### `role-bundles.md` — Signed Role Bundles
- From `docs/MagNET-RoleBundle-v1.md`: JSON envelope fields, the pipe-delimited signing input, v1 HMAC vs planned v2 Ed25519 trust model, the install pipeline error-code table, NVS persistence + auto-resume, authoring with `sign_bundle.py`, Forth role conventions.
- "Bundles live on the Scribe" decision and the two distribution paths (compiled-in vs `push_bundles.py`).

### `devices.md` — The Cast: Devices & Boards
- Card/table per subproject: **Dial** (S3, ruler + display), **Atom Echo** (classic ESP32, spawn, hex LEDs + chirps), **Hive Camera** (AI-Thinker / CamS3, spy, MJPEG), **Capsule Scribe** (S3, KV store), **Capsule Scribe Redis** (RESP2 sidecar), **ReSpeaker Boombox** (XIAO S3, audio), **Vitals** (C6, radar presence). Each: chip, role, standout feature, link to its deep-dive page if any.
- Pull in the chip-specific gotchas worth surfacing (DRAM budget on no-PSRAM S3; IDF v5.4 efuse collision) as cross-links to existing `docs/*.md`.

### `forth-words.md` — Controlling the Hive from Forth
- The vocabulary actually registered on hardware, grouped: **app/display** (`theme`, `brightness`, `ping`, `starburst`, `invert`, `mute`, `appbeep`, `appsleep`, `appshowmem`, `appdevinfo`); **provisioning** (`prov-status`, `prov-reset`); **hive/ruler** (`ruler-status`, `grant-role`, `lineage-auth`); **KV** (`kv-set`, `kv-get`, `kv-list`); **audio (Boombox)** (`tone`, `sweep`, `am`, `sleep`, `alert`, `notify`, `warn`, `error`, `siren`, `yelp`, `nee-naw`, `air-raid`, `sunrise`, `vol`, `audio-on`).
- Stack-effect notation for each, e.g. `tone ( freq ms -- )`, plus a couple of REPL transcripts.

### `scribe-redis.md` — Scribe & the Redis Sidecar
- The Scribe role (NVS-backed KV), then the RESP2-compatible variant: default port 6379, bind profiles, no-AUTH-in-v1, supported commands (strings + lists), the on-device `redis-do` client, off-by-default toggle, Dial's orange status dot.
- "Related Work" callout linking `github.com/DankJugal/ESP32RedisClient` (already referenced in the subproject).

### `boombox-audio.md` — Boombox: Audio Notifications
- I2S-slave architecture on ReSpeaker Lite (XU316 clocks; 16 kHz, 32-bit stereo slots; mono→stereo expansion), software sine-LUT synth, segment patterns + gain envelopes.
- Primitives explained: `tone`, `sweep`, `am`; canned sounds; the **siren family** (`siren`/`yelp`/`nee-naw`/`air-raid`) and the `sunrise` boot sound; remote trigger via `boombox:cmd` KV key.

### `bring-up.md` — Bench Bring-Up & Verification
- A reader-facing adaptation of `test-plan.md`: flash the ruler, provision WiFi over BLE, watch a spawn join, toggle the lineage gate, push a bundle, verify with `fake_ruler.py`.
- DRAM-budget recovery knobs as a troubleshooting callout.

---

## 5. Diagrams to produce (ASCII → Mermaid)

| Diagram | Source | Target page |
|---|---|---|
| Ruler/node discovery+join topology | HiveProtocol "Topology" | `hive-protocol.md` (or `architecture.md`) |
| Node session state machine | HiveProtocol "Session state machine" | `hive-protocol.md` |
| HELLO→CHALLENGE→RESPONSE→WELCOME round-trip | Generations "State machine addition" | `generations-lineage.md` |
| Current-checkpoint hive topology | README "Topology at the current checkpoint" | `architecture.md` |
| Mycology lineage ladder | Generations | `generations-lineage.md` (Mermaid flow or simple table) |

All renderable with the `{{< mermaid >}}` shortcode (proven in the theme's `example-content/mermaid.md`).

---

## 6. Conventions & decisions baked into this plan

- **Location:** `exampleSite/content/docs/hive-ai/` (because that's what Netlify builds). Flagging this explicitly since the repo root also has a `docs/` that is the *legacy mkdocs* site — we are **not** adding there.
- **Front matter:** YAML, with `weight`, `title`, `description`, `icon`, `toc: true`, `date`, `lastmod`, `draft: false`, `tags`. Icons are Material Symbols Outlined names (sidebar + title icons are enabled).
- **No new facts invented:** every page maps to reviewed source. Where the source says "planned / not yet" (e.g. Ed25519, `gen_floor`, hyphae+ keys), the doc says so too, using an `{{< alert >}}` "Planned" callout, so the public docs don't overstate the prototype.
- **Cross-linking:** specs link to each other and back to the narrative pages; `devices.md` links to the existing `docs/macOS-LAN-networking.md` and `docs/idf-v54-efuse-collision.md` gotcha docs (decide whether to migrate those into the section or link to the repo).
- **Tone:** matches the existing design docs — precise, slightly playful (the biology metaphor), honest about non-goals.

---

## 7. Open questions for you

1. **Plan file location** — I placed this plan at the `projectmagnet.github.io` repo root. Want it somewhere else (e.g. inside `exampleSite/` or back in the `MagNET_M5DialFiddlerCrab` folder)?
2. **Full set vs MVP** — author all 12 pages in one pass, or start with the 5-page narrative core and iterate?
3. **Demo content** — should I leave the stock LotusDocs demo pages (`quickstart`, `example-content`, `section folder`) in place alongside Hive AI, or remove them so the sidebar shows only ProjectMagNET content?
4. **Top-level IA** — Hive AI is the first real section. Do you want a thin top-level `docs/_index.md` (ProjectMagNET overview) above it now, or defer site-wide IA until we document the non-hive parts?
5. **Site identity** — `exampleSite/hugo.toml` still says "Lotus Docs Example Site", `baseURL`, footer, social, and `repoURL` are all theme defaults. Want me to include a config pass (title, baseURL `https://projectmagnet.github.io/`, footer, GitHub repo, theme accent color) as part of this work, or keep this PR content-only?
6. **Diagrams** — Mermaid (text, version-controlled, my default) vs hand-drawn SVGs for the hero/topology images?

---

## 8. Suggested execution order (once approved)

1. (Optional) config pass: site title / baseURL / repo / accent color in `exampleSite/hugo.toml`.
2. `hive-ai/_index.md` + `concepts.md` + `architecture.md` (with topology + bring-up Mermaid).
3. `roles.md`, then the three spec pages (`hive-protocol`, `generations-lineage`, `role-bundles`).
4. `devices.md`, `forth-words.md`.
5. Deep dives: `scribe-redis.md`, `boombox-audio.md`, `bring-up.md`.
6. `cd exampleSite && hugo server` to preview; fix any front-matter/Mermaid rendering issues.

---

## 9. How to preview locally

```bash
cd /Users/dkords/dev/projects/iotone/projectmagnet.github.io/exampleSite
hugo server --themesDir ../..    # serves at http://localhost:1313/docs/
```

(Requires Hugo extended ≥ 0.140 per `config.toml`; Netlify uses 0.142.0.)
