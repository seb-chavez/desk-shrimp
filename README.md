# Desk Shrimp

![A shrimp hunched over a laptop](desk-shrimp.png)

Too long at the desk turns you into a shrimp. Desk Shrimp is an AI break coach for Claude Code. When your time is up, it blocks your next prompt, Claude picks an exercise for you, and your webcam counts the reps. Finish them and you're back in.

## What a break looks like

1. **Timer starts.** Your first prompt shows `Desk Shrimp timer started: 60 seconds.`
2. **Time's up.** Your next prompt is blocked. Claude reads it first: if it's a plea for more time, the coach may cut you a deal (see below).
3. **The coach picks.** A camera window opens with "Coach is picking..." while Claude chooses the exercise and reps from today's history.
4. **You move.** The window counts reps live, like `squats: 7 / 13`.
5. **Unlocked.** At the target, the break is logged, the timer restarts, and your prompt goes through when you resend it.

## The coach (Claude)

The coach runs Claude Haiku through the `claude` CLI, so it uses your existing Claude login. No API key needed.

**Picking the exercise.** Claude chooses one of three exercises and 5 to 20 reps. Its rules:
- Don't repeat the last exercise.
- Add reps if you skipped the last break.
- More breaks today means more reps.
- Add any reps you owe from deals.

If Claude fails or times out, the fallback is 10 jumping jacks. The log records which one picked (`"source": "claude"` or `"fallback"`).

**Negotiating.** Once time is up, Claude judges your blocked prompt:
- Normal work ("refactor the auth middleware") gets blocked.
- A good plea ("live demo, 30 more seconds") can earn up to 60 seconds, always at the cost of 3 to 10 extra reps at your next break.
- Each extension is harder to get. After 2 per break, it always says no.

## Exercises

| Exercise | One rep | Needs in frame |
|---|---|---|
| Jumping jacks | Both wrists from below your shoulders to above your head | Head, shoulders, arms |
| Squats | Knees close to hip height, then stand back up | Shoulders to knees |
| High knees | One knee up to hip height | Shoulders to knees |

Rep counting runs on your Mac with MediaPipe Pose. Nothing is uploaded.

## Controls

- `pineapple` by itself turns Desk Shrimp off. `apple` turns it back on with a fresh timer. Claude never sees either word.
- `q` in the camera window quits without unlocking (logged as skipped).
- A file named `disabled` in this folder also turns it off.
- Change the limit with `LIMIT_SECONDS` in `gate.py`. It's 60 for demos.

## Setup

Requires macOS, a webcam, [uv](https://docs.astral.sh/uv/), and the `claude` CLI logged in.

```
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python "mediapipe==0.10.14" "opencv-contrib-python==4.11.0.86" "numpy<2"
```

Add to a project's `.claude/settings.local.json`:

```json
"hooks": {
  "UserPromptSubmit": [
    { "hooks": [{ "type": "command", "command": "/usr/bin/python3 /path/to/desk-shrimp/gate.py" }] }
  ]
}
```

The first time the camera opens, macOS asks to let your terminal use it. Allow it.

## Files

| File | What it does |
|---|---|
| `gate.py` | The hook. Runs on every prompt: timer, safe words, blocking, negotiation |
| `coach.py` | Talks to Claude: picks exercises, judges pleas, keeps the logs |
| `counter.py` | Camera window and rep counting |
| `agent-spec.md` | One-page spec: job, trigger, inputs, outputs, done, tools |
| `breaks.jsonl` | Local log of every break (not committed) |
| `deals.json` | Extensions and owed reps since your last break (not committed) |
