import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.modules['render'] = types.SimpleNamespace(render_video=lambda *a, **k: None, REVIEWED={})
spec = importlib.util.spec_from_file_location('pipeline', Path(__file__).resolve().parents[1] / 'scripts' / 'run_pipeline.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
IST = timezone(timedelta(hours=5, minutes=30))

class SlotSchedulingTests(unittest.TestCase):
    def test_before_morning_window_skips(self):
        self.assertIsNone(p.next_due_slot(datetime(2026, 10, 12, 7, 29, tzinfo=IST), []))

    def test_morning_window_opens_slot_one(self):
        self.assertEqual(p.next_due_slot(datetime(2026, 10, 12, 7, 30, tzinfo=IST), []), 1)

    def test_missed_morning_catches_up_before_afternoon(self):
        self.assertEqual(p.next_due_slot(datetime(2026, 10, 12, 12, 30, tzinfo=IST), []), 1)

    def test_after_morning_then_evening_due(self):
        self.assertIsNone(p.next_due_slot(datetime(2026, 10, 12, 12, 30, tzinfo=IST), [1]))
        self.assertEqual(p.next_due_slot(datetime(2026, 10, 12, 19, 30, tzinfo=IST), [1]), 2)

    def test_only_one_slot_per_run_then_catchup(self):
        now = datetime(2026, 10, 12, 19, 30, tzinfo=IST)
        self.assertEqual(p.next_due_slot(now, []), 1)
        self.assertEqual(p.next_due_slot(now, [1]), 2)

    def test_five_hour_late_fire_catches_up_morning_slot(self):
        five_hours_after_morning = datetime(2026, 10, 12, 12, 30, tzinfo=IST)
        self.assertEqual(p.next_due_slot(five_hours_after_morning, []), 1)

    def test_no_duplicate_for_completed_slots(self):
        self.assertIsNone(p.next_due_slot(datetime(2026, 10, 12, 20, 0, tzinfo=IST), [1, 2]))

    def test_legacy_count_migrates_sequentially(self):
        self.assertEqual(p.published_slots_for_date({'last_published_date':'2026-10-12','published_today_count':1}, '2026-10-12'), [1])
        self.assertEqual(p.published_slots_for_date({'last_published_date':'2026-10-12','published_today_count':2}, '2026-10-12'), [1,2])

    def test_explicit_per_date_slot_state_wins(self):
        state = {'last_published_date':'2026-10-12','published_today_count':1,'published_slots_by_date':{'2026-10-12':[2]}}
        self.assertEqual(p.published_slots_for_date(state, '2026-10-12'), [2])

    def test_new_ist_date_starts_empty(self):
        self.assertEqual(p.published_slots_for_date({'last_published_date':'2026-10-11','published_today_count':2}, '2026-10-12'), [])

if __name__ == '__main__':
    unittest.main()
