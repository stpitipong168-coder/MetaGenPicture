"""
MetaGenPicture — SaaS dark UI
Features:
  - Crop/pan per slot (streamlit-cropper)
  - Flip photo horizontally per slot (⇄ button)
  - Live result preview
"""
import io
import math
import os
import zipfile

import streamlit as st
from PIL import Image, ImageDraw
from streamlit_cropper import st_cropper

from splitter import split
from variants import generate_variant_parts, LAYOUT_NEEDS
from composer import compose, compose_direct, get_slot_layout

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MetaGenPicture",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
)

LAYOUTS = {"1+3": "4 รูป", "1+2": "3 รูป", "2+3": "5 รูป"}
SLOT_LABELS = {
    "1+2": ["ซ้าย (หลัก)", "ขวา 1", "ขวา 2"],
    "1+3": ["ซ้าย (หลัก)", "ขวา 1", "ขวา 2", "ขวา 3"],
    "2+3": ["ซ้าย 1", "ซ้าย 2", "ขวา 1", "ขวา 2", "ขวา 3"],
}

if "layout"   not in st.session_state: st.session_state.layout   = "1+3"
if "results"  not in st.session_state: st.session_state.results  = {}
if "selected" not in st.session_state: st.session_state.selected = {}
if "api_key"  not in st.session_state: st.session_state.api_key  = ""


