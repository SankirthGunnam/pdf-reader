"""Post-process a DoclingDocument JSON for feeding to a local LLM.

Docling embeds every picture as a base64 `data:` URI inside docling.json,
with no description of its contents. That is wasteful/harmful for an LLM:
text LLMs choke on base64, vision LLMs want real image files.

This module, given the *source PDF* (best) or only the JSON:
  1. Writes each picture to  images/p<page>_pic<idx>_<caption-slug>.png
  2. Re-renders it at high resolution by re-cropping the PDF page using
     the picture bbox (true detail, ~72*scale dpi). Fallback, when no PDF
     is supplied: Lanczos-upscale the embedded 72-dpi crop (no new detail,
     but bigger/sharper for VLM input resizing).
  3. Rewrites pictures[].image.uri -> "images/<file>" (link only, same
     JSON schema) and updates dpi/size to the new image. Raw base64 is
     removed. Original JSON is preserved as docling_raw.json.
  4. Writes images/manifest.json: file, page, caption, bbox, original and
     new size, method, size-filter flag, and prev/next text context from
     document (body) order — everything an LLM prompt-builder needs.
  5. Rewrites docling.md: <!-- image --> -> ![caption](images/<file>)
"""
from __future__ import annotations

import base64, io, json, re
from pathlib import Path

def _slug(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen].strip("-")

def _resolve(doc: dict, ref: str):
    node = doc
    for part in ref.lstrip("#/").split("/"):
        node = node[int(part)] if part.isdigit() else node[part]
    return node

