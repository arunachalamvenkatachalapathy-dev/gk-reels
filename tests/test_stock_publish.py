"""Gate tests for the EN Drive-stock publisher. No network, no credentials."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stock_publish as sp


CONFIG = {
    "drive_folder_id": "folder",
    "channel_id": "UCcaMzi9aIDVCU3qqoqFtmuQ",
    "slots": {"morning": "07:30", "afternoon": "19:30"},
    "window_minutes": 120,
    "held_ids": ["q0758"],
    "skip_qid_range_end": 92,
    "studio_slots_until": "2026-11-03",
    "state_branch": "en-stock-publication-state",
    "state_file": "stock_state.json",
}


def ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc) - timedelta(hours=5, minutes=30)


class NameParsing(unittest.TestCase):
    def test_stock_zip(self):
        self.assertEqual(sp.parse_stock_name("GK_EN_private_P1_40048484761.zip"), "P1")

    def test_foreign_rejected(self):
        self.assertIsNone(sp.parse_stock_name("GK_TA_private_p0464-e1.zip"))
        self.assertIsNone(sp.parse_stock_name("readme.txt"))


class VideoEntryGate(unittest.TestCase):
    def entry(self, **kw):
        base = {"question_id": "q0569", "title": "How many spokes? #Shorts", "description": "d", "file": "q0569.mp4", "sha256": "0" * 64, "duration": 12.0}
        base.update(kw)
        return base

    def test_valid(self):
        self.assertEqual(sp.validate_video_entry(self.entry(), CONFIG), "q0569")

    def test_already_published_range_rejected(self):
        with self.assertRaises(ValueError):
            sp.validate_video_entry(self.entry(question_id="q0050"), CONFIG)

    def test_bad_qid(self):
        with self.assertRaises(ValueError):
            sp.validate_video_entry(self.entry(question_id="x"), CONFIG)

    def test_duration_cap(self):
        with self.assertRaises(ValueError):
            sp.validate_video_entry(self.entry(duration=36.0), CONFIG)

    def test_title_length(self):
        with self.assertRaises(ValueError):
            sp.validate_video_entry(self.entry(title="t" * 101), CONFIG)


class SlotGate(unittest.TestCase):
    def test_suppressed_while_studio_queue_active(self):
        self.assertIsNone(sp.select_slot(ist(2026, 11, 2, 7, 45), CONFIG, {"slots": {}}))
        self.assertIsNone(sp.select_slot(ist(2026, 11, 3, 19, 45), CONFIG, {"slots": {}}))

    def test_open_after_studio_queue(self):
        slot = sp.select_slot(ist(2026, 11, 4, 7, 45), CONFIG, {"slots": {}})
        self.assertEqual(slot["key"], "2026-11-04:morning")

    def test_published_slot_not_repicked(self):
        state = {"slots": {"2026-11-04:morning": {"status": "published"}}}
        self.assertIsNone(sp.select_slot(ist(2026, 11, 4, 7, 45), CONFIG, state))

    def test_outside_window(self):
        self.assertIsNone(sp.select_slot(ist(2026, 11, 4, 12, 0), CONFIG, {"slots": {}}))


if __name__ == "__main__":
    unittest.main()
