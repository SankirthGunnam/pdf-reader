"""Extract Docling's embedded base64 pictures to images/, link them from
docling.json (+ docling.md), and upscale by re-cropping the source PDF.

Usage:
  python scripts/postprocess.py output/<chip>/docling.json [--pdf samples/<chip>.pdf] [--scale 3]

Backs the original up as docling_raw.json. Safe to re-run (idempotent).
For a fresh conversion, convert.py already runs this automatically."""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rf_reader.postprocess import postprocess

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("docling_json")
    ap.add_argument("--pdf", help="source PDF for hi-res re-crop (recommended)")
    ap.add_argument("--scale", type=float, default=3.0, help="3 = ~216 dpi re-crop / 3x upscale")
    ap.add_argument("--min-size", type=int, default=48, help="max dimension below which an image is flagged decorative (logos)")
    a = ap.parse_args()
    r = postprocess(Path(a.docling_json), Path(a.pdf) if a.pdf else None, a.scale, a.min_size)
    kept = [e for e in r["images"] if not e["likely_decorative"]]
    print(f"{len(r['images'])} images -> {r['out_dir']}/images/ "
          f"({len(kept)} figures, {len(r['images']) - len(kept)} decorative/logo)")
    for e in r["images"]:
        print(f"  p{e['page']:02d} {e['file']:60s} {e['method']:18s} {e['caption'][:60]}")
