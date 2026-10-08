"""Read-only: count unpublished source-checked questions in the queue."""
import json, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = "en"
qs = json.load(open(os.path.join(BASE, "data", f"questions_{LANG}.json"), encoding="utf-8"))
rv = json.load(open(os.path.join(BASE, "data", f"reviewed_{LANG}.json"), encoding="utf-8"))
st = json.load(open(os.path.join(BASE, "data", "state.json"), encoding="utf-8"))
pub = set(st.get("published_ids", []))
ids = [q["id"] for q in qs if q["id"] in rv and q["id"] not in pub]
print(f"{LANG}: reviewed={len(rv)} bank={len(qs)} buffer_unpublished_checked={len(ids)} -> {ids}")
