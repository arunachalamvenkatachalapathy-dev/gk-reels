import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "upload_drive_stock.py"
spec = importlib.util.spec_from_file_location("upload_drive_stock", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DriveManifestTests(unittest.TestCase):
    def make_zip(self, manifest, mp4s=None):
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w") as z:
            z.writestr("manifest.json", json.dumps(manifest))
            for name in (mp4s or {}): z.writestr(name, b"video")
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
        return zipfile.ZipFile(tmp.name)

    def base_video(self, qid="q0509"):
        return {"question_id":qid,"title":"Title #Shorts","description":"Description","file":qid+".mp4","sha256":"a"*64}

    def test_accepts_matching_channel_and_preserves_metadata(self):
        v=self.base_video()
        z=self.make_zip({"destination_channel_id":mod.EXPECTED_CHANNEL_ID,"videos":[v]}, {v["file"]})
        with z:
            m, items, dup=mod.archive_candidates(z)
        self.assertEqual(items[0]["title"],v["title"])
        self.assertEqual(items[0]["description"],v["description"])
        self.assertEqual(dup,[])

    def test_rejects_wrong_channel(self):
        v=self.base_video()
        z=self.make_zip({"destination_channel_id":"wrong","videos":[v]}, {v["file"]})
        with z, self.assertRaisesRegex(RuntimeError,"destination channel"):
            mod.archive_candidates(z)

    def test_rejects_unsafe_path(self):
        v=self.base_video(); v["file"]="../q0509.mp4"
        z=self.make_zip({"destination_channel_id":mod.EXPECTED_CHANNEL_ID,"videos":[v]})
        with z, self.assertRaisesRegex(RuntimeError,"unsafe"):
            mod.archive_candidates(z)

    def test_rejects_bad_digest_and_metadata(self):
        v=self.base_video(); v["sha256"]="bad"
        z=self.make_zip({"destination_channel_id":mod.EXPECTED_CHANNEL_ID,"videos":[v]}, {v["file"]})
        with z, self.assertRaisesRegex(RuntimeError,"SHA-256"):
            mod.archive_candidates(z)
        v=self.base_video(); v["description"]=""
        z=self.make_zip({"destination_channel_id":mod.EXPECTED_CHANNEL_ID,"videos":[v]}, {v["file"]})
        with z, self.assertRaisesRegex(RuntimeError,"description"):
            mod.archive_candidates(z)

    def test_duplicate_question_ids_reported_and_only_first_kept(self):
        v=self.base_video()
        z=self.make_zip({"destination_channel_id":mod.EXPECTED_CHANNEL_ID,"videos":[v,v]}, {v["file"]})
        with z: _,items,duplicates=mod.archive_candidates(z)
        self.assertEqual(len(items),1)
        self.assertEqual(duplicates,[v["question_id"]])

if __name__ == "__main__": unittest.main()
