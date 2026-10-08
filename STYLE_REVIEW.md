# GK Shorts style preview (approval required)

Main, scheduling, credentials and upload scripts are unchanged. This branch is not approved for merge or publishing.

- Navy/gold, one logo, large central question and A/B/C/D options.
- Real 3, 2, 1 seconds after the question finishes; green answer reveal, then one checked explanation and a readable follow line.
- Critical content stays inside x=72..896 and y=220..1460 at 1080x1920. The right rail and lower Shorts captions are reserved.
- Explanation, source and topic are editorial data, not model-generated claims. Only reviewed questions can render. Missing explanation, silent voice failure, excess duration and overflow fail closed.
- Preview voices use existing Edge TTS fallback. Existing Fish voice models and environment-only key lookup are preserved.
- English preview: q0075, Paper Gold. IMF source: https://www.imf.org/en/topics/special-drawing-right. Historical nickname: https://www.imf.org/external/pubs/ft/silent/index.htm.
- Hindi preview: q0061, Servants of India Society. BMC source: https://www.mcgm.gov.in/irj/go/km/docs/documents/D%20Ward/Heritage-Sites/72_Legacy%20of%20D%20Ward_Article_Servants%20of%20India%20Society.pdf.

## Before rollout

Owner approval of the sample is required. Supply source-checked explanations and short display wording for upcoming queue entries before enabling this renderer on main. The old bank is not automatically certified: q0073 in English gives the wrong current LPSC location, and needs correction before use (ISRO: https://www.isro.gov.in/ISRO_EN/LPSC.html).

Run `python -m unittest discover -s tests -v`. Local previews call `render_video` directly, never `run_pipeline.py`, to avoid uploads and state changes.
