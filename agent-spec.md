# Desk Shrimp

## 1. The job that this agent does for me
Gets me moving during long Claude Code sessions. When time's up, it blocks me and runs the break: it decides what I do, watches me do it, adjusts if I stall or step out of frame, and decides when I'm unlocked.

## 2. What the trigger is
Every message I send in Claude Code. The first starts a 60-second timer; the first after 60 seconds gets blocked and starts a coach session. The trigger is plain code (`gate.py`). Everything after it is the agent's call.

## 3. What the inputs are
- My blocked message (safe words `pineapple` = off, `apple` = on never reach the agent)
- The break log (what I did, what I skipped)
- Deals since my last break (extensions, owed reps)
- Live results from the camera: reps, pace, in frame or not, whether I quit

## 4. What the output is
- "Desk Shrimp timer started: 60 seconds."
- A plea verdict: extra seconds for extra reps, or an exercise
- An exercise, a rep target, and one-line messages in the camera window
- Mid-break changes: a nudge, a different exercise, a new target
- A longer or shorter next work window
- A log of every tool call (`sessions.jsonl`)

## 5. What done looks like
The agent decides. It calls `finish` once the camera has counted the target (window says "Unlocked!", break logged, timer restarts, my message goes through), or logs a skip if I quit. Code refuses an unlock the reps don't support.

## 6. What tools the agent can call
The model chooses which of these to call, in what order, and when to stop:
- `read_history`: past breaks, extensions used, reps owed
- `grant_extension`: more time now, extra reps later
- `start_exercise`: pick or switch the exercise and target
- `watch`: look at the camera for a few seconds and get the numbers back
- `say`: one line in the camera window
- `set_next_timer`: shorten or lengthen the next work window
- `finish`: end the break as unlocked or skipped

## 7. What it's built with
- Claude Code `UserPromptSubmit` hook
- Claude Haiku via the Claude Agent SDK and the `claude` CLI
- Python (`gate.py`, `coach.py`, `counter.py`)
- MediaPipe Pose (body tracking)
- OpenCV (webcam)
