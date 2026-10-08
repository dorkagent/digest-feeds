#!/usr/bin/env python3
"""Free-stuff sweep collection: r/freebies (Arctic Shift) + HN front page (Algolia).

Keyless. Usage: collect_freebies.py <out.json>
"""
import datetime
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from collect_reddit import fetch_posts, slim_post  # noqa: E402

UA = {"User-Agent": "dorkagent-digest-feeds/1.0 (weekly free-stuff collector)"}


def hn_frontpage(n=30, tries=4):
    url = ("https://hn.algolia.com/api/v1/search?tags=front_page"
           f"&hitsPerPage={n}")
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            d = json.load(urllib.request.urlopen(req, timeout=30))
            break
        except Exception as e:
            last = e
            time.sleep(2 ** attempt + 1)
    else:
        raise last
    items = []
    for h in d.get("hits", []):
        items.append({
            "title": h.get("title"),
            "url": h.get("url"),
            "points": h.get("points"),
            "hn_url": "https://news.ycombinator.com/item?id="
                      + str(h.get("objectID")),
            "created_at": h.get("created_at"),
        })
    return items


def main():
    out = sys.argv[1]
    freebies = fetch_posts("freebies", 7)
    ranked = sorted(freebies, key=lambda p: p.get("score") or 0,
                    reverse=True)[:30]
    doc = {
        "collected_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "r_freebies": {
            "n_posts": len(freebies),
            "note": "scores are ingest-time, not live",
            "top_by_score": [slim_post(p) for p in ranked],
        },
        "hn_frontpage": hn_frontpage(),
    }
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {out}: {len(freebies)} freebies posts, "
          f"{len(doc['hn_frontpage'])} HN items")


if __name__ == "__main__":
    main()
