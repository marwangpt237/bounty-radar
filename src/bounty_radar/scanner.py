"""
Main scanner entrypoint — runs on GitHub Actions every 6 hours.

Flow:
1. Search GitHub Issues for `label:bounty` across multiple queries
2. Filter out scams / mirrors / token bounties / over-competitive / stale / irrelevant
3. Rank the remaining ones by score
4. Send top N to Telegram channel

v2 — query-level exclusions for known bad orgs + tighter search.
"""
from __future__ import annotations

import os
import sys

# Allow running both as `python -m bounty_radar.scanner` and `python src/bounty_radar/scanner.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bounty_radar.github_client import search_bounties
from bounty_radar.filters import filter_and_rank
from bounty_radar.telegram import send_bounties
from bounty_radar.cover_letter import generate_cover_letter
from bounty_radar.github_client import Bounty


# Orgs/users to exclude at the GitHub search level (most efficient — they never enter pipeline).
# Format: `-user:OWNERNAME` (excludes all repos owned by that user/org)
EXCLUDED_ORGS = [
    "-user:mergeos-bounties",   # MRG token bounties, 0/20 PRs merged
    "-user:Vikingr2023",        # Mirror aggregator account
    "-user:zhangjiayang6835",   # AI-generated security spam
    "-user:Nexussyn",           # Over-subscribed agent tasks
    "-user:TauCetiStation",     # Russian-language game bounties
    "-user:relayhop",           # Stacker News mirror source
]

# Search queries — cast a wide net but exclude known-bad orgs.
# The EXCLUDED_ORGS string is appended to each query.
_BASE = "label:bounty state:open sort:created-desc"
_EXCLUDES = " ".join(EXCLUDED_ORGS)

QUERIES = [
    f"{_BASE} {_EXCLUDES}",
    f"{_BASE} language:typescript {_EXCLUDES}",
    f"{_BASE} language:javascript {_EXCLUDES}",
    f"{_BASE} language:python {_EXCLUDES}",
    # Removed: language:html and css queries — they were surfacing MergeOS theme-pack bounties.
    # If we want HTML/CSS bounties later, we'll add them back with stricter filters.
    f"{_BASE} language:rust {_EXCLUDES}",
    f"{_BASE} language:go {_EXCLUDES}",
    # Real-money bounties only — explicit USDC/USDT/$ mentions
    f"label:bounty state:open USDC sort:created-desc {_EXCLUDES}",
    f"label:bounty state:open USDT sort:created-desc {_EXCLUDES}",
    f"label:bounty state:open \\$ sort:created-desc {_EXCLUDES}",
]


def run():
    print("[scanner] starting bounty scan")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[scanner] WARNING: GITHUB_TOKEN not set — using anonymous (rate-limited) mode")

    # Search
    all_bounties = search_bounties(QUERIES, token=token, per_page=30)
    print(f"[scanner] fetched {len(all_bounties)} total bounties")

    # Filter + rank (logs skip reasons)
    top = filter_and_rank(all_bounties, max_results=5)
    print(f"[scanner] {len(top)} bounties passed filters")

    # Log to console for GitHub Actions logs
    for i, b in enumerate(top, 1):
        print(f"  [{i}] {b.title[:80]} — {b.repo} — {b.comments}c — payout={b.payout_hint}")

    if not top:
        print("[scanner] no bounties passed filters this run — try again in 6 hours")
        return []

    # Send to Telegram (resilient — returns 0 if auth fails, doesn't crash)
    sent = send_bounties(top)
    print(f"[scanner] sent {sent}/{len(top)} to Telegram")

    # Also print cover letters for top 3 to Actions logs (so user can copy from logs too)
    print("\n[scanner] cover letters for top 3 (also in Telegram):")
    for i, b in enumerate(top[:3], 1):
        print(f"\n=== #{i} {b.title} ===")
        print(f"URL: {b.url}")
        print(f"Payout hint: {b.payout_hint or 'unknown'}")
        print("--- cover letter ---")
        print(generate_cover_letter(b))
        print("--- end ---\n")

    return top


if __name__ == "__main__":
    run()
