# 🛡 Bounty Radar

Automated GitHub bounty scanner that posts fresh, filtered, ranked bounties to a private Telegram channel every 6 hours. Built for hunters who don't have time to scroll GitHub Issues all day.

## How it works

```
Every 6 hours (GitHub Actions, free):
  → Scans GitHub Issues API for `label:bounty`
  → Filters out scams, stale, over-competitive bounties
  → Scores each remaining bounty (payout ÷ competition ÷ age)
  → Sends top 5 to your private Telegram channel
  → Each message includes title, payout, link, score, and labels
```

You check Telegram in the morning, see 3-5 fresh bounties, pick one, paste the link to your AI pair-programmer, and they write the fix. 15 min/day total.

## Setup (10 minutes, all from your phone)

### Step 1: Create a Telegram bot (2 min)
1. Open Telegram, search `@BotFather`
2. Send `/newbot`
3. Pick a name (e.g., `Marwan Bounty Radar`)
4. Pick a username ending in `bot` (e.g., `marwan_bounty_radar_bot`)
5. Copy the **bot token** (looks like `7812345678:AAH...`)

### Step 2: Create a private channel (1 min)
1. In Telegram, tap the pencil icon → **New Channel**
2. Name it `Bounty Radar` (or whatever)
3. Set to **Private**
4. Add your bot as an **administrator** (it needs to post messages)

### Step 3: Get your channel ID (2 min)
1. In your channel, post any message
2. Forward that message to `@userinfobot` (a free Telegram utility bot)
3. It will reply with the chat ID — looks like `-1001234567890` (negative number)
4. Copy that

### Step 4: Add secrets to the GitHub repo (5 min)
1. Go to https://github.com/marwangpt237/bounty-radar/settings/secrets/actions
2. Click **New repository secret** twice — add these two:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | your bot token from step 1 |
| `TELEGRAM_CHAT_ID` | your channel ID from step 3 |

> **Note:** Do NOT try to create a secret named `GITHUB_TOKEN` — GitHub will reject it ("secret name cannot begin with GITHUB_"). GitHub Actions automatically provides a `GITHUB_TOKEN` with read access to public repos, which is all the scanner needs.

### Step 5: Trigger the first run
1. Go to https://github.com/marwangpt237/bounty-radar/actions
2. Click **Bounty Radar Scan** workflow
3. Click **Run workflow** → **Run workflow**
4. Wait 2 minutes → check your Telegram channel — first batch of bounties should arrive

After that, it runs automatically every 6 hours forever (free).

## Customizing filters

Edit `src/bounty_radar/filters.py`:

- `skill_keywords` in `filter_and_rank()` — add your own skills (e.g., `"rust"`, `"go"`, `"kotlin"`)
- `max_comments` in `is_too_competitive()` — lower it for less competition, raise for more options
- `max_days` in `is_too_old()` — only see fresh bounties
- `BAD_REPO_PATTERNS` — add repos you want to permanently skip
- `SCAM_KEYWORDS` — add new scam patterns you discover

## Customizing search queries

Edit `src/bounty_radar/scanner.py`:

```python
QUERIES = [
    "label:bounty state:open sort:created-desc",
    "label:bounty state:open language:typescript sort:created-desc",
    # Add more languages or topics:
    # "label:bounty state:open language:rust sort:created-desc",
    # "label:bounty state:open language:go sort:created-desc",
]
```

## Local testing

```bash
# Run tests
pip install pytest
python -m pytest tests/ -v

# Run scanner manually (needs env vars)
export GITHUB_TOKEN=ghp_xxx
export TELEGRAM_BOT_TOKEN=7812345678:AAHxxx
export TELEGRAM_CHAT_ID=-1001234567890
cd src && python -m bounty_radar.scanner
```

## Costs

- GitHub Actions: **Free** (2000 min/month — this uses ~5 min/run × 4 runs/day = 600 min/month)
- Telegram Bot API: **Free**
- GitHub API: **Free** (with token, 5000 req/hr)

Total: **$0/month forever.**

## License

MIT — do whatever you want.