def _body_order(doc: dict) -> list[str]:
    """self_refs in reading (body) order, recursively."""
    order: list[str] = []
    def walk(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref and ref != "#/body":
                order.append(ref)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(doc.get("body", {}))
    return order

def _recrop(pdf_path: Path, page_no: int, bbox: dict, scale: float, cache: dict):
    """Render PDF page at `scale`x and crop bbox (BOTTOMLEFT, PDF points)."""
    import pypdfium2 as pdfium
    if "pdf" not in cache:
        cache["pdf"] = pdfium.PdfDocument(str(pdf_path))
        cache["pages"] = {}
    pdf = cache["pdf"]
    if page_no not in cache["pages"]:
        page = pdf[page_no - 1]
        w_pt, h_pt = page.get_size()
        bitmap = page.render(scale=scale)
        cache["pages"][page_no] = (bitmap.to_pil(), w_pt, h_pt)
    pil, w_pt, h_pt = cache["pages"][page_no]
    x0 = int(bbox["l"] * scale); x1 = int(bbox["r"] * scale)
    y0 = int((h_pt - bbox["t"]) * scale); y1 = int((h_pt - bbox["b"]) * scale)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(pil.width, x1), min(pil.height, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return pil.crop((x0, y0, x1, y1))

def postprocess(docling_json: Path, pdf: Path | None = None,
                scale: float = 3.0, min_size: int = 48) -> dict:
    """Transform docling_json in place (backup -> docling_raw.json).
    Returns manifest dict. Idempotent: skips pictures already linked."""
    docling_json = Path(docling_json)
    out_dir = docling_json.parent
    img_dir = out_dir / "images"
    img_dir.mkdir(exist_ok=True)

    raw = out_dir / "docling_raw.json"
    orig_bytes = docling_json.read_bytes()
    if not raw.exists():
        raw.write_bytes(orig_bytes)
    doc = json.loads(orig_bytes)

    order = _body_order(doc)
    pos = {ref: i for i, ref in enumerate(order)}

    def context_for(ref: str) -> tuple[str, str]:
        prev_t = next_t = ""
        if ref in pos:
            before = [o for o in order[:pos[ref]] if o.startswith("#/texts/")]
            after = [o for o in order[pos[ref] + 1:] if o.startswith("#/texts/")]
            if before:
                prev_t = _resolve(doc, before[-1]).get("text", "").strip()[:300]
            if after:
                next_t = _resolve(doc, after[0]).get("text", "").strip()[:300]
        return prev_t, next_t

    # preserve first-run manifest facts (original size/method) on re-runs
    prev: dict[int, dict] = {}
    mf = img_dir / "manifest.json"
    if mf.exists():
        try:
            prev = {e["index"]: e for e in json.loads(mf.read_text())["images"]}
        except Exception:
            prev = {}

    cache: dict = {}
    manifest: list[dict] = []
    md_links: list[tuple[str, str]] = []  # (filename, caption) in body order

    pics = doc.get("pictures", [])
    # process in body order so md placeholder replacement lines up
    pic_indices = sorted(range(len(pics)),
                         key=lambda i: pos.get(f"#/pictures/{i}", i))

    for i in pic_indices:
        pic = pics[i]
        img = pic.get("image") or {}
        uri = img.get("uri", "")
        prov = (pic.get("prov") or [{}])[0]
        page = prov.get("page_no", 0)
        caption = " ".join(
            _resolve(doc, c["$ref"]).get("text", "").strip()
            for c in pic.get("captions", []) if c.get("$ref"))
        fname = f"p{page:02d}_pic{i:02d}" + (f"_{_slug(caption)}" if caption else "") + ".png"
        dest = img_dir / fname
        orig_size = img.get("size") or {}
        method = "already-linked"

        if uri.startswith("data:"):
            data = base64.b64decode(uri.split(",", 1)[1])
            new_img, method = None, "upscale-lanczos"
            if pdf is not None and prov.get("bbox"):
                try:
                    new_img = _recrop(Path(pdf), page, prov["bbox"], scale, cache)
                    method = f"recrop-pdf-{int(72 * scale)}dpi" if new_img else method
                except Exception as e:  # fall through to upscale
                    print(f"  recrop failed pic{i} ({e}); falling back to upscale")
            if new_img is None:
                from PIL import Image
                src = Image.open(io.BytesIO(data))
                if scale != 1.0:
                    new_img = src.resize(
                        (max(1, int(src.width * scale)), max(1, int(src.height * scale))),
                        Image.LANCZOS)
                else:
                    new_img = src
            new_img.save(dest)
            img["uri"] = f"images/{fname}"
            img["mimetype"] = "image/png"
            img["dpi"] = int(72 * scale) if method.startswith("recrop") else img.get("dpi", 72)
            img["size"] = {"width": float(new_img.width), "height": float(new_img.height)}

        prev_t, next_t = context_for(f"#/pictures/{i}")
        old = prev.get(i, {}) if method == "already-linked" else {}
        small = old.get("likely_decorative",
                        max(float(orig_size.get("width", 0)), float(orig_size.get("height", 0))) < min_size)
        entry = {
            "index": i, "file": f"images/{fname}", "page": page,
            "caption": caption, "bbox": prov.get("bbox"),
            "original_size": old.get("original_size", orig_size), "size": img.get("size"),
            "method": old.get("method", method), "likely_decorative": bool(small),
            "context_before": prev_t, "context_after": next_t,
        }
        manifest.append(entry)
        md_links.append((fname, caption))

    manifest.sort(key=lambda e: e["index"])
    docling_json.write_text(json.dumps(doc, indent=2, ensure_ascii=False))

    (img_dir / "manifest.json").write_text(json.dumps(
        {"source": docling_json.name, "pdf": str(pdf) if pdf else None,
         "scale": scale, "images": manifest}, indent=2, ensure_ascii=False))

    # Markdown: replace <!-- image --> placeholders in body order
    md_path = out_dir / "docling.md"
    if md_path.exists() and md_links:
        md = md_path.read_text()
        it = iter(md_links)
        def repl(_m):
            try:
                fname, caption = next(it)
            except StopIteration:
                return "<!-- image -->"
            return f"![{caption or 'figure'}](images/{fname})"
        md_path.write_text(re.sub(r"<!-- image -->", repl, md))

    return {"images": manifest, "out_dir": str(out_dir)}
