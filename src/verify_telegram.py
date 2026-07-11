"""
Standalone Telegram auth verifier — runs as a separate workflow.

Use this to debug 403 errors without doing a full bounty scan.
Prints clear, actionable diagnostics.
"""
from __future__ import annotations

import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bounty_radar.telegram import verify_bot_access


def main():
    print("=" * 60)
    print("Telegram Bot Auth Verifier")
    print("=" * 60)

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        print("\n❌ TELEGRAM_BOT_TOKEN is not set.")
        print("   Add it as a GitHub repo secret:")
        print("   https://github.com/marwangpt237/bounty-radar/settings/secrets/actions")
        sys.exit(1)

    if not chat_id:
        print("\n❌ TELEGRAM_CHAT_ID is not set.")
        print("   Add it as a GitHub repo secret.")
        sys.exit(1)

    print(f"\nBot token: {bot_token[:8]}...{bot_token[-4:]}  (length: {len(bot_token)})")
    print(f"Chat ID:   {chat_id}")

    # Sanity check chat ID format
    if not chat_id.startswith("-100"):
        print(f"\n⚠️  WARNING: Chat ID '{chat_id}' does not start with '-100'.")
        print("   For private channels, the ID should look like: -1001234567890")
        print("   Re-forward a channel message to @userinfobot to get the correct ID.")
    else:
        print("✅ Chat ID format looks correct (starts with -100)")

    # Bot token sanity check
    if ":" not in bot_token:
        print(f"\n⚠️  WARNING: Bot token doesn't contain ':'.")
        print("   Real bot tokens look like: 7812345678:AAHxxxxx...xxxxx")
    else:
        print("✅ Bot token format looks correct (contains ':')")

    # Live verification
    print("\n--- Live verification ---")
    ok, msg = verify_bot_access(bot_token, chat_id)
    if ok:
        print(f"\n🎉 SUCCESS: {msg}")
        print("\nNext: trigger the 'Bounty Radar Scan' workflow — bounties should arrive in your channel.")
    else:
        print(f"\n❌ FAILED: {msg}")
        print("\nFix steps:")
        print("  1. Open your Telegram channel")
        print("  2. Tap the channel title at the top")
        print("  3. Tap 'Administrators' → 'Add Admin'")
        print("  4. Search for your bot's username (the one you gave BotFather)")
        print("  5. Add it with 'Post Messages' permission ON")
        print("  6. Save")
        print("  7. Re-run this workflow")


if __name__ == "__main__":
    main()
