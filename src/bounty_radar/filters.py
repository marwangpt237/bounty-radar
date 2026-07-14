"""
Filtering and ranking logic for bounty-radar.

Given a list of Bounty objects, returns the ones worth pinging the user about,
ranked by estimated value ÷ estimated effort ÷ competition.

v2 — tightened filters to cut noise (token bounties, mirrors, low-quality orgs).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
try:
    from .github_client import Bounty
except ImportError:
    # Allow running as a standalone module (for testing)
    from github_client import Bounty


# Repos/orgs/users known to be low-quality, scam, or speculative-token bounties.
# Matched as substrings against the "owner/repo" string.
BAD_REPO_PATTERNS = [
    r"mergeos-bounties",       # MRG token bounties — 0/20 PRs merged, token has no liquidity
    r"Vikingr2023",            # Mirror account — re-posts Stacker News bounties
    r"awesome-agent-bounties", # Mirror aggregator
    r"zhangjiayang6835",       # AI-generated security spam
    r"Nexussyn",               # Over-subscribed agent tasks
    r"TauCetiStation",         # Russian-language game bounties
    r"sn-monetization-runtime",# Stacker News social bounty mirror
    r"31day",                  # Speculative token bounty platform
    r"thirtyoneday",           # Same platform
]

# Label patterns that indicate spam / low quality / non-human work
BAD_LABEL_PATTERNS = [
    r"agent-task",            # AI agent oriented, not human-friendly
    r"external-mirror",       # Re-posted from elsewhere — second-hand signal
    r"radar",                 # Mirror/aggregator tag
    r"sn",                    # Stacker News mirror
    r"bounty-hunter",         # MergeOS-style platform tag
]

# Token symbols that indicate a speculative-token bounty (not real money).
# If the payout_hint or labels contain these WITHOUT a $ or USDC/USDT/ETH/SOL,
# the bounty is paying in a project token, not stable value.
SPECULATIVE_TOKEN_SYMBOLS = [
    "mrg", "mergeos", "points", "credits", "tokens", "stars",
    "xp", "karma", "rep", " merit",  # note leading space on " merit" to avoid substring false-positives
    "coin", "gems", "loot",
]

# Currencies we accept as "real money" payout
REAL_CURRENCY_PATTERNS = [
    r"\$\s?\d",            # $100, $ 50
    r"\d+\s*usdc",
    r"\d+\s*usdt",
    r"\d+\s*eth",
    r"\d+\s*sol",
    r"\d+\s*bnb",
    r"\d+\s*btc",
    r"\d+\s*usd\b",
    r"\d+\s*eur",
]

# Keywords that suggest scam/bait
SCAM_KEYWORDS = [
    "deploy this contract",
    "verify your wallet",
    "connect your wallet to claim",
    "kyc required for payout",
    "send 0.1 eth to claim",
    "airdrop claim",
    "presale access",
]

# Title patterns that indicate a mirror/aggregator post, not a real bounty
MIRROR_TITLE_PATTERNS = [
    r"^\[radar\]",
    r"^\[mirror\]",
    r"^\[external",
    r"radar\]",  # matches "[radar]" anywhere in title
    r"mirror\]",
    r"open bounty detected",
    r"bounty detected",
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


def is_mirror(b: Bounty) -> bool:
    """Detect mirror/aggregator posts — these are second-hand signals, not real bounties.

    Catches:
    - Titles like "[radar] ...", "[mirror] ...", "Open bounty detected: ..."
    - Issues from awesome-*-bounties aggregator repos
    - Body text mentioning "mirrored on" or "external bounty"
    """
    if _matches_any(b.title, MIRROR_TITLE_PATTERNS):
        return True
    if "awesome" in b.repo.lower() and "bount" in b.repo.lower():
        return True
    body_lower = b.body_preview.lower()
    if "mirrored on" in body_lower or "external bounty" in body_lower:
        return True
    if "githubbountyhunter" in body_lower or "31day.cloud" in body_lower:
        return True
    return False


def is_speculative_token_bounty(b: Bounty) -> bool:
    """Detect bounties paid in project tokens rather than real money.

    A bounty is "speculative token" if:
    - Its payout_hint or labels mention a token symbol (MRG, points, credits, etc.)
    - AND it does NOT contain any real-currency indicator ($, USDC, USDT, ETH, SOL, BTC)

    Examples filtered:
    - "[25 MRG] Theme pack sample"  → MRG with no $ → skip
    - "bounty: 25 mrg"              → MRG → skip
    - "Earn 500 points"             → points → skip
    - "$100 USDC bounty"            → has $ → keep
    - "50 USDC for the fix"         → has USDC → keep
    """
    text = f"{b.title} {b.payout_hint or ''} {' '.join(b.labels)}".lower()

    # If real currency is mentioned, keep it
    if _matches_any(text, REAL_CURRENCY_PATTERNS):
        return False

    # If speculative token symbol is mentioned, skip
    for sym in SPECULATIVE_TOKEN_SYMBOLS:
        if sym in text:
            return True

    # If payout_hint looks like a number with no currency (e.g. "bounty: 25"),
    # and there's no real currency anywhere, treat as suspicious
    if b.payout_hint:
        nums = re.findall(r"\d+", b.payout_hint.replace(",", ""))
        if nums and not _matches_any(text, REAL_CURRENCY_PATTERNS):
            # Bare number with no currency context — likely a token amount
            return True

    return False


def is_too_competitive(b: Bounty, max_comments: int = 5) -> bool:
    """Bounties with many comments are usually already being worked on.

    Tightened from 15 → 5: by the time 5 people have commented, the maintainer
    has usually picked someone.
    """
    return b.comments > max_comments


def is_too_old(b: Bounty, max_days: int = 7) -> bool:
    """Bounties older than 1 week are usually stuck, abandoned, or already taken.

    Tightened from 14 → 7 days.
    """
    try:
        created = datetime.fromisoformat(b.created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        return age_days > max_days
    except Exception:
        return False


def is_relevant(b: Bounty, skill_keywords: list[str]) -> bool:
    """Check if bounty matches any of the user's skill keywords.

    v2: requires the keyword in the TITLE or first 200 chars of body — not just
    anywhere in the body. This avoids false positives from long body text that
    mentions 20 languages.
    """
    title_lower = b.title.lower()
    body_lower = b.body_preview[:300].lower()
    labels_lower = " ".join(b.labels).lower()

    # Strong match: keyword in title or labels
    for k in skill_keywords:
        k_lower = k.lower()
        if k_lower in title_lower or k_lower in labels_lower:
            return True

    # Weaker match: keyword in first 300 chars of body (intro / "what you'll build")
    for k in skill_keywords:
        if k.lower() in body_lower:
            return True

    return False


def score_bounty(b: Bounty) -> float:
    """
    Higher = better. Considers:
    - Payout amount (extracted or estimated)
    - Comment count (lower = better)
    - Age (newer = better)
    - Has "good first issue" label (bonus)
    - Real-currency bonus (penalize token bounties further)
    """
    score = 0.0

    # Payout
    if b.payout_hint:
        nums = re.findall(r"\d+", b.payout_hint.replace(",", ""))
        if nums:
            amount = int(nums[0])
            # Logarithmic scaling — $50 vs $500 vs $5000 all matter but not linearly
            score += min(50, amount / 50)

    # Comments (fewer is better) — tightened scoring
    if b.comments < 2:
        score += 25
    elif b.comments < 4:
        score += 15
    elif b.comments <= 5:
        score += 5
    else:
        score -= 15

    # Age (newer is better) — tightened to favor very fresh
    try:
        created = datetime.fromisoformat(b.created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days <= 1:
            score += 20
        elif age_days <= 3:
            score += 12
        elif age_days <= 5:
            score += 5
        else:
            score -= 10
    except Exception:
        pass

    # Good first issue bonus
    if any("good first issue" in l.lower() for l in b.labels):
        score += 8

    # Help wanted bonus
    if any("help wanted" in l.lower() for l in b.labels):
        score += 5

    # REAL currency bonus — strong signal the bounty actually pays
    text = f"{b.title} {b.payout_hint or ''} {' '.join(b.labels)}".lower()
    if _matches_any(text, REAL_CURRENCY_PATTERNS):
        score += 25  # Big bonus: this is a real-money bounty

    # Penalize bare-number payouts (likely tokens)
    if b.payout_hint:
        nums = re.findall(r"\d+", b.payout_hint.replace(",", ""))
        if nums and not _matches_any(text, REAL_CURRENCY_PATTERNS):
            score -= 30  # Heavy penalty: speculative token

    return score


def filter_and_rank(
    bounties: list[Bounty],
    skill_keywords: list[str] | None = None,
    max_results: int = 10,
) -> list[Bounty]:
    """
    Apply all filters + return ranked top N bounties.

    skill_keywords defaults to a Python/backend/OSINT developer profile
    (tightened from the previous kitchen-sink list).
    """
    if skill_keywords is None:
        # Tightened: focus on what the user actually ships in
        skill_keywords = [
            # Languages
            "python", "typescript", "javascript",
            # Backend / infra
            "api", "rest", "fastapi", "flask", "django",
            "scraper", "scraping", "automation", "crawler",
            "telegram", "bot", "discord",
            # OSINT / security
            "osint", "intelligence", "investigation",
            "security", "vulnerability", "exploit",
            # Data
            "database", "sql", "postgres", "sqlite",
            "etl", "pipeline", "data",
            # Web3 (only real-money)
            "solidity", "web3", "ethereum", "solana",
            # Common bounty verbs
            "fix", "implement", "build", "migrate", "refactor",
        ]

    filtered = []
    skip_reasons = {"scam": 0, "mirror": 0, "token": 0, "competitive": 0, "old": 0, "irrelevant": 0}

    for b in bounties:
        if is_scam(b):
            skip_reasons["scam"] += 1
            continue
        if is_mirror(b):
            skip_reasons["mirror"] += 1
            continue
        if is_speculative_token_bounty(b):
            skip_reasons["token"] += 1
            continue
        if is_too_competitive(b):
            skip_reasons["competitive"] += 1
            continue
        if is_too_old(b):
            skip_reasons["old"] += 1
            continue
        if not is_relevant(b, skill_keywords):
            skip_reasons["irrelevant"] += 1
            continue
        filtered.append(b)

    # Log skip reasons (visible in GitHub Actions logs)
    total_skipped = sum(skip_reasons.values())
    if total_skipped > 0:
        print(f"[filters] skipped {total_skipped} bounties: {skip_reasons}")

    filtered.sort(key=score_bounty, reverse=True)
    return filtered[:max_results]
