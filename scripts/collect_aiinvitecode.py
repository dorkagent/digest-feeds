#!/usr/bin/env python3
"""Collect AIInviteCode listings (https://aiinvitecode.com/new).

Keyless plain-HTTPS fetch -- the listing cards render server-side, no JS needed.
Output: JSON envelope {"collected_at", "source", "page", "n_listings",
"listings"} where each listing is {page, slug, url, name, category, code,
bonus_type, added} ("added" is relative, e.g. "Added 5h ago" — anchored by
the envelope's collected_at).

Cards are parsed by class anchors (font-semibold=name, sm:inline-flex badge=
category, font-mono=code, tabular meta span="{bonus} · Added {rel}"), NOT by
text position — a card missing a field no longer shifts the others.

Fail-loud: fetch failure or zero parsed cards exits 1 so the workflow does
NOT commit an empty file (an empty commit would look like a quiet week and
defeat the VM stale-data fallback).

Usage: python3 scripts/collect_aiinvitecode.py data/aiinvitecode/new-2026-10-14.json
"""
import datetime
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://aiinvitecode.com"
PAGE = "/new"  # "Codes and products added in the last 7 days."
# NOTE: /free-ai-api-credits is an editorial guide page (startup programs &
# free tiers), not a time-ordered feed -- not a monitoring target.

UA = {"User-Agent": "dork-agent (+https://github.com/dorkagent/digest-feeds)"}


def fetch(path, tries=3):
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(BASE + path, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(2 ** attempt + 1)
    raise last


def _span_text(inner, class_frag):
    """Text of the first <span> whose class attribute contains class_frag."""
    m = re.search(r'<span[^>]*class="[^"]*' + re.escape(class_frag) +
                  r'[^"]*"[^>]*>(.*?)</span>', inner, re.S)
    if not m:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())


def parse_card(href, inner):
    name = _span_text(inner, "font-semibold")
    category = _span_text(inner, "sm:inline-flex")
    code = _span_text(inner, "font-mono")
    meta = _span_text(inner, "tabular")  # "Sign-up bonus · Added 5h ago"
    bonus_type, added = "", ""
    if "Added" in meta:
        pre, _, rel = meta.partition("Added")
        bonus_type = pre.replace("·", "").strip()
        added = "Added " + rel.strip()
    if not name:
        return None  # not a listing card (or markup changed)
    return {
        "page": "new",
        "slug": href.strip("/"),
        "url": BASE + href,
        "name": name,
        "category": category,
        "code": code,
        "bonus_type": bonus_type,
        "added": added,
    }


def parse_cards(page_html):
    out, skipped = [], 0
    for m in re.finditer(r'<a[^>]*href="(/[\w-]+)"[^>]*>(.*?)</a>',
                         page_html, re.S):
        href, inner = m.group(1), m.group(2)
        if href in ("/", "/new", "/submit") or not href[1:]:
            continue
        if "font-semibold" not in inner:
            continue  # nav/promo anchor, not a listing card
        card = parse_card(href, inner)
        if card is None:
            skipped += 1
            print(f"WARN: unparseable card {href}", file=sys.stderr)
            continue
        out.append(card)
    # dedupe (mobile+desktop render the card twice)
    seen, uniq = set(), []
    for c in out:
        key = (c["slug"], c["code"])
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq, skipped


def main():
    if len(sys.argv) != 2:
        print("usage: collect_aiinvitecode.py <out.json>", file=sys.stderr)
        sys.exit(2)
    try:
        page_html = fetch(PAGE)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: fetch {PAGE} failed after retries: {e}",
              file=sys.stderr)
        sys.exit(1)
    cards, skipped = parse_cards(page_html)
    if not cards:
        print("ERROR: 0 cards parsed — refusing to write an empty file "
              "(would look like a quiet week)", file=sys.stderr)
        sys.exit(1)
    doc = {
        "collected_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "source": BASE + PAGE,
        "page": "new",
        "n_listings": len(cards),
        "n_cards_skipped": skipped,
        "note": '"added" is relative to collected_at',
        "listings": cards,
    }
    with open(sys.argv[1], "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {len(cards)} listings -> {sys.argv[1]} "
          f"({skipped} cards skipped)")


if __name__ == "__main__":
    main()
