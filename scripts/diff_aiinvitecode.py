#!/usr/bin/env python3
"""Diff AIInviteCode daily snapshots: report genuinely new codes/services.

Reads data/aiinvitecode/new-YYYY-MM-DD.json files, compares the two most
recent, and emits the listings present in the latest but not the previous
one, ranked by worth. Used by the VM daily check (alerts only on new
arrivals); also handy for manual runs.

Ranking ("worth"): a brand-new service (slug never seen before) outranks a
new code on a known service; Access / Purchase bonus outrank plain Sign-up
bonus.

Usage: python3 scripts/diff_aiinvitecode.py [data_dir]
Prints a JSON doc to stdout; exit 0 always (no news is a valid result).
"""
import glob
import json
import os
import sys

WORTH_BONUS = {"access": 1, "purchase bonus": 1}


def load_latest_two(data_dir):
    files = sorted(glob.glob(os.path.join(data_dir, "new-*.json")))
    if len(files) < 2:
        return None, None
    docs = []
    for f in files[-2:]:
        with open(f) as fh:
            docs.append(json.load(fh))
    return docs[0], docs[1]


def listings_of(doc):
    # supports the envelope format; falls back to a bare list
    if isinstance(doc, dict):
        return doc.get("listings", [])
    return doc or []


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data",
        "aiinvitecode")
    prev, latest = load_latest_two(data_dir)
    if prev is None:
        print(json.dumps({"ok": False,
                          "reason": "need at least 2 daily snapshots"}))
        return
    prev_keys = {(c.get("slug"), c.get("code")) for c in listings_of(prev)}
    prev_slugs = {c.get("slug") for c in listings_of(prev)}
    new_items = []
    for c in listings_of(latest):
        key = (c.get("slug"), c.get("code"))
        if key in prev_keys:
            continue
        worth = 0
        is_new_service = c.get("slug") not in prev_slugs
        if is_new_service:
            worth += 2
        worth += WORTH_BONUS.get((c.get("bonus_type") or "").lower(), 0)
        new_items.append({**c, "new_service": is_new_service,
                          "worth": worth})
    new_items.sort(key=lambda c: (-c["worth"], c.get("name", ""),
                                  c.get("code", "")))
    print(json.dumps({
        "ok": True,
        "compared": "previous daily snapshot -> latest",
        "n_new": len(new_items),
        "items": new_items,
    }, indent=1))


if __name__ == "__main__":
    main()
