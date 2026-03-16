#!/usr/bin/env python3
"""
archive_emails.py — Archive emails identified in an email triage digest.

Usage:
    python archive_emails.py inbox/personal/YYYY-MM-DD.md [--dry-run] [--account personal]

Reads the triage .md file to extract message IDs for emails in the
Promotional (no deal) and Spam buckets, then removes the INBOX label
via the Gmail API to archive them.

Account resolution order:
  1. --account CLI flag
  2. account: line in the digest's archive_ids block
  3. default_account from accounts.json
  4. Legacy hardcoded paths (~/.gmail_token.json)

Setup (one-time):
    pip install google-auth-oauthlib google-api-python-client
    Then authenticate by running this script once — it will open a browser
    for OAuth consent and save credentials to ~/.gmail_token.json.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
ACCOUNTS_PATH = Path(__file__).resolve().parent.parent / "accounts.json"

# Legacy fallback paths (used when accounts.json is missing)
LEGACY_TOKEN_PATH = Path.home() / ".gmail_token.json"
LEGACY_CREDS_PATH = Path.home() / ".gmail_credentials.json"


def load_accounts_config():
    """Load and return accounts.json config, or None if not found."""
    if ACCOUNTS_PATH.exists():
        return json.loads(ACCOUNTS_PATH.read_text())
    return None


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def resolve_credential_paths(account_slug: str = ""):
    """Return (token_path, creds_path) for the given account.

    Falls back to legacy hardcoded paths if accounts.json is missing.
    """
    config = load_accounts_config()
    if config is None:
        return LEGACY_TOKEN_PATH, LEGACY_CREDS_PATH

    if not account_slug:
        account_slug = config.get("default_account", "")

    accounts = config.get("accounts", {})
    if account_slug not in accounts:
        print(f"Warning: account '{account_slug}' not in accounts.json, using legacy paths")
        return LEGACY_TOKEN_PATH, LEGACY_CREDS_PATH

    acct = accounts[account_slug]
    return _expand(acct["token_path"]), _expand(acct["credentials_path"])


def get_gmail_service(token_path: Path = None, creds_path: Path = None):
    if token_path is None:
        token_path = LEGACY_TOKEN_PATH
    if creds_path is None:
        creds_path = LEGACY_CREDS_PATH

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("Missing dependencies. Run: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print(f"Gmail credentials not found at {creds_path}")
                print("Download OAuth 2.0 credentials from Google Cloud Console")
                print("and save as the credentials file for this account")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def extract_message_ids_from_digest(digest_path: Path) -> tuple:
    """
    Parse the digest .md file and return (buckets_dict, account_slug).
    Reads the <!-- archive_ids ... --> block written by the email-triage skill.
    Returns ({'must_read': [...], 'deals': [...], ...}, 'personal')
    """
    content = digest_path.read_text()
    match = re.search(r'<!--\s*archive_ids\s*(.*?)-->', content, re.DOTALL)
    if not match:
        print("⚠️  No archive_ids block found in digest.")
        print("This digest was likely generated before message ID tracking was added.")
        print("Re-run email-triage to generate a new digest with embedded IDs.")
        return {}, ""

    buckets = {}
    account = ""
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()
        if key == "account":
            account = value
        else:
            ids = value.split()
            buckets[key] = [i for i in ids if i.lower() != 'none']

    return buckets, account


def archive_messages(service, message_ids: list, dry_run: bool = False):
    """Remove INBOX label from a list of message IDs."""
    archived = 0
    for msg_id in message_ids:
        if dry_run:
            print(f"  [dry-run] would archive: {msg_id}")
        else:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["INBOX"]}
            ).execute()
            print(f"  ✓ archived: {msg_id}")
            archived += 1
    return archived


DEFAULT_BUCKETS = {"promotional_no_deal", "spam"}


def main():
    parser = argparse.ArgumentParser(description="Archive emails from a triage digest")
    parser.add_argument("digest", help="Path to the triage .md file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without archiving")
    parser.add_argument(
        "--buckets",
        nargs="+",
        metavar="BUCKET",
        help=(
            "Buckets to archive (default: promotional_no_deal spam). "
            "Options: must_read deals other promotional_no_deal spam"
        ),
    )
    parser.add_argument(
        "--account",
        default="",
        help="Account slug from accounts.json (overrides digest metadata)",
    )
    args = parser.parse_args()

    digest_path = Path(args.digest)
    if not digest_path.exists():
        print(f"Digest file not found: {digest_path}")
        sys.exit(1)

    all_buckets, digest_account = extract_message_ids_from_digest(digest_path)
    if not all_buckets:
        sys.exit(0)

    # Account resolution: CLI flag > digest metadata > default
    account_slug = args.account or digest_account or ""
    token_path, creds_path = resolve_credential_paths(account_slug)

    target_buckets = set(args.buckets) if args.buckets else DEFAULT_BUCKETS
    service = get_gmail_service(token_path, creds_path)

    total = 0
    for bucket in target_buckets:
        ids = all_buckets.get(bucket, [])
        if ids:
            print(f"\nArchiving {len(ids)} emails from '{bucket}'...")
            total += archive_messages(service, ids, dry_run=args.dry_run)
        else:
            print(f"\nNo emails to archive in '{bucket}'.")

    action = "Would archive" if args.dry_run else "Archived"
    print(f"\n{action} {total} emails total.")


if __name__ == "__main__":
    main()