def _get_api_key() -> str:
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY", "")
        if k:
            return k
    except Exception:
        pass
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if k:
        return k
    return st.session_state.api_key

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
[data-testid="stAppViewContainer"] { background:#0e0e16; }
[data-testid="stHeader"]           { background:transparent; }
.block-container { padding-top:2rem; padding-bottom:3rem; }
[data-testid="stSidebar"] {
  background:#09090f !important;
  border-right:1px solid #1c1c2e !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top:0.6rem !important; }
[data-testid="stSidebarCollapseButton"] { display:none !important; }
.stButton > button[kind="primary"] {
  background:linear-gradient(135deg,#7c3aed,#4338ca) !important;
  color:#fff !important; border:none !important;
  border-radius:8px !important; font-weight:700 !important;
  box-shadow:0 4px 14px rgba(124,58,237,.4) !important;
}
.stButton > button[kind="secondary"] {
  background:#111120 !important; color:#6b6b9a !important;
  border:1px solid #1e1e32 !important; border-radius:8px !important;
  font-weight:600 !important;
}
.stButton > button[kind="secondary"]:hover {
  color:#a78bfa !important; border-color:#4c3a8a !important;
}
[data-testid="stFileUploaderDropzone"] {
  background:#0d0d1a !important;
  border:2px dashed #1e1e38 !important; border-radius:16px !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color:#5b21b6 !important; }
[data-testid="stDownloadButton"] > button {
  background:linear-gradient(135deg,#059669,#0891b2) !important;
  color:#fff !important; border:none !important;
  border-radius:8px !important; font-weight:700 !important;
}
[data-testid="stExpander"] {
  background:#0c0c18 !important; border:1px solid #1c1c2e !important;
  border-radius:14px !important;
}
[data-testid="stExpander"] summary { color:#d1d5db !important; font-weight:600 !important; }
hr { border-color:#1c1c2e !important; }
#MainMenu,footer,[data-testid="stToolbar"] { display:none !important; }
.logo    { font-size:.82rem; font-weight:800; margin:0 0 6px 0;
           background:linear-gradient(110deg,#a78bfa 30%,#60a5fa);
           -webkit-background-clip:text; -webkit-text-fill-color:transparent;
           background-clip:text; }
.lbl     { color:#3a3a58; font-size:.62rem; font-weight:700;
           text-transform:uppercase; letter-spacing:.1em; }
.sec-lbl { color:#4b5563; font-size:.68rem; font-weight:700;
           text-transform:uppercase; letter-spacing:.08em; margin-bottom:2px; }
</style>""", unsafe_allow_html=True)


# ── Image helpers ─────────────────────────────────────────────────────────────

def _cap(img: Image.Image, max_px: int = 800) -> Image.Image:
    if max(img.size) <= max_px:
        return img
    r = max_px / max(img.size)
    return img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)


@st.cache_data
def layout_preview(key: str, sel: bool) -> Image.Image:
    W, H = 108, 68
    BG=(9,9,15); ACC=(120,52,220); MID=(46,38,72); DIM=(24,24,42); G=4
    main=ACC if sel else MID; bd=ACC if sel else (22,22,38)
    img=Image.new("RGB",(W,H),BG); draw=ImageDraw.Draw(img)
    if key=="1+3":
        lw=int(W*.58); rs=(H-G*2)//3
        draw.rounded_rectangle([G,G,lw-G,H-G],radius=4,fill=main)
        for i in range(3): y0=G+i*(rs+G); draw.rounded_rectangle([lw+G,y0,W-G,y0+rs],radius=3,fill=DIM)
    elif key=="1+2":
        lw=int(W*.52); rs=(H-G)//2
        draw.rounded_rectangle([G,G,lw-G,H-G],radius=4,fill=main)
        for i in range(2): y0=G+i*(rs+G); draw.rounded_rectangle([lw+G,y0,W-G,y0+rs],radius=3,fill=DIM)
    elif key=="2+3":
        lw=int(W*.52); lh=(H-G)//2; rs=(H-G*2)//3
        for i in range(2): y0=G+i*(lh+G); draw.rounded_rectangle([G,y0,lw-G,y0+lh],radius=4,fill=main)
        for i in range(3): y0=G+i*(rs+G); draw.rounded_rectangle([lw+G,y0,W-G,y0+rs],radius=3,fill=DIM)
    draw.rounded_rectangle([0,0,W-1,H-1],radius=6,outline=bd,width=2)
    return img


# ══════════════════════════════════════════════════════════════════════════════
# MAIN UPLOAD + PROCESSING  (must run BEFORE sidebar so results are ready)
# ══════════════════════════════════════════════════════════════════════════════
layout = st.session_state.layout

st.markdown('<p class="sec-lbl">อัพโหลดภาพ Collage</p>', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    label="วาง หรือ คลิกเพื่อเลือกไฟล์",
    type=["jpg","jpeg","png","webp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)
st.button("⚡  ประมวลผล", type="primary", width="stretch",
          disabled=not uploaded_files, key="process_btn")

if st.session_state.get("process_btn") and uploaded_files:
    prog = st.progress(0, text="กำลังประมวลผล…")
    for idx, uf in enumerate(uploaded_files):
        prog.progress(idx / len(uploaded_files), text=f"ประมวลผล {uf.name}…")
        try:
            uf.seek(0)
            src   = Image.open(uf).convert("RGB")
            parts = split(src, api_key=_get_api_key())
            if len(parts) < 1:
                st.warning(f"{uf.name}: ตรวจจับ sub-images ไม่ได้")
                continue
            vparts = generate_variant_parts(parts, layout, n=4)
            st.session_state.results[uf.name] = {
                "src": src, "parts": parts, "gen_layout": layout,
                "variant_parts": vparts,
            }
            st.session_state.selected.setdefault(uf.name, 0)
        except Exception as e:
            st.error(f"{uf.name}: {e}")
    prog.progress(1.0, text="เสร็จแล้ว ✓")


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR  (declared after processing so results are already in session_state)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<p class="logo">🖼️ MetaGenPicture</p>', unsafe_allow_html=True)
    st.markdown('<p class="lbl">Layout</p>', unsafe_allow_html=True)
    cols = st.columns(3, gap="small")
    for col, (code, short) in zip(cols, LAYOUTS.items()):
        with col:
            sel = st.session_state.layout == code
            st.image(layout_preview(code, sel), width="stretch")
            lbl = f"✓ {code}" if sel else code
            if st.button(lbl, key=f"pick_{code}",
                         type="primary" if sel else "secondary", width="stretch"):
                st.session_state.layout = code
                st.rerun()
            st.caption(short)

    # ── API Key ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<p class="lbl">AI Detection</p>', unsafe_allow_html=True)
    _ak = _get_api_key()
    if not _ak:
        entered = st.text_input(
            "Anthropic API Key", type="password",
            placeholder="sk-ant-...",
            help="ใส่ key เพื่อให้ AI ตรวจจับรูปใน collage แม่นยำขึ้น",
            key="_api_key_field",
        )
        if entered:
            st.session_state.api_key = entered
            st.rerun()
        st.caption("ไม่มี key → ใช้ variance scan")
    else:
        st.success("AI พร้อมใช้งาน", icon="🤖")

    if st.session_state.results:
        st.markdown("---")
        st.markdown('<p class="lbl">ต้นฉบับ</p>', unsafe_allow_html=True)
        last_src = list(st.session_state.results.values())[-1]["src"]
        st.image(last_src, use_container_width=True)

if not st.session_state.results:
    st.stop()

# ── Results ───────────────────────────────────────────────────────────────────
st.markdown("---")
all_dl: list = []
slots_info = get_slot_layout(layout)
needed     = LAYOUT_NEEDS.get(layout, 4)

for fname, data in st.session_state.results.items():
    src: Image.Image = data["src"]

    # ── Regenerate variant orderings if layout changed since processing ────────
    if data.get("gen_layout") != layout and data.get("parts"):
        vparts = generate_variant_parts(data["parts"], layout, n=4)
        data.update({"variant_parts": vparts, "gen_layout": layout})
        st.session_state.results[fname] = data
        st.session_state.selected[fname] = 0

    vparts: list = data.get("variant_parts", [])
    sel_idx: int = st.session_state.selected.get(fname, 0)
    photos_base  = vparts[sel_idx] if sel_idx < len(vparts) else []
    n_slots      = min(len(slots_info), len(photos_base))
    labels       = SLOT_LABELS.get(layout, [f"ช่อง {i+1}" for i in range(n_slots)])
    photos       = photos_base[:n_slots]

    with st.expander(f"📄  {fname}", expanded=True):

        if n_slots < needed:
            st.warning(f"ตรวจพบ {n_slots} ภาพ / Layout {layout} ต้องการ {needed} ภาพ — ช่องที่ขาดจะเว้นว่าง")

        # ── Variant selector ──────────────────────────────────────────────────
        n_variants = len(vparts)
        vcols = st.columns(max(n_variants, 1), gap="small")
        for i, vc in enumerate(vcols):
            is_sel = i == sel_idx
            with vc:
                lbl = f"แบบ {i+1}" + ("  ✓" if is_sel else "")
                if st.button(lbl, key=f"v_{fname}_{i}",
                             type="primary" if is_sel else "secondary",
                             width="stretch"):
                    st.session_state.selected[fname] = i
                    st.rerun()

        st.markdown(" ")

        # ── Main 2-panel layout ───────────────────────────────────────────────
        panel_left, panel_right = st.columns([3, 2], gap="large")

        # ── LEFT: crop grid ───────────────────────────────────────────────────
        with panel_left:
            st.markdown('<p class="sec-lbl">ลากกรอบ = ปรับ crop  ·  ⇄ = กลับภาพ</p>',
                        unsafe_allow_html=True)

            cropped: list = [None] * n_slots
            n_rows = math.ceil(n_slots / 2)

            for row in range(n_rows):
                g_col1, g_col2 = st.columns(2, gap="small")

                for col_idx, g_col in enumerate([g_col1, g_col2]):
                    si = row * 2 + col_idx
                    if si >= n_slots:
                        break

                    _, _, sw, sh = slots_info[si]
                    photo_orig = photos[si]
                    flip_key   = f"flip_{fname}_{sel_idx}_{si}"
                    is_flipped = st.session_state.get(flip_key, False)

                    photo = (photo_orig.transpose(Image.FLIP_LEFT_RIGHT)
                             if is_flipped else photo_orig)

                    with g_col:
                        h_lbl, h_flip = st.columns([5, 1])
                        with h_lbl:
                            st.caption(labels[si])
                        with h_flip:
                            flip_label = "⇄✓" if is_flipped else "⇄"
                            if st.button(flip_label,
                                         key=f"tog_flip_{fname}_{sel_idx}_{si}",
                                         type="primary" if is_flipped else "secondary",
                                         help="กลับภาพซ้าย↔ขวา"):
                                st.session_state[flip_key] = not is_flipped
                                st.rerun()

                        result = st_cropper(
                            _cap(photo),
                            realtime_update=True,
                            box_color="#7c3aed",
                            aspect_ratio=(sw, sh),
                            return_type="image",
                            key=f"crop_{fname}_{sel_idx}_{si}{'_f' if is_flipped else ''}",
                        )
                        cropped[si] = result

        # ── RIGHT: compose fresh from current layout ──────────────────────────
        with panel_right:
            st.markdown('<p class="sec-lbl">ผลลัพธ์ — 1080 × 1080 px</p>',
                        unsafe_allow_html=True)

            valid = [c for c in cropped if c is not None]
            if len(valid) == n_slots:
                chosen = compose_direct(valid, layout)
            else:
                # Fresh compose — always uses current layout, no stale cache
                chosen = compose(photos[:n_slots], layout=layout, respect_order=True)

            st.image(chosen, width="stretch")
            st.markdown(" ")

            buf = io.BytesIO()
            chosen.save(buf, format="JPEG", quality=95)
            b   = buf.getvalue()
            out = fname.rsplit(".", 1)[0] + f"_v{sel_idx+1}_out.jpg"
            st.download_button(
                f"⬇  ดาวน์โหลด แบบ {sel_idx+1}  ·  1080×1080 px",
                data=b, file_name=out, mime="image/jpeg", width="stretch",
            )
            all_dl.append((out, b))


# ── Batch ZIP ─────────────────────────────────────────────────────────────────
if len(all_dl) > 1:
    st.markdown("---")
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, d in all_dl:
            zf.writestr(n, d)
    st.download_button(
        f"⬇  ดาวน์โหลดทั้งหมด {len(all_dl)} ไฟล์  (ZIP)",
        data=zb.getvalue(), file_name="metagenpicture_batch.zip",
        mime="application/zip", width="stretch", type="primary",
    )
