"""Stage-2 (deterministic first): find RFFE register tables and
antenna/switch truth tables inside a DoclingDocument JSON by header
keywords, emit RfConfig. Diagrams/pinouts need a VLM pass later —
tables carry ~90% of 'which register / which throw' information.

Handles real vendor formats, e.g. Skyworks SKY13473:
  Table 11 Register_0 Truth Table: State | Mode(TRX1..) | D7..D0 columns
  Table 12 Register Description: Name | Address(Hex)="001A" | Parameter | ...
Addresses may be bare hex (001A) without 0x; Qorvo style uses 0x1C.
"""
import re
from .schema import RfConfig, RegisterWrite, RfPath

HEX = re.compile(r"0x[0-9A-Fa-f]+|\b[0-9A-Fa-f]{2}h\b")
BARE_HEX = re.compile(r"^[0-9A-Fa-f]{4}$|^[0-9A-Fa-f]{2}$")

def _addr(cell: str) -> str:
    cell = cell.strip()
    m = HEX.search(cell)
    if m:
        return m.group(0)
    if BARE_HEX.match(cell):          # Skyworks "001A" / "0000"
        return "0x" + cell.lstrip("0").upper().zfill(2) if cell.strip("0") else "0x00"
    return ""

def _bits_value(cells: list[str]) -> str:
    """Concatenate D7..D0 bit cells ('0 0' in a merged D4D3 cell counts twice)."""
    bits = ""
    for c in cells:
        toks = re.findall(r"[01x]", c.lower())
        bits += "".join(toks)
    if not bits or "x" in bits[1:] and len(bits) < 4:
        return ""
    bits = bits.replace("x", "0")     # D7 is usually don't-care in Reg0 tables
    if len(bits) >= 4:
        return f"0x{int(bits[-8:], 2):02X} (0b{bits[-8:]})"
    return ""

def extract(doc_json: dict) -> RfConfig:
    cfg = RfConfig()
    for t in doc_json.get("tables", []):
        grid = t.get("data", {}).get("grid", [])
        rows = [[c.get("text", "").strip() for c in r] for r in grid]
        if len(rows) < 2:
            continue
        # Some vendor tables have a 2-row header (merged 'Register' over
        # 'Name | Address (Hex) | ...'): use the row containing keywords.
        hrow = next((i for i, r in enumerate(rows[:3])
                     if any(k in " ".join(r).lower() for k in ("address", "mode", "pin", "symbol"))), 0)
        head = " ".join(rows[hrow]).lower()
        body = rows[hrow + 1:]
        page = (t.get("prov") or [{}])[0].get("page_no")

        # 1) Switch truth table: State | Mode | Register_x Bits - D7..D0
        if "bits" in " ".join(rows[0]).lower() or ("mode" in head and "state" in head):
            for r in body:
                if not (r and r[0].strip().isdigit()):
                    continue  # skip duplicated sub-header row (D7 D6 ...)
                mode = next((c for c in r if re.search(r"trx|ant|isolation|rf|lb|hb|gsm|lte", c, re.I)), r[1] if len(r) > 1 else "")
                val = _bits_value(r[2:])
                if mode:
                    cfg.rf_paths.append(RfPath(
                        state=r[0], input_pin="ANT", output_pin=mode,
                        control=f"Register_0 = {val}" if val else " | ".join(r), page=page))
            continue

        # 2) Register map: header row has Address (register name is col 0)
        if "address" in head and ("parameter" in head or "default" in head or "register" in " ".join(rows[0]).lower()):
            ai = next((i for i, c in enumerate(rows[hrow]) if "address" in c.lower()), 1)
            for r in body:
                addr = _addr(r[ai]) if ai < len(r) else ""
                if not addr and not any(r):
                    continue
                cfg.registers.append(RegisterWrite(
                    address=addr,
                    field=r[ai + 1] if ai + 1 < len(r) else (r[0] if r else ""),
                    value=r[-1] if r else "",
                    purpose=r[ai + 2] if ai + 2 < len(r) else "",
                    raw=" | ".join(r), page=page))
            continue

        # 3) Generic RF truth/state table
        if any(h in head for h in ("truth table", "antenna", "switch")):
            for r in body:
                cfg.rf_paths.append(RfPath(
                    state=r[0] if r else "",
                    input_pin=next((c for c in r if re.search(r"rf_?in|input|tx\d|trx", c, re.I)), ""),
                    output_pin=next((c for c in r if re.search(r"ant|rf_?out|output", c, re.I)), ""),
                    band=next((c for c in r if re.search(r"\b[bn]\d{1,3}\b", c, re.I)), ""),
                    control=" | ".join(r), page=page))

        # 4) Pin table: Pin No/# | Symbol/Name | ... | Description
        #    (TI style has a 2-row header: PIN|PIN / NO.|NAME)
        hdr2 = " ".join(rows[0] + (rows[1] if len(rows) > 1 else [])).lower()
        if "pin" in hdr2 and ("name" in hdr2 or "symbol" in hdr2):
            pin_cols = [i for i, c in enumerate(rows[0]) if "pin" in c.lower()] or [0]
            start = 2 if len(rows) > 1 and not rows[1][0].strip().isdigit() and "pin" in " ".join(rows[0]).lower() and ("no" in rows[1][0].lower() or "name" in rows[1][0].lower() or rows[1][0].strip() == "") else hrow + 1
            if start == 2:
                pin_cols = [0]  # 2-row header: PIN/PIN merged, not dual-pin
            for r in rows[start:]:
                for pc in (pin_cols or [0]):  # 1 or 2 pins per row
                    if pc + 1 < len(r) and r[pc].strip().isdigit():
                        # dual-pin row: description is pc+2; single-pin: last col
                        desc = r[pc + 2] if len(pin_cols) > 1 and pc + 2 < len(r) else (r[-1] if len(r) > 3 else (r[pc + 2] if pc + 2 < len(r) else ""))
                        cfg.pins[r[pc].strip()] = " ".join(x for x in (r[pc + 1], desc) if x)

    if not cfg.registers:  # fallback for borderless tables (see synthetic test)
        for t in doc_json.get("texts", []):
            txt = t.get("text", "")
            m = HEX.search(txt)
            if m and re.search(r"PA_|REG_|SW_|_CTRL|_EN\b", txt):
                cfg.registers.append(RegisterWrite(
                    address=m.group(0), raw=txt,
                    page=(t.get("prov") or [{}])[0].get("page_no")))
    return cfg
