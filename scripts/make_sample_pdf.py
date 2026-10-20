"""Generate a minimal fake RF datasheet PDF (no deps) to smoke-test Docling offline."""
from pathlib import Path

lines = [
    "QPA9999 Power Amplifier - Datasheet (SYNTHETIC TEST ONLY)",
    "MIPI RFFE Register Map",
    "Register Address Bits Field Default Description",
    "REG_PA_CTRL 0x1C [3] PA_EN 0x0 PA enable: 1=on",
    "REG_PA_CTRL 0x1C [2:0] PA_MODE 0x0 Gain mode select",
    "REG_SW_CTRL 0x1D [3:0] SW_STATE 0x0 Antenna switch state",
    "",
    "Antenna Switch Truth Table",
    "State Input Output Band Control",
    "1 RFIN1 ANT1 B3 0x1",
    "2 RFIN2 ANT1 B1 0x2",
    "3 RFIN1 ANT2 n78 0x3",
]
def esc(s): return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
content = ["BT /F1 11 Tf 50 800 Td"]
for i, l in enumerate(lines):
    if i: content.append("0 -16 Td")
    content.append(f"({esc(l)}) Tj")
content.append("ET")
stream = "\n".join(content).encode()
objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
]
out, offsets = bytearray(b"%PDF-1.4\n"), []
for i, o in enumerate(objs, 1):
    offsets.append(len(out)); out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
xref = len(out); out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
for off in offsets: out += f"{off:010d} 00000 n \n".encode()
out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
p = Path(__file__).resolve().parents[1] / "samples" / "synthetic_qpa9999.pdf"
p.parent.mkdir(exist_ok=True); p.write_bytes(out); print(p)
