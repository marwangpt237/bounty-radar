"""
Telegram bot integration — posts bounty matches to a channel.

Uses Telegram Bot API directly (no SDK needed, urllib only).
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
import urllib.error
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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Read the error body — Telegram always returns JSON with description
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            description = err_json.get("description", err_body)
        except Exception:
            description = str(e)
        raise RuntimeError(f"Telegram API error {e.code} on {method}: {description}") from e


def verify_bot_access(bot_token: str, chat_id: str) -> tuple[bool, str]:
    """
    Pre-flight check: can the bot post to this chat?
    Returns (success, message).
    """
    try:
        resp = _tg_request(bot_token, "getChat", {"chat_id": chat_id})
        if resp.get("ok"):
            chat = resp.get("result", {})
            chat_type = chat.get("type", "unknown")
            chat_title = chat.get("title", chat.get("username", "untitled"))
            return True, f"Bot can access chat: '{chat_title}' (type: {chat_type})"
        return False, f"Telegram returned ok=false: {resp}"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


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

    Pre-flight checks the bot can access the chat, prints a clear error
    if not, and exits gracefully (no stack trace) on auth failure.
    """
    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars required. "
            "Set them in GitHub repo secrets."
        )

    # Pre-flight: verify bot can access the chat
    ok, msg = verify_bot_access(bot_token, chat_id)
    if not ok:
        print(f"[telegram] ❌ Pre-flight check failed: {msg}")
        print("[telegram] Common fixes:")
        print("  1. Add the bot as ADMINISTRATOR of your channel (not just member)")
        print("  2. Make sure TELEGRAM_CHAT_ID starts with '-100' (e.g., -1001234567890)")
        print("  3. Re-check TELEGRAM_BOT_TOKEN is the full string from @BotFather")
        print("  4. Forward any channel message to @userinfobot to confirm chat ID")
        # Return 0 instead of raising — workflow can still pass with results in logs
        return 0
    print(f"[telegram] ✅ {msg}")

    sent = 0
    if not bounties:
        try:
            _tg_request(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": "📭 No fresh bounties matched your filter this run.",
                "parse_mode": "Markdown",
            })
        except RuntimeError as e:
            print(f"[telegram] failed to send empty notification: {e}")
        return 0

    # Header
    import datetime
    try:
        _tg_request(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"🛡 *Bounty Radar* — {len(bounties)} new match(es)\n_{datetime.datetime.utcnow().isoformat()}_",
            "parse_mode": "Markdown",
        })
    except RuntimeError as e:
        print(f"[telegram] failed to send header: {e}")
        return 0

    for i, b in enumerate(bounties, 1):
        try:
            _tg_request(bot_token, "sendMessage", {
                "chat_id": chat_id,
                "text": _format_bounty(b, i),
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
            sent += 1
        except RuntimeError as e:
            print(f"[telegram] failed to send {b.url}: {e}")

    return sent
