import json
import unittest
from pathlib import Path

class EditorialTopicTests(unittest.TestCase):
    def test_corrected_category_boundaries(self):
        reviewed = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'reviewed_en.json').read_text())
        for number in range(783, 807):
            self.assertEqual(reviewed[f'q{number:04}']['verified_topic'], 'CULTURE')
        self.assertEqual(reviewed['q0848']['verified_topic'], 'HISTORY')
        for number in range(996, 1008):
            qid = f'q{number:04}'
            if qid in reviewed:
                self.assertEqual(reviewed[qid]['verified_topic'], 'SPORTS')
