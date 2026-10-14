# digest-feeds

Keyless data collectors for the weekly digest jobs. The dumb half of a
split-brain design: GitHub Actions does the deterministic fetching (free),
the VM cron jobs do the judgment (dedupe, filter, write the digest).

No secrets, no auth, no PII — everything here is public data
(Reddit public posts via Arctic Shift, a public blog index, HN front page).

## Feeds

| Feed | Collector | Schedule (UTC) | Data | VM consumer |
|---|---|---|---|---|
| r/ai_trading | `collect-ai-trading.yml` | Thu 16:30 (≈09:30 PT) | `data/ai-trading/posts-YYYY-Www.json` | `ai-trading-subreddit-watch` (Thu 10:44 PT) |
| r/AI_Agents | `collect-ai-agents.yml` | Wed 16:30 (≈09:30 PT) | `data/ai-agents/posts-YYYY-Www.json` | `wednesday-intel-digest` (Wed 09:44 PT) |
| getaiperks + freebies | `collect-getaiperks.yml` | Wed 15:30 (≈08:30 PT) | `data/getaiperks/blog-YYYY-Www.json`, `data/getaiperks/freebies-YYYY-Www.json` | `wednesday-intel-digest` (Wed 09:44 PT) |
| aiinvitecode | `collect-aiinvitecode.yml` | daily 15:30 (≈08:30 PT) | `data/aiinvitecode/new-YYYY-MM-DD.json` | `aiinvitecode-daily-check` (daily 09:00 PT) |

`YYYY-Www` is the ISO week in America/Los_Angeles (`TZ=America/Los_Angeles
date +%G-W%V`) — PT, not UTC — so the collector and the VM jobs (which run
on PT) always agree on the filename, including for manual dispatches. The
aiinvitecode feed uses calendar dates (`%F`) instead of ISO weeks because it
is a daily feed.

## Data contracts (backward-compatible: keys are only ever added)

- Reddit pulls (`collect_reddit.py`): envelope `collected_at`, `subreddit`,
  `window_days`, `n_posts`, `posts`, plus `truncated` (true if the page cap
  was hit before reaching the cutoff — treat as a partial week),
  `pages_fetched`, `n_removed_skipped` ([removed]/[deleted] posts are
  filtered out of `posts`), and `newest` (unranked freshest 25).
- `top_by_score` ranks only posts older than 36h. Arctic Shift scores are
  ingest-time and sit at 0–1 for ~36h, so young posts would never surface;
  the `newest` list covers them instead. The VM jobs were told not to rank
  by score — this makes the file honest about that.
- `selftext` is cut at 600 chars with a `… [truncated]` marker and a
  `selftext_truncated` boolean. All text fields are HTML-unescaped.
- `collect_freebies.py` isolates its two sources: if one fails, the other
  still writes and the failure lands in the top-level `errors` list.
  `hn_frontpage` is kept as an alias of the weekly `hn_weekly` list.
- `collect_aiinvitecode.py` writes an envelope (`collected_at`, `source`,
  `n_listings`, `listings`). The relative `added` field ("Added 5h ago") is
  anchored by the envelope's `collected_at`. The script exits 1 on fetch
  failure or zero parsed cards so a broken run never commits an empty file.
- `scripts/diff_aiinvitecode.py` diffs the two latest daily snapshots and
  ranks new arrivals by worth (new service > Access/Purchase bonus >
  Sign-up bonus) for the daily check.

## Notes

- Arctic Shift scores are ingest-time, not live — collectors never rank by
  score as ground truth; the JSON carries the caveat.
- Collectors are polite: ~1 req/sec against Arctic Shift (volunteer-run).
- If a collector fails or data is stale, the VM jobs fall back to pulling
  directly — the digest never hard-depends on this repo.
- All workflows share one concurrency group (`digest-feeds-data-push`) and
  `git pull --rebase` before pushing, so scheduled runs and manual
  dispatches can't collide on a push.
- GitHub disables scheduled workflows after 60 days of zero repo activity;
  every scheduled workflow here commits data on each run, so they stay
  active on their own.
- Retention: history is the point (digests compare week over week), so old
  files stay. If clone size ever becomes a problem, prune by year or move
  data to a separate branch — a decision for then, not now.
- DST: schedules are fixed UTC. After the Nov 2026 PDT→PST switch they run
  one hour earlier in PT (still comfortably before the VM jobs); the
  `github-actions-dst-revisit` job (Nov 2) owns confirming this.
