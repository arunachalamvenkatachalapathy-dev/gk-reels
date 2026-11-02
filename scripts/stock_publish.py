"""English GK Drive-stock publisher.

Publishes the next cleared video straight from the owner's private Drive stock
(his approved plan, 2026-10-31): read-only keyless service account, one video
per due IST slot, with each video's own SEO from its ZIP manifest. Fails
loudly; reserves durable state before any external upload.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IST = timezone(timedelta(hours=5, minutes=30))
ZIP_NAME = re.compile(r"^GK_EN_private_([A-Z]\d+)_\d+\.zip$")
QID = re.compile(r"^q(\d{4})$")
DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]


def load(p):
    return json.loads(Path(p).read_text())


def save(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")


def persist(state_dir, state, config, note):
    save(state_dir / config["state_file"], state)
    subprocess.run(["git", "-C", str(state_dir), "add", config["state_file"]],
                   check=True, stdout=subprocess.DEVNULL)
    dirty = subprocess.run(["git", "-C", str(state_dir), "diff", "--cached", "--quiet"]).returncode != 0
    if not dirty:
        return
    for args in (
        ("commit", "-m", note),
        ("push", "origin", "HEAD:" + config["state_branch"]),
    ):
        subprocess.run(["git", "-C", str(state_dir), *args], check=True, stdout=subprocess.DEVNULL)


def parse_stock_name(name):
    m = ZIP_NAME.match(name)
    return m.group(1) if m else None


def select_slot(now, config, state):
    local = now.astimezone(IST)
    today = local.date().isoformat()
    if today <= config.get("studio_slots_until", ""):
        return None  # owner-scheduled Studio uploads hold all slots until that date
    for name, clock in config["slots"].items():
        h, m = map(int, clock.split(":"))
        opening = local.replace(hour=h, minute=m, second=0, microsecond=0)
        lag = (local - opening).total_seconds()
        key = f"{today}:{name}"
        if 0 <= lag < config["window_minutes"] * 60 and state.get("slots", {}).get(key, {}).get("status") != "published":
            return {"key": key, "slot": name, "opens_at": opening.isoformat(), "drift_seconds": round(lag)}
    return None


def select_run_slot(now, config, state, mode):
    if mode in ("facebook-retry", "instagram-retry"):
        return None
    if mode == "scheduled":
        return select_slot(now, config, state)
    local = now.astimezone(IST)
    return {"key": f"manual:{local.date()}", "slot": "manual", "opens_at": now.isoformat(), "drift_seconds": 0}


def dispatch_mode(event, mode=None):
    if event != "workflow_dispatch":
        return "scheduled"
    mode = mode or "manual"
    if mode not in ("manual", "scheduled", "facebook-retry", "instagram-retry"):
        raise ValueError("Invalid dispatch mode")
    return mode


def validate_video_entry(v, config):
    qid = v.get("question_id", "")
    m = QID.match(qid)
    if not m:
        raise ValueError("Invalid question_id in stock manifest")
    if int(m.group(1)) <= int(config.get("skip_qid_range_end", 0)):
        raise ValueError("already-published bank range")
    title = v.get("title", "")
    if not title.strip() or len(title) > 100:
        raise ValueError("Invalid title length")
    if len(v.get("description", "")) > 5000:
        raise ValueError("Description too long")
    if not (0 < float(v.get("duration", 0)) <= 35.0):
        raise ValueError("Stock video exceeds the 35 s format cap")
    if not v.get("file") or not v.get("sha256"):
        raise ValueError("Manifest missing file or sha256")
    return qid


def drive_client():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw = os.environ.get("GDRIVE_SA_KEY_JSON", "").strip()
    if not raw:
        raise RuntimeError("Missing repository secret: GDRIVE_SA_KEY_JSON")
    creds = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=DRIVE_SCOPE)
    return build("drive", "v3", credentials=creds)


def list_stock(drive, folder_id):
    items, token = [], None
    while True:
        resp = (
            drive.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false and name contains 'GK_EN_private_'",
                fields="nextPageToken, files(id,name,md5Checksum,size)",
                pageSize=1000,
                pageToken=token,
                orderBy="name",
            )
            .execute()
        )
        items.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return items


def download_zip(drive, file_id, dest):
    from googleapiclient.http import MediaIoBaseDownload

    request = drive.files().get_media(fileId=file_id)
    with open(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def recent_titles(youtube, scan):
    channels = youtube.channels().list(part="contentDetails", mine=True).execute().get("items", [])
    if len(channels) != 1:
        raise RuntimeError("OAuth identity mismatch while reading uploads playlist")
    uploads = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    titles, token = set(), None
    while len(titles) < scan:
        resp = youtube.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50, pageToken=token).execute()
        for item in resp.get("items", []):
            titles.add(item["snippet"].get("title", ""))
        token = resp.get("nextPageToken")
        if not token or len(resp.get("items", [])) == 0:
            break
    return titles


def zip_candidates(stock, config):
    out = []
    for item in sorted(stock, key=lambda f: f["name"]):
        batch = parse_stock_name(item["name"])
        if batch:
            out.append(item)
    return out



def retry_facebook_failures(sd, state, config, drive, work):
    # Re-attempt Facebook for slots with a confirmed YouTube receipt but a failed
    # Facebook destination. Never picks a new video; re-fetches the exact reserved
    # asset from Drive, re-verifies its hash, and adopts an existing reel first.
    if not (config.get("facebook_enabled") or config.get("instagram_enabled")):
        return
    today = datetime.now(IST).date().isoformat()
    pending = []
    for k, s in sorted(state.get("slots", {}).items()):
        if s.get("status") != "published":
            continue
        errs = s.get("destination_errors", {})
        if "facebook" in errs or "instagram" in errs:
            pending.append((k, s))
        elif config.get("instagram_enabled") and today in k and "instagram" not in s.get("destinations", {}):
            s.setdefault("destination_errors", {})["instagram"] = "backfill: instagram enabled after publish"
            pending.append((k, s))
    if not pending:
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from upload_facebook import publish_facebook_reel, find_recent_reel
    stock = list_stock(drive, config["drive_folder_id"])
    zips = zip_candidates(stock, config)
    for key, slot in pending[:2]:
        qid = slot.get("question_id")
        found = None
        for item in zips:
            zip_path = work / item["name"]
            if not zip_path.is_file():
                download_zip(drive, item["id"], zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                if manifest.get("destination_channel_id") != config["channel_id"]:
                    continue
                for v in manifest.get("videos", []):
                    if v.get("question_id") == qid:
                        found = (zf.read(v["file"]), v)
                        break
            if found:
                break
        if not found:
            raise RuntimeError(f"Facebook retry for {key}: stock asset {qid} not found in Drive")
        payload, v = found
        if hashlib.sha256(payload).hexdigest() != v["sha256"]:
            raise ValueError(f"Stock video hash mismatch for {qid}")
        errors = slot.get("destination_errors", {})
        destinations = slot.setdefault("destinations", {})
        video_path = None
        if config.get("facebook_enabled") and "facebook" in errors:
            existing = find_recent_reel(v["title"], slot.get("published_at"))
            if existing:
                fb_id = existing
                print(f"Facebook retry adopted existing reel for {qid}: {fb_id}")
            else:
                video_path = work / v["file"]
                video_path.write_bytes(payload)
                fb_id = publish_facebook_reel(str(video_path), v["title"], v["description"])
                if not fb_id:
                    raise RuntimeError("Facebook destination returned no receipt")
            destinations["facebook"] = fb_id
            errors.pop("facebook", None)
            persist(sd, state, config, f"Record retried EN stock Facebook receipt for {qid}")
            print(f"Facebook retry published {qid}: {fb_id}")
        if config.get("instagram_enabled") and "instagram" in errors:
            from upload_instagram import upload_reel, find_recent_reel_by_caption
            existing = find_recent_reel_by_caption(v["title"], slot.get("published_at"))
            if existing:
                destinations["instagram"] = existing
                print(f"Instagram retry adopted existing reel for {qid}: {existing['id']}")
            else:
                if video_path is None:
                    video_path = work / v["file"]
                    video_path.write_bytes(payload)
                media_id, permalink = upload_reel(str(video_path), build_ig_caption(v), "ig-host-" + key.replace(":", "-") + "-" + qid, v["file"])
                destinations["instagram"] = {"id": str(media_id), "url": permalink}
            errors.pop("instagram", None)
            persist(sd, state, config, f"Record retried EN stock Instagram receipt for {qid}")
            print(f"Instagram retry published {qid}: {destinations['instagram']}")

def build_ig_caption(v):
    import ast
    title = v.get("title", "").strip()
    tags = v.get("tags") or []
    if isinstance(tags, str):
        try:
            parsed = ast.literal_eval(tags)
            tags = parsed if isinstance(parsed, list) else [tags]
        except Exception:
            tags = [t.strip() for t in tags.split(",") if t.strip()]
    hashtags = ["#" + re.sub(r"[^0-9A-Za-z]+", "", str(t)) for t in tags]
    hashtags = [h for h in hashtags if len(h) > 1][:15]
    return (title + "\n\n" + " ".join(hashtags)).strip()[:2100]


def main():
    config = load(ROOT / "data/stock_config.json")
    sd = Path(os.environ["PUBLICATION_STATE_DIR"])
    state_path = sd / config["state_file"]
    state = load(state_path) if state_path.is_file() else {"slots": {}, "published_ids": [], "checks": [], "skipped_external": []}
    now = datetime.now(timezone.utc)
    mode = dispatch_mode(os.getenv("GITHUB_EVENT_NAME"), os.getenv("DISPATCH_MODE"))
    slot = select_run_slot(now, config, state, mode)
    state.setdefault("checks", []).append(
        {"at": now.isoformat(), "run_id": os.getenv("GITHUB_RUN_ID"), "event": os.getenv("GITHUB_EVENT_NAME"), "slot": slot, "mode": mode}
    )
    state["checks"] = state["checks"][-500:]
    if config.get("facebook_enabled") or config.get("instagram_enabled"):
        retry_drive = drive_client()
        retry_work = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "en-stock-retry"
        retry_work.mkdir(parents=True, exist_ok=True)
        retry_facebook_failures(sd, state, config, retry_drive, retry_work)
    if not slot:
        persist(sd, state, config, "Record EN stock slot check")
        print("No active IST slot")
        return
    previous = state.setdefault("slots", {}).get(slot["key"], {})
    if previous.get("status") in ("pending", "ambiguous"):
        persist(sd, state, config, "Record blocked pending EN stock publication")
        raise RuntimeError("Reconcile pending receipt before retry")

    drive = drive_client()
    stock = list_stock(drive, config["drive_folder_id"])
    zips = zip_candidates(stock, config)
    if not zips:
        persist(sd, state, config, "Record EN stock slot with no stock ZIPs")
        print("No stock ZIPs")
        return

    sys.path.insert(0, str(ROOT / "scripts"))
    from upload_youtube import get_youtube_client, upload_short

    for name in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not os.getenv(name):
            raise RuntimeError("Missing repository secret: " + name)
    youtube = get_youtube_client()
    items = youtube.channels().list(part="id", mine=True).execute().get("items", [])
    if [c.get("id") for c in items] != [config["channel_id"]]:
        raise RuntimeError("OAuth identity mismatch: refusing to publish to a non-English channel")
    known_titles = recent_titles(youtube, int(config.get("recent_upload_scan", 200)))

    published = set(state.get("published_ids", []))
    published.update(x.get("question_id") for x in state.get("slots", {}).values() if x.get("status") in ("pending", "ambiguous", "published"))
    held = set(config.get("held_ids", []))

    work = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "en-stock"
    work.mkdir(parents=True, exist_ok=True)
    chosen = None
    for item in zips:
        zip_path = work / item["name"]
        if not zip_path.is_file():
            download_zip(drive, item["id"], zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            if manifest.get("destination_channel_id") != config["channel_id"]:
                raise ValueError("Stock manifest targets a different channel")
            for v in manifest.get("videos", []):
                try:
                    qid = validate_video_entry(v, config)
                except ValueError:
                    continue
                if qid in published or qid in held:
                    continue
                if v["title"] in known_titles:
                    state.setdefault("skipped_external", []).append({"question_id": qid, "reason": "title already on channel", "at": now.isoformat()})
                    continue
                payload = zf.read(v["file"])
                if hashlib.sha256(payload).hexdigest() != v["sha256"]:
                    raise ValueError(f"Stock video hash mismatch for {qid}")
                chosen = (qid, v, payload)
                break
        if chosen:
            break
    if not chosen:
        persist(sd, state, config, "Record EN stock slot with all candidates skipped")
        print("No eligible stock candidate")
        return

    qid, v, payload = chosen
    video_path = work / v["file"]
    video_path.write_bytes(payload)
    state["slots"][slot["key"]] = dict(slot, status="pending", question_id=qid, sha256=v["sha256"], run_id=os.getenv("GITHUB_RUN_ID"))
    persist(sd, state, config, "Reserve exact EN stock asset before external upload")
    try:
        receipt = upload_short(str(video_path), v["title"], v["description"], tags=v.get("tags"), privacy="public")
    except Exception:
        state["slots"][slot["key"]]["status"] = "ambiguous"
        persist(sd, state, config, "Hold uncertain EN stock upload for reconciliation")
        raise
    destinations = {"youtube": receipt}
    state["slots"][slot["key"]].update(status="published", youtube_id=receipt, destinations=destinations, published_at=datetime.now(timezone.utc).isoformat())
    state.setdefault("published_ids", []).append(qid)
    persist(sd, state, config, "Record confirmed EN stock YouTube receipt")
    if config.get("facebook_enabled", False):
        try:
            from upload_facebook import publish_facebook_reel
            fb_id = publish_facebook_reel(str(video_path), v["title"], v["description"])
            if not fb_id:
                raise RuntimeError("Facebook destination returned no receipt")
            destinations["facebook"] = fb_id
            state["slots"][slot["key"]]["destinations"] = destinations
            persist(sd, state, config, "Record confirmed EN stock Facebook receipt")
        except Exception as exc:
            state["slots"][slot["key"]].setdefault("destination_errors", {})["facebook"] = str(exc)[:200]
            persist(sd, state, config, "Record EN stock Facebook destination failure")
            raise
    if config.get("instagram_enabled", False):
        try:
            from upload_instagram import upload_reel
            media_id, permalink = upload_reel(str(video_path), build_ig_caption(v), "ig-host-" + slot["key"].replace(":", "-") + "-" + qid, v["file"])
            destinations["instagram"] = {"id": str(media_id), "url": permalink}
            state["slots"][slot["key"]]["destinations"] = destinations
            persist(sd, state, config, "Record confirmed EN stock Instagram receipt")
        except Exception as exc:
            state["slots"][slot["key"]].setdefault("destination_errors", {})["instagram"] = str(exc)[:200]
            persist(sd, state, config, "Record EN stock Instagram destination failure")
            raise
    else:
        print("Instagram disabled for this run; YouTube/Facebook only.")
    print(json.dumps({"question_id": qid, "youtube_id": receipt, "destinations": destinations, "slot": slot["key"], "drift_seconds": slot["drift_seconds"]}))


if __name__ == "__main__":
    main()
