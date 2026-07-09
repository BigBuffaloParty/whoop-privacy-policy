"""
whoop_sync.py

Run this daily (manually or via cron) to:
  1. Refresh your WHOOP access token
  2. Pull the previous day's recovery, sleep, and workout data
  3. Append a formatted markdown entry to whoop_journal.md

whoop_journal.md is meant to be uploaded (or re-uploaded) to your Claude
Project's knowledge, so Claude can cross-reference Whoop trends with your
personal written journal entries.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["WHOOP_CLIENT_ID"]
CLIENT_SECRET = os.environ["WHOOP_CLIENT_SECRET"]

TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer/v2"

SCRIPT_DIR = os.path.dirname(__file__)
TOKENS_FILE = os.path.join(SCRIPT_DIR, "tokens.json")
JOURNAL_FILE = os.path.join(SCRIPT_DIR, "whoop_journal.md")


def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        raise RuntimeError(
            "No tokens.json found. Run auth_setup.py first to authorize this app."
        )
    with open(TOKENS_FILE) as f:
        return json.load(f)


def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def refresh_access_token(tokens):
    response = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "offline",
    })
    response.raise_for_status()
    new_tokens = response.json()
    save_tokens(new_tokens)
    return new_tokens


def api_get(path, access_token, params=None):
    response = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params or {},
    )
    response.raise_for_status()
    return response.json()


def get_window_for_yesterday():
    """Return (start_iso, end_iso) covering all of 'yesterday' in UTC."""
    now = datetime.now(timezone.utc)
    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start = end - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def ms_to_hours_minutes(milli):
    total_minutes = int(milli / 1000 / 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


def format_entry(date_label, recovery, sleep_records, workout_records):
    lines = [f"## {date_label}", ""]

    # --- Recovery ---
    if recovery and recovery.get("score_state") == "SCORED":
        score = recovery["score"]
        lines.append("**Recovery**")
        lines.append(f"- Recovery score: {score.get('recovery_score')}%")
        lines.append(f"- Resting heart rate: {score.get('resting_heart_rate')} bpm")
        lines.append(f"- HRV: {round(score.get('hrv_rmssd_milli', 0), 1)} ms")
        if score.get("skin_temp_celsius") is not None:
            lines.append(f"- Skin temp: {round(score['skin_temp_celsius'], 1)}°C")
        lines.append("")
    else:
        lines.append("**Recovery**: no scored data for this day")
        lines.append("")

    # --- Sleep ---
    if sleep_records:
        lines.append("**Sleep**")
        for sleep in sleep_records:
            if sleep.get("score_state") != "SCORED":
                continue
            score = sleep["score"]
            stage = score.get("stage_summary", {})
            total_sleep_milli = (
                stage.get("total_light_sleep_time_milli", 0)
                + stage.get("total_slow_wave_sleep_time_milli", 0)
                + stage.get("total_rem_sleep_time_milli", 0)
            )
            label = "Nap" if sleep.get("nap") else "Sleep"
            lines.append(f"- {label} duration: {ms_to_hours_minutes(total_sleep_milli)}")
            lines.append(f"  - Sleep performance: {score.get('sleep_performance_percentage')}%")
            lines.append(f"  - Sleep efficiency: {round(score.get('sleep_efficiency_percentage', 0), 1)}%")
            lines.append(f"  - Disturbances: {stage.get('disturbance_count')}")
        lines.append("")
    else:
        lines.append("**Sleep**: no data for this day")
        lines.append("")

    # --- Workouts ---
    if workout_records:
        lines.append("**Workouts**")
        for w in workout_records:
            if w.get("score_state") != "SCORED":
                continue
            score = w["score"]
            lines.append(
                f"- {w.get('sport_name', 'Activity').title()}: "
                f"Strain {round(score.get('strain', 0), 1)}, "
                f"Avg HR {score.get('average_heart_rate')} bpm, "
                f"{round(score.get('distance_meter', 0) / 1000, 2)} km"
                if score.get("distance_meter") else
                f"- {w.get('sport_name', 'Activity').title()}: "
                f"Strain {round(score.get('strain', 0), 1)}, "
                f"Avg HR {score.get('average_heart_rate')} bpm"
            )
        lines.append("")
    else:
        lines.append("**Workouts**: none logged")
        lines.append("")

    lines.append("_Journal note:_ ")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main():
    tokens = load_tokens()
    tokens = refresh_access_token(tokens)
    access_token = tokens["access_token"]

    start_iso, end_iso = get_window_for_yesterday()
    date_label = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    recovery_data = api_get("/recovery", access_token, {"start": start_iso, "end": end_iso, "limit": 5})
    sleep_data = api_get("/activity/sleep", access_token, {"start": start_iso, "end": end_iso, "limit": 5})
    workout_data = api_get("/activity/workout", access_token, {"start": start_iso, "end": end_iso, "limit": 10})

    recovery_records = recovery_data.get("records", [])
    latest_recovery = recovery_records[0] if recovery_records else None

    entry = format_entry(
        date_label,
        latest_recovery,
        sleep_data.get("records", []),
        workout_data.get("records", []),
    )

    file_existed = os.path.exists(JOURNAL_FILE)
    with open(JOURNAL_FILE, "a") as f:
        if not file_existed:
            f.write("# WHOOP Journal Log\n\n")
            f.write("Auto-generated daily entries from WHOOP data. ")
            f.write("Upload/re-upload this file to your Claude Project to help ")
            f.write("Claude spot trends alongside your written journal entries.\n\n")
        f.write(entry)

    print(f"Added entry for {date_label} to {JOURNAL_FILE}")


if __name__ == "__main__":
    main()
