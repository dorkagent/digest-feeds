#!/usr/bin/env python3
"""Collect AIInviteCode listings (https://aiinvitecode.com/new).

Keyless plain-HTTPS fetch -- the listing cards render server-side, no JS needed.
Output: JSON list of {slug, url, name, category, code, bonus_type, added}
written to the path given as argv[1].

Usage: python3 scripts/collect_aiinvitecode.py data/aiinvitecode/new-2026-10-14.json
"""
import json
import re
import sys
import urllib.request

BASE = "https://aiinvitecode.com"
PAGE = "/new"  # "Codes and products added in the last 7 days."
# NOTE: /free-ai-api-credits is an editorial guide page (startup programs &
# free tiers), not a time-ordered feed -- not a monitoring target.

UA = {"User-Agent": "dork-agent (+https://github.com/dorkagent/digest-feeds)"}


def fetch(path):
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def parse_cards(html, page):
    """Extract listing cards. Each card is an <a href="/<slug>"> whose text
    nodes run: name, category, code, bonus_type, ..., 'Added', '<rel>'."""
    out = []
    # split on card anchors
    for m in re.finditer(r'<a[^>]*href="(/[\w-]+)"[^>]*>(.*?)</a>', html, re.S):
        href, inner = m.group(1), m.group(2)
        if href in ("/", "/new", "/submit") or not href[1:]:
            continue
        texts = [t.strip() for t in re.findall(r">([^<>]+)<", inner) if t.strip()]
        if len(texts) < 5 or "Added" not in texts:
            continue
        try:
            added_i = texts.index("Added")
        except ValueError:
            continue
        name = texts[0]
        category = texts[1] if len(texts) > 1 else ""
        code = texts[2] if len(texts) > 2 else ""
        bonus_type = texts[3] if len(texts) > 3 else ""
        added = " ".join(texts[added_i : added_i + 2])  # "Added 3h ago"
        out.append(
            {
                "page": page,
                "slug": href.strip("/"),
                "url": BASE + href,
                "name": name,
                "category": category,
                "code": code,
                "bonus_type": bonus_type,
                "added": added,
            }
        )
    # dedupe (mobile+desktop render the card twice)
    seen, uniq = set(), []
    for c in out:
        key = (c["slug"], c["code"])
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def main():
    if len(sys.argv) != 2:
        print("usage: collect_aiinvitecode.py <out.json>", file=sys.stderr)
        sys.exit(2)
    all_cards = []
    try:
        html = fetch(PAGE)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: fetch {PAGE} failed: {e}", file=sys.stderr)
        html = ""
    if html:
        all_cards = parse_cards(html, "new")
        print(f"new: {len(all_cards)} listings", file=sys.stderr)
    with open(sys.argv[1], "w") as f:
        json.dump(all_cards, f, indent=1)
    print(f"wrote {len(all_cards)} listings -> {sys.argv[1]}")


if __name__ == "__main__":
    main()
