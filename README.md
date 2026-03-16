# claude-productivity-skills

A collection of Claude Code skills and supporting infrastructure for personal productivity automation. Currently focused on Gmail triage, with more skills planned.

## Skills

Skills live in `skills/` and are the source of truth. To use them, copy or symlink each skill directory into `~/.claude/skills/`:

```bash
# Option A: symlink (edits in the repo take effect immediately)
ln -s ~/git/claude-productivity-skills/skills/email-triage ~/.claude/skills/email-triage
ln -s ~/git/claude-productivity-skills/skills/email-review ~/.claude/skills/email-review

# Option B: copy (snapshot; re-copy to update)
cp -r skills/email-triage ~/.claude/skills/
cp -r skills/email-review ~/.claude/skills/
```

### email-triage

Fetches the last 24 hours of inbox email per configured account, classifies every message into five buckets (Must Read, Deals, Other, Promotional — No Deal, Spam), extracts explicit action items, and writes a digest to `inbox/{account}/YYYY-MM-DD.md`.

Invoke with `/email-triage` in Claude Code or Claude Desktop.

### email-review

Finds unreviewed digests, presents them interactively, walks you through each section, and archives confirmed emails via the Gmail API.

Invoke with `/email-review` in Claude Code or Claude Desktop.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/claude-productivity-skills.git ~/git/claude-productivity-skills
cd ~/git/claude-productivity-skills
```

### 2. Configure accounts

```bash
cp accounts.json.example accounts.json
```

Edit `accounts.json` with your Gmail address(es) and OAuth credential paths. The default credential paths (`~/.gmail_credentials.json`, `~/.gmail_token.json`) work fine for a single account. Add additional entries under `accounts` for multiple accounts, each with a unique slug.

### 3. Set up Gmail OAuth credentials

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/) and enable the Gmail API
2. Create OAuth 2.0 credentials (Desktop app type), download the JSON file, and place it at the `credentials_path` you set in `accounts.json`
3. Run the archive script interactively to complete the OAuth flow and save the token:
   ```bash
   pip install google-auth-oauthlib google-api-python-client
   python scripts/archive_emails.py --account personal
   ```
   A browser window will open for you to authorize access. The token is saved to `token_path`.

### 4. Install skills

Follow the copy/symlink instructions above to install skills to `~/.claude/skills/`.

### 5. Configure Claude Code permissions

The `.claude/settings.local.json` file whitelists tools needed for unattended triage runs (launchd). Copy and customize the example:

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
```

Update the `Write` path if your repo is not at `~/git/claude-productivity-skills/`.

### 6. (Optional) Set up the local Gmail MCP server

The `scripts/gmail_mcp_server.py` script is a local MCP server that provides Gmail search/read capabilities when running Claude Code headlessly (e.g. via launchd, where Claude Desktop's Gmail tools are not available). It reads `accounts.json` and uses the same OAuth credentials.

`.mcp.json` is already configured to start this server. No additional setup is required if you have Python 3 and the dependencies from step 3.

### 7. (Optional) Schedule daily triage with launchd

A launchd plist template is in `launchd/com.example.email-triage.plist`. Copy it, substitute your username and repo path, and load it:

```bash
# 1. Copy the template
cp launchd/com.example.email-triage.plist \
   ~/Library/LaunchAgents/com.$(whoami).email-triage.plist

# 2. Edit the copy — replace YOUR_USERNAME and REPO_DIR throughout
open ~/Library/LaunchAgents/com.$(whoami).email-triage.plist

# 3. Load the job (runs daily at 8:00 AM)
launchctl load ~/Library/LaunchAgents/com.$(whoami).email-triage.plist
```

Logs go to `logs/email-triage.log` and `logs/email-triage-error.log` (gitignored).

---

## Project structure

```
claude-productivity-skills/
├── skills/
│   ├── email-triage/SKILL.md       # Triage skill (source of truth)
│   └── email-review/SKILL.md       # Review skill (source of truth)
├── scripts/
│   ├── run-email-triage.sh         # launchd entry point
│   ├── archive_emails.py           # Archives emails via Gmail API
│   └── gmail_mcp_server.py         # Local MCP server for headless runs
├── launchd/
│   └── com.example.email-triage.plist  # launchd template
├── accounts.json.example           # Account config template
├── .claude/
│   └── settings.local.json.example # Claude Code permissions template
├── .mcp.json                       # MCP server config
├── CLAUDE.md                       # Claude Code project instructions
└── CLAUDE_PROJECT_PROMPT.md        # Claude Desktop project prompt
```

## Email digest format

Digests are written to `inbox/{account}/YYYY-MM-DD.md` (gitignored). Each digest has:

- Sections: Action Items, Must Read, Deals Worth Knowing, Other, Promotional — No Deal, Spam
- A status footer (`_Unreviewed_` or `_Reviewed: ..._`) used to track review state
- A hidden `<!-- archive_ids ... -->` block with Gmail message IDs per bucket, used by `archive_emails.py`

## Adding a new account

1. Add an entry to `accounts.json` with the slug, label, email, and credential/token paths
2. Place the OAuth client credentials file at `credentials_path`
3. Run `python scripts/archive_emails.py --account <slug>` to trigger the OAuth flow
4. Run `/email-triage` to verify — the new account's digest should appear in `inbox/<slug>/`
