"""Tests for the gate and the coach's tools. No camera, no Claude, no network.

Run with: python3 -m unittest test_desk_shrimp -v
"""
import asyncio
import importlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

os.environ["DESK_SHRIMP_HOME"] = tempfile.mkdtemp()
os.environ.pop("DESK_SHRIMP_COACH", None)
import gate   # noqa: E402
import coach  # noqa: E402


def fresh():
    """Points both modules at an empty data folder."""
    os.environ["DESK_SHRIMP_HOME"] = tempfile.mkdtemp()
    importlib.reload(gate)
    importlib.reload(coach)
    coach.WATCH_MIN = 0


def call(box, name, **args):
    return asyncio.run(box.call(name, args))


def do_reps(session, n):
    for _ in range(n):
        session.observe(True, rep=True)


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def remaining():
    start, _ = gate.read_state()
    return gate.LIMIT_SECONDS - (time.time() - start)


class ToolGuardrails(unittest.TestCase):
    def setUp(self):
        fresh()
        self.s = coach.Session("refactor the auth middleware")
        self.box = coach.Toolbox(self.s)

    def test_no_free_unlock(self):
        self.assertIn("refused", call(self.box, "finish", outcome="unlocked"))
        call(self.box, "start_exercise", exercise="squats", reps=8, message="8 squats")
        do_reps(self.s, 7)
        self.assertIn("refused", call(self.box, "finish", outcome="unlocked"))
        self.assertIsNone(self.s.outcome)
        do_reps(self.s, 1)
        self.assertEqual(call(self.box, "finish", outcome="unlocked")["ended"], "unlocked")
        entry = coach.read_breaks()[-1]
        self.assertEqual((entry["exercise"], entry["reps"], entry["completed"], entry["source"]),
                         ("squats", 8, True, "claude"))
        self.assertAlmostEqual(remaining(), gate.LIMIT_SECONDS, delta=2)
        self.assertFalse(gate.read_state()[1])  # next prompt announces the new timer

    def test_start_exercise_limits(self):
        self.assertIn("refused", call(self.box, "start_exercise", exercise="burpees", reps=10, message=""))
        self.assertIsNone(self.s.exercise)
        self.assertEqual(call(self.box, "start_exercise", exercise="squats", reps=500, message="")["target"], 20)
        self.assertEqual(call(self.box, "start_exercise", exercise="squats", reps=1, message="")["target"], 5)

    def test_owed_reps_raise_the_floor(self):
        coach.write_deals({"extensions": 1, "owed_reps": 6, "next_timer": None})
        self.assertEqual(call(self.box, "start_exercise", exercise="squats", reps=1, message="")["target"], 11)

    def test_switching_exercise_resets_count_and_changes_are_capped(self):
        call(self.box, "start_exercise", exercise="squats", reps=10, message="")
        do_reps(self.s, 4)
        result = call(self.box, "start_exercise", exercise="jumping jacks", reps=8, message="")
        self.assertEqual((result["reps_so_far"], self.s.reps), (0, 0))
        call(self.box, "start_exercise", exercise="jumping jacks", reps=9, message="")
        call(self.box, "start_exercise", exercise="jumping jacks", reps=10, message="")
        self.assertIn("refused", call(self.box, "start_exercise", exercise="jumping jacks", reps=11, message=""))

    def test_cannot_move_the_goalposts_after_target_met(self):
        call(self.box, "start_exercise", exercise="squats", reps=5, message="")
        do_reps(self.s, 5)
        self.assertIn("refused", call(self.box, "start_exercise", exercise="squats", reps=20, message=""))
        self.assertIn("refused", call(self.box, "finish", outcome="skipped"))

    def test_extension_limits(self):
        result = call(self.box, "grant_extension", seconds=9999, extra_reps=0, reply="Fine — go")
        self.assertEqual((result["seconds"], result["extra_reps"]), (60, 3))
        self.assertEqual(self.s.outcome, "extension")
        self.assertAlmostEqual(remaining(), 60, delta=2)
        self.assertEqual(coach.read_deals()["owed_reps"], 3)
        reply = load(gate.REPLY)[0]
        self.assertEqual((reply["kind"], reply["text"]), ("extension", "Fine, go"))

    def test_third_extension_refused(self):
        for _ in range(2):
            call(coach.Toolbox(coach.Session("demo!")), "grant_extension", seconds=30, extra_reps=5, reply="ok")
        box = coach.Toolbox(coach.Session("demo again"))
        self.assertIn("refused", call(box, "grant_extension", seconds=30, extra_reps=5, reply="ok"))
        self.assertIsNone(box.s.outcome)
        self.assertEqual(coach.read_deals()["extensions"], 2)

    def test_no_extension_once_exercise_started(self):
        call(self.box, "start_exercise", exercise="squats", reps=10, message="")
        self.assertIn("refused", call(self.box, "grant_extension", seconds=30, extra_reps=5, reply=""))

    def test_skip_needs_a_quit_or_a_stall(self):
        call(self.box, "start_exercise", exercise="squats", reps=10, message="")
        self.assertIn("refused", call(self.box, "finish", outcome="skipped"))
        self.s.quit()
        self.assertIn("refused", call(self.box, "start_exercise", exercise="squats", reps=5, message=""))
        gate.write_state(time.time() - 500)
        self.assertEqual(call(self.box, "set_next_timer", seconds=1)["applied_seconds"], coach.MIN_TIMER)
        self.assertEqual(call(self.box, "finish", outcome="skipped")["ended"], "skipped")
        self.assertFalse(coach.read_breaks()[-1]["completed"])
        self.assertLess(remaining(), 0)  # a skip never unlocks
        # The coach's shorter timer carries to the next completed break.
        s2 = coach.Session("")
        box2 = coach.Toolbox(s2)
        call(box2, "start_exercise", exercise="high knees", reps=5, message="")
        do_reps(s2, 5)
        call(box2, "finish", outcome="unlocked")
        self.assertAlmostEqual(remaining(), coach.MIN_TIMER, delta=2)
        self.assertIsNone(coach.read_deals()["next_timer"])

    def test_timer_bounds(self):
        self.assertEqual(call(self.box, "set_next_timer", seconds=10**6)["applied_seconds"], coach.MAX_TIMER)
        self.assertEqual(call(self.box, "set_next_timer", seconds="soon")["applied_seconds"], gate.LIMIT_SECONDS)

    def test_watch_reports_and_returns_early(self):
        self.assertIn("error", call(self.box, "watch", seconds=5))
        call(self.box, "start_exercise", exercise="squats", reps=5, message="")

        def camera():
            for i in range(10):
                time.sleep(0.05)
                self.s.observe(framed=i >= 5, rep=i >= 5)
        threading.Thread(target=camera).start()
        started = time.time()
        result = call(self.box, "watch", seconds=20)
        self.assertLess(time.time() - started, 5)
        self.assertEqual((result["reps"], result["target_met"], result["user_quit"]), (5, True, False))
        self.assertLessEqual(result["in_frame_percent"], 60)

    def test_reps_stop_counting_at_target(self):
        call(self.box, "start_exercise", exercise="squats", reps=5, message="")
        do_reps(self.s, 9)
        self.assertEqual(self.s.reps, 5)

    def test_budget_hands_over_to_fallback(self):
        for _ in range(coach.MAX_CALLS):
            call(self.box, "read_history")
        self.assertFalse(self.s.fallback)
        self.assertIn("error", call(self.box, "read_history"))
        self.assertTrue(self.s.fallback)
        self.assertEqual((self.s.exercise, self.s.target), ("jumping jacks", 10))
        self.assertIn("error", call(self.box, "finish", outcome="unlocked"))

    def test_tools_dead_after_the_break_ends(self):
        call(self.box, "grant_extension", seconds=30, extra_reps=5, reply="ok")
        self.assertIn("error", call(self.box, "start_exercise", exercise="squats", reps=5, message=""))
        self.assertIsNone(self.s.exercise)

    def test_every_call_is_logged(self):
        call(self.box, "read_history", days=3)
        call(self.box, "say", message="Step back — I can't see your knees")
        lines = load(coach.SESSIONS)
        self.assertEqual([entry["tool"] for entry in lines], ["read_history", "say"])
        self.assertEqual(lines[1]["result"]["shown"], "Step back, I can't see your knees")

    def test_bad_arguments_do_not_crash(self):
        self.assertIn("error", call(self.box, "finish", verdict="unlocked"))


