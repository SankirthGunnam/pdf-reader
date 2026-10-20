# RF Frontend PDF Reader — Offline (Docling)

Converts RF-frontend vendor datasheets (Qorvo / Skyworks / Infineon /
Qualcomm / Samsung / Broadcom / Murata, ...) into LLM-ready form, fully
offline: `docling.md` (text + tables) + `docling.json` (structured,
provenance) + `images/*.png` (hi-res diagrams). Your **local LLM in the
office** then reads those to answer things like:

- MIPI RFFE register maps → what to write to enable PA / LNA / switch
- Truth / state tables → input pin, output/ANT pin, band, mode selection
- Pin lists, band tables, block/application diagrams

There is intentionally **no rule-based RF extractor** in this repo —
Docling does layout/text/tables/pictures, the local LLM does the
understanding.

## Why offline / Git-LFS?

Office PC cannot reach `huggingface.co`. Docling's standard pipeline
downloads models on first run. Fix: download models **here** (internet PC),
ship them in a **public** GitHub repo via Git LFS (models are open weights,
public is fine and needs no login to pull in the office), and run Docling
100% offline via `artifacts_path`. **Never commit vendor datasheets/PDFs
or generated outputs to the public repo — code + model weights only**
(`samples/*.pdf` and `output/` are gitignored for this reason).

```
[INTERNET PC]  scripts/download_models.py -> models/docling/ (762 MB)
               git push (incl. LFS objects) -> YOUR public repo
[OFFICE PC]    git clone <public repo>     (anonymous, no login)
               git lfs pull                (fetches models/)
               scripts/convert.py <datasheet.pdf>
                 -> output/<part>/docling.md + docling.json + images/
               feed docling.md + images/*.png to your local LLM
```

> ⚠️ GitHub Free LFS = 1 GB storage / 1 GB-mo bandwidth, 2 GB/file limit.
> This repo is 762 MB (largest file 203 MB) — fits, but every office
> `git lfs pull` counts against the owner's bandwidth quota. If many PCs
> pull it, mirror the model zip on SharePoint/Nexus instead. Verify model
> downloads against `models/MANIFEST.sha256`. Also check your office
> policy allows pulling code/models from a personal public GitHub repo.

## Setup (internet PC, once — to build/push this repo)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/download_models.py                   # -> models/docling/
# create an EMPTY public repo on github.com, then:
git remote add origin https://github.com/<YOUR-USER>/pdf-reader.git
git push -u origin main                             # uploads code + LFS models
```

## Setup (office PC, offline)

```bash
git clone https://github.com/<YOUR-USER>/pdf-reader.git
cd pdf-reader && git lfs pull                       # models/, no login needed
python -m venv .venv && .venv\Scripts\activate      # Windows (bash: source .venv/bin/activate)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -c "import rapidocr_onnxruntime"            # sanity: OCR engine present
```

Notes:
- `convert.py` sets `HF_HUB_OFFLINE=1` automatically and loads models only
  from `models/docling/` (`artifacts_path`). Verified: a full conversion
  succeeds with networking completely disabled — **no model downloads at
  runtime**. Do not enable Docling features that are off by default here
  (picture description/VLM, formula/code enrichment, EasyOCR) — those
  would try to download extra models/binaries.
- If PyPI is *also* blocked in the office, `pip install` above fails for a
  different reason (packages, not models). Then build a wheelhouse on the
  internet PC (`pip download -r requirements.txt -d wheelhouse/`, plus
  CPU-torch wheels for the office OS) and install in the office with
  `pip install --no-index --find-links wheelhouse/ -r requirements.txt`.
  `wheelhouse/` is LFS-tracked if present, but is **not** in this repo yet.
- Check model integrity: `sha256sum -c models/MANIFEST.sha256`
  (Windows PowerShell: compare with `Get-FileHash`).

## Usage

```bash
python scripts/convert.py <datasheet.pdf>             # full pipeline (with OCR)
python scripts/convert.py --no-ocr <datasheet.pdf>    # ~3x faster, native-text PDFs
python scripts/convert.py --scale 4 <datasheet.pdf>   # higher base image scale

