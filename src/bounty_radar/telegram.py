"""
Telegram bot integration — posts bounty matches to a channel.

Uses Telegram Bot API directly (no SDK needed, urllib only).
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
from .github_client import Bounty
from .filters import score_bounty


def _tg_request(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _format_bounty(b: Bounty, rank: int) -> str:
    """Format a bounty as a Telegram message (Markdown)."""
    payout = f"💰 *Payout hint:* `{b.payout_hint}`\n" if b.payout_hint else ""
    labels = ", ".join(f"#{l.replace(' ', '_').replace('-', '_')}" for l in b.labels[:5])
    score = score_bounty(b)

    return (
        f"*#{rank} — {b.title}*\n\n"
        f"{payout}"
        f"📦 *Repo:* `{b.repo}`\n"
        f"📅 *Created:* {b.created_at[:10]}\n"
        f"💬 *Comments:* {b.comments}\n"
        f"⭐ *Score:* {score:.1f}\n\n"
        f"🏷 {labels}\n\n"
        f"Preview: {b.body_preview[:200]}...\n\n"
        f"🔗 {b.url}"
    )


def send_bounties(
    bounties: list[Bounty],
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> int:
    """
    Send a batch of bounties to the Telegram channel.
    Returns number of successfully sent messages.
    """
    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars required. "
            "Set them in GitHub repo secrets."
        )

    sent = 0
    if not bounties:
        _tg_request(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "📭 No fresh bounties matched your filter this run.",
            "parse_mode": "Markdown",
        })
        return 0

    # Header
    _tg_request(bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": f"🛡 *Bounty Radar* — {len(bounties)} new match(es)\n_{__import__('datetime').datetime.utcnow().isoformat()}_",
        "parse_mode": "Markdown",
    })

    for i, b in enumerate(bounties, 1):
        try:
            _tg_request(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": _format_bounty(b, i),
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
            sent += 1
        except Exception as e:
            print(f"[telegram] failed to send {b.url}: {e}")

    return sent
