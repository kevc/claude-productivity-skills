---
name: email-triage
description: Triage the Gmail inbox for the last 24 hours. Classifies every email into one of five buckets (must read, promotional with a worthwhile deal, promotional with no deal, spam, other), extracts explicit action items and commitments, and persists the result to ~/git/claude-productivity-skills/inbox/{account}/YYYY-MM-DD.md. Supports multiple Gmail accounts via accounts.json. Use this skill whenever the user asks to triage their inbox, check their email, run the daily email digest, or anything similar. Also invoked by the daily 8am cron job.
---

# Email Triage

Your job is to fetch the last 24 hours of inbox email for all configured accounts, classify each message, surface action items, and write a clean digest per account to disk.

## Step 0: Discover accounts

Read `~/git/claude-productivity-skills/accounts.json` to get the list of configured accounts. For each account entry you'll find:
- `label` — human-readable name for digest headers and notifications
- `email` — the Gmail address
- `credentials_path` / `token_path` — OAuth paths (only relevant for the MCP server and archive script)

Run Steps 1–4 for **each account** in the config. Pass `account: "<slug>"` to every MCP tool call so the right credentials are used.

**Claude Desktop context**: If only `mcp__claude_ai_Gmail__*` tools are available (no `account` parameter), you're running inside Claude Desktop with a single connected Gmail account. Triage that account only. To determine which account slug to use, match the connected email address against the `email` fields in `accounts.json`. If no match, use `default_account`.

## Step 1: Fetch emails

Search Gmail for emails received in the last 24 hours:

```
in:inbox after:<epoch timestamp for 24h ago>
```

Use `gmail_search_messages` with `q: "in:inbox after:YYYY/MM/DD"` (yesterday's date) and `account: "<slug>"`. Fetch up to 100 results. Paginate if `nextPageToken` is returned.

For each message, read the full content with `gmail_read_message` (passing `account: "<slug>"`). You need: sender, subject, snippet/body, and any explicit asks or deadlines.

Work through emails efficiently — for clear-cut cases (newsletters, receipts, automated notifications) you don't need to read the full body. For anything ambiguous or potentially important, read it fully.

## Step 2: Classify each email

Sort every email into exactly one bucket:

### Must Read
Emails that require the user's personal attention — direct human-to-human communication, anything from a real person who expects a response or follow-up, important account/legal/financial notices that need acknowledgement. When in doubt between "must read" and "other", lean toward must read.

### Promotional — Deal Worth Knowing About
Marketing or retail emails that contain a concrete discount of **≥10% off** (or equivalent dollar savings on something plausibly desirable). Think: apparel, tech, gear, experiences, software, restaurants, travel. Use taste — a 10% coupon for a brand the user has clearly never heard of is not "worth knowing about". A notable sale from a recognizable brand or category probably is.

### Promotional — No Deal
All other marketing, newsletters, product announcements, brand updates, drip campaigns, digest emails where the user is not the primary recipient — anything promotional that doesn't clear the deal bar above.

### Spam
Unsolicited, irrelevant, or suspicious emails. Phishing attempts, scammy offers, bulk mail the user clearly never signed up for.

### Other
Everything that doesn't fit above — automated receipts/confirmations, shipping notifications, calendar invites (already handled elsewhere), GitHub/Jira notifications, system alerts, internal tooling emails. Things the user might want to be aware of but don't require action and aren't promotional.

### Classification overrides
Some senders should always land in a specific bucket regardless of the general rules above:
- **Zillow** daily listing digests (e.g. "N Results for 'For Sale in …'") → **Promotional — No Deal**

## Step 3: Extract action items

From the full 24h window, pull out only **explicit** action items — things where:
- Someone is directly asking the user to do something, or
- The user has verifiably committed to something (confirmed attendance, agreed to send something, said they'd follow up)

Do NOT include vague "might be nice to" items or things inferred from context. If it's not clear that the user is on the hook for something, leave it out.

Format each action item as:
- **[Sender name]**: What is being asked or committed to _(email subject for reference)_

## Step 4: Write the digest

Write to `~/git/claude-productivity-skills/inbox/<slug>/YYYY-MM-DD.md` where `<slug>` is the account slug (e.g. `personal`, `work`) and the date is today's date.

If a file for today already exists, **overwrite it** — this is an idempotent operation.

As you classify each email, track its Gmail message ID by bucket. You'll need these for the hidden ID block at the end.

Use this exact structure:

```markdown
# Email Digest — YYYY-MM-DD (<Account Label>)
_Triage window: last 24 hours · Generated: HH:MM_

## Action Items
<!-- Leave this section empty (just the header) if there are none -->
- **[Sender]**: [What's needed] _([Subject])_

## Must Read ([N])
| # | From | Subject | Notes |
|---|------|---------|-------|
| 1 | Name <email> | Subject line | One-line note if helpful |

## Deals Worth Knowing ([N])
| # | From | Subject | Deal |
|---|------|---------|------|
| 1 | Brand | Subject | 20% off sitewide, ends Sunday |

## Other ([N])
| # | From | Subject |
|---|------|---------|
| 1 | Sender | Subject |

## Promotional — No Deal ([N])
_[N] newsletters/marketing emails. Senders: Brand A, Brand B, Brand C..._

## Spam ([N])
_[N] spam emails. Not listed._

---
_Unreviewed — run email-review to process_

<!-- archive_ids
account: <slug>
must_read: <space-separated message IDs, or "none">
deals: <space-separated message IDs, or "none">
other: <space-separated message IDs, or "none">
promotional_no_deal: <space-separated message IDs, or "none">
spam: <space-separated message IDs, or "none">
-->
```

Note the `account: <slug>` line in the archive_ids block — this tells the archive script which credentials to use.

For **Promotional — No Deal** and **Spam**: don't list individual emails, just the count and a comma-separated list of senders. These aren't worth the user's attention.

For **Other**: include the table but keep it tight — subject line only, no notes needed unless something is time-sensitive.

The `<!-- archive_ids ... -->` block is invisible in rendered markdown. Fill in the actual Gmail message IDs for every email in each bucket. These are used by the review skill to archive emails without re-fetching from Gmail.

## Step 5: Fire a macOS notification

After writing digests for **all accounts**, fire a single aggregated notification:

```bash
osascript -e 'display notification "Personal: [N] must-read, [N] deals; Work: [N] must-read, [N] action items" with title "📬 Email Digest" sound name "Glass"'
```

Adjust the message to reflect all accounts that were triaged and their actual counts. If only one account is configured, use the simpler format:

```bash
osascript -e 'display notification "Inbox triage ready — [N] must-read, [N] deals, [N] action items" with title "📬 Email Digest" sound name "Glass"'
```

## What to tell the user

After completing, briefly confirm per account:
- File written to `inbox/<slug>/YYYY-MM-DD.md`
- Total email count and breakdown by bucket
- Number of action items found
