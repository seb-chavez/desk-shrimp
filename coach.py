"""Asks Claude to pick the next exercise and keeps a log of past breaks."""
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime

HOME = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HOME, "breaks.jsonl")
EXERCISES = ["jumping jacks", "squats", "high knees"]
DEFAULT = {"exercise": "jumping jacks", "reps": 10, "message": "Up you get. 10 jumping jacks."}
MIN_REPS, MAX_REPS = 5, 20


def todays_breaks():
    today = datetime.now().date()
    breaks = []
    try:
        with open(LOG) as f:
            for line in f:
                entry = json.loads(line)
                if datetime.fromtimestamp(entry["ts"]).date() == today:
                    breaks.append(entry)
    except (OSError, ValueError):
        pass
    return breaks


def log_break(exercise, reps, completed):
    with open(LOG, "a") as f:
        f.write(json.dumps({"ts": time.time(), "exercise": exercise, "reps": reps, "completed": completed}) + "\n")


def build_prompt(breaks):
    if breaks:
        history = "\n".join(
            f"- {datetime.fromtimestamp(b['ts']).strftime('%-I:%M%p')}: {b['reps']} {b['exercise']}, "
            f"{'done' if b['completed'] else 'skipped'}"
            for b in breaks
        )
    else:
        history = "No breaks yet today."
    return f"""You are a desk-break coach. Someone has been coding too long and must move before they can keep working.
Pick ONE exercise from this list: {", ".join(EXERCISES)}.
Pick reps between {MIN_REPS} and {MAX_REPS}.

Rules:
- Avoid repeating the last exercise.
- If they skipped the last break, add reps.
- The more breaks today, the more reps.
- Write a one-sentence message that says the exercise and reps, playful but short. No em dashes.

Current time: {datetime.now().strftime('%-I:%M%p')}
Today's breaks:
{history}

Reply with only JSON: {{"exercise": "...", "reps": N, "message": "..."}}"""


def pick_exercise():
    """Returns {"exercise", "reps", "message"}. Falls back to DEFAULT on any failure."""
    claude = shutil.which("claude") or "/usr/local/bin/claude"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        out = subprocess.run(
            [claude, "-p", build_prompt(todays_breaks()), "--model", "haiku"],
            cwd=HOME, env=env, capture_output=True, text=True, timeout=45,
        ).stdout
        choice = json.loads(re.search(r"\{.*\}", out, re.S).group(0))
        if choice["exercise"] not in EXERCISES:
            return DEFAULT
        choice["reps"] = max(MIN_REPS, min(MAX_REPS, int(choice["reps"])))
        choice["message"] = str(choice.get("message", ""))[:80]
        return choice
    except Exception:
        return DEFAULT


if __name__ == "__main__":
    print(build_prompt(todays_breaks()))
    print(pick_exercise())
