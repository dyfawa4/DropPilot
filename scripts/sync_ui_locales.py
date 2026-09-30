"""Validate edited offline catalogs and update the browser bundle, without network access."""
import json
from pathlib import Path

base = Path(__file__).resolve().parents[1] / "web"
packs = json.loads((base / "locales.json").read_text(encoding="utf-8"))
english_keys = set(packs["English"]["messages"])
for language, pack in packs.items():
    if language != "简体中文" and set(pack["messages"]) != english_keys:
        raise ValueError(f"Incomplete catalog: {language}")
    if not all(isinstance(value, str) and value.strip() for value in pack["messages"].values()):
        raise ValueError(f"Empty translation: {language}")
(base / "locales.js").write_text("globalThis.DropPilotLocales=" + json.dumps(
    packs, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
print(f"Synced {len(packs)} offline language packs.")
