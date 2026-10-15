#!/usr/bin/env python3
"""Keyless Reddit pull via Arctic Shift (https://arctic-shift.photon-reddit.com).

No auth, no signup. Pulls a subreddit's recent posts, slims them to
digest-ready JSON. Importable: `fetch_posts()` / `slim_post()` /
`ranked_and_newest()`.

Ranking honesty: Arctic Shift scores are ingest-time and sit at 0-1 for
~36h after a post appears, so `top_by_score` only ranks posts OLDER than
36h. Fresh posts are covered by the separate unranked `newest` list.
"""
import argparse
import datetime
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://arctic-shift.photon-reddit.com"
UA = {"User-Agent": "dorkagent-digest-feeds/1.0 (weekly digest collector)"}
LAST_CALL = [0.0]
RANK_MIN_AGE_S = 36 * 3600  # scores are meaningless before this
REMOVED_MARKERS = ("[removed]", "[deleted]")
# 422 = Arctic Shift's "Timeout. Maybe slow down"; 504 and 520-524 are
# Cloudflare-fronted gateway/origin timeouts.
RETRY_CODES = (422, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524)


def get(path, params, tries=5):
    """GET with retries. Retries HTTP 422/429/5xx (RETRY_CODES) AND network errors
    (URLError, timeouts, connection resets) — Arctic Shift is volunteer-run
    and intermittently flaky on both."""
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
            if e.code not in RETRY_CODES:
                raise
            time.sleep(2 ** attempt + 1)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(2 ** attempt + 1)
    raise last


def is_removed(p):
    """A [removed]/[deleted] post has no content left — it only eats budget."""
    title = (p.get("title") or "").strip()
    selftext = (p.get("selftext") or "").strip()
    # removed_by_category (reddit / moderator / automod_filtered / deleted /
    # ...) also catches removed link posts whose text was never replaced.
    return (title in REMOVED_MARKERS or selftext in REMOVED_MARKERS
            or p.get("removed") is True
            or bool(p.get("removed_by_category")))


def slim_post(p):
    created = p.get("created_utc") or 0
    selftext = html.unescape(p.get("selftext") or "")
    truncated = len(selftext) > 600
    if truncated:
        selftext = selftext[:600] + "\u2026 [truncated]"
    return {
        "id": p.get("id"),
        "author": p.get("author"),
        "created_utc": created,
        "created_iso": (datetime.datetime.fromtimestamp(
            created, datetime.timezone.utc).isoformat() if created else None),
        "title": html.unescape(p.get("title") or ""),
        "selftext": selftext,
        "selftext_truncated": truncated,
        "score": p.get("score"),
        "num_comments": p.get("num_comments"),
        "permalink": "https://www.reddit.com" + (p.get("permalink") or ""),
        "url": p.get("url"),
        "flair": p.get("link_flair_text"),
    }


def fetch_posts(subreddit, days, max_pages=12, page_size=100, pace=1.1):
    """Newest-first slimmed post dicts within the last `days` days.

    Pages until the oldest post on a page is older than the cutoff (or the
    page cap is hit). Returns (posts, info) where info carries truncated /
    removed-skipped / page counts for the envelope.

    NOTE on `before`: Arctic Shift's before=TS *excludes* posts at exactly
    TS, so we page with before = oldest + 1 and de-dupe by id on overlap.
    """
    cutoff = time.time() - days * 86400
    posts, pages, n_removed = [], 0, 0
    before = None
    truncated = False
    for _ in range(max_pages):
        params = {"subreddit": subreddit, "limit": page_size}
        if before:
            params["before"] = before
        data = get("/api/posts/search", params).get("data", [])
        if not data:
            break
        pages += 1
        fresh = [p for p in data if (p.get("created_utc") or 0) >= cutoff]
        for p in fresh:
            if is_removed(p):
                n_removed += 1
            else:
                posts.append(p)
        stamps = [p.get("created_utc") or 0 for p in data]
        stamps = [s for s in stamps if s > 0]
        if not stamps:
            break
        oldest = min(stamps)
        if oldest < cutoff:
            break
        before = oldest + 1
        time.sleep(pace)
    else:
        truncated = True  # loop exhausted max_pages without reaching cutoff
    # de-dupe (pages can overlap), newest first
    uniq = {}
    for i, p in enumerate(posts):
        uniq[p.get("id") or f"__noid_{i}"] = p
    ordered = sorted(uniq.values(),
                     key=lambda p: p.get("created_utc") or 0, reverse=True)
    info = {"pages_fetched": pages, "truncated": truncated,
            "n_removed_skipped": n_removed}
    return ordered, info


def ranked_and_newest(posts, top_n=25, newest_n=25, now=None):
    """Split posts into (top_by_score, newest).

    top_by_score ranks ONLY posts older than RANK_MIN_AGE_S (younger posts'
    scores are still 0-1 and would never surface). newest is the unranked
    freshest slice so new posts are never invisible.
    """
    now = now or time.time()
    old = [p for p in posts
           if (now - (p.get("created_utc") or 0)) >= RANK_MIN_AGE_S]
    ranked = sorted(old, key=lambda p: p.get("score") or 0,
                    reverse=True)[:top_n]
    newest = sorted(posts, key=lambda p: p.get("created_utc") or 0,
                    reverse=True)[:newest_n]
    return ranked, newest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subreddit", required=True)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-n", type=int, default=0,
                    help="also emit top-N by score (posts >36h old only) "
                         "plus an unranked newest list")
    a = ap.parse_args()

    posts, info = fetch_posts(a.subreddit, a.days)
    doc = {
        "collected_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "subreddit": a.subreddit,
        "window_days": a.days,
        "n_posts": len(posts),
        "truncated": info["truncated"],
        "pages_fetched": info["pages_fetched"],
        "n_removed_skipped": info["n_removed_skipped"],
        "note": ("scores are ingest-time and meaningless under ~36h: "
                 "top_by_score ranks posts older than 36h only; newest is "
                 "the unranked freshest slice"),
        "posts": [slim_post(p) for p in posts],
    }
    if a.top_n:
        ranked, newest = ranked_and_newest(posts, top_n=a.top_n)
        doc["top_by_score"] = [slim_post(p) for p in ranked]
        doc["newest"] = [slim_post(p) for p in newest]
    with open(a.out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {a.out}: {len(posts)} posts "
          f"({info['n_removed_skipped']} removed skipped, "
          f"truncated={info['truncated']})")


if __name__ == "__main__":
    main()
