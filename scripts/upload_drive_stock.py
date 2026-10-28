"""Upload selected existing GK EN videos from a Drive ZIP as PRIVATE drafts.

The ZIP is fetched only at workflow runtime after its Drive link is temporarily
available. Nothing from the ZIP is checked into the public repository.
"""
import argparse
import hashlib
import contextlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
OUT = BASE / "output" / "private_batch"
EXPECTED_CHANNEL_ID = "UCcaMzi9aIDVCU3qqoqFtmuQ"
HELD_QUESTION_IDS = {"q0758"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def archive_candidates(zf):
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except (KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError("Drive ZIP lacks a valid manifest.json") from exc
    if manifest.get("destination_channel_id") != EXPECTED_CHANNEL_ID:
        raise RuntimeError("manifest destination channel does not match GK English channel; aborting")
    videos = manifest.get("videos")
    if not isinstance(videos, list):
        raise RuntimeError("manifest videos must be a list")
    names = set(zf.namelist())
    seen_archive = set()
    candidates = []
    skipped_duplicates = []
    for v in videos:
        qid = v.get("question_id")
        if not isinstance(qid, str) or not re.fullmatch(r"q\d{4}", qid):
            raise RuntimeError("invalid question_id in manifest")
        if qid in seen_archive:
            skipped_duplicates.append(qid)
            continue
        seen_archive.add(qid)
        title, desc = v.get("title"), v.get("description")
        fname, digest = v.get("file"), v.get("sha256")
        if not isinstance(title, str) or not title.strip() or len(title) > 100:
            raise RuntimeError(f"invalid title for {qid}")
        if not isinstance(desc, str) or not desc.strip() or len(desc) > 5000:
            raise RuntimeError(f"invalid description for {qid}")
        if not isinstance(fname, str) or PurePosixPath(fname).name != fname or fname not in names or not fname.lower().endswith(".mp4"):
            raise RuntimeError(f"unsafe or missing MP4 path for {qid}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise RuntimeError(f"invalid SHA-256 for {qid}")
        info = zf.getinfo(fname)
        if info.file_size <= 0 or info.file_size > 50_000_000:
            raise RuntimeError(f"invalid MP4 size for {qid}")
        candidates.append({**v, "question_id": qid, "file": fname, "sha256": digest.lower()})
    return manifest, candidates, skipped_duplicates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--limit", type=int, required=True)
    ap.add_argument("--ids", default="", help="Optional exact question IDs for a sample")
    args = ap.parse_args()
    if not 1 <= args.limit <= 10:
        raise SystemExit("limit must be between 1 and 10")

    OUT.mkdir(parents=True, exist_ok=True)
    ledger = load(DATA / "private_batch.json") if (DATA / "private_batch.json").exists() else {"batches": []}
    state = load(DATA / "state.json")
    already = set(state.get("published_ids", [])) | HELD_QUESTION_IDS
    for batch in ledger.get("batches", []):
        already.update(v.get("question_id") for v in batch.get("videos", []) if v.get("question_id"))
        already.update(v.get("question_id") for v in batch.get("unverified_attempts", []) if v.get("question_id"))

    with zipfile.ZipFile(args.archive) as zf:
        manifest, candidates, skipped_duplicates = archive_candidates(zf)
        eligible = [v for v in candidates if v["question_id"] not in already]
        requested_ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        if len(requested_ids) != len(set(requested_ids)):
            raise RuntimeError("sample question ID list contains duplicates")
        if requested_ids:
            if len(requested_ids) != args.limit:
                raise RuntimeError("explicit sample IDs must match --limit exactly")
            by_id = {v["question_id"]: v for v in eligible}
            missing = [qid for qid in requested_ids if qid not in by_id]
            if missing:
                raise RuntimeError("explicit sample IDs are missing or already uploaded: " + ",".join(missing))
            eligible = [by_id[qid] for qid in requested_ids]
        if len(eligible) < args.limit:
            raise RuntimeError(f"only {len(eligible)} non-ledger videos available; need {args.limit}")
        selected = eligible[:args.limit]
        if len({v["question_id"] for v in selected}) != len(selected):
            raise RuntimeError("selected question IDs are not unique")
        source_batch_key = str(manifest.get("batch_id", "drive-stock"))
        batch_key = source_batch_key + "-" + selected[0]["question_id"] + "-" + selected[-1]["question_id"]
        if any(str(b.get("batch_id")) == batch_key for b in ledger.get("batches", [])):
            raise RuntimeError("this exact ZIP question-ID range is already reconciled; refusing replay")
        if len({v["question_id"] for v in selected}) != args.limit:
            raise RuntimeError("selected question IDs are not unique")

        from upload_youtube import get_youtube_client, upload_short
        yt = get_youtube_client()
        items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
        if not items:
            raise RuntimeError("OAuth identity has no YouTube channel; aborting before upload")
        channel_id = items[0]["id"]
        if channel_id != EXPECTED_CHANNEL_ID:
            raise RuntimeError(f"WRONG CHANNEL: {channel_id}; expected GK English; aborting before upload")

        results = []
        attempts = []
        checkpoint_path = OUT / "upload_results.json"
        # Start a checkpoint before the first upload so even a mid-batch failure
        # is reconcilable. Keep the original source metadata byte-for-byte as strings.
        checkpoint = {
            "batch_id": batch_key,
            "uploaded_at": None,
            "channel_id": channel_id,
            "videos": results,
            "attempts": attempts,
            "source_archive": Path(args.archive).name,
            "source_destination_channel_id": manifest.get("destination_channel_id"),
            "skipped_archive_duplicate_question_ids": skipped_duplicates,
            "skipped_already_uploaded_question_ids": [v["question_id"] for v in candidates if v["question_id"] in already and v["question_id"] not in HELD_QUESTION_IDS],
            "skipped_held_question_ids": [v["question_id"] for v in candidates if v["question_id"] in HELD_QUESTION_IDS],
        }
        save(checkpoint_path, checkpoint)
        for v in selected:
            payload = zf.read(v["file"])
            if hashlib.sha256(payload).hexdigest() != v["sha256"]:
                raise RuntimeError(f"SHA-256 mismatch for {v['question_id']}; refusing upload")
            local_path = OUT / v["file"]
            local_path.write_bytes(payload)
            # The shared helper prints upload URLs/progress. Suppress stdout so a
            # public Actions log does not disclose private-stock IDs or metadata.
            with contextlib.redirect_stdout(io.StringIO()):
                video_id = upload_short(str(local_path), v["title"], v["description"], tags=v.get("tags"), privacy="private")
            attempt = {"question_id": v["question_id"], "yt_id": video_id, "state": "uploaded_unverified"}
            attempts.append(attempt)
            save(checkpoint_path, checkpoint)
            chk_items = yt.videos().list(part="status,snippet", id=video_id).execute().get("items", [])
            if len(chk_items) != 1:
                raise RuntimeError(f"post-upload verification missing for {video_id}")
            chk = chk_items[0]
            privacy = chk.get("status", {}).get("privacyStatus")
            snippet = chk.get("snippet", {})
            if privacy != "private" or snippet.get("channelId") != channel_id:
                raise RuntimeError(f"post-upload verification failed for {video_id}: privacy={privacy}; aborting")
            if snippet.get("title") != v["title"] or snippet.get("description") != v["description"]:
                raise RuntimeError(f"post-upload metadata verification failed for {v['question_id']}; aborting")
            results.append({
                "question_id": v["question_id"], "yt_id": video_id,
                "privacy": privacy, "scheduled": False,
            })
            attempt["state"] = "verified_private"
            checkpoint["uploaded_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            save(checkpoint_path, checkpoint)
            print(f"PRIVATE upload verified: {v['question_id']}")
        for v in selected:
            (OUT / v["file"]).unlink(missing_ok=True)
        print(json.dumps({"uploaded": len(results), "channel_id_verified": channel_id == EXPECTED_CHANNEL_ID,
                          "question_ids": [v["question_id"] for v in results],
                          "privacy": "private"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
