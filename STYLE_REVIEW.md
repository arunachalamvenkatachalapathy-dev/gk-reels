# Studio arena production rollout

The owner chose Studio arena on October 8, 2026: "This works, use this for both."

The production renderer uses navy/gold studio glow, moving background, staged options, speech-led real three-second ring, green reveal, separate checked explanation/memory cue and follow promise. Existing background track is mixed quietly below speech. Fonts are bundled. Voices and environment-only key lookup remain unchanged. No schedule, credentials or upload code changes.

Missing source-checked explanations, long speech, silent speech failure and unsafe layout refuse to render. No made-up explanation or silent old-style fallback.

Two upcoming questions per repository are checked for Friday October 9 morning and afternoon: EN q0075/q0077 (IMF SDRs, Prakash Padukone), HI q0062/q0063 (Delhi Chalo, Chauri Chaura). Source URLs are beside each checked editorial entry in render.py. Local renders and speech-duration checks passed; actual production voice-service timing can differ and remains guarded. After this buffer, remaining unreviewed entries require source checking before scheduled publication can continue.

Run `python -m unittest discover -s tests -v`. For local review, call render_video directly, never the upload pipeline. Existing publication safeguard tests are retained.
