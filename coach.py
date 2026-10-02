"""The AI coach. Asks Claude to pick exercises and to judge pleas for more time.

Also keeps the break log (breaks.jsonl) and any deals made since the last break (deals.json).
"""
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime

HOME = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HOME, "breaks.jsonl")
DEALS = os.path.join(HOME, "deals.json")
EXERCISES = ["jumping jacks", "squats", "high knees"]
DEFAULT = {"exercise": "jumping jacks", "reps": 10, "message": "Up you get. 10 jumping jacks."}
MIN_REPS, MAX_REPS = 5, 20
MAX_EXTENSION_SECONDS = 60


def ask_claude(prompt):
    """Runs Claude Haiku through the claude CLI and returns the first JSON object in its reply."""
    claude = shutil.which("claude") or "/usr/local/bin/claude"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    out = subprocess.run(
        [claude, "-p", prompt, "--model", "haiku"],
        cwd=HOME, env=env, capture_output=True, text=True, timeout=45,
    ).stdout
    return json.loads(re.search(r"\{.*\}", out, re.S).group(0))


def clean(text):
    # Claude sometimes ignores the no-em-dash rule.
    return re.sub(r"\s*[—–]\s*", ", ", str(text)).strip()


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


def log_break(choice, completed):
    entry = {"ts": time.time(), "exercise": choice["exercise"], "reps": choice["reps"],
             "completed": completed, "source": choice.get("source", "claude")}
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    if completed:
        clear_deals()


def read_deals():
    try:
        with open(DEALS) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"extensions": 0, "owed_reps": 0}


def clear_deals():
    try:
        os.remove(DEALS)
    except OSError:
        pass


def history_text():
    breaks = todays_breaks()
    if not breaks:
        return "No breaks yet today."
    return "\n".join(
        f"- {datetime.fromtimestamp(b['ts']).strftime('%-I:%M%p')}: {b['reps']} {b['exercise']}, "
        f"{'done' if b['completed'] else 'skipped'}"
        for b in breaks
    )


def pick_exercise():
    """Returns {"exercise", "reps", "message", "source"}. Falls back to DEFAULT on any failure."""
    owed = read_deals()["owed_reps"]
    prompt = f"""You are a desk-break coach. Someone has been coding too long and must move before they can keep working.
Pick ONE exercise from this list: {", ".join(EXERCISES)}.
Pick base reps between {MIN_REPS} and {MAX_REPS}, then add the {owed} reps they owe from earlier deals.

Rules:
- Avoid repeating the last exercise.
- If they skipped the last break, add reps.
- The more breaks today, the more reps.
- Write a one-sentence message that says the exercise and total reps, playful but short. If they owe reps, rub it in. No em dashes.

Current time: {datetime.now().strftime('%-I:%M%p')}
Today's breaks:
{history_text()}

Reply with only JSON: {{"exercise": "...", "reps": N, "message": "..."}}"""
    try:
        choice = ask_claude(prompt)
        if choice["exercise"] not in EXERCISES:
            raise ValueError(choice["exercise"])
        choice["reps"] = max(MIN_REPS + owed, min(MAX_REPS + owed, int(choice["reps"])))
        choice["message"] = clean(choice.get("message", ""))[:90]
        choice["source"] = "claude"
        return choice
    except Exception:
        return dict(DEFAULT, reps=DEFAULT["reps"] + owed, source="fallback")


def negotiate(message):
    """Judges a message sent after time is up.

    Returns {"grant": bool, "seconds": int, "extra_reps": int, "reply": str}.
    Anything that isn't a plea for time, or any failure, is a denial.
    """
    deals = read_deals()
    prompt = f"""You are a strict but fair desk-break coach. Their time is up, and their next message is blocked until they exercise.
They just sent this message:
<message>
{message[:500]}
</message>

Decide:
- If the message is NOT asking for more time (it's just normal work), deny.
- If it IS a plea, judge the reason. A good reason (live demo, meeting, mid-deploy) can earn up to {MAX_EXTENSION_SECONDS} seconds, and it always costs extra reps at the next break (3 to 10).
- They have already gotten {deals['extensions']} extension(s) since their last break. Each one should be harder to get. After 2, always deny.
- Write a one-sentence reply to them, witty and direct. Don't state the seconds or rep numbers (they're shown separately). Only mention these exercises: {", ".join(EXERCISES)}. No em dashes.

Reply with only JSON: {{"grant": true or false, "seconds": N, "extra_reps": N, "reply": "..."}}"""
    try:
        verdict = ask_claude(prompt)
        grant = bool(verdict.get("grant")) and deals["extensions"] < 2
        seconds = max(0, min(MAX_EXTENSION_SECONDS, int(verdict.get("seconds", 0)))) if grant else 0
        extra = max(0, min(10, int(verdict.get("extra_reps", 0)))) if grant else 0
        reply = clean(verdict.get("reply", ""))[:200]
    except Exception:
        grant, seconds, extra, reply = False, 0, 0, "Nice try. Time to move."
    if grant and seconds:
        with open(DEALS, "w") as f:
            json.dump({"extensions": deals["extensions"] + 1, "owed_reps": deals["owed_reps"] + extra}, f)
    return {"grant": bool(grant and seconds), "seconds": seconds, "extra_reps": extra, "reply": reply}


if __name__ == "__main__":
    print(pick_exercise())
