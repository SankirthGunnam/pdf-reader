"""Offline PDF -> Docling JSON + Markdown. Usage:
    HF_HUB_OFFLINE=1 python scripts/convert.py datasheet.pdf
Models are loaded ONLY from models/docling (no network call)."""
import os, sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parents[1]

def main(pdf: str, do_ocr: bool = True, post: bool = True, scale: float = 3.0) -> None:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    opts = PdfPipelineOptions(artifacts_path=ROOT / "models" / "docling")
    opts.do_ocr = do_ocr               # --no-ocr: much faster for native-text PDFs
    opts.do_table_structure = True     # TableFormer: register/truth tables
    opts.generate_picture_images = True  # crops for pin/block diagrams (for your local LLM)
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})

    doc = conv.convert(pdf).document
    out = ROOT / "output" / Path(pdf).stem
    out.mkdir(parents=True, exist_ok=True)
    doc.save_as_json(out / "docling.json")
    doc.save_as_markdown(out / "docling.md")
    print(f"Wrote {out}/docling.json + docling.md")
    if post:  # extract base64 pictures -> images/, link in JSON/MD, hi-res re-crop
        sys.path.insert(0, str(ROOT / "src"))
        from rf_reader.postprocess import postprocess
        r = postprocess(out / "docling.json", Path(pdf), scale=scale)
        print(f"Post-processed: {len(r['images'])} images -> {out}/images/ "
              f"(docling.json links only, no base64 kept)")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--no-ocr", action="store_true", help="faster for native-text PDFs")
    ap.add_argument("--no-postprocess", action="store_true", help="keep base64 embedded in docling.json")
    ap.add_argument("--scale", type=float, default=3.0, help="image re-crop scale (3 = ~216 dpi)")
    a = ap.parse_args()
    main(a.pdf, do_ocr=not a.no_ocr, post=not a.no_postprocess, scale=a.scale)
