"""
Cover letter generator — drafts a tailored comment for each bounty.

The user can copy-paste this as their initial comment on a GitHub issue
to claim a bounty, then we (the AI) write the actual fix.
"""
from __future__ import annotations

import re
from .github_client import Bounty


def _detect_stack(b: Bounty) -> list[str]:
    """Infer the tech stack from title/body/labels."""
    text = f"{b.title} {b.body_preview} {' '.join(b.labels)}".lower()
    stacks = []
    if any(k in text for k in ["react", "tsx", "jsx", "next.js", "nextjs"]):
        stacks.append("React/TypeScript")
    if any(k in text for k in ["node", "express", "npm", "yarn"]):
        stacks.append("Node.js")
    if any(k in text for k in ["python", "pytest", "pip", "django", "flask"]):
        stacks.append("Python")
    if any(k in text for k in ["css", "responsive", "mobile", "tailwind", "bootstrap"]):
        stacks.append("CSS/Responsive")
    if any(k in text for k in ["telegram", "telegraf", "bot"]):
        stacks.append("Telegram bots")
    if any(k in text for k in ["solidity", "web3", "ethers", "hardhat"]):
        stacks.append("Web3/Solidity")
    if any(k in text for k in ["docs", "documentation", "readme"]):
        stacks.append("Documentation")
    if any(k in text for k in ["translation", "translate", "localization"]):
        stacks.append("Translation")
    return stacks or ["general development"]


def _extract_task_summary(b: Bounty) -> str:
    """Try to pull a one-line summary of what's needed."""
    title = b.title
    # Strip common prefixes
    title = re.sub(r"^\[(Bounty|BUG|Agent[\- ]?Task|Fix)\][:\-]?\s*", "", title, flags=re.IGNORECASE)
    # Strip payout prefixes
    title = re.sub(r"\$\d[\d,]*\s*", "", title)
    title = re.sub(r"bounty[:\s]*\$\d[\d,]*", "", title, flags=re.IGNORECASE)
    return title.strip()[:120]


def generate_cover_letter(b: Bounty) -> str:
    """Generate a tailored claim comment for a bounty."""
    stacks = _detect_stack(b)
    summary = _extract_task_summary(b)
    stack_line = ", ".join(stacks)

    return (
        f"Hi! I'd like to take this on.\n\n"
        f"Plan:\n"
        f"1. Clone the repo and reproduce the issue locally\n"
        f"2. Read the relevant code ({summary}) and identify the root cause\n"
        f"3. Implement the fix with tests covering the new behavior\n"
        f"4. Update docs/README if needed\n"
        f"5. Submit PR with before/after description and reproduction steps\n\n"
        f"Stack I work in: {stack_line}\n"
        f"ETA: PR within 24 hours of assignment, open to quick revisions.\n\n"
        f"Profile: https://github.com/marwangpt237"
    )