class Fallback(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_coach_failure_falls_back_to_jumping_jacks_plus_owed(self):
        coach.write_deals({"extensions": 1, "owed_reps": 4, "next_timer": None})
        s = coach.Session("hi")

        async def broken(session):
            raise RuntimeError("claude unreachable")
        with mock.patch.object(coach, "agent_loop", broken):
            coach.run_coach(s)
        self.assertTrue(s.fallback and s.decided.is_set())
        self.assertEqual((s.exercise, s.target), ("jumping jacks", 14))
        self.assertEqual(load(gate.REPLY)[0]["kind"], "exercise")
        do_reps(s, 14)
        s.end("unlocked", "fallback")  # what the camera loop does in fallback mode
        self.assertEqual(coach.read_breaks()[-1]["source"], "fallback")
        self.assertGreater(remaining(), 0)

    def test_coach_that_stops_early_falls_back(self):
        s = coach.Session("hi")

        async def lazy(session):
            return None
        with mock.patch.object(coach, "agent_loop", lazy):
            coach.run_coach(s)
        self.assertTrue(s.fallback)


class Gate(unittest.TestCase):
    def setUp(self):
        fresh()
        with open(gate.TIMER, "w") as f:
            json.dump({"seconds": 60}, f)

    def run_gate(self, prompt):
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps({"prompt": prompt}))), redirect_stdout(out):
            gate.main()
        return json.loads(out.getvalue()) if out.getvalue() else None

    def test_timer_and_block(self):
        self.assertIn("60 seconds", self.run_gate("hello")["systemMessage"])
        self.assertIsNone(self.run_gate("more work"))
        gate.write_state(time.time() - 61)

        def fake_launch(prompt):
            coach.write_reply("exercise", "12 squats, shrimp.")
        with mock.patch.object(gate, "launch_session", fake_launch):
            out = self.run_gate("refactor the auth middleware")
        self.assertEqual(out["decision"], "block")
        self.assertIn("12 squats, shrimp.", out["reason"])

    def test_extension_reply_and_missing_reply(self):
        self.assertIn("45 seconds; +5 reps", gate.describe(
            {"kind": "extension", "text": "Fine.", "seconds": 45, "extra_reps": 5}))
        self.assertIn("camera window", gate.describe(None))

    def test_running_session_blocks_without_relaunch(self):
        gate.write_state(time.time() - 61)
        with open(gate.PIDFILE, "w") as f:
            f.write(str(os.getpid()))
        with mock.patch.object(gate, "launch_session", side_effect=AssertionError("relaunched")):
            self.assertIn("Finish your reps", self.run_gate("anything")["reason"])

    def test_safe_words(self):
        gate.write_state(time.time() - 61)
        self.assertEqual(self.run_gate("pineapple")["decision"], "block")
        self.assertIsNone(self.run_gate("work while off"))
        self.assertIn("how long", self.run_gate(" Apple ")["reason"])
        self.assertIn("how long", self.run_gate("work again")["reason"])
        self.assertIn("20 minutes", self.run_gate("20 minutes")["reason"])
        self.assertIsNone(self.run_gate("work again"))

    def test_gate_ignores_the_coachs_own_claude_session(self):
        gate.write_state(time.time() - 61)
        with mock.patch.dict(os.environ, {"DESK_SHRIMP_COACH": "1"}):
            with mock.patch.object(gate, "launch_session", side_effect=AssertionError("launched")):
                self.assertIsNone(self.run_gate("Time is up."))

    def test_first_run_asks_for_the_timer(self):
        os.remove(gate.TIMER)
        self.assertIn("how long", self.run_gate("refactor the auth middleware")["reason"])
        self.assertIn("how long", self.run_gate("forever")["reason"])
        self.assertIn("45 minutes", self.run_gate("45 minutes")["reason"])
        self.assertEqual(gate.read_limit(), 2700)
        self.assertIsNone(self.run_gate("back to work"))  # timer is running, nothing to announce
        self.assertEqual([gate.parse_duration(t) for t in ("1 hour", "90s", "2 Hrs", "1.5 min", "0 min", "ten minutes")],
                         [3600, 90, 7200, 90, None, None])

    def test_shortened_timer_is_announced_with_the_real_number(self):
        gate.start_window(30, announced=False)
        self.assertIn("30 seconds", self.run_gate("back to work")["systemMessage"])


if __name__ == "__main__":
    unittest.main()
