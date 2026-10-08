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
| r/AI_Agents | `collect-ai-agents.yml` | Wed 16:30 (≈09:30 PT) | `data/ai-agents/posts-YYYY-Www.json` | `ai-agents-subreddit-watch` (Wed 10:44 PT) |
| getaiperks + freebies | `collect-getaiperks.yml` | Wed 15:30 (≈08:30 PT) | `data/getaiperks/blog-YYYY-Www.json`, `data/getaiperks/freebies-YYYY-Www.json` | `getaiperks-blog-watch` (Wed 09:44 PT) |

`YYYY-Www` is the ISO week (`date -u +%G-W%V`), so the collector and the
VM job always agree on the filename.

## Notes

- Arctic Shift scores are ingest-time, not live — collectors never rank by
  score as ground truth; the JSON carries the caveat.
- Collectors are polite: ~1 req/sec against Arctic Shift (volunteer-run).
- If a collector fails or data is stale, the VM jobs fall back to pulling
  directly — the digest never hard-depends on this repo.
- DST: schedules are fixed UTC. After the Nov 2026 PDT→PST switch they run
  one hour earlier in PT (still comfortably before the VM jobs); the
  `github-actions-dst-revisit` job (Nov 2) owns confirming this.
