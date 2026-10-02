"""Claude Code UserPromptSubmit hook: block prompts after LIMIT_SECONDS until
the exercise the coach picks is done on camera.

Once time is up, the coach reads the blocked message: a good plea can buy extra
seconds at the cost of extra reps. Everything else opens the camera.
Create ~/jumpjack-gate/disabled to turn the gate off, or send the safe words:
"pineapple" turns it off, "apple" turns it back on.
"""
import json
import os
import subprocess
import sys
import time

import coach

LIMIT_SECONDS = 60
HOME = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HOME, "state.json")
PIDFILE = os.path.join(HOME, "counter.pid")
DISABLED = os.path.join(HOME, "disabled")
PYTHON = os.path.join(HOME, ".venv", "bin", "python")
COUNTER = os.path.join(HOME, "counter.py")


def read_state():
    try:
        with open(STATE) as f:
            state = json.load(f)
        return state["window_start"], state.get("announced", True)
    except (OSError, ValueError, KeyError):
        return None, False


def write_state(ts):
    with open(STATE, "w") as f:
        json.dump({"window_start": ts, "announced": True}, f)


def announce():
    # JSON stdout with systemMessage is shown to the user in Claude Code.
    print(json.dumps({"systemMessage": f"Desk Shrimp timer started: {LIMIT_SECONDS} seconds."}))


def counter_running():
    try:
        with open(PIDFILE) as f:
            os.kill(int(f.read().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def launch_counter():
    log = open(os.path.join(HOME, "counter.log"), "a")
    subprocess.Popen(
        [PYTHON, COUNTER],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        start_new_session=True,
    )


def handle_safe_word(prompt):
    """Turns the gate off or on. Blocks the prompt so Claude never sees it."""
    word = prompt.strip().lower()
    if word == "pineapple":
        open(DISABLED, "w").close()
        message = "Desk Shrimp off. Send \"apple\" to turn it back on."
    elif word == "apple":
        if os.path.exists(DISABLED):
            os.remove(DISABLED)
        write_state(time.time())
        message = f"Desk Shrimp on. Timer started: {LIMIT_SECONDS} seconds."
    else:
        return False
    block(message)
    return True


def block(reason):
    # Stops the prompt before Claude sees it and shows reason to the user.
    print(json.dumps({"decision": "block", "reason": reason}))


def main():
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except ValueError:
        prompt = ""
    if handle_safe_word(prompt):
        return 0
    if os.path.exists(DISABLED):
        return 0
    now = time.time()
    start, announced = read_state()
    if start is None:
        write_state(now)
        announce()
        return 0
    if now - start < LIMIT_SECONDS:
        if not announced:
            write_state(start)
            announce()
        return 0
    if counter_running():
        block("Finish your reps in the camera window, then resend your message.")
        return 0
    verdict = coach.negotiate(prompt)
    if verdict["grant"]:
        # Move the window start so exactly verdict["seconds"] remain.
        write_state(now - LIMIT_SECONDS + verdict["seconds"])
        block(f"{verdict['reply']} You get {verdict['seconds']} seconds; "
              f"+{verdict['extra_reps']} reps at your next break. Resend your message.")
        return 0
    launch_counter()
    block(f"{verdict['reply']} Your coach is picking an exercise in the camera window. "
          "Finish it, then resend your message.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
