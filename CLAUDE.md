# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MetaGenPicture** — Python/Streamlit app ที่รับภาพ collage (4–6 รูปรวมกัน) แล้วแยกแต่ละรูปออกมา กรอง duplicate และจัดเรียงใหม่เป็น layout 1080×1080 px สำหรับเพจ Facebook "ข่าวทันเหตุการณ์"

**ข้อบังคับหลัก**: หน้าคน/ใบหน้าต้องไม่ถูก crop หรือแก้ไขใดๆ — ปรับได้เฉพาะขอบ, สี, brightness, และ layout เท่านั้น

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Web UI (วิธีหลัก)
streamlit run app.py

# CLI — ไฟล์เดียว
python main.py --input photo.jpg --layout 1+3

# CLI — batch
python main.py --input a.jpg b.jpg c.jpg --output-dir out/ --layout 1+3

# CLI flags: --layout 1+2|1+3|2+3  --seed int  --output-dir path

# Tests
python -m pytest tests/ -v
```

## Architecture & Data Flow

```
Input collage image
    → layout_detector.detect_layout()   2-level variance scan → list[(x0,y0,x1,y1)]
    → splitter.split()                  crop cells + deduplicate → list[PIL.Image]
    → variants.generate_variants()      สร้าง 4 แบบ → list[PIL.Image 1080×1080]
    → app.py แสดง before/after + เลือกแบบ + download
```

### layout_detector.py

**2-level variance scan**:
1. Horizontal scan → แบ่ง horizontal bands
2. Vertical scan ภายในแต่ละ band → แบ่ง cells

Relative threshold 4–15% of max variance, smooth window=5  
Filter cell < 18% of image dimension → กำจัด text banner / watermark

### splitter.py

Crop cells จาก detector:
- Filter cell < 80px
- **Deduplicate** ด้วย RGB MSE บน 16×16 thumbnail — MSE < 4% = duplicate → ทิ้ง  
  (ป้องกัน Facebook "+N" overlay region ที่อาจตรวจเจอซ้ำ)

### variants.py — Variant generation

สร้าง n=4 แบบ:
1. **Main-left candidates** = รูปที่ area ≥ 35% ของรูปใหญ่สุด  
   → ป้องกัน thumbnail/"+N" cell (area ~10-22%) ถูกขยายเป็น main → blur/black
2. **Cycle main** ผ่าน candidates (ถ้ามีหลายรูปใหญ่ เช่น 2×2 collage)
3. **Rotate right-column order** ทุก cycle → ลำดับรูปขวาต่างกัน
4. **Rotate seed** ทุก variant → transform ต่างกันเล็กน้อย

### transformer.py

Reproducible subtle transforms per photo:
- Edge crop 1–4% → resize กลับ (ไม่แตะ center 70%)
- Brightness ±8%, Contrast ±6%, Saturation ±10%

### composer.py — Layouts

Output 1080×1080 px เสมอ  
`respect_order=True` → ใช้ลำดับจาก variants.py ตรงๆ ไม่ re-sort

| Layout | รูปที่ใช้ | โครงสร้าง |
|--------|-----------|-----------|
| `1+2`  | 3 รูป    | 1 ใหญ่ซ้าย + 2 square ขวา |
| `1+3`  | 4 รูป    | 1 ใหญ่ซ้าย + 3 square ขวา |
| `2+3`  | 5 รูป    | 2 ซ้ายเรียงตั้ง + 3 square ขวา |

Right photos = **square** เสมอ: `rsize = (1080 - GAP*(n-1)) // n`  
Left panel ≥ 35% ของ canvas (clamp ป้องกัน lw negative เมื่อรูปน้อยกว่า layout ต้องการ)

### app.py (Streamlit Web UI)

- **Sidebar**: logo + layout selector (3 PIL cards แนวนอน, กด button เพื่อเลือก)
- **Main**: upload → ⚡ ประมวลผล → ต้นฉบับ|ผลลัพธ์ → 4 variant buttons → download
- **Batch**: หลายไฟล์ + ZIP download
- `st.session_state` persist results/selected variant

## Python Version

Python 3.9 — ใช้ `Optional[X]` และ `"list[X]"` string annotation แทน `X | None` และ `list[X]`

## Known Input Limitations

Input ที่ดีที่สุด: collage ที่รูปชัดเจน แยกกันด้วย separator  
Input ที่มีปัญหา: Facebook screenshot ที่มี "+N" overlay บน cell สุดท้าย → cell นั้นอาจปรากฏใน right column แต่จะไม่เป็น main left photo