# Re-run only post-processing on an existing output (images/manifest):
python scripts/postprocess.py output/<part>/docling.json --pdf <datasheet.pdf> \
    [--target-px 1400] [--max-scale 6] [--scale 3]
```

Typical speed on a mid-range CPU: ~10 s/page without OCR, ~18 s/page with.

## Output structure (per datasheet, in `output/<part>/`)

`convert.py` runs post-processing automatically (disable: `--no-postprocess`).
Post-processing on success **deletes** the intermediate base64 JSON, so
only LLM-ready files remain:

```
docling.json       DoclingDocument: texts/tables/pictures with page+bbox
                   provenance, reading order in body. pictures[].image.uri
                   is a link ("images/<file>"), dpi/size updated. No base64.
docling.md         Readable rendering of the above; image placeholders
                   replaced by ![caption](images/<file>). Lossy vs JSON
                   (no coordinates), ideal as LLM text input.
images/*.png       Pictures re-cropped from the source PDF at adaptive
                   resolution: long edge -> ~1400 px (what vision LLMs
                   consume), scale clamped [3, 6] = 216-432 dpi; without
                   the PDF, Lanczos upscale fallback (no new detail).
                   Filenames: p<page>_pic<idx>_<caption-slug>.png
images/manifest.json  Per image: file, page, caption, bbox, orig/new size,
                   method, render_scale, page_source (vector/raster/mixed
                   — raster pages capped at native scan dpi),
                   likely_decorative (logos), prev/next text context.
```

To redo images at other settings after a run, re-run `convert.py`
(the base64 intermediate is not kept).

### Feeding your local LLM

- Text/tables: `docling.md` (or `docling.json` if you need page/bbox or
  exact table grids — Markdown can mangle merged cells).
- Images: pick entries from `images/manifest.json` (skip
  `likely_decorative`), and give the LLM the PNG + its `caption` +
  `context_before`/`context_after`.
- Practical tips from testing: filter `page_header`/`page_footer` texts
  out of `docling.json` (repeated vendor legalese); tables split across
  pages stay as separate table objects and may need stitching; a
  picture's `children` in `docling.json` often contain the diagram's
  internal labels as native text — free ground truth next to the PNG.

## Tested datasheets

Full log with sources and timings: `samples/SOURCES.md`, `samples/RESULTS.md`.
Highlights (all offline):

| Part | Vendor / type | Result |
|---|---|---|
| SKY13473-569LF | Skyworks SP10T antenna switch, MIPI RFFE 1.10 | 20 pins, Register_0 truth table (ANT→TRX1..10), register map 0x00/0x1A-0x1F, 17 images |
| BGSX44MU18 | Infineon 4P4T cross switch, MIPI RFFE 2.1 | Register map 0x00-0x2E, truth table (per-port bits), USID table, 36 images |
| RC1602B / HD44780U | 16x2 LCD module / controller | 16-pin table; instruction table |
| LM555, ESP32 | TI timer, Espressif SoC | Pin/electrical tables; 66 tables (ESP32) |

Sample PDFs are kept locally in `samples/` (gitignored) so outputs can be
regenerated; generated outputs live in `output/` (gitignored).

## Layout

| Path | Purpose |
|---|---|
| `scripts/download_models.py` | Download Docling artifacts to `models/` (no HF cache symlinks) |
| `scripts/convert.py` | Offline PDF → Docling JSON/Markdown, then post-processing |
| `scripts/postprocess.py` | Standalone post-processing CLI (also run by convert.py) |
| `src/rf_reader/postprocess.py` | Library: image extraction, hi-res re-crop, link-only JSON/MD, manifest |
| `models/` | LFS-tracked Docling model artifacts (do not trim — office cannot re-download) |
| `samples/` | Public test datasheet PDFs (local only) + SOURCES/RESULTS logs |
| `output/` | Generated per-datasheet results (local only) |
