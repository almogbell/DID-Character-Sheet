from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

snapshot = ROOT / "android" / "phase8" / "DidCharacterSnapshot.kt"
text = snapshot.read_text(encoding="utf-8")
specialized = '''private fun JSONArray.mapObjects(transform: (JSONObject) -> ImprovementSnapshot): List<ImprovementSnapshot> =
    (0 until length()).mapNotNull { index -> optJSONObject(index)?.let(transform) }

'''
if text.count(specialized) != 1:
    raise SystemExit(f"Expected one specialized mapObjects overload, found {text.count(specialized)}")
text = text.replace(specialized, "", 1)
snapshot.write_text(text, encoding="utf-8")

bridge = ROOT / "android" / "phase8" / "Phase8ActivityBridge.kt"
bridge_text = bridge.read_text(encoding="utf-8")n