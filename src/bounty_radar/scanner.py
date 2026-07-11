"""
Main scanner entrypoint — runs on GitHub Actions every 6 hours.

Flow:
1. Search GitHub Issues for `label:bounty` across multiple queries
2. Filter out scams / over-competitive / stale / irrelevant bounties
3. Rank the remaining ones by score
4. Send top N to Telegram channel
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


# Search queries — cast a wide net across JS/TS/Python/Web3
QUERIES = [
    "label:bounty state:open sort:created-desc",
    "label:bounty state:open language:typescript sort:created-desc",
    "label:bounty state:open language:javascript sort:created-desc",
    "label:bounty state:open language:python sort:created-desc",
    "label:bounty state:open language:html sort:created-desc",
    "label:bounty state:open css sort:created-desc",
]


def run():
    print("[scanner] starting bounty scan")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[scanner] WARNING: GITHUB_TOKEN not set — using anonymous (rate-limited) mode")

    # Search
    all_bounties = search_bounties(QUERIES, token=token, per_page=30)
    print(f"[scanner] fetched {len(all_bounties)} total bounties")

    # Filter + rank
    top = filter_and_rank(all_bounties, max_results=5)
    print(f"[scanner] {len(top)} bounties passed filters")

    # Log to console for GitHub Actions logs
    for i, b in enumerate(top, 1):
        print(f"  [{i}] {b.title[:80]} — {b.repo} — {b.comments}c — score={filter_and_rank([b])[0] if False else ''}")

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
