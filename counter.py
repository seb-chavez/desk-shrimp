"""Opens the webcam, asks the coach for an exercise, and counts reps with MediaPipe Pose.

Each exercise maps a pose to 'up', 'down', or None. One rep is a move from down to up.
At the target, resets the gate timer and closes. Press q to quit without unlocking.
"""
import json
import os
import threading
import time

import cv2
import mediapipe as mp

import coach

HOME = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HOME, "state.json")
PIDFILE = os.path.join(HOME, "counter.pid")
WINDOW = "Desk Shrimp"

P = mp.solutions.pose.PoseLandmark


def visible(lm, *names):
    pts = [lm[n] for n in names]
    return pts if min(p.visibility for p in pts) >= 0.5 else None


def jumping_jacks(lm):
    pts = visible(lm, P.NOSE, P.LEFT_SHOULDER, P.RIGHT_SHOULDER, P.LEFT_WRIST, P.RIGHT_WRIST)
    if not pts:
        return None
    nose, ls, rs, lw, rw = pts
    # Image y grows downward: smaller y means higher on screen.
    if lw.y < nose.y and rw.y < nose.y:
        return "up"
    if lw.y > ls.y and rw.y > rs.y:
        return "down"
    return None


def legs(lm):
    """Returns (shoulder_y, hip_y, left_knee_y, right_knee_y, torso) or None."""
    pts = visible(lm, P.LEFT_SHOULDER, P.RIGHT_SHOULDER, P.LEFT_HIP, P.RIGHT_HIP, P.LEFT_KNEE, P.RIGHT_KNEE)
    if not pts:
        return None
    ls, rs, lh, rh, lk, rk = pts
    shoulder, hip = (ls.y + rs.y) / 2, (lh.y + rh.y) / 2
    torso = hip - shoulder
    return (shoulder, hip, lk.y, rk.y, torso) if torso > 0.05 else None


def squats(lm):
    # Standing: knees sit about a torso-length below the hips. Squatting: close to hip level.
    body = legs(lm)
    if not body:
        return None
    _, hip, lk, rk, torso = body
    ratio = ((lk + rk) / 2 - hip) / torso
    if ratio < 0.5:
        return "down"
    if ratio > 0.8:
        return "up"
    return None


def high_knees(lm):
    # One rep per knee lift: a knee near hip height is 'up', both knees low is 'down'.
    body = legs(lm)
    if not body:
        return None
    _, hip, lk, rk, torso = body
    if min(lk, rk) - hip < 0.35 * torso:
        return "up"
    if min(lk, rk) - hip > 0.7 * torso:
        return "down"
    return None


EXERCISES = {
    "jumping jacks": (jumping_jacks, "Arms all the way up, then back down."),
    "squats": (squats, "Step back so your knees are in frame. Sit low, then stand."),
    "high knees": (high_knees, "Step back so your knees are in frame. Knee up to hip height."),
}


def draw(frame, text, sub, color):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 110), (0, 0, 0), -1)
    cv2.putText(frame, text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, color, 4)
    cv2.putText(frame, sub, (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)


def main():
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    choice = {}
    threading.Thread(target=lambda: choice.update(coach.pick_exercise()), daemon=True).start()

    cap = cv2.VideoCapture(0)
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    reps, last, done = 0, None, False
    try:
        with mp.solutions.pose.Pose(model_complexity=0) as pose:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                if not choice:
                    draw(frame, "Coach is picking...", "Get ready to move.", (0, 220, 255))
                else:
                    name, target = choice["exercise"], choice["reps"]
                    detect, tip = EXERCISES[name]
                    result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    if result.pose_landmarks:
                        mp.solutions.drawing_utils.draw_landmarks(
                            frame, result.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS)
                        pos = detect(result.pose_landmarks.landmark)
                        if pos == "up" and last == "down":
                            reps += 1
                        if pos:
                            last = pos
                    sub = choice["message"] if reps == 0 else tip
                    draw(frame, f"{name}: {reps} / {target}", f"{sub} q to quit.", (0, 220, 255))
                    if reps >= target:
                        done = True
                        draw(frame, "Unlocked!", "Go back to Claude Code and resend your message.", (0, 255, 0))
                        cv2.imshow(WINDOW, frame)
                        cv2.waitKey(2000)
                        with open(STATE, "w") as f:
                            json.dump({"window_start": time.time(), "announced": False}, f)
                        break
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        if choice:
            coach.log_break(choice, done)
        cap.release()
        cv2.destroyAllWindows()
        try:
            os.remove(PIDFILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
