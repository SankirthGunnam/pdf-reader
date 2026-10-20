"""Usage: python scripts/extract_rf.py output/<chip>/docling.json"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rf_reader.extract import extract

src = Path(sys.argv[1])
cfg = extract(json.loads(src.read_text()))
out = src.parent / "rf_config.json"
out.write_text(cfg.model_dump_json(indent=2))
print(f"{out}: {len(cfg.registers)} register rows, {len(cfg.rf_paths)} RF paths — HUMAN REVIEW REQUIRED")
