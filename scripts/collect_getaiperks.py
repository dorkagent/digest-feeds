#!/usr/bin/env python3
"""Get AI Perks blog index -> JSON (title, url, date, excerpt, tags, is_new).

Index is server-rendered (Next.js on Vercel), 24 cards per page, newest first,
paginated at /en/blogs/page/N. Walks pages until a card is older than the
window. A later page that fails is recorded in errors with truncated=true
(pages already read are kept); so is hitting MAX_PAGES first. Exits
non-zero if nothing parses (markup changed) so the workflow never commits
an empty file that looks like a quiet week.
Usage: collect_getaiperks.py <out.json> [--days 7]
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://www.getaiperks.com"
UA = {"User-Agent": "dorkagent-digest-feeds/1.0 (+https://github.com/dorkagent/digest-feeds)"}
CARD = re.compile(r'<a[^>]+href="(/en/blogs/\d+-[^"]+)"[^>]*>(.*?)</a>', re.S)
MAX_PAGES = 5


def fetch(path, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt + 1)


def text(fragment):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def parse(page):
    cards = []
    for href, body in CARD.findall(page):
        t = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S)
        if not t:
            continue
        d = re.search(r'<time[^>]+date[Tt]ime="([^"]+)"', body)
        p = re.search(r"<p[^>]*>(.*?)</p>", body, re.S)
        # tag chips sit in the wrap div right after the excerpt; author is the
        # bold span after the avatar. Kept separate so views/author aren't tags.
        tagbox = re.search(r'<div class="[^"]*flex-wrap[^"]*">(.*?)</div>', body, re.S)
        au = re.search(r'<span class="[^"]*font-semibold[^"]*">(.*?)</span>', body, re.S)
        cards.append({
            "title": text(t.group(1)),
            "url": BASE + href,
            "date": d.group(1)[:10] if d else None,
            "excerpt": text(p.group(1)) if p else "",
            "tags": [text(s) for s in re.findall(r"<span[^>]*>(.*?)</span>", tagbox.group(1), re.S)] if tagbox else [],
            "author": text(au.group(1)) if au else None,
        })
    return cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)).date().isoformat()

    posts, seen, pages, errors = [], set(), 0, []
    truncated = False
    for n in range(1, MAX_PAGES + 1):
        path = "/en/blogs" if n == 1 else f"/en/blogs/page/{n}"
        try:
            cards = parse(fetch(path))
        except urllib.error.HTTPError as e:
            if n > 1 and e.code == 404:
                break  # walked past the last index page: end, not an error
            if n == 1:
                raise
            errors.append(f"{path}: HTTP {e.code}")
            truncated = True
            break
        except Exception as e:  # noqa: BLE001
            if n == 1:
                raise  # nothing collected: fail the run
            # keep the pages we already have; flag the week as partial
            errors.append(f"{path}: {type(e).__name__}: {e}")
            truncated = True
            break
        pages = n
        if not cards:
            break
        for c in cards:
            if c["url"] not in seen:
                seen.add(c["url"])
                c["is_new"] = bool(c["date"] and c["date"] >= cutoff)
                posts.append(c)
        oldest = min((c["date"] for c in cards if c["date"]), default=None)
        if oldest is None or oldest < cutoff:
            break  # this page already reaches past the window
        if n == 1:
            page_size = len(cards)
        elif len(cards) < page_size:
            break  # short page = last page of the index
    else:
        truncated = True  # hit MAX_PAGES before reaching the cutoff

    if not posts:
        print("ERROR: 0 cards parsed -- index markup likely changed", file=sys.stderr)
        sys.exit(1)
    undated = sum(1 for p in posts if not p["date"])
    doc = {
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": BASE + "/en/blogs",
        "window_days": a.days,
        "pages_read": pages,
        "truncated": truncated,
        "errors": errors,
        "n_posts": len(posts),
        "n_new": sum(p["is_new"] for p in posts),
        "n_undated": undated,
        "posts": posts,
    }
    with open(a.out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {a.out}: {len(posts)} posts ({doc['n_new']} new, {undated} undated)")


if __name__ == "__main__":
    main()
