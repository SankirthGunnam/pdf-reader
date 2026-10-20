"""Run ONCE on an internet PC. Downloads Docling model artifacts into
models/docling/ in Docling's native layout (no HF-cache symlinks, which
break on Windows + Git LFS). Then: git add models && git lfs push.

Equivalent CLI:  docling-tools models download -o models/docling
This script does the same via the Python API and prints total size so
you can check it against your Git-LFS quota (GitHub free: 2 GB/file).
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "models" / "docling"

def main() -> None:
    from docling.utils.model_downloader import download_models
    # Standard pipeline only: layout (docling-layout-heron) + TableFormer
    # + picture classification. Add with_vlm=True later if you want
    # Granite-Docling for block/pin diagrams (+~1 GB, separate download).
    download_models(output_dir=OUT, with_layout=True, with_tableformer=True,
                    with_code_formula=False, with_picture_classifier=True,
                    with_rapidocr=True, with_easyocr=False)
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"\nDownloaded to {OUT}  total={total/1e9:.2f} GB")
    print("Next: git lfs install; git add .gitattributes models; git commit; git push")

if __name__ == "__main__":
    main()
