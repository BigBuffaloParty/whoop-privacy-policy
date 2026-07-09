# WHOOP Journal Integration

A personal, single-user integration that pulls daily WHOOP data (recovery,
sleep, workouts) and formats it into a markdown journal file. This file is
meant to be uploaded to a Claude Project, so Claude can help spot trends
between WHOOP metrics and personal journal entries about eating, exercise,
and wellness.

**This is for personal use only and is not intended for others to run or
fork.** See [privacy policy](privacy.md) for details on how data is handled.

## Setup

1. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Create your `.env` file**
   Copy `.env.example` to `.env` and fill in your WHOOP Client ID and
   Client Secret (from the WHOOP Developer Dashboard). Get these from
   Bitwarden, not from any committed file.
   ```
   cp .env.example .env
   ```

3. **Authorize the app (one-time)**
   ```
   python3 auth_setup.py
   ```
   This opens your browser, asks you to log in to WHOOP and grant access,
   and saves your tokens locally to `tokens.json` (this file is gitignored
   and never committed).

4. **Run a sync manually to test**
   ```
   python3 whoop_sync.py
   ```
   This pulls yesterday's data and appends a formatted entry to
   `whoop_journal.md`.

## Automating daily runs (cron)

To run the sync automatically every morning at 7:00 AM, add a cron job:

```
crontab -e
```

Add this line (adjust the path to match where you cloned this repo):

```
0 7 * * * cd /path/to/whoop-journal && /usr/bin/python3 whoop_sync.py >> sync.log 2>&1
```

This pulls the previous day's complete data each morning.

## Using this with your Claude Project

Periodically (e.g., weekly), upload the updated `whoop_journal.md` file to
your Claude Project's knowledge base, replacing the previous version. Once
it's there, you can ask Claude things like:

- "Look at my WHOOP data and journal entries from the last two weeks — any
  patterns between sleep and how I described my energy?"
- "Summarize trends in my recovery scores this month."

## Files

| File | Purpose |
|---|---|
| `auth_setup.py` | One-time OAuth authorization flow |
| `whoop_sync.py` | Daily data pull + journal formatting |
| `whoop_journal.md` | Generated output — upload this to your Claude Project |
| `tokens.json` | Local token storage (gitignored, never commit) |
| `.env` | Local credentials (gitignored, never commit) |
| `privacy.md` | Privacy policy required by WHOOP's developer registration |

## Security notes

- Never commit `.env` or `tokens.json` — both are in `.gitignore`.
- Store your Client ID and Client Secret in Bitwarden, not in this repo.
- If you ever want to revoke access, do so from your WHOOP account settings.
