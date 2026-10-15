#!/usr/bin/env python3
"""Free-stuff sweep collection: r/freebies (Arctic Shift) + HN (Algolia).

Keyless. Each source is isolated: if one fails, the other still writes and
the failure is recorded in the top-level "errors" list (partial output beats
losing both files). If BOTH fail, the file is still written (with errors)
but the script exits 1.

Usage: collect_freebies.py <out.json>
"""
import datetime
import html
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from collect_reddit import (fetch_posts, ranked_and_newest,  # noqa: E402
                            slim_post)

UA = {"User-Agent": "dorkagent-digest-feeds/1.0 (weekly free-stuff collector)"}


def hn_weekly(n=30, tries=4):
    """Top-scoring stories of the last 7 days via Algolia.

    (The old front_page snapshot only covered one moment in time; a week
    window matches the digest's cadence.) The /search endpoint ranks by
    points by default; we re-sort client-side to be sure.
    """
    now = int(time.time())
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>{now - 7 * 86400},created_at_i<{now}",
        "hitsPerPage": n,
    }
    url = ("https://hn.algolia.com/api/v1/search?"
           + urllib.parse.urlencode(params))
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            break
        except Exception as e:  # noqa: BLE001 - any network/parse failure
            last = e
            time.sleep(2 ** attempt + 1)
    else:
        raise last
    hits = sorted(d.get("hits", []), key=lambda h: h.get("points") or 0,
                  reverse=True)[:n]
    items = []
    for h in hits:
        items.append({
            "title": html.unescape(h.get("title") or ""),
            "url": h.get("url"),
            "points": h.get("points"),
            "hn_url": "https://news.ycombinator.com/item?id="
                      + str(h.get("objectID")),
            "created_at": h.get("created_at"),
        })
    return items


def main():
    if len(sys.argv) != 2:
        print("usage: collect_freebies.py <out.json>", file=sys.stderr)
        sys.exit(2)
    out = sys.argv[1]
    errors = []

    freebies, freebies_info = [], {}
    try:
        freebies, freebies_info = fetch_posts("freebies", 7)
    except Exception as e:  # noqa: BLE001 - isolate: HN must still run
        errors.append(f"r/freebies: {type(e).__name__}: {e}")

    hn_items = []
    try:
        hn_items = hn_weekly()
    except Exception as e:  # noqa: BLE001 - isolate: freebies data survives
        errors.append(f"hn: {type(e).__name__}: {e}")

    ranked, newest = ranked_and_newest(freebies, top_n=30)
    doc = {
        "collected_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "errors": errors,
        "r_freebies": {
            "n_posts": len(freebies),
            "truncated": freebies_info.get("truncated", None),
            "n_removed_skipped": freebies_info.get("n_removed_skipped", None),
            "note": ("scores are ingest-time and meaningless under ~36h: "
                     "top_by_score ranks posts older than 36h only; newest "
                     "is the unranked freshest slice"),
            "top_by_score": [slim_post(p) for p in ranked],
            "newest": [slim_post(p) for p in newest],
        },
        "hn_weekly": hn_items,
        # hn_frontpage kept as an alias: downstream consumers written
        # against the old name keep working.
        "hn_frontpage": hn_items,
    }
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {out}: {len(freebies)} freebies posts, "
          f"{len(hn_items)} HN items, errors={errors or 'none'}")
    if len(errors) == 2:
        # Both sources failed: the file carries the errors for inspection,
        # but exit 1 so the run shows red instead of passing silently.
        sys.exit(1)


if __name__ == "__main__":
    main()
