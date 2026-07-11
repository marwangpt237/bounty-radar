"""
Filtering and ranking logic for bounty-radar.

Given a list of Bounty objects, returns the ones worth pinging the user about,
ranked by estimated value ÷ estimated effort ÷ competition.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from .github_client import Bounty


# Repos/keywords known to be low-quality or scam patterns
BAD_REPO_PATTERNS = [
    r"zhangjiayang6835",      # AI-generated security spam
    r"Nexussyn",              # Over-subscribed agent tasks
    r"TauCetiStation",        # Russian-language game bounties
]

# Label patterns that indicate spam/low quality
BAD_LABEL_PATTERNS = [
    r"agent-task",  # AI agent oriented, not human-friendly
]

# Keywords that suggest scam/bait
SCAM_KEYWORDS = [
    "deploy this contract",
    "verify your wallet",
    "connect your wallet to claim",
    "kyc required for payout",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def is_scam(b: Bounty) -> bool:
    """Heuristic scam detector."""
    text = f"{b.title} {b.body_preview} {' '.join(b.labels)}"
    if _matches_any(text, SCAM_KEYWORDS):
        return True
    if _matches_any(b.repo, BAD_REPO_PATTERNS):
        return True
    if _matches_any(" ".join(b.labels), BAD_LABEL_PATTERNS):
        return True
    return False


def is_too_competitive(b: Bounty, max_comments: int = 15) -> bool:
    """Bounties with many comments are usually already being worked on."""
    return b.comments > max_comments


def is_too_old(b: Bounty, max_days: int = 14) -> bool:
    """Bounties older than 2 weeks are usually stuck or abandoned."""
    try:
        created = datetime.fromisoformat(b.created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        return age_days > max_days
    except Exception:
        return False


def is_relevant(b: Bounty, skill_keywords: list[str]) -> bool:
    """Check if bounty matches any of the user's skill keywords."""
    text = f"{b.title} {b.body_preview} {' '.join(b.labels)}".lower()
    return any(k.lower() in text for k in skill_keywords)


def score_bounty(b: Bounty) -> float:
    """
    Higher = better. Considers:
    - Payout amount (extracted or estimated)
    - Comment count (lower = better)
    - Age (newer = better)
    - Has "good first issue" label (bonus)
    """
    score = 0.0

    # Payout
    if b.payout_hint:
        import re
        nums = re.findall(r"\d+", b.payout_hint.replace(",", ""))
        if nums:
            amount = int(nums[0])
            # Logarithmic scaling — $50 vs $500 vs $5000 all matter but not linearly
            score += min(50, amount / 50)

    # Comments (fewer is better)
    if b.comments < 3:
        score += 20
    elif b.comments < 8:
        score += 10
    elif b.comments < 15:
        score += 2
    else:
        score -= 10

    # Age (newer is better)
    try:
        created = datetime.fromisoformat(b.created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days <= 1:
            score += 15
        elif age_days <= 3:
            score += 10
        elif age_days <= 7:
            score += 5
        else:
            score -= 5
    except Exception:
        pass

    # Good first issue bonus
    if any("good first issue" in l.lower() for l in b.labels):
        score += 10

    # Help wanted bonus
    if any("help wanted" in l.lower() for l in b.labels):
        score += 5

    # Has actual $ amount in labels
    if any("$" in l or "usdc" in l.lower() or "usdt" in l.lower() for l in b.labels):
        score += 5

    return score


def filter_and_rank(
    bounties: list[Bounty],
    skill_keywords: list[str] | None = None,
    max_results: int = 10,
) -> list[Bounty]:
    """
    Apply all filters + return ranked top N bounties.

    skill_keywords defaults to a developer-friendly profile.
    """
    if skill_keywords is None:
        skill_keywords = [
            "javascript", "typescript", "node", "react", "python", "telegram",
            "bot", "api", "rest", "css", "html", "responsive", "bug", "fix",
            "documentation", "docs", "translation", "web3", "solidity",
        ]

    filtered = []
    for b in bounties:
        if is_scam(b):
            continue
        if is_too_competitive(b):
            continue
        if is_too_old(b):
            continue
        if not is_relevant(b, skill_keywords):
            continue
        filtered.append(b)

    filtered.sort(key=score_bounty, reverse=True)
    return filtered[:max_results]
