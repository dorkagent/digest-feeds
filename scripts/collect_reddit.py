#!/usr/bin/env python3
"""Keyless Reddit pull via Arctic Shift (https://arctic-shift.photon-reddit.com).

No auth, no signup. Pulls a subreddit's recent posts, slims them to
digest-ready JSON. Importable: `fetch_posts()` / `slim_post()`.
"""
import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://arctic-shift.photon-reddit.com"
UA = {"User-Agent": "dorkagent-digest-feeds/1.0 (weekly digest collector)"}
LAST_CALL = [0.0]


def get(path, params, tries=5):
    """GET with retries — Arctic Shift intermittently 422s paged requests."""
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(tries):
        # Gentle pacing: min 1s between requests (volunteer-run service).
        wait = 1.0 - (time.time() - LAST_CALL[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                LAST_CALL[0] = time.time()
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (422, 429, 500, 502, 503):
                raise
            time.sleep(2 ** attempt + 1)
    raise last


def slim_post(p):
    return {
        "id": p.get("id"),
        "author": p.get("author"),
        "created_utc": p.get("created_utc"),
        "created_iso": datetime.datetime.fromtimestamp(
            p.get("created_utc", 0), datetime.timezone.utc).isoformat(),
        "title": p.get("title"),
        "selftext": (p.get("selftext") or "")[:600],
        "score": p.get("score"),
        "num_comments": p.get("num_comments"),
        "permalink": "https://www.reddit.com" + (p.get("permalink") or ""),
        "url": p.get("url"),
        "flair": p.get("link_flair_text"),
    }


def fetch_posts(subreddit, days, max_pages=6, page_size=100, pace=1.1):
    """Newest-first raw post dicts within the last `days` days."""
    cutoff = time.time() - days * 86400
    posts, seen_ids = [], set()
    before = None
    for _ in range(max_pages):
        params = {"subreddit": subreddit, "limit": page_size}
        if before:
            params["before"] = before
        data = get("/api/posts/search", params).get("data", [])
        if not data:
            break
        for p in data:
            seen_ids.add(p.get("id"))
        fresh = [p for p in data if p.get("created_utc", 0) >= cutoff]
        posts.extend(fresh)
        oldest = min(p.get("created_utc", 0) for p in data)
        if oldest < cutoff:
            break
        before = oldest
        time.sleep(pace)
    # de-dupe (pages can overlap), newest first
    uniq = {p["id"]: p for p in posts}
    return sorted(uniq.values(), key=lambda p: p.get("created_utc", 0),
                  reverse=True)


def week_name():
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subreddit", required=True)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-n", type=int, default=0,
                    help="also emit top-N by score (scores are ingest-time)")
    a = ap.parse_args()

    posts = fetch_posts(a.subreddit, a.days)
    doc = {
        "collected_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "subreddit": a.subreddit,
        "window_days": a.days,
        "n_posts": len(posts),
        "note": "scores are ingest-time, not live — do not rank by score alone",
        "posts": [slim_post(p) for p in posts],
    }
    if a.top_n:
        ranked = sorted(posts, key=lambda p: p.get("score") or 0,
                        reverse=True)[:a.top_n]
        doc["top_by_score"] = [slim_post(p) for p in ranked]
    with open(a.out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {a.out}: {len(posts)} posts")


if __name__ == "__main__":
    main()
