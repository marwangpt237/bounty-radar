"""
GitHub Issues Search client for bounty-radar.

Uses the public GitHub REST API (no auth needed for low volume,
but auth raises rate limit from 10 → 30 req/min and 60 → 5000/hr).
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.parse
from dataclasses import dataclass, asdict
from typing import Iterable


GITHUB_API = "https://api.github.com"


@dataclass
class Bounty:
    """Normalized bounty object."""
    title: str
    url: str
    repo: str
    state: str
    created_at: str
    comments: int
    labels: list[str]
    body_preview: str
    payout_hint: str | None  # extracted from title/body if possible

    def to_dict(self) -> dict:
        return asdict(self)


def _request(url: str, token: str | None = None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "bounty-radar/1.0")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_payout_hint(title: str, body: str, labels: list[str]) -> str | None:
    """Try to extract a payout amount from title/body/labels."""
    text = f"{title} {body[:1000]} {' '.join(labels)}".lower()

    # Look for $NNN or NNN USDC/USDT/XLM/ETH patterns
    import re
    patterns = [
        r"\$(\d{1,5}(?:[,\d]*)?)",  # $100, $1,500
        r"(\d{1,5})\s*usdc",
        r"(\d{1,5})\s*usdt",
        r"(\d{1,5})\s*xlm",
        r"(\d{1,5})\s*eth",
        r"(\d{1,5})\s*\$",
        r"bounty[:\s]*(\d{1,5})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0).strip()
    return None


def search_bounties(
    queries: list[str],
    token: str | None = None,
    per_page: int = 30,
) -> list[Bounty]:
    """
    Run multiple GitHub Issues searches and return deduped Bounty objects.

    queries: list of GitHub search query strings, e.g.
        ["label:bounty state:open language:typescript",
         "label:bounty state:open language:python"]
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    seen_urls: set[str] = set()
    bounties: list[Bounty] = []

    for q in queries:
        params = urllib.parse.urlencode({
            "q": q,
            "per_page": per_page,
            "sort": "created",
            "order": "desc",
        })
        url = f"{GITHUB_API}/search/issues?{params}"
        try:
            data = _request(url, token=token)
        except Exception as e:
            print(f"[search] query failed: {q[:60]}... — {e}")
            continue

        for item in data.get("items", []):
            url = item["html_url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            repo_full = item["repository_url"].split("/repos/")[-1]
            labels = [l["name"] for l in item.get("labels", [])]
            body = item.get("body") or ""
            payout = _extract_payout_hint(item["title"], body, labels)

            bounties.append(Bounty(
                title=item["title"],
                url=url,
                repo=repo_full,
                state=item["state"],
                created_at=item["created_at"],
                comments=item["comments"],
                labels=labels,
                body_preview=body[:500].replace("\n", " ").strip(),
                payout_hint=payout,
            ))

    return bounties
