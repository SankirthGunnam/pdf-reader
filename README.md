# RF Frontend PDF Reader — Offline (Docling)

Extracts structured RF configuration from vendor datasheets
(Qorvo / Skyworks / Qualcomm / Samsung / Broadcom / Murata, ...):

- MIPI RFFE register maps → what to write to enable PA / LNA / switch
- Truth / state tables → input pin, output/ANT pin, band, mode selection
- Pin lists, band tables, block/application diagrams (as cropped images)

## Why offline / Git-LFS?

Office PC cannot reach `huggingface.co`. Docling's standard pipeline
downloads models on first run. Fix: download models **here** (internet PC),
ship them in a **public** repo via Git LFS (models are open weights, public
is fine and needs no login to pull in the office), and run Docling 100%
offline via `artifacts_path` + `HF_HUB_OFFLINE=1`.
**Never commit vendor datasheets/PDFs or extracted configs to the public
repo — code + model weights only.**

```
[PUBLIC PC] scripts/download_models.py  -> models/docling/  (~0.7-1.5 GB)
            git lfs push                -> private repo
[OFFICE PC] git lfs pull
            scripts/convert.py datasheet.pdf -> output/<chip>/docling.json|md
            scripts/extract_rf.py            -> output/<chip>/rf_config.json
```

> ⚠️ GitHub Free LFS = 1 GB storage / 1 GB-mo bandwidth, 2 GB/file limit.
> This repo is 762 MB (largest file 203 MB) — fits, but every office
> `git lfs pull` counts against the owner's bandwidth quota. If many PCs
> pull it, mirror the zip on SharePoint/Nexus instead. Verify downloads
> against `models/MANIFEST.sha256`. Check your office policy allows
> pulling code/models from a personal public GitHub repo.

## Setup (internet PC, once)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_models.py            # -> models/docling/
git lfs install && git lfs pull              # after first clone
```

## Setup (office PC, offline)

```bash
pip install --no-index --find-links wheelhouse/ -r requirements.txt  # if PyPI also blocked
git lfs pull                                  # fetches models/
set HF_HUB_OFFLINE=1                          # Windows cmd; PowerShell: $env:HF_HUB_OFFLINE=1
export HF_HUB_OFFLINE=1                       # bash
python scripts/convert.py samples/QPAxxxx.pdf
python scripts/extract_rf.py output/QPAxxxx/docling.json
```

If PyPI is also blocked in the office, build a wheelhouse here too:
`pip download -r requirements.txt -d wheelhouse/` and LFS-track it (often 1-2 GB).

## What Docling does NOT do

Docling gives you layout + text + tables + pictures (`DoclingDocument`).
It does **not** understand "write Reg 0x1D[3]=1 to turn PA on, route
RFIN2→ANT1 for B3". That is stage-2 in `src/rf_reader/extract.py`:
table-header heuristics + regex (rules first, deterministic), with
optional local VLM (e.g. Granite-Docling, extra ~1 GB) only for
block/pin diagrams. **Always human-review `rf_config.json` before using
it to drive hardware — a wrong switch/PA state can damage the front-end.**

## Output structure (per datasheet, in `output/<part>/`)

`convert.py` runs post-processing automatically (disable: `--no-postprocess`,
standalone: `scripts/postprocess.py`). Docling's embedded base64 pictures are
extracted so a local LLM gets clean text + real image files:

```
docling_raw.json   original Docling output (base64 embedded) — backup/audit
docling.json       same, but pictures[].image.uri = "images/<file>" (link only),
                   dpi/size updated. No base64 anywhere.
docling.md         same, but <!-- image --> -> ![caption](images/<file>)
images/*.png       pictures re-cropped from the source PDF at ~216 dpi
                   (--scale 2/3/4; without the PDF, Lanczos upscale fallback).
                   Filenames: p<page>_pic<idx>_<caption-slug>.png
images/manifest.json  per image: page, caption, bbox, orig/new size, method,
                   likely_decorative (logos), prev/next text context.
```

Feed your LLM: `docling.md` for text/tables, plus for each relevant
`manifest.json` entry the PNG + `caption` + `context_before/after`.

## Layout

| Path | Purpose |
|---|---|
| `scripts/download_models.py` | Download Docling artifacts to `models/` (no HF cache symlinks) |
| `scripts/convert.py` | Offline PDF → Docling JSON/Markdown + table/picture crops |
| `scripts/extract_rf.py` | Docling JSON → `rf_config.json` (registers, pins, RF paths) |
| `src/rf_reader/schema.py` | Pydantic schema for the extracted configuration |
| `src/rf_reader/extract.py` | Rule-based register/truth-table parser |
| `models/` | LFS-tracked model artifacts (not normal git) |
