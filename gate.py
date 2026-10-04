"""Claude Code UserPromptSubmit hook: the trigger for Desk Shrimp.

This file is deterministic on purpose. It keeps the timer, handles the safe words,
and when time is up it starts a coach session (counter.py) and blocks the prompt.
Everything about the break itself (plea or exercise, which one, how many reps, when
it is done) is decided by the coach in coach.py.

Create a file named "disabled" in this folder to turn the gate off, or send the safe
words: "pineapple" turns it off, "apple" turns it back on.
"""
import json
import os
import subprocess
import sys
import time

LIMIT_SECONDS = 60
REPLY_WAIT_SECONDS = 15  # how long the hook waits for the coach's first line
HOME = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DESK_SHRIMP_HOME", HOME)  # where state and logs live (tests override this)
STATE = os.path.join(DATA, "state.json")
PIDFILE = os.path.join(DATA, "counter.pid")
DISABLED = os.path.join(DATA, "disabled")
PENDING = os.path.join(DATA, "pending.json")
REPLY = os.path.join(DATA, "reply.json")
PYTHON = os.path.join(HOME, ".venv", "bin", "python")
COUNTER = os.path.join(HOME, "counter.py")


def read_state():
    try:
        with open(STATE) as f:
            state = json.load(f)
        return state["window_start"], state.get("announced", True)
    except (OSError, ValueError, KeyError):
        return None, False


def write_state(ts, announced=True):
    with open(STATE, "w") as f:
        json.dump({"window_start": ts, "announced": announced}, f)


def start_window(seconds, announced=True):
    """Starts a work window that runs out in `seconds`, whatever LIMIT_SECONDS is."""
    write_state(time.time() - LIMIT_SECONDS + seconds, announced)


def announce(seconds):
    # JSON stdout with systemMessage is shown to the user in Claude Code.
    print(json.dumps({"systemMessage": f"Desk Shrimp timer started: {round(seconds)} seconds."}))


def session_running():
    try:
        with open(PIDFILE) as f:
            os.kill(int(f.read().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def launch_session(prompt):
    """Starts the coach session in its own process and hands it the blocked message."""
    with open(PENDING, "w") as f:
        json.dump({"message": prompt[:500], "ts": time.time()}, f)
    try:
        os.remove(REPLY)
    except OSError:
        pass
    log = open(os.path.join(DATA, "counter.log"), "a")
    # The coach runs its own Claude session. DESK_SHRIMP_COACH stops this hook from gating it.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env["DESK_SHRIMP_COACH"] = "1"
    proc = subprocess.Popen(
        [PYTHON, COUNTER],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        start_new_session=True, env=env,
    )
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))


def wait_for_reply(timeout=REPLY_WAIT_SECONDS):
    """Waits for the coach's first decision so it can be shown in the terminal."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(REPLY) as f:
                return json.load(f)
        except (OSError, ValueError):
            time.sleep(0.2)
    return None


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


def describe(reply):
    """Turns the coach's first decision into the line shown in the terminal."""
    if reply is None:
        return ("Your coach is deciding. Watch for the camera window, finish the exercise, "
                "then resend your message.")
    if reply.get("kind") == "extension":
        return (f"{reply['text']} You get {reply['seconds']} seconds; "
                f"+{reply['extra_reps']} reps at your next break. Resend your message.")
    return f"{reply['text']} Do it in the camera window, then resend your message."


def main():
    if os.environ.get("DESK_SHRIMP_COACH"):
        return 0  # this is the coach's own Claude session, never gate it
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
        announce(LIMIT_SECONDS)
        return 0
    if now - start < LIMIT_SECONDS:
        if not announced:
            write_state(start)
            announce(LIMIT_SECONDS - (now - start))
        return 0
    if session_running():
        block("Finish your reps in the camera window, then resend your message.")
        return 0
    launch_session(prompt)
    block(describe(wait_for_reply()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
