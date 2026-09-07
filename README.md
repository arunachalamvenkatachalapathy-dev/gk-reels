# GK Reels — automated SSC General Knowledge quiz pipeline

Publishes 4 quiz videos/day to YouTube Shorts and Instagram Reels, fully
automated via GitHub Actions. Zero image-generation API dependency — every
frame is rendered from local HTML/CSS, every sound is synthesized locally
with ffmpeg. The only external calls are the two publishing APIs.

## How a video is made

- **15 seconds total.** Slide 1 (question + 4 options) for 10s, slide 2
  (same layout, correct option highlighted) for 5s.
- **Full-bleed white background**, one rotating accent color per video
  (`data/state.json` → `palette`).
- **Audio**: a procedurally generated tension bed (pulsing bass + rising
  pad, 0–10s) and a two-tone reveal ding at the 10s mark. Generated once
  by `scripts/make_audio.py` and cached in `assets/` — no network call at
  render time.
- **387 questions** pre-extracted from the Disha GS MCQ book
  (`data/questions_en.json`), filtered down from ~2,150 raw MCQs to only
  the ones simple enough to read in 10 seconds (match-the-following,
  assertion-reason, and "arrange in sequence" question types were
  excluded — they don't work in this format).
- At 4/day, 387 questions ≈ **97 days** before the pool repeats.

## One-time setup

### 1. Push this repo to GitHub

```bash
cd gk-reels
git init
git add .
git commit -m "Initial GK Reels pipeline"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

### 2. YouTube — get OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project.
2. Enable **YouTube Data API v3**.
3. Create OAuth 2.0 credentials (type: Desktop app). Note the **Client ID** and **Client Secret**.
4. Get a one-time refresh token (run locally, once):
   ```bash
   pip install google-auth-oauthlib
   python3 -c "
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_config(
       {'installed': {
           'client_id': 'YOUR_CLIENT_ID',
           'client_secret': 'YOUR_CLIENT_SECRET',
           'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
           'token_uri': 'https://oauth2.googleapis.com/token',
       }},
       scopes=['https://www.googleapis.com/auth/youtube.upload'],
   )
   creds = flow.run_local_server(port=0)
   print('REFRESH TOKEN:', creds.refresh_token)
   "
   ```
5. This opens a browser, you approve access on the channel you want to
   publish to, and it prints a refresh token — save it.

### 3. Instagram — get Graph API credentials

1. Your Instagram account must be a **Business or Creator account**,
   connected to a **Facebook Page**.
2. Go to [Meta for Developers](https://developers.facebook.com/) → create an app → add the **Instagram Graph API** product.
3. Generate a **long-lived Page access token** with `instagram_content_publish`,
   `pages_show_list`, and `instagram_basic` permissions (via Graph API Explorer,
   then exchange for long-lived via the `/oauth/access_token` endpoint).
4. Get your **Instagram Business Account ID** via:
   `GET /me/accounts` → `GET /{page_id}?fields=instagram_business_account`

### 4. Add repo secrets

GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `YT_CLIENT_ID` | from step 2 |
| `YT_CLIENT_SECRET` | from step 2 |
| `YT_REFRESH_TOKEN` | from step 2 |
| `IG_ACCESS_TOKEN` | from step 3 |
| `IG_USER_ID` | from step 3 |

`GITHUB_TOKEN` is provided automatically by Actions — you don't set it.

### 5. Done

The workflow (`.github/workflows/publish.yml`) runs automatically at
08:00, 13:00, 18:00, and 21:00 IST every day. You can also trigger a run
manually any time from the **Actions** tab → "Publish GK Reels" → **Run workflow**
— useful for testing before the first scheduled run.

## How Instagram publishing actually works here

Instagram's API needs a **public URL** for the video, not a file upload.
Rather than paying for a CDN, each run uploads the rendered mp4 as a
**GitHub Release asset** on this same repo (free, instant), grabs its
public download URL, and hands that to Instagram. The release also
doubles as a free backup archive of every video you've published.

## Testing locally before your first scheduled run

```bash
pip install -r requirements.txt
python -m playwright install chromium
python scripts/make_audio.py        # generates assets/*.mp3 once
python scripts/render.py            # renders one sample video: output_test.mp4
```

Open `output_test.mp4` to sanity-check the design before wiring up the
upload credentials.

To test the full pipeline (render + upload) without waiting for the
schedule, set the secrets as local environment variables and run:

```bash
export YT_CLIENT_ID=... YT_CLIENT_SECRET=... YT_REFRESH_TOKEN=...
export IG_ACCESS_TOKEN=... IG_USER_ID=...
export GITHUB_TOKEN=... GITHUB_REPOSITORY=you/gk-reels
python scripts/run_pipeline.py
```

If YouTube or Instagram secrets are missing, that platform is skipped
with a warning rather than crashing the run — so you can wire up and test
each platform independently.

## Changing the schedule or volume

- **Videos per day**: edit `videos_per_day` in `data/state.json`.
- **Posting times**: edit the four `cron:` lines in
  `.github/workflows/publish.yml` (all times in UTC; IST = UTC + 5:30).
- **Accent colors**: edit the `palette` array in `data/state.json`.

## Adding more questions later

`data/questions_en.json` is a flat list of
`{id, question, options, correct_index}`. Append more in the same shape
and the pipeline will pick them up automatically — no code changes needed.
A Hindi version can live alongside as `data/questions_hi.json` with a
second workflow/state file once you're ready to add that channel.
