# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Personal productivity system integrating Gmail with Claude AI. Two main workflows:

1. **Automated triage** — launchd runs `scripts/run-email-triage.sh` on a schedule, which invokes the Claude CLI to classify the last 24 hours of email per account and write digests to `inbox/{account}/YYYY-MM-DD.md`
2. **Interactive review** — Claude Desktop detects unreviewed digests (via the `_Unreviewed — run email-review to process_` marker line) and surfaces them to the user

## Accounts

Account configuration lives in `accounts.json` at the project root. Each entry has a slug (e.g. `personal`, `work`), a human-readable label, the Gmail address, and paths to OAuth credentials.

**Adding a new account:**
1. Add an entry to `accounts.json` with the slug, label, email, and credential/token paths
2. Place the OAuth client credentials file at the configured `credentials_path`
3. Run `python scripts/archive_emails.py --account <slug>` interactively to trigger the OAuth flow and save the token
4. Run `/email-triage` to verify — the new account's digest should appear in `inbox/<slug>/`

## Scripts

```bash
# Run triage manually (normally invoked by launchd)
./scripts/run-email-triage.sh

# Archive processed emails (dry run first)
python scripts/archive_emails.py inbox/personal/YYYY-MM-DD.md --dry-run
python scripts/archive_emails.py inbox/work/YYYY-MM-DD.md --account work

# Python dependencies for archiving
pip install google-auth-oauthlib google-api-python-client
```

## Architecture

**Account registry** (`accounts.json`):
- Central config for all Gmail accounts — slugs, labels, email addresses, credential paths
- Every component reads this file to discover accounts and resolve paths
- `default_account` field used as fallback when no account is specified

**Email digest format** (`inbox/{account}/YYYY-MM-DD.md`):
- Sections: Action Items, Must Read, Deals Worth Knowing, Other, Promotional — No Deal, Spam
- Header includes account label: `# Email Digest — 2026-03-15 (Personal)`
- `archive_ids` block includes `account: <slug>` for credential resolution
- Status line `_Unreviewed — run email-review to process_` marks a digest as pending review; this line is removed/replaced when the review skill processes the file
- Legacy flat `inbox/*.md` files from before multi-account support still work

**Claude Desktop behavior** (`CLAUDE_PROJECT_PROMPT.md`):
- On first message of a conversation, check `inbox/` and subdirectories for unreviewed digests
- If found, surface a one-sentence summary with account labels before answering the user's query
- Only check once per conversation

**Gmail credentials**: OAuth2 tokens at paths specified in `accounts.json` (default: `~/.gmail_credentials.json` and `~/.gmail_token.json` for the personal account)

**Permissions**: `.claude/settings.local.json` whitelists specific tools for unattended launchd execution (notably `gmail_read_message` and `osascript` for desktop notifications)
