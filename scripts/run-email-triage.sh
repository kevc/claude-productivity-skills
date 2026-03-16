#!/bin/zsh
# run-email-triage.sh — Wrapper for launchd to invoke email triage via Claude Code
# launchd runs with a minimal environment, so we set HOME and PATH explicitly.
# Update HOME below to match your macOS home directory.

export HOME="/Users/$(whoami)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

REPO_DIR="$HOME/git/claude-productivity-skills"

# Create inbox subdirectories for each configured account
if command -v python3 >/dev/null 2>&1; then
  python3 -c "
import json
from pathlib import Path
repo = '$REPO_DIR'
config = json.loads(Path(repo, 'accounts.json').read_text())
for slug in config.get('accounts', {}):
    Path(repo, 'inbox', slug).mkdir(parents=True, exist_ok=True)
"
fi

"$HOME/.local/bin/claude" \
  --dangerously-skip-permissions \
  -p "Run email triage for all configured accounts (see accounts.json) for the last 24 hours and write each digest to $REPO_DIR/inbox/{account}/"

# Open Claude Desktop so the digest is surfaced when user next interacts with it
open -a "Claude"
