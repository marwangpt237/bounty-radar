"""Tests for bounty-radar — uses no network (mocked)."""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bounty_radar.github_client import Bounty, _extract_payout_hint, search_bounties
from bounty_radar.filters import (
    is_scam, is_too_competitive, is_too_old, is_relevant,
    score_bounty, filter_and_rank,
)
from bounty_radar.cover_letter import generate_cover_letter, _detect_stack


def make_bounty(**overrides) -> Bounty:
    defaults = dict(
        title="Fix CSS bug",
        url="https://github.com/test/repo/issues/1",
        repo="test/repo",
        state="open",
        created_at=datetime.now(timezone.utc).isoformat(),
        comments=2,
        labels=["bounty", "good first issue"],
        body_preview="Need to fix the responsive layout on mobile devices",
        payout_hint="$50",
    )
    defaults.update(overrides)
    return Bounty(**defaults)


# --- Payout extraction ---

def test_extract_payout_dollar():
    assert _extract_payout_hint("[Bounty $100] Fix bug", "", []) == "$100"

def test_extract_payout_usdc():
    assert _extract_payout_hint("Title", "5 USDC reward", []) == "5 usdc"

def test_extract_payout_none():
    assert _extract_payout_hint("Just a title", "no money mentioned", []) is None


# --- Scam detection ---

def test_scam_by_repo():
    b = make_bounty(repo="zhangjiayang6835-cyber/ai-research")
    assert is_scam(b)

def test_scam_by_keyword():
    b = make_bounty(body_preview="Please deploy this contract to verify your wallet")
    assert is_scam(b)

def test_not_scam_clean():
    b = make_bounty()
    assert not is_scam(b)


# --- Competition filter ---

def test_too_competitive():
    assert is_too_competitive(make_bounty(comments=20))
    assert not is_too_competitive(make_bounty(comments=5))


# --- Age filter ---

def test_too_old():
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert is_too_old(make_bounty(created_at=old_date))

def test_not_old():
    assert not is_too_old(make_bounty())


# --- Relevance ---

def test_relevant_python():
    b = make_bounty(title="Python CLI bug", body_preview="Fix the parser")
    assert is_relevant(b, ["python", "javascript"])

def test_not_relevant():
    b = make_bounty(title="Rust kernel module", body_preview="Assembly required")
    assert not is_relevant(b, ["python", "javascript", "css"])


# --- Scoring ---

def test_score_high_payout_low_competition():
    b = make_bounty(payout_hint="$500", comments=2)
    score = score_bounty(b)
    assert score > 20

def test_score_low_payout_high_competition():
    b = make_bounty(payout_hint="$10", comments=20)
    high_b = make_bounty(payout_hint="$500", comments=2)
    assert score_bounty(b) < score_bounty(high_b)

def test_score_good_first_issue_bonus():
    b1 = make_bounty(labels=["bounty"])
    b2 = make_bounty(labels=["bounty", "good first issue"])
    assert score_bounty(b2) > score_bounty(b1)


# --- Filter & rank ---

def test_filter_rank_returns_top_n():
    bounties = [
        make_bounty(title="Low", payout_hint="$10", comments=20),
        make_bounty(title="High", payout_hint="$500", comments=2),
        make_bounty(title="Med", payout_hint="$50", comments=5),
    ]
    ranked = filter_and_rank(bounties, max_results=2)
    assert len(ranked) == 2
    assert ranked[0].title == "High"

def test_filter_excludes_scam():
    bounties = [
        make_bounty(repo="zhangjiayang6835-cyber/x"),
        make_bounty(payout_hint="$100"),
    ]
    ranked = filter_and_rank(bounties, max_results=5)
    assert all("zhangjiayang6835" not in b.repo for b in ranked)


# --- Cover letter ---

def test_cover_letter_mentions_profile():
    b = make_bounty()
    letter = generate_cover_letter(b)
    assert "marwangpt237" in letter
    assert "Plan:" in letter

def test_detect_stack_react():
    b = make_bounty(title="Fix React component", body_preview="The tsx file has a bug")
    assert "React/TypeScript" in _detect_stack(b)

def test_detect_stack_python():
    b = make_bounty(title="Python pytest failing", body_preview="")
    assert "Python" in _detect_stack(b)


# --- search_bounties (mocked) ---

@patch("bounty_radar.github_client._request")
def test_search_bounties_dedupes(mock_request):
    # Same issue returned by two queries should be deduped
    mock_request.return_value = {
        "items": [
            {
                "html_url": "https://github.com/test/repo/issues/1",
                "title": "Bug",
                "repository_url": "https://api.github.com/repos/test/repo",
                "state": "open",
                "created_at": "2026-07-10T00:00:00Z",
                "comments": 2,
                "labels": [{"name": "bounty"}],
                "body": "Fix the bug",
            }
        ]
    }
    results = search_bounties(["query1", "query2"], token="fake")
    assert len(results) == 1  # deduped
