"""Runs one break: the camera window on the main thread, the coach on a worker thread.

The coach (coach.py) decides what happens. This file is its eyes and its screen: it counts
reps with MediaPipe Pose, reports what it sees into the shared Session, and draws whatever
the coach has chosen. It does not decide when the break is done unless the coach has failed
and the fallback has taken over.

Each exercise maps a pose to 'up', 'down', or None. One rep is a move from down to up.
Press q to quit without unlocking.
"""
import json
import os
import threading
import time

import cv2
import mediapipe as mp

import coach
import gate

WINDOW = "Desk Shrimp"
FINISH_GRACE = 20  # seconds to wait for the coach to unlock after the target is met
QUIT_GRACE = 10    # seconds to wait for the coach to log a skip after q

P = mp.solutions.pose.PoseLandmark
UPPER = (P.NOSE, P.LEFT_SHOULDER, P.RIGHT_SHOULDER, P.LEFT_WRIST, P.RIGHT_WRIST)
LOWER = (P.LEFT_SHOULDER, P.RIGHT_SHOULDER, P.LEFT_HIP, P.RIGHT_HIP, P.LEFT_KNEE, P.RIGHT_KNEE)


def visible(lm, *names):
    pts = [lm[n] for n in names]
    return pts if min(p.visibility for p in pts) >= 0.5 else None


def jumping_jacks(lm):
    pts = visible(lm, *UPPER)
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
    pts = visible(lm, *LOWER)
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


# name -> (pose detector, landmarks that must be in frame, tip)
EXERCISES = {
    "jumping jacks": (jumping_jacks, UPPER, "Arms all the way up, then back down."),
    "squats": (squats, LOWER, "Step back so your knees are in frame. Sit low, then stand."),
    "high knees": (high_knees, LOWER, "Step back so your knees are in frame. Knee up to hip height."),
}


def draw(frame, text, line, tip, color):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 135), (0, 0, 0), -1)
    cv2.putText(frame, text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, color, 4)
    cv2.putText(frame, line, (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)
    cv2.putText(frame, tip, (20, 123), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)


def camera_loop(session):
    """Shows the camera until the break ends. Returns when the window should close."""
    cap = cv2.VideoCapture(0)
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    last, current, met_at = None, None, None
    try:
        with mp.solutions.pose.Pose(model_complexity=0) as pose:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                view = session.view()
                if view["outcome"] == "unlocked":
                    draw(frame, "Unlocked!", "Go back to Claude Code and resend your message.", "", (0, 255, 0))
                    cv2.imshow(WINDOW, frame)
                    cv2.waitKey(2000)
                    break
                if view["outcome"] is not None:
                    break
                name, target = view["exercise"], view["target"]
                detect, required, tip = EXERCISES[name]
                if name != current:  # the coach switched exercise: start the rep cycle fresh
                    current, last = name, None
                framed, rep = False, False
                result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if result.pose_landmarks:
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, result.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS)
                    lm = result.pose_landmarks.landmark
                    framed = visible(lm, *required) is not None
                    pos = detect(lm)
                    rep = pos == "up" and last == "down"
                    if pos:
                        last = pos
                session.observe(framed, rep)
                view = session.view()
                draw(frame, f"{name}: {view['reps']} / {target}", view["line"], f"{tip} q to quit.", (0, 220, 255))
                cv2.imshow(WINDOW, frame)
                if view["reps"] >= target:
                    met_at = met_at or time.time()
                    if view["fallback"]:
                        session.end("unlocked", "fallback")
                    elif time.time() - met_at > FINISH_GRACE:
                        session.engage_fallback("coach did not finish after the target was met")
                else:
                    met_at = None  # the coach raised the target
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    session.quit()
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    with open(gate.PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    try:
        try:
            with open(gate.PENDING) as f:
                message = json.load(f).get("message", "")
        except (OSError, ValueError):
            message = ""
        session = coach.Session(message)
        worker = threading.Thread(target=coach.run_coach, args=(session,), daemon=True)
        worker.start()
        # Wait for the coach to pick an exercise or grant an extension. No camera for a granted plea.
        if not session.decided.wait(coach.SESSION_SECONDS + 10):
            session.engage_fallback("coach never decided")
        if session.outcome is None:
            camera_loop(session)
        if session.outcome is None:
            # They pressed q or the camera died. Give the coach a moment to log the skip itself.
            deadline = time.time() + (0 if session.fallback else QUIT_GRACE)
            while session.outcome is None and time.time() < deadline:
                time.sleep(0.1)
            session.end("skipped", "fallback")
        worker.join(5)  # let the coach's last tool call reach sessions.jsonl
    finally:
        try:
            os.remove(gate.PIDFILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
