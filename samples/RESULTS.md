# Test results — 2026-10-20 (offline, HF_HUB_OFFLINE=1, CPU, WSL2 on /mnt/d)

| Datasheet | Pages | Mode | Time | Docling tables/pics | Stage-2 extraction |
|---|---|---|---|---|---|
| RC1602B 16x2 LCD module | 5 | OCR | 1m11s | 4 / 5 | **16/16 pins** (VSS,VDD,VO,RS,R/W,E,DB0-DB7,A,K) |
| SKY13473-569LF SP10T MIPI RFFE switch | 18 | OCR | 5m34s | 17 / 17 | **20/20 pins, 23 register fields, 11 RF paths** (see below) |
| TI LM555 | 29 | no-OCR | 3m12s | 13 / 71 | **8/8 pins** |
| HD44780U LCD controller | 60 | no-OCR | ~10m | 31 / 47 | Pin/instruction tables perfect in Markdown (Signal-style header, not Pin-No style — stage-2 pin parser N/A) |
| ESP32 SoC | 78 | no-OCR | ~17m | 66 / 14 | 66 tables in Markdown; pin parser partial (13) — ESP32 pin-overview format differs |

Speed: ~10 s/page without OCR, ~18 s/page with OCR on this machine.
Native-text datasheets (most vendor PDFs) should use `--no-ocr`.

## Proof for the RF use-case (SKY13473, from Docling Table 11/12 in docling.md — stage-2 extractor since removed, local LLM does this now)

ANT -> TRX routing from Register_0 truth table (Table 11), computed from D7..D0 bits:

```
Isolation=0x00  TRX1=0x02  TRX2=0x0A  TRX3=0x0E  TRX4=0x0B  TRX5=0x01
TRX6=0x09  TRX7=0x06  TRX8=0x04  TRX9=0x0C  TRX10=0x08
```

Register map (Table 12): Register_0@0x00, RFFE_STATUS@0x1A, GROUP_SID@0x1B,
PM_TRIG@0x1C, PRODUCT_ID@0x1D (=0x45), MANUFACTURER_ID@0x1E, MAN_USID@0x1F (USID default 1011b).

i.e. to route ANT->TRX3: MIPI RFFE Reg0 write (USID=0xB) data 0x0E.
Values verified by hand against the datasheet bit table. Still `needs_review: true`.

## Update 2026-10-20 (evening): second RFFE device — Infineon BGSX44MU18

23 pages, `--no-ocr`, 8m23s. Docling: 326 texts, 22 tables, 36 pictures ->
post-processed images (7 captioned figures, 5 decorative flagged, 0 base64).

Extracted cleanly in docling.md:
- Table 15-17 register mapping (0x00-0x03 SWITCH_CTRL_RF_A1..A4, 0x1C PM_TRIG,
  0x1D PRODUCT_ID=0xE8, 0x1E MAN_ID=0x1A, 0x1F MAN_USID, 0x20-0x2E ext/trigger)
- Table 18 truth table: per-port register, D0=RF_B1 D1=RF_B2 D2=RF_B3 D3=RF_B4
  (1=connect, 0=isolate) — e.g. RF_A1->RF_B3 = Reg 0x00 bits `xxxx0100`
- Table 14 USID: USID_SEL=GND -> 0xA, =VIO -> 0xB (pin-selectable)
- Table 19 pin definition (19 pins) + footprint/block/schematic images

Vendor-format differences vs Skyworks SKY13473 the LLM must handle:
0x-prefixed addresses (vs bare hex), one register per RF port (vs one
Register_0 for all throws), multi-row bit descriptions that Docling
sometimes splits/duplicates (Table 15 PM_TRIG D5/D4, Table 17 rows),
hyphenation artefacts ("Re- served", "receivedwith").
