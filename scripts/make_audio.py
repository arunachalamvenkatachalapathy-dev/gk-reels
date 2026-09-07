"""
Procedurally generates the two audio assets used in every video, using
ffmpeg's built-in synth sources. No downloads, no API calls, no licensing
concerns -- fully self-contained so a network hiccup can never break a
scheduled render.

Run once (assets are cached to disk and reused across all future renders):
    python3 scripts/make_audio.py
"""
import subprocess
import os

ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

TENSION_PATH = os.path.join(ASSET_DIR, "tension_bed.mp3")
DING_PATH = os.path.join(ASSET_DIR, "reveal_ding.mp3")


def run(cmd):
    subprocess.run(cmd, check=True)


def make_tension_bed():
    """
    10s rising-tension bed: a low pulsing sine (heartbeat-like amplitude
    modulation) layered under a slowly rising pad tone. Mirrors the
    'Jeopardy DNA' structure -- pulsing bass + rising pad, no melody.
    """
    if os.path.exists(TENSION_PATH):
        return
    filter_complex = (
        # pulsing low bass, amplitude modulated to feel like a heartbeat/clock
        "sine=frequency=110:duration=10[bass];"
        "[bass]tremolo=f=2.2:d=0.6[bass_puls];"
        # slowly rising pad from 220Hz to 340Hz over 10s
        "aevalsrc=0.18*sin(2*PI*(220+12*t)*t):duration=10[pad];"
        # soft tick every 0.5s for clock-like urgency
        "sine=frequency=1800:duration=10[tickraw];"
        "[tickraw]tremolo=f=2:d=0.97,volume=0.05[tick];"
        "[bass_puls][pad]amix=inputs=2:weights=0.5 0.35[bed1];"
        "[bed1][tick]amix=inputs=2:weights=1 1[bed];"
        "[bed]afade=t=in:st=0:d=0.3,afade=t=out:st=9.5:d=0.5[out]"
    )
    run([
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", "10",
        "-c:a", "libmp3lame", "-q:a", "4",
        TENSION_PATH,
    ])


def make_reveal_ding():
    """Bright two-tone chime for the answer reveal (~1s)."""
    if os.path.exists(DING_PATH):
        return
    filter_complex = (
        "sine=frequency=880:duration=0.9[a];"
        "sine=frequency=1318:duration=0.9[b];"
        "[a]afade=t=out:st=0.1:d=0.8,volume=0.5[a2];"
        "[b]afade=t=out:st=0.15:d=0.75,volume=0.4[b2];"
        "[a2][b2]amix=inputs=2:weights=1 1[out]"
    )
    run([
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", "1",
        "-c:a", "libmp3lame", "-q:a", "4",
        DING_PATH,
    ])


if __name__ == "__main__":
    make_tension_bed()
    make_reveal_ding()
    print(f"Audio assets ready:\n  {TENSION_PATH}\n  {DING_PATH}")
