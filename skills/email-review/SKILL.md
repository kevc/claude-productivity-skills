---
name: email-review
description: Review the latest email triage digest interactively. Scans inbox/{account}/ subdirectories and legacy inbox/*.md for unreviewed digests, presents the contents in a clean structured format, walks the user through each section, lets them confirm or reclassify groups, and produces a list of emails to archive. Use this skill whenever the user asks to review their inbox, look at the email digest, process their triage, or anything similar. Also triggers proactively at conversation start if an unreviewed digest file exists.
---

# Email Review

Your job is to present the latest email digest to the user in a readable way, walk them through it, and help them decide what to do with each group.

## Step 1: Find the digest

Scan both `~/git/claude-productivity-skills/inbox/*.md` (legacy flat files) and `~/git/claude-productivity-skills/inbox/*/*.md` (account subdirectories) for any `.md` files containing the line `_Unreviewed — run email-review to process_`.

If **multiple unreviewed digests** exist (across accounts or dates), list them with their account label and date, and ask the user which to review first — or offer to walk through them sequentially.

If no unreviewed file exists, say so briefly and stop. If there's no digest file at all, suggest running the `email-triage` skill first.

## Step 2: Present the digest

Render the contents cleanly — don't just dump the raw markdown. Include the account label prominently in the header. Structure your output like this:

---

**📬 Email Digest — [date] ([Account Label])** · _[N] total emails · [N] action items · Generated [time]_

---

**🔴 Action Items ([N])**
> List each one clearly. If there are none, say "None — clean slate."

---

**📌 Must Read ([N])**
> Render the table. Add a brief (one sentence max) note on any email where context helps the user prioritize.

---

**🤑 Deals ([N])**
> Render the deals table. Include the deal details clearly.

---

**📦 Other ([N])**
> Render the table. Keep it tight.

---

**📣 Promotional — No Deal ([N])**
**🗑️ Spam ([N])**
> Just the summary line for these — no detail needed.

---

## Step 3: Confirm groupings

After presenting, ask the user:

> "Does this look right? Anything miscategorized, or want to flag something before we move to cleanup?"

Give them space to respond. If they reclassify anything, note it for the archive step. Don't re-read emails to re-argue a classification — trust the user's judgment.

## Step 4: Archive confirmed emails

Once the user confirms they're ready to clean up, summarize what will be archived:

> "Archiving [N] promotional + [N] spam emails now..."

Then build the `--buckets` argument based on what the user confirmed:
- Always include `promotional_no_deal` and `spam` unless the user said to keep them
- Add `other` if the user confirmed those are done
- Add `must_read` or `deals` only if the user explicitly said to archive them

Run the archive script via bash, using the correct path for the digest:

```bash
python3 ~/git/claude-productivity-skills/scripts/archive_emails.py inbox/personal/YYYY-MM-DD.md --buckets promotional_no_deal spam
```

For legacy flat digests (no account subdirectory):
```bash
python3 ~/git/claude-productivity-skills/scripts/archive_emails.py inbox/YYYY-MM-DD.md --buckets promotional_no_deal spam
```

Adjust `--buckets` to match what the user confirmed. The archive script reads the `account:` line from the digest metadata to resolve credentials automatically. Report back how many emails were archived when the script completes.

If the script fails with "No archive_ids block found", explain that the digest predates message ID tracking and they'll need to re-run triage to get a fresh digest.

## Step 5: Mark digest as reviewed

Once the user is done, replace the `_Unreviewed_` footer line in the `.md` file with:

```
_Reviewed: YYYY-MM-DD HH:MM_
```

This prevents the digest from showing up again in future sessions.

## Tone

Keep this conversational and efficient. The user is processing their inbox — they don't need ceremony. Lead with what matters (action items first, then must-reads), let them move fast through the low-priority stuff.
