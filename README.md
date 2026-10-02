# Desk Shrimp

![A shrimp hunched over a laptop](desk-shrimp.png)

Too long at the desk turns you into a shrimp. Desk Shrimp is a Claude Code hook that blocks your prompts after a time limit until you do 10 jumping jacks on camera.

## Setup

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

## How it works

- `gate.py` runs on every prompt. The first prompt starts the timer (`LIMIT_SECONDS`, 60 for demos). Past the limit, it blocks the prompt and opens the camera.
- `coach.py` asks Claude (Haiku, through the `claude` CLI) to pick the exercise and reps: jumping jacks, squats, or high knees. It looks at today's breaks in `breaks.jsonl`, avoids repeats, and adds reps after a skip.
- `counter.py` opens the camera and counts reps with MediaPipe Pose. When you hit the target, it resets the timer.
- Send `pineapple` by itself to turn the gate off, and `apple` to turn it back on with a fresh timer. Claude never sees either word.
- Create a file named `disabled` in this folder to pause the gate. Press `q` in the camera window to quit without unlocking.
