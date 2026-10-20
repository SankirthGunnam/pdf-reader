"""Stage-2 (deterministic first): find RFFE register tables and
antenna/switch truth tables inside a DoclingDocument JSON by header
keywords, emit RfConfig. Diagrams/pinouts need a VLM pass later —
tables carry ~90% of 'which register / which throw' information."""
import re
from .schema import RfConfig, RegisterWrite, RfPath

REG_HINTS = ("register", "address", "rffe", "mipi", "bit", "field", "default")
PATH_HINTS = ("truth table", "state", "antenna", "switch", "rf path", "mode", "band")
HEX = re.compile(r"0x[0-9A-Fa-f]+|\b[0-9A-Fa-f]{2}h\b")

def _rows(table) -> list[list[str]]:
    return [[c.text.strip() for c in row] for row in table]

def extract(doc_json: dict) -> RfConfig:
    cfg = RfConfig()
    # Docling JSON: tables live under "tables", text under "texts"
    for t in doc_json.get("tables", []):
        grid = t.get("data", {}).get("grid", [])
        rows = [[c.get("text", "").strip() for c in r] for r in grid]
        if not rows:
            continue
        head = " ".join(rows[0]).lower()
        page = (t.get("prov") or [{}])[0].get("page_no")
        if any(h in head for h in REG_HINTS) and ("address" in head or "register" in head):
            for r in rows[1:]:
                addr = HEX.search(" ".join(r))
                cfg.registers.append(RegisterWrite(
                    address=addr.group(0) if addr else "",
                    field=r[1] if len(r) > 1 else "", value=r[-1] if r else "",
                    raw=" | ".join(r), page=page))
        elif any(h in head for h in PATH_HINTS):
            for r in rows[1:]:
                joined = " ".join(r)
                cfg.rf_paths.append(RfPath(
                    state=r[0] if r else "",
                    input_pin=next((c for c in r if re.search(r"rf_?in|input|tx\d|trx", c, re.I)), ""),
                    output_pin=next((c for c in r if re.search(r"ant|rf_?out|output", c, re.I)), ""),
                    band=next((c for c in r if re.search(r"\b[bn]\d{1,3}\b", c, re.I)), ""),
                    control=joined, page=page))
    # Fallback: tables without ruling lines aren't detected as tables.
    # Scan raw text lines for "NAME 0xADDR [bits] FIELD ..." patterns.
    if not cfg.registers:
        for t in doc_json.get("texts", []):
            txt = t.get("text", "")
            m = HEX.search(txt)
            if m and re.search(r"PA_|REG_|SW_|_CTRL|_EN\b", txt):
                page = (t.get("prov") or [{}])[0].get("page_no")
                cfg.registers.append(RegisterWrite(address=m.group(0), raw=txt, page=page))
    return cfg
