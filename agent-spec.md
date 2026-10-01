# Jumping Jack Gate

## 1. The job that this agent does for me
Blocks Claude Code after 60 seconds until I do 10 jumping jacks.

## 2. What the trigger is
Every message I send in Claude Code. The first starts the timer; the first after 60 seconds gets blocked.

## 3. What the inputs are
- My message (checked for `pineapple` = off, `apple` = on)
- Timer start time
- Webcam feed

## 4. What the output is
- Blocked message: "Time's up. Do 10 jumping jacks…"
- Camera window with a live rep count

## 5. What done looks like
10 reps counted, window says "Unlocked!", timer restarts, my message goes through.

## 6. What tools we're utilizing
- Claude Code `UserPromptSubmit` hook
- Python (`gate.py`, `counter.py`)
- MediaPipe Pose (body tracking)
- OpenCV (webcam)
