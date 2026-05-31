#!/usr/bin/env python3
"""Generate the docs Roadmap page from the live GitHub issue tracker.

Pulls open issues from the Project MagNET repo via the `gh` CLI, groups them
into themes, and writes `exampleSite/content/docs/roadmap.md`.

Usage:
    scripts/gen_roadmap.py                 # regenerate from live issues
    scripts/gen_roadmap.py --check         # exit 1 if the file would change (CI)
    scripts/gen_roadmap.py --repo X --output path/to/roadmap.md

Requirements: Python 3.9+ and an authenticated `gh` CLI (`gh auth status`).
No third-party packages.

Maintaining the themes
----------------------
Categorization is, in order of precedence:
  1. CURATED   — explicit {issue_number: theme_key}; always wins. Add a number
                 here to pin it to a theme.
  2. LABEL_HINTS — {github_label: theme_key}; used when a number isn't curated.
  3. keyword match against the issue title (first theme in THEMES order wins).
  4. otherwise the issue lands in "uncategorized" so it shows up for triage.

When a new issue should live in a specific theme, add it to CURATED. New issues
left alone will auto-appear via label/keyword, or under "Uncategorized".
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "IoTone/ProjectMagNET"
# roadmap.md lives next to the other docs; resolve relative to this script so
# the generator works from any cwd.
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "exampleSite" / "content" / "docs" / "roadmap.md"
)

# Theme order defines section order on the page AND keyword-fallback precedence.
# Each: key -> (heading, [title keyword substrings, lower-case]).
THEMES = [
    ("vision", "Vision & specifications",
     ["spec", "architecture", "ota", "local first", "local-first",
      "generative ui", "kernel", "roadmap"]),
    ("hyperlocal", "Hyperlocal context & distributed intelligence",
     ["hyperlocal", "contextual", "sighting", "ifttt", "rules", "prolog",
      "lisp", "ask questions", "talk to your data", "swarm"]),
    ("spatial", "Spatial, WebXR & audio UX",
     ["webxr", "ar/vr", "ar / vr", " xr ", "digital twin", "audio hud",
      "audio alert", "hud"]),
    ("app", "App (mobile & desktop)",
     ["mobileapp", "app)", "widget", "drawer", "hamburger", "menu", "haptic",
      "onboarding", "swift", "desktop", "viewer", "seen devices", "help"]),
    ("discovery", "Discovery, provisioning & device identity",
     ["provision", "discovery", "zeroconf", "bonjour", "beacon", "qr",
      "nfc", "scanning", "airguard", "bluetooth", "ble data", "profile",
      "catalog", "lighting", "manufacturer"]),
    ("datasink", "Data sink, sync & storage",
     ["data sink", "datasink", "sink node", "datalog", "serialization",
      "storage", "sync to", "data adaptor"]),
    ("networking", "Networking, mesh & interop",
     ["lora", "meshtastic", "mesh", "network", "protocol", "morse", "p2p",
      "chat", "zigbee", "thread", "ecosystem", "api"]),
    ("hardware", "Hardware & reference designs",
     ["sensor", "wearable", "firmware", "energy", "power", "petwear",
      "board", "hardware", "reference-design", "reference design",
      "wifi manager", "wifimanager", "overlay"]),
    ("hygiene", "Project hygiene",
     ["cleanup", "clean up", "readme", "empty director", "directory",
      "directories"]),
    ("uncategorized", "Uncategorized (needs triage)", []),
]
THEME_KEYS = {k for k, _, _ in THEMES}

# 1. Explicit pins — the hand-curated categorization. Always wins.
CURATED = {
    # Vision & specifications
    2: "vision", 27: "vision", 39: "vision", 54: "vision", 65: "vision",
    80: "vision", 89: "vision", 90: "vision", 92: "vision", 94: "vision",
    # Hyperlocal context & distributed intelligence
    14: "hyperlocal", 18: "hyperlocal", 19: "hyperlocal", 28: "hyperlocal",
    46: "hyperlocal", 55: "hyperlocal", 71: "hyperlocal", 79: "hyperlocal",
    # Spatial, WebXR & audio UX
    6: "spatial", 43: "spatial", 44: "spatial", 91: "spatial",
    # App (mobile & desktop)
    7: "app", 16: "app", 31: "app", 32: "app", 47: "app", 48: "app",
    49: "app", 50: "app", 51: "app", 67: "app", 72: "app",
    # Discovery, provisioning & device identity
    12: "discovery", 17: "discovery", 22: "discovery", 23: "discovery",
    24: "discovery", 29: "discovery", 30: "discovery", 36: "discovery",
    66: "discovery", 70: "discovery",
    # Data sink, sync & storage
    8: "datasink", 13: "datasink", 40: "datasink", 45: "datasink",
    52: "datasink", 61: "datasink",
    # Networking, mesh & interop
    34: "networking", 35: "networking", 41: "networking", 58: "networking",
    59: "networking", 87: "networking",
    # Hardware & reference designs
    9: "hardware", 33: "hardware", 56: "hardware", 62: "hardware",
    85: "hardware", 86: "hardware", 93: "hardware",
    # Project hygiene
    73: "hygiene", 74: "hygiene", 78: "hygiene",
}

# 2. Label-based hints (lower-cased label name -> theme) for un-curated issues.
LABEL_HINTS = {
    "mobileapp": "app",
    "architecture": "vision",
}

# Optional per-issue annotations appended after the title (e.g. status).
ANNOTATIONS = {
    78: "✅ *(addressed)*",
}

ISSUE_URL = "https://github.com/{repo}/issues/{n}"


def run_gh(repo: str, state: str) -> list[dict]:
    cmd = [
        "gh", "issue", "list", "--repo", repo, "--state", state,
        "--limit", "1000", "--json", "number,title,labels",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("error: `gh` CLI not found. Install it and run `gh auth login`.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: `gh` failed:\n{e.stderr.strip()}")
    return json.loads(out)


def classify(issue: dict) -> str:
    n = issue["number"]
    if n in CURATED:
        return CURATED[n]
    labels = {lbl["name"].lower() for lbl in issue.get("labels", [])}
    for lbl, theme in LABEL_HINTS.items():
        if lbl in labels:
            return theme
    title = issue["title"].lower()
    for key, _, keywords in THEMES:
        if key == "uncategorized":
            continue
        if any(kw in title for kw in keywords):
            return key
    return "uncategorized"


def md_escape(text: str) -> str:
    # MAG*Net etc. — keep '*' from being read as emphasis in the title.
    return text.replace("*", r"\*")


def render(issues: list[dict], repo: str, open_count: int) -> str:
    buckets: dict[str, list[dict]] = {k: [] for k, _, _ in THEMES}
    for issue in issues:
        buckets[classify(issue)].append(issue)
    for items in buckets.values():
        items.sort(key=lambda i: i["number"])

    today = datetime.date.today().isoformat()
    lines: list[str] = []
    lines.append("---")
    lines.append("weight: 5")
    lines.append('title: "Roadmap"')
    lines.append(
        'description: "Where Project MagNET is headed — a themed view distilled '
        'from the public issue tracker."'
    )
    lines.append('icon: "map"')
    lines.append(f'date: "{today}T00:00:00-05:00"')
    lines.append(f'lastmod: "{today}T00:00:00-05:00"')
    lines.append("draft: false")
    lines.append("toc: true")
    lines.append('tags: ["roadmap", "planning"]')
    lines.append("---")
    lines.append("")
    lines.append(
        "This roadmap groups the project's open work into themes. It's distilled "
        f"from the [public issue tracker](https://github.com/{repo}/issues) — "
        "issue numbers link to the canonical discussion, which is always the "
        "source of truth."
    )
    lines.append("")
    lines.append(
        "{{< alert context=\"info\" text=\"Auto-generated by "
        "<code>scripts/gen_roadmap.py</code> on " + today + f" ({open_count} open "
        "issues). The tracker moves faster than this page; treat GitHub as "
        "authoritative.\" />}}"
    )
    lines.append("")

    for key, heading, _ in THEMES:
        items = buckets[key]
        if not items:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        for issue in items:
            n = issue["number"]
            url = ISSUE_URL.format(repo=repo, n=n)
            title = md_escape(issue["title"]).strip()
            note = f" {ANNOTATIONS[n]}" if n in ANNOTATIONS else ""
            lines.append(f"- {title} — [#{n}]({url}){note}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--state", default="open", choices=["open", "all"])
    ap.add_argument("--check", action="store_true",
                    help="don't write; exit 1 if the output would change")
    args = ap.parse_args()

    issues = run_gh(args.repo, args.state)
    content = render(issues, args.repo, open_count=len(issues))

    existing = args.output.read_text() if args.output.exists() else None
    # ignore the date lines when comparing for --check so a new day alone
    # doesn't report drift
    def strip_dates(s: str | None) -> str | None:
        if s is None:
            return None
        return "\n".join(
            l for l in s.splitlines()
            if not l.startswith(("date:", "lastmod:"))
            and "Auto-generated by" not in l
        )

    if args.check:
        if strip_dates(existing) != strip_dates(content):
            print(f"roadmap is out of date: {args.output}", file=sys.stderr)
            sys.exit(1)
        print("roadmap is up to date.")
        return

    # report the buckets so a maintainer can spot mis-filed / untriaged issues
    counts: dict[str, int] = {}
    untriaged: list[int] = []
    for issue in issues:
        t = classify(issue)
        counts[t] = counts.get(t, 0) + 1
        if t == "uncategorized":
            untriaged.append(issue["number"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content)
    print(f"wrote {args.output} ({len(issues)} open issues)")
    for key, heading, _ in THEMES:
        if counts.get(key):
            print(f"  {counts[key]:>3}  {heading}")
    if untriaged:
        print(f"  note: untriaged issues need a CURATED entry: "
              f"{', '.join('#'+str(n) for n in sorted(untriaged))}")


if __name__ == "__main__":
    main()
