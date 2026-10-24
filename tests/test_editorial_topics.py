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

    def test_next_sports_and_culture_boundaries(self):
        reviewed = json.loads((Path(__file__).resolve().parents[1] / "data" / "reviewed_en.json").read_text())
        for number in range(692, 703):
            self.assertEqual(reviewed[f"q{number:04}"]["verified_topic"], "SPORTS")
        for number in [690, 691]:
            self.assertEqual(reviewed[f"q{number:04}"]["verified_topic"], "CULTURE")

    def test_next_literary_authors_are_culture(self):
        reviewed = json.loads((Path(__file__).resolve().parents[1] / "data" / "reviewed_en.json").read_text())
        for number in range(640, 645):
            self.assertEqual(reviewed[f"q{number:04}"]["verified_topic"], "CULTURE")

    def test_national_song_authors_are_culture(self):
        reviewed = json.loads((Path(__file__).resolve().parents[1] / "data" / "reviewed_en.json").read_text())
        for number in [566, 567]:
            self.assertEqual(reviewed[f"q{number:04}"]["verified_topic"], "CULTURE")
