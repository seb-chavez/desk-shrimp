"""Claude Code UserPromptSubmit hook: block prompts after LIMIT_SECONDS until
10 jumping jacks are done on camera.

Exit 0 lets the prompt through. Exit 2 blocks it and shows stderr to the user.
Create ~/jumpjack-gate/disabled to turn the gate off.
"""
import json
import os
import subprocess
import sys
import time

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
    print(json.dumps({"systemMessage": f"Jumping jack timer started: {LIMIT_SECONDS} seconds."}))


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


def main():
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
    if not counter_running():
        launch_counter()
    print(
        "Time's up. Do 10 jumping jacks in the camera window to keep going, "
        "then resend your message.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
