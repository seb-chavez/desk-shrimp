"""Opens the webcam and counts jumping jacks with MediaPipe Pose.

One rep: both wrists go from below the shoulders to above the head.
At TARGET reps, resets the gate timer and closes. Press q to quit without unlocking.
"""
import json
import os
import time

import cv2
import mediapipe as mp

TARGET = 10
HOME = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HOME, "state.json")
PIDFILE = os.path.join(HOME, "counter.pid")
WINDOW = "Jumping jacks to continue"

P = mp.solutions.pose.PoseLandmark


def arm_position(lm):
    """Returns 'up', 'down', or None if the body isn't clearly visible."""
    pts = [lm[P.NOSE], lm[P.LEFT_SHOULDER], lm[P.RIGHT_SHOULDER], lm[P.LEFT_WRIST], lm[P.RIGHT_WRIST]]
    if min(p.visibility for p in pts) < 0.5:
        return None
    nose, ls, rs, lw, rw = pts
    # Image y grows downward: smaller y means higher on screen.
    if lw.y < nose.y and rw.y < nose.y:
        return "up"
    if lw.y > ls.y and rw.y > rs.y:
        return "down"
    return None


def draw(frame, text, sub, color):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 110), (0, 0, 0), -1)
    cv2.putText(frame, text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.8, color, 4)
    cv2.putText(frame, sub, (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)


def main():
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    cap = cv2.VideoCapture(0)
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    reps, last = 0, None
    try:
        with mp.solutions.pose.Pose(model_complexity=0) as pose:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if result.pose_landmarks:
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, result.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS)
                    pos = arm_position(result.pose_landmarks.landmark)
                    if pos == "up" and last == "down":
                        reps += 1
                    if pos:
                        last = pos
                draw(frame, f"{reps} / {TARGET}", "Arms all the way up, then back down. q to quit.", (0, 220, 255))
                cv2.imshow(WINDOW, frame)
                if reps >= TARGET:
                    draw(frame, "Unlocked!", "Go back to Claude Code and resend your message.", (0, 255, 0))
                    cv2.imshow(WINDOW, frame)
                    cv2.waitKey(2000)
                    with open(STATE, "w") as f:
                        json.dump({"window_start": time.time(), "announced": False}, f)
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        try:
            os.remove(PIDFILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
