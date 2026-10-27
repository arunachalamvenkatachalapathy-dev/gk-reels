"""Isolated GK EN private-batch builder.

Creates stock Shorts from the BACK of the reviewed bank and uploads them as
PRIVATE YouTube drafts for owner review. Never touches the daily route:
- no slot logic, no day/slot counters, no Instagram/Facebook/Telegram;
- picks only questions that are source-reviewed, unpublished and suitable,
  walking the bank backwards so the front-moving daily picker is undisturbed;
- records question IDs in state.published_ids ONLY after a verified private
  upload, so no future daily run can repost the same question;
- aborts before any upload if the OAuth identity is not @gk_snippets.

Modes:
  render  - render + verify + sample frames + manifest (no state changes)
  upload  - verify manifest/hashes, upload as private, verify privacy,
            write data/private_batch.json + state.published_ids (commit is
            done by the workflow step)
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

DATA = BASE / "data"
OUT = BASE / "output" / "private_batch"
# Authoritative EN channel ID. Triple-grounded 2026-10-23: today's confirmed EN
# production upload (youtube.com/watch?v=1CYS7HJE93Q page channelId) and both
# handle pages @gk_snippets and @GK_Snippets_English resolve to this same ID.
EXPECTED_CHANNEL_ID = "UCcaMzi9aIDVCU3qqoqFtmuQ"
KNOWN_HANDLES = {"@gk_snippets", "@gk_snippets_english"}  # informational; handles change, ID does not
PINNED = "Comment your answer below."


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_copy(text):
    # Same editorial filter as the daily pipeline (kept in sync manually).
    text = re.sub(r"[^\n.!?]*\b(?:90|99)%[^\n.!?]*(?:[.!?]|$)", "", str(text), flags=re.I)
    lines = [line for line in text.splitlines() if not re.search(r"giveaway|free.*(?:notes|pdf)|pdf.*notes|win.*(?:gift|material)|गिवअवे|फ्री.*(?:नोट्स|PDF)|18[- ]second|00:\d\d", line, re.I)]
    return "\n".join(lines).replace("9 AM & 7 PM IST", "7:30 AM & 7:30 PM IST").replace("9 AM & 7 PM", "7:30 AM & 7:30 PM").strip() or "Daily GK quiz"


def stock_content(q):
    """Existing editorial records win; otherwise use the supplied bank verbatim."""
    reviewed = load(DATA / "reviewed_en.json")
    if q["id"] in reviewed:
        return reviewed[q["id"]]
    if len(q.get("options", [])) != 4 or not isinstance(q.get("correct_index"), int) or not 0 <= q["correct_index"] < 4:
        raise ValueError("Four supplied options and a valid answer index required: " + q["id"])
    return {
        "display_question": q["question"], "speech_question": q["question"],
        "options": q["options"], "correct_index": q["correct_index"],
        "speech_answer": q["options"][q["correct_index"]] + ".",
        "explanation": "Answer as supplied in the question bank.",
        "memory_key": "Supplied answer: " + q["options"][q["correct_index"]],
        "source_url": None, "source_label": "Source: Supplied question bank",
        "provenance": "supplied_question_bank",
    }


def select_batch(questions, state, reviewed, count):
    from run_pipeline import is_suitable_short_question
    published = set(state.get("published_ids", []))
    picked = []
    for q in reversed(questions):
        if q["id"] in published:
            continue
        if not is_suitable_short_question(q):
            continue
        picked.append(q)
        if len(picked) == count:
            break
    if len(picked) < count:
        raise RuntimeError(f"Only {len(picked)} eligible questions available for batch")
    picked.reverse()
    return picked


def build_metadata(q, day, slot, state):
    topic = "General Knowledge & Daily Trivia"
    try:
        from seo_agent import detect_topic
        topic, _, _ = detect_topic(q.get("question", ""))
    except Exception:
        pass
    seo = None
    try:
        from seo_agent import generate_seo
        seo = generate_seo(q, day, slot, videos_per_day=state.get("videos_per_day", 2),
                           yt_client=None, published_history=state.get("published_history", []))
    except Exception as exc:
        print(f"  [SEO] static fallback for {q['id']}: {exc}")
    if seo:
        title, caption, tags = seo["title"], seo["description"], seo["tags"]
    else:
        opts_preview = " | ".join(f"({chr(65+i)}) {o}" for i, o in enumerate(q.get("options", [])))
        title = f"{q['question'][:28].rsplit(' ', 1)[0]} | GK Questions and Answers #Shorts"
        caption = (f"❓ {q['question']}\n👉 Drop your answer in the comments: {opts_preview}\n\n"
                   f"#Shorts #GKQuiz #GeneralKnowledge #DailyGK #UPSC #SSCCGL")
        tags = ["GK Snippets", "GK Quiz", "General Knowledge", "SSC CGL", "UPSC", "Shorts", "Daily GK"]
    caption = "\n".join(
        line for line in safe_copy(caption).splitlines()
        if not re.search(r"100 Days of GK|Day\s*\d+", line)
    )
    return topic, safe_copy(title), caption, tags


def select_explicit(questions, reviewed, ids):
    qmap = {q["id"]: q for q in questions}
    picked = []
    for qid in ids:
        q = qmap.get(qid)
        if q is None:
            raise RuntimeError(f"Explicit batch id {qid} not in bank")
        stock_content(q)  # structural validation, no external fact checks
        picked.append(q)
    return picked


def mode_render(count, ids=None):
    from render import REVIEWED, render_video
    os.environ["PRIVATE_STOCK_SUPPLIED_INPUT"] = "1"
    from run_pipeline import get_slot_track
    questions = load(DATA / "questions_en.json")
    state = load(DATA / "state.json")
    picked = select_explicit(questions, REVIEWED, ids) if ids else select_batch(questions, state, REVIEWED, count)
    OUT.mkdir(parents=True, exist_ok=True)
    palette = state.get("palette", ["#4D96FF"])
    cursor = int(state.get("palette_cursor", 0))
    base_day = int(state.get("current_day", 0))
    manifest = {
        "batch_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "destination_channel_id": EXPECTED_CHANNEL_ID,
        "videos": [],
    }
    if os.environ.get("REPLACES_BATCH_ID"):
        manifest["replaces_batch_id"] = os.environ["REPLACES_BATCH_ID"]
    for i, q in enumerate(picked):
        REVIEWED[q["id"]] = stock_content(q)
        day = base_day + 1 + i  # legacy arg only; no day/date text is put into batch metadata
        topic, title, caption, tags = build_metadata(q, day, 1, state)
        accent = palette[(cursor + i) % len(palette)]
        out_mp4 = OUT / f"{q['id']}.mp4"
        render_video(q, accent, str(out_mp4), str(OUT / f"tmp_{q['id']}"),
                     bg_music=get_slot_track(1), day=day, slot=1,
                     topic_name=topic, viral_badge="DAILY GK QUIZ")
        size = out_mp4.stat().st_size
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(out_mp4)], text=True).strip())
        if size <= 400_000 or not 6.0 <= dur <= 60.0:
            raise RuntimeError(f"Render verification failed for {q['id']}: size={size} duration={dur}")
        frames = []
        for j, frac in enumerate((0.2, 0.5, 0.8)):
            fp = OUT / f"{q['id']}_f{j+1}.jpg"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{dur*frac:.2f}",
                            "-i", str(out_mp4), "-frames:v", "1", str(fp)], check=True)
            frames.append(fp.name)
        sha = hashlib.sha256(out_mp4.read_bytes()).hexdigest()
        manifest["videos"].append({
            "question_id": q["id"], "title": title, "description": caption, "tags": tags,
            "provisional_day": day, "topic": topic, "file": out_mp4.name,
            "sha256": sha, "duration": dur, "frames": frames,
        })
        print(f"[BATCH] rendered {q['id']} ({dur:.1f}s, {size//1024} KB) topic={topic}")
    save(OUT / "manifest.json", manifest)
    print(f"[BATCH] render complete: {len(manifest['videos'])} videos, manifest written")


def mode_upload(batch_dir):
    bdir = Path(batch_dir)
    manifest = load(bdir / "manifest.json")
    if manifest.get("destination_channel_id") != EXPECTED_CHANNEL_ID:
        raise RuntimeError("manifest destination channel does not match GK English channel; aborting")
    from upload_youtube import get_youtube_client, upload_short
    yt = get_youtube_client()
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        raise RuntimeError("OAuth identity has no YouTube channel; aborting before any upload")
    handle = items[0]["snippet"].get("customUrl", "").lower()
    channel_id = items[0]["id"]
    if channel_id != EXPECTED_CHANNEL_ID:
        raise RuntimeError(f"WRONG CHANNEL: id={channel_id} handle={handle or '(none)'}; expected channel {EXPECTED_CHANNEL_ID}; aborting before any upload")
    if handle not in KNOWN_HANDLES:
        print(f"[BATCH] note: current handle {handle!r} not in known set; channel ID match is authoritative")
    print(f"[BATCH] channel verified by ID: {channel_id} (current handle {handle})")
    results = []
    published = set(load(DATA / "state.json").get("published_ids", []))
    ledger = load(DATA / "private_batch.json") if (DATA / "private_batch.json").exists() else {"batches": []}
    recorded_ids = {v.get("question_id") for b in ledger.get("batches", []) for v in b.get("videos", [])}
    seen_in_manifest = set()
    for v in manifest["videos"]:
        qid = v.get("question_id")
        if qid in seen_in_manifest:
            print(f"[BATCH] duplicate question in manifest, skipping {qid}")
            continue
        seen_in_manifest.add(qid)
        if qid in published or qid in recorded_ids:
            print(f"[BATCH] already recorded, skipping {qid}")
            continue
        # Preserve the exact per-video metadata supplied in the Drive manifest.
        if not isinstance(v.get("title"), str) or not v["title"].strip() or len(v["title"]) > 100:
            raise RuntimeError(f"invalid manifest title for {qid}")
        if not isinstance(v.get("description"), str) or not v["description"].strip() or len(v["description"]) > 5000:
            raise RuntimeError(f"invalid manifest description for {qid}")
        if not isinstance(v.get("file"), str) or Path(v["file"]).name != v["file"] or not v["file"].lower().endswith(".mp4"):
            raise RuntimeError(f"unsafe manifest file for {qid}")
        path = bdir / v["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != v["sha256"]:
            raise RuntimeError(f"sha256 mismatch for {v['file']}; refusing upload")
        vid = upload_short(str(path), v["title"], v["description"],
                           tags=v["tags"], pinned_comment=PINNED, privacy="private")
        chk = yt.videos().list(part="status,snippet", id=vid).execute()["items"][0]
        privacy = chk["status"].get("privacyStatus")
        if privacy != "private" or chk["snippet"]["channelId"] != channel_id:
            raise RuntimeError(f"Post-upload verification failed for {vid}: privacy={privacy}")
        results.append({
            "question_id": v["question_id"], "yt_id": vid, "title": v["title"],
            "privacy": privacy, "watch_url": f"https://www.youtube.com/watch?v={vid}",
            "scheduled": False,
        })
        print(f"[BATCH] PRIVATE upload verified: {v['question_id']} -> {vid}")
        checkpoint = {
            "batch_id": manifest.get("batch_id"),
            "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "channel_id": channel_id, "videos": results,
        }
        if manifest.get("replaces_batch_id"):
            checkpoint["replaces_batch_id"] = manifest["replaces_batch_id"]
        save(bdir / "upload_results.json", checkpoint)
    up = {
        "batch_id": manifest.get("batch_id"),
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "channel_id": channel_id,
        "videos": results,
    }
    if manifest.get("replaces_batch_id"):
        up["replaces_batch_id"] = manifest["replaces_batch_id"]
    save(bdir / "upload_results.json", up)
    ledger_path = DATA / "private_batch.json"
    ledger = load(ledger_path) if ledger_path.exists() else {"batches": []}
    ledger["batches"].append({
        "batch_id": manifest.get("batch_id"),
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "destination_channel_id": EXPECTED_CHANNEL_ID,
        "note": "Private drafts pending owner review; scheduling dates decided later. Description day numbers are provisional.",
        "videos": results,
    })
    save(ledger_path, ledger)
    state_path = DATA / "state.json"
    state = load(state_path)
    ids = state.setdefault("published_ids", [])
    for r in results:
        if r["question_id"] not in ids:
            ids.append(r["question_id"])
    save(state_path, state)
    print(json.dumps({"private_uploads": [r["watch_url"] for r in results]}, indent=2))


def mode_reconcile(batch_dir):
    """Idempotently merge upload results into data/ (run after `git reset --hard origin/main`).

    Union published_ids (never removes), append the ledger batch only if its
    batch_id is absent, so retry loops can re-run this safely. No slot, day,
    index or counter fields are touched.
    """
    res = load(Path(batch_dir) / "upload_results.json")
    ledger_path = DATA / "private_batch.json"
    ledger = load(ledger_path) if ledger_path.exists() else {"batches": []}
    if not any(b.get("batch_id") == res["batch_id"] for b in ledger["batches"]):
        entry = {
            "batch_id": res["batch_id"],
            "uploaded_at": res["uploaded_at"],
            "destination_channel_id": EXPECTED_CHANNEL_ID,
            "channel_id": res["channel_id"],
            "note": "Private drafts pending owner review; scheduling dates decided later. No day/date claims in metadata.",
            "videos": res["videos"],
        }
        if res.get("replaces_batch_id"):
            entry["replaces_batch_id"] = res["replaces_batch_id"]
            entry["note"] = "Corrected re-render replacing batch " + str(res["replaces_batch_id"]) + " (source-label fix). Originals remain private; deletion only on owner approval."
        ledger["batches"].append(entry)
        save(ledger_path, ledger)
    else:
        entry = next(b for b in ledger["batches"] if b.get("batch_id") == res["batch_id"])
        known = {v["question_id"]: v["yt_id"] for v in entry["videos"]}
        for video in res["videos"]:
            if video["question_id"] in known:
                if known[video["question_id"]] != video["yt_id"]:
                    raise RuntimeError("Conflicting uploaded video identity")
            else:
                entry["videos"].append(video)
        save(ledger_path, ledger)
    state_path = DATA / "state.json"
    state = load(state_path)
    ids = state.setdefault("published_ids", [])
    for r in res["videos"]:
        if r["question_id"] not in ids:
            ids.append(r["question_id"])
    save(state_path, state)
    print(f"[BATCH] reconciled {len(res['videos'])} private uploads into state + ledger")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["render", "upload", "reconcile"])
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--ids", default="", help="Comma-separated explicit question IDs to render (correction re-render; bypasses published filter)")
    ap.add_argument("--batch-dir", default=str(OUT))
    args = ap.parse_args()
    if args.mode == "render":
        ids = [x.strip() for x in args.ids.split(",") if x.strip()] or None
        mode_render(args.count, ids=ids)
    elif args.mode == "upload":
        mode_upload(args.batch_dir)
    else:
        mode_reconcile(args.batch_dir)


if __name__ == "__main__":
    main()
