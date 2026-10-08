import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# Isolate orchestration tests from rendering, API clients and live credentials.
sys.modules["seo_agent"] = types.SimpleNamespace()
sys.modules["upload_telegram"] = types.SimpleNamespace(send_telegram_update=lambda *a, **k: False)
sys.modules["render"] = types.SimpleNamespace(render_video=lambda *a, **k: None, REVIEWED={"q1": {}})
spec = importlib.util.spec_from_file_location("pipeline", Path(__file__).resolve().parents[1] / "scripts" / "run_pipeline.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.q = {"id": "q1", "question": "What is it?", "options": ["A", "B"], "answer": "A"}
        self.state = {"published_ids": [], "current_day": 1, "total_published": 0}

    def run_main(self, modules, env):
        with patch.object(p, "load_json", side_effect=[[self.q], self.state]), patch.object(p, "save_json") as save, patch.dict(sys.modules, modules), patch.dict(p.os.environ, env, clear=True), patch.object(p.sys, "argv", ["run_pipeline.py"]):
            try:
                p.main()
            finally:
                self.saved = save.call_args_list

    def test_all_paused_preserves_state(self):
        self.run_main({}, {"PAUSED_DESTINATIONS": "youtube,instagram,facebook"})
        self.assertEqual(self.state["published_ids"], [])
        self.assertEqual(self.state["total_published"], 0)
        self.assertEqual(self.saved, [])

    def test_exhaustion_does_not_repeat(self):
        with self.assertRaises(RuntimeError):
            p.pick_next_question([self.q], {"published_ids": ["q1"]})

    def test_unreviewed_never_consumed_or_picked(self):
        other = {"id": "q2", "question": "x", "options": ["A", "B"]}
        state = {"published_ids": []}
        self.assertEqual(p.pick_next_question([other, self.q], state)["id"], "q1")
        self.assertEqual(state["published_ids"], [])
        with self.assertRaisesRegex(RuntimeError, "BUFFER EMPTY"):
            p.pick_next_question([other], {"published_ids": []})

    def test_empty_bank_fails_clearly(self):
        with self.assertRaises(RuntimeError):
            p.pick_next_question([], {})

    def test_no_destinations_keeps_question(self):
        with self.assertRaises(RuntimeError):
            self.run_main({}, {})
        self.assertEqual(self.state["published_ids"], [])
        self.assertEqual(self.state["total_published"], 0)

    def test_upload_failure_is_failure_and_not_consumed(self):
        mod = types.SimpleNamespace(upload_short=lambda *a, **k: None, get_youtube_client=lambda: None)
        with self.assertRaises(RuntimeError):
            self.run_main({"upload_youtube": mod}, {"YT_CLIENT_ID": "test", "YT_CLIENT_SECRET": "test", "YT_REFRESH_TOKEN": "test"})
        self.assertEqual(self.state["published_ids"], [])
        self.assertEqual(self.state["total_published"], 0)
        self.assertEqual(self.state["pending_publication"]["question_id"], "q1")
        self.assertTrue(self.saved)

    def test_partial_success_retained(self):
        yt = types.SimpleNamespace(upload_short=lambda *a, **k: "video-id", get_youtube_client=lambda: None)
        ig = types.SimpleNamespace(upload_to_github_release=lambda *a: "https://example.invalid/video", publish_reel=lambda *a: (None, None))
        fb = types.SimpleNamespace(publish_facebook_reel=lambda *a, **k: None)
        env = {k:"test" for k in ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "IG_ACCESS_TOKEN", "IG_USER_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY", "FB_PAGE_ID"]}
        with self.assertRaises(RuntimeError):
            self.run_main({"upload_youtube": yt, "upload_instagram": ig, "upload_facebook": fb}, env)
        self.assertIn("youtube", self.state["pending_publication"]["results"])
        self.assertEqual(self.state["published_ids"], [])

    def test_success_advances_once(self):
        yt = types.SimpleNamespace(upload_short=lambda *a, **k: "video-id", get_youtube_client=lambda: None)
        self.run_main({"upload_youtube": yt}, {"YT_CLIENT_ID": "test", "YT_CLIENT_SECRET": "test", "YT_REFRESH_TOKEN": "test"})
        self.assertEqual(self.state["published_ids"], ["q1"])
        self.assertEqual(self.state["total_published"], 1)

    def test_stale_partial_publication_is_blocked(self):
        self.state["pending_publication"] = {"date": "2000-01-01", "question_id": "q1"}
        with self.assertRaisesRegex(RuntimeError, "earlier date"):
            self.run_main({}, {})

if __name__ == "__main__":
    unittest.main()
