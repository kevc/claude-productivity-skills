#!/usr/bin/env python3
"""
Local Gmail MCP server for headless email triage.

Exposes gmail_search_messages and gmail_read_message via stdio,
using OAuth credentials configured in accounts.json.  Supports
multiple Gmail accounts — pass `account` to select which one.
Designed to run under launchd where the Claude.ai connected-account
Gmail tools are unavailable.
"""

import base64
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
ACCOUNTS_PATH = Path(__file__).resolve().parent.parent / "accounts.json"

mcp = FastMCP("gmail")

# ---------------------------------------------------------------------------
# Account config
# ---------------------------------------------------------------------------

_accounts_config = None


def _load_accounts():
    global _accounts_config
    if _accounts_config is not None:
        return _accounts_config

    if not ACCOUNTS_PATH.exists():
        raise RuntimeError(f"accounts.json not found at {ACCOUNTS_PATH}")

    _accounts_config = json.loads(ACCOUNTS_PATH.read_text())
    return _accounts_config


def _resolve_account(account: str) -> str:
    """Return the account slug to use, falling back to default_account."""
    config = _load_accounts()
    if not account:
        account = config.get("default_account", "")
    if account not in config.get("accounts", {}):
        available = ", ".join(config.get("accounts", {}).keys())
        raise RuntimeError(
            f"Unknown account '{account}'. Available: {available}"
        )
    return account


def _expand(p: str) -> Path:
    return Path(p).expanduser()


# ---------------------------------------------------------------------------
# Gmail API clients (lazy, one per account)
# ---------------------------------------------------------------------------

_services: dict = {}


def _get_service(account: str = ""):
    account = _resolve_account(account)
    if account in _services:
        return _services[account]

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    acct = _load_accounts()["accounts"][account]
    token_path = _expand(acct["token_path"])
    creds_path = _expand(acct["credentials_path"])

    if not token_path.exists():
        raise RuntimeError(
            f"No Gmail token found at {token_path} for account '{account}'. "
            "Run archive_emails.py interactively once to complete the OAuth flow."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        else:
            raise RuntimeError(
                f"Gmail token for account '{account}' is invalid and cannot be refreshed. "
                "Run archive_emails.py interactively to re-authenticate."
            )

    _services[account] = build("gmail", "v1", credentials=creds)
    return _services[account]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_headers(headers: list, names: set) -> dict:
    """Pull specific headers into a dict keyed by lowercase name."""
    out = {}
    for h in headers:
        if h["name"].lower() in names:
            out[h["name"]] = h["value"]
    return out


def _decode_body(payload: dict) -> str:
    """Walk MIME parts and return the best plain-text body."""
    # Single-part message
    if "parts" not in payload:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

    # Multipart — prefer text/plain, fall back to text/html
    plain = html = ""
    stack = list(payload["parts"])
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        if mime.startswith("multipart/"):
            stack.extend(part.get("parts", []))
            continue
        data = part.get("body", {}).get("data", "")
        if not data:
            continue
        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        if mime == "text/plain" and not plain:
            plain = decoded
        elif mime == "text/html" and not html:
            html = decoded

    return plain or html


def _list_attachments(payload: dict) -> list:
    """Return a list of {filename, mimeType, size} for real attachments."""
    attachments = []
    stack = [payload]
    while stack:
        part = stack.pop()
        if part.get("filename"):
            attachments.append({
                "filename": part["filename"],
                "mimeType": part.get("mimeType", "unknown"),
                "size": part.get("body", {}).get("size", 0),
            })
        stack.extend(part.get("parts", []))
    return attachments


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

HEADER_NAMES = {"from", "to", "subject", "date", "cc", "bcc", "reply-to"}


@mcp.tool()
def gmail_search_messages(
    q: str = "",
    maxResults: int = 20,
    pageToken: str = "",
    includeSpamTrash: bool = False,
    account: str = "",
) -> dict:
    """Search Gmail messages using Gmail search syntax.

    Args:
        q: Gmail search query (e.g. "in:inbox after:2024/01/01").
        maxResults: Maximum messages to return per request (1-500, default 20).
        pageToken: Token from a previous response for pagination.
        includeSpamTrash: Include SPAM and TRASH messages.
        account: Account slug from accounts.json (e.g. "personal", "work"). Defaults to default_account.
    """
    service = _get_service(account)

    kwargs = {"userId": "me", "maxResults": min(maxResults, 500)}
    if q:
        kwargs["q"] = q
    if pageToken:
        kwargs["pageToken"] = pageToken
    if includeSpamTrash:
        kwargs["includeSpamTrash"] = True

    resp = service.users().messages().list(**kwargs).execute()
    message_ids = resp.get("messages", [])

    messages = []
    for stub in message_ids:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=stub["id"], format="metadata", metadataHeaders=list(HEADER_NAMES))
            .execute()
        )
        headers = _extract_headers(msg.get("payload", {}).get("headers", []), HEADER_NAMES)
        messages.append({
            "id": msg["id"],
            "threadId": msg["threadId"],
            "labelIds": msg.get("labelIds", []),
            "snippet": msg.get("snippet", ""),
            "headers": headers,
        })

    result = {"messages": messages}
    if "nextPageToken" in resp:
        result["nextPageToken"] = resp["nextPageToken"]
    return result


@mcp.tool()
def gmail_read_message(messageId: str, account: str = "") -> dict:
    """Read the full content of a Gmail message by its ID.

    Args:
        messageId: The unique message ID (from gmail_search_messages).
        account: Account slug from accounts.json (e.g. "personal", "work"). Defaults to default_account.
    """
    service = _get_service(account)

    msg = (
        service.users()
        .messages()
        .get(userId="me", id=messageId, format="full")
        .execute()
    )

    payload = msg.get("payload", {})
    headers = _extract_headers(payload.get("headers", []), HEADER_NAMES)
    body = _decode_body(payload)
    attachments = _list_attachments(payload)

    return {
        "id": msg["id"],
        "threadId": msg["threadId"],
        "labelIds": msg.get("labelIds", []),
        "snippet": msg.get("snippet", ""),
        "headers": headers,
        "body": body,
        "attachments": attachments,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
