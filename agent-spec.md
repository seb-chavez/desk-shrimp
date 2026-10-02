# Desk Shrimp

## 1. The job that this agent does for me
Blocks Claude Code after 60 seconds until I do a quick exercise that Claude picks for me.

## 2. What the trigger is
Every message I send in Claude Code. The first starts the timer; the first after 60 seconds gets blocked.

## 3. What the inputs are
- My message (checked for `pineapple` = off, `apple` = on)
- Timer start time
- Today's break log (what I did, what I skipped)
- Webcam feed

## 4. What the output is
- Blocked message: "Time's up. Your coach is picking an exercise…"
- Claude's pick: jumping jacks, squats, or high knees, plus reps and a one-line message
- Camera window with a live rep count

## 5. What done looks like
Target reps counted, window says "Unlocked!", break logged, timer restarts, my message goes through.

## 6. What tools we're utilizing
- Claude Code `UserPromptSubmit` hook
- Claude Haiku via the `claude` CLI (picks the exercise)
- Python (`gate.py`, `coach.py`, `counter.py`)
- MediaPipe Pose (body tracking)
- OpenCV (webcam)
