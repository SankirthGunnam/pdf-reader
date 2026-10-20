"""Offline PDF -> Docling JSON + Markdown. Usage:
    HF_HUB_OFFLINE=1 python scripts/convert.py datasheet.pdf
Models are loaded ONLY from models/docling (no network call)."""
import os, sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parents[1]

def main(pdf: str) -> None:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    opts = PdfPipelineOptions(artifacts_path=ROOT / "models" / "docling")
    opts.do_ocr = True                 # scanned datasheets; RapidOCR is bundled
    opts.do_table_structure = True     # TableFormer: register/truth tables
    opts.generate_picture_images = True  # crops for pin/block diagrams (stage-2 VLM)
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})

    doc = conv.convert(pdf).document
    out = ROOT / "output" / Path(pdf).stem
    out.mkdir(parents=True, exist_ok=True)
    doc.save_as_json(out / "docling.json")
    doc.save_as_markdown(out / "docling.md")
    print(f"Wrote {out}/docling.json + docling.md")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: convert.py <file.pdf>")
    main(sys.argv[1])
