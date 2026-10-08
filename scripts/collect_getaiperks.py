#!/usr/bin/env python3
"""Fetch the Get AI Perks blog index (https://www.getaiperks.com/en/blogs).

Keyless HTML parse: title, URL, publish date, tags per card.
Usage: collect_getaiperks.py <out.json>
"""
import datetime
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"}


def main():
    out = sys.argv[1]
    req = urllib.request.Request("https://www.getaiperks.com/en/blogs",
                                 headers=UA)
    html = urllib.request.urlopen(req, timeout=40).read().decode(
        "utf-8", "replace")
    posts = []
    for m in re.finditer(r'<a[^>]+href="(/en/blogs/[^"]+)"[^>]*>(.*?)</a>',
                         html, re.S):
        href, body = m.group(1), m.group(2)
        t = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.S)
        d = re.search(r'<time[^>]+dateTime="([^"]+)"', body)
        if not t:
            continue
        title = re.sub(r"\s+", " ",
                       re.sub(r"<[^>]+>", "", t.group(1))).strip()
        posts.append({
            "title": title,
            "url": "https://www.getaiperks.com" + href,
            "date": d.group(1) if d else None,
        })
    seen, uniq = set(), []
    for p in posts:
        if p["url"] not in seen:
            seen.add(p["url"])
            uniq.append(p)
    doc = {
        "collected_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "source": "https://www.getaiperks.com/en/blogs",
        "n_posts": len(uniq),
        "posts": uniq,
    }
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {out}: {len(uniq)} posts")


if __name__ == "__main__":
    main()
