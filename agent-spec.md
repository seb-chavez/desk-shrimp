# Desk Shrimp

## 1. The job that this agent does for me
Gets me moving during long Claude Code sessions. When time's up, it blocks me until I do an exercise that Claude picks.

## 2. What the trigger is
Every message I send in Claude Code. The first starts a 60-second timer; the first after 60 seconds gets blocked.

## 3. What the inputs are
- My message (safe words `pineapple` = off, `apple` = on; otherwise judged by Claude as a plea for more time)
- Timer start time
- Today's break log (what I did, what I skipped)
- Deals since my last break (extensions, owed reps)
- Webcam feed

## 4. What the output is
- "Desk Shrimp timer started: 60 seconds."
- Claude's verdict on a blocked message: extra seconds for extra reps, or a denial
- Claude's pick: jumping jacks, squats, or high knees, plus reps and a one-line message
- Camera window with a live rep count

## 5. What done looks like
Target reps counted, window says "Unlocked!", break logged, timer restarts, my message goes through.

## 6. What tools we're utilizing
- Claude Code `UserPromptSubmit` hook
- Claude Haiku via the `claude` CLI (picks exercises, judges pleas)
- Python (`gate.py`, `coach.py`, `counter.py`)
- MediaPipe Pose (body tracking)
- OpenCV (webcam)
