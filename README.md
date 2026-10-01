# Jumping jack gate

A Claude Code hook that blocks your prompts after a time limit until you do 10 jumping jacks on camera.

## Setup

```
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python "mediapipe==0.10.14" "opencv-contrib-python==4.11.0.86" "numpy<2"
```

Add to a project's `.claude/settings.local.json`:

```json
"hooks": {
  "UserPromptSubmit": [
    { "hooks": [{ "type": "command", "command": "/usr/bin/python3 /Users/sebastianchavez/jumpjack-gate/gate.py" }] }
  ]
}
```

## How it works

- `gate.py` runs on every prompt. The first prompt starts the timer (`LIMIT_SECONDS`, 60 for demos). Past the limit, it blocks the prompt and opens the camera.
- `counter.py` counts reps with MediaPipe Pose: both wrists from below the shoulders to above the head. At 10, it resets the timer.
- Create a file named `disabled` in this folder to pause the gate. Press `q` in the camera window to quit without unlocking.
