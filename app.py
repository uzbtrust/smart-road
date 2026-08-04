"""Smart Road — detect road distresses and grade the surface with ASTM D6433.

    streamlit run app.py

Weights are pulled from Hugging Face on first use; `scripts/download_models.py`
does the same thing ahead of time.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

from smartroad.detect.tiled import detect_tiled, road_roi
from smartroad.geometry.ipm import Camera
from smartroad.pci.engine import RATING_SCALE
from smartroad.pci.from_detections import pci_from_detections

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
HF_REPO = "uzbtrust/smart-road-pci-yolo11"
KAGGLE_URL = "https://www.kaggle.com/datasets/uzbtrust/smartroad-yolo"
GITHUB_URL = "https://github.com/uzbtrust/smart-road"
WEIGHTS = "yolo11l_640_best.pt"

#: Only the first eight heads were trained; see the model card.
TRAINED_CLASSES = tuple(range(8))

COLOURS = {
    "longitudinal_transverse_crack": "#ff6b6b",
    "alligator_crack": "#4dabf7",
    "block_crack": "#ffd43b",
    "patching": "#69db7c",
    "pothole": "#f783ac",
    "weathering_raveling": "#ffa94d",
    "lane_shoulder_drop_off": "#b197fc",
    "marking_manhole": "#868e96",
}

PRETTY = {
    "longitudinal_transverse_crack": "Longitudinal / transverse crack",
    "alligator_crack": "Alligator crack",
    "block_crack": "Block crack",
    "patching": "Patching",
    "pothole": "Pothole",
    "weathering_raveling": "Weathering / raveling",
    "lane_shoulder_drop_off": "Lane / shoulder drop-off",
    "marking_manhole": "Marking / manhole",
}

UNIT_SUFFIX = {"area": "m²", "linear": "m", "count": "×"}

st.set_page_config(page_title="Smart Road — ASTM D6433 PCI",
                   page_icon="🛣️", layout="wide",
                   initial_sidebar_state="expanded")

CSS = """
<style>
  .block-container { padding-top: 2.2rem; max-width: 1500px; }
  #MainMenu, footer { visibility: hidden; }

  .sr-title { font-size: 2.35rem; font-weight: 750; letter-spacing: -.02em;
              margin: 0 0 .15rem 0; }
  .sr-sub   { font-size: 1.02rem; opacity: .72; margin: 0 0 .35rem 0; }
  .sr-links { font-size: .88rem; opacity: .6; margin-bottom: 1.4rem; }
  .sr-links a { text-decoration: none; }

  .sr-card { border-radius: 16px; padding: 1.35rem 1.5rem; }
  .sr-card .lbl { font-size: .74rem; letter-spacing: .16em; font-weight: 700;
                  opacity: .62; }
  .sr-card .val { font-size: 4.4rem; font-weight: 800; line-height: .96;
                  margin: .1rem 0 .1rem 0; }
  .sr-card .rate { font-size: 1.3rem; font-weight: 700; }

  .sr-stat { border: 1px solid rgba(140,140,160,.25); border-radius: 12px;
             padding: .8rem 1rem; }
  .sr-stat .k { font-size: .72rem; letter-spacing: .1em; opacity: .6;
                text-transform: uppercase; }
  .sr-stat .v { font-size: 1.5rem; font-weight: 700; }
  .sr-stat .u { font-size: .85rem; opacity: .6; font-weight: 500; }

  .sr-chain { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
              font-size: .95rem; line-height: 1.9; }
  .sr-chip { display:inline-block; padding:.12rem .5rem; border-radius:6px;
             background: rgba(140,140,160,.16); margin-right:.3rem; }

  .sr-note { font-size: .82rem; opacity: .6; }
  .sr-partner { border-left: 3px solid #4dabf7; padding: .55rem 0 .55rem .85rem;
                font-size: .86rem; opacity: .82; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Fetching weights from Hugging Face…")
def load_model():
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO

    local = ROOT / "models" / WEIGHTS
    path = str(local) if local.exists() else hf_hub_download(HF_REPO, WEIGHTS)
    return YOLO(path)


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def draw(image: Image.Image, dets, names, roi) -> Image.Image:
    canvas = image.copy()
    d = ImageDraw.Draw(canvas, "RGBA")
    w = max(2, canvas.width // 480)
    d.rectangle(roi, outline=(0, 210, 106, 190), width=w)
    for det in dets:
        name = names.get(det.class_id, str(det.class_id))
        colour = COLOURS.get(name, "#ffffff")
        d.rectangle(det.as_xyxy(), outline=colour, width=w + 1)
    return canvas


def scale_bar(pci: float) -> str:
    """ASTM D6433 Fig. 1 rating scale with the current score marked."""
    bands = sorted(RATING_SCALE, key=lambda b: b[0])          # low -> high
    segs = []
    for i, (lo, label, colour) in enumerate(bands):
        hi = bands[i + 1][0] if i + 1 < len(bands) else 100.0
        segs.append(f'<div style="flex:{hi - lo};background:{colour}" title="{label} {lo:.0f}-{hi:.0f}"></div>')
    return f"""
    <div style="margin:.55rem 0 .2rem 0">
      <div style="display:flex;height:11px;border-radius:6px;overflow:hidden">{''.join(segs)}</div>
      <div style="position:relative;height:20px">
        <div style="position:absolute;left:{max(0, min(100, pci)):.1f}%;transform:translateX(-50%);
                    font-size:1.05rem;line-height:1">▲</div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:.7rem;opacity:.55">
        <span>0 Failed</span><span>55 Fair</span><span>100 Good</span>
      </div>
    </div>"""


# ────────────────────────────────────────────────────────────── header
st.markdown('<div class="sr-title">Smart Road</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sr-sub">Road-surface distresses detected and graded through '
    '<b>ASTM D6433</b> — the standard that turns a distress survey into a '
    'Pavement Condition Index.</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sr-links"><a href="{GITHUB_URL}">Code</a> · '
    f'<a href="https://huggingface.co/{HF_REPO}">Weights</a> · '
    f'<a href="{KAGGLE_URL}">Dataset</a></div>', unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────── sidebar
with st.sidebar:
    st.markdown("### Image")
    samples = sorted(SAMPLES.glob("*.jpg")) if SAMPLES.is_dir() else []
    source = st.radio("Source", ["Sample", "Upload"], horizontal=True,
                      label_visibility="collapsed",
                      disabled=not samples, index=0 if samples else 1)
    image = None
    if source == "Sample" and samples:
        choice = st.selectbox("Sample", samples,
                              format_func=lambda p: p.stem.replace("_", " "))
        image = Image.open(choice).convert("RGB")
    else:
        up = st.file_uploader("Road image", type=["jpg", "jpeg", "png"])
        if up:
            image = Image.open(io.BytesIO(up.read())).convert("RGB")

    st.markdown("### Detection")
    conf = st.slider("Confidence", 0.05, 0.90, 0.25, 0.05)
    tiled = st.toggle("Tiled inference", value=True,
                      help="Detect on overlapping 640 px tiles instead of "
                           "resizing the whole frame down to 640. On a 4 K "
                           "frame that resize is 6×, and a crack four pixels "
                           "wide in training falls below one pixel.")
    overlap = st.slider("Tile overlap", 0.0, 0.5, 0.20, 0.05, disabled=not tiled)
    top = st.slider("Sky cut-off", 0.0, 0.90, 0.45, 0.05,
                    help="Fraction of frame height ignored as sky and horizon.")

    st.markdown("### Camera")
    st.caption("Ground area goes as height², so this is the largest single "
               "source of error in the score.")
    height_m = st.number_input("Height above road (m)", 0.5, 4.0, 1.95, 0.05)
    focal_35 = st.number_input("Focal length, 35 mm equiv. (mm)", 10.0, 100.0, 25.0, 1.0)
    horizon = st.slider("Horizon row", 0.0, 0.90, 0.139, 0.005)
    far_m = st.slider("Measure out to (m)", 4.0, 25.0, 15.0, 1.0)

    st.markdown("### ASTM severity")
    severity = st.select_slider("Applied to every detection",
                                ["low", "medium", "high"], value="medium")
    st.caption("The detector has no severity head. Move this to see the range "
               "the answer really occupies.")

if image is None:
    st.info("Choose a sample or upload a road image to begin.")
    st.stop()

# ────────────────────────────────────────────────────────────── inference
model = load_model()
names = dict(model.names)
frame = np.array(image)
h, w = frame.shape[:2]
roi = road_roi(w, h, top_fraction=top)
device = pick_device()

with st.spinner("Detecting…"):
    if tiled:
        dets = detect_tiled(model, frame, tile=640, overlap=overlap, roi=roi,
                            conf=conf, classes=TRAINED_CLASSES, device=device)
    else:
        from smartroad.detect.tiled import Detection

        res = model.predict(frame, imgsz=640, conf=conf, device=device,
                            classes=list(TRAINED_CLASSES), verbose=False)[0]
        dets = [Detection(*map(float, b.xyxy[0].tolist()),
                          float(b.conf), int(b.cls)) for b in res.boxes]
        dets = [d for d in dets if d.y2 >= roi[1]]

camera = Camera.create(width=w, height=h, height_m=height_m,
                       focal_35mm=focal_35, horizon_row=horizon * h)
try:
    result = pci_from_detections(dets, camera, severity=severity,
                                 class_names=names, roi=roi, near_m=3.0, far_m=far_m)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

# ────────────────────────────────────────────────────────────── layout
left, right = st.columns([1.55, 1], gap="large")

with left:
    st.image(draw(image, dets, names, roi), use_container_width=True)
    seams = sum(1 for d in dets if d.on_seam)
    st.markdown(
        f'<div class="sr-note">{len(dets)} detections · {w}×{h} px · '
        f'green outline is the surface searched'
        + (f' · {seams} box(es) touch a tile seam, i.e. possibly one distress '
           f'split in two' if seams else '')
        + '</div>', unsafe_allow_html=True)

    if dets:
        seen = {names.get(d.class_id) for d in dets}
        chips = " ".join(
            f'<span style="display:inline-block;margin:.2rem .35rem .2rem 0;'
            f'font-size:.8rem"><span style="display:inline-block;width:10px;'
            f'height:10px;border-radius:3px;background:{COLOURS.get(n, "#fff")};'
            f'margin-right:.35rem"></span>{PRETTY.get(n, n)}</span>'
            for n in sorted(seen))
        st.markdown(chips, unsafe_allow_html=True)

    with st.expander("How this number is produced, and what it assumes"):
        st.markdown(f"""
Detections become square metres and metres on the road plane by inverse
perspective mapping, those become densities over the measured surface, and ASTM
D6433's deduct-value curves turn the densities into a PCI between 0 and 100.

The engine reproduces the worked example printed in ASTM D6433-07: the standard
gives max CDV **51** and PCI **49**, this implementation gives **51.4** and
**48.6**.

What this figure is **not**:

- **A certified sample-unit PCI.** ASTM's asphalt sample unit is 232 ± 93 m²;
  this frame covers {result.inspected_area_m2:.0f} m². A real survey aggregates
  frames into sample units, which needs frame-to-frame deduplication.
- **Severity-aware.** Every detection is graded `{severity}` because the model
  does not predict severity. Moving that slider moves the PCI substantially,
  which is the honest picture of the uncertainty.
- **Insensitive to camera height.** Ground area goes as height², so a 10 % error
  in the {height_m:.2f} m above becomes a 21 % error in every density here.

`Marking / manhole` is detected but never graded — road markings and manhole
covers are not pavement distresses. They are in the class list because they are
what a detector most often mistakes for one.
""")

with right:
    _, colour = next((r[1], r[2]) for r in RATING_SCALE if result.pci >= r[0])
    # ASTM's own band colours run from pale yellow to near-black, so the card
    # text has to follow the background rather than assume one or the other.
    r8, g8, b8 = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * r8 + 0.7152 * g8 + 0.0722 * b8
    ink = "#0b0b0c" if lum > 0.45 else "#ffffff"
    st.markdown(
        f'<div class="sr-card" style="background:{colour};color:{ink}">'
        f'<div class="lbl">PAVEMENT CONDITION INDEX</div>'
        f'<div class="val">{result.pci:.0f}</div>'
        f'<div class="rate">{result.rating}</div></div>',
        unsafe_allow_html=True)
    st.markdown(scale_bar(result.pci), unsafe_allow_html=True)

    a, b = st.columns(2)
    a.markdown(f'<div class="sr-stat"><div class="k">Surface measured</div>'
               f'<div class="v">{result.inspected_area_m2:.0f}'
               f'<span class="u"> m²</span></div></div>', unsafe_allow_html=True)
    b.markdown(f'<div class="sr-stat"><div class="k">Distress types</div>'
               f'<div class="v">{len(result.quantities)}'
               f'<span class="u"> / {len(dets)} boxes</span></div></div>',
               unsafe_allow_html=True)

    if result.quantities:
        st.markdown("##### Densities")
        st.dataframe(
            [{"Distress": PRETTY.get(q.distress, q.distress).replace("_", " "),
              "n": q.detections,
              "Quantity": f"{q.amount:.1f} {UNIT_SUFFIX[q.unit]}",
              "Density": f"{q.density_pct:.2f} %"} for q in result.quantities],
            hide_index=True, use_container_width=True)

        st.markdown("##### How ASTM gets from there to the score")
        chain = " ".join(f'<span class="sr-chip">{d:.1f}</span>'
                         for d in result.deduct_values)
        st.markdown(
            f'<div class="sr-chain">deduct values &nbsp;{chain}<br>'
            f'corrected (q = {result.q}) &nbsp;<b>{result.max_cdv:.1f}</b><br>'
            f'PCI = 100 − {result.max_cdv:.1f} = <b>{result.pci:.1f}</b></div>',
            unsafe_allow_html=True)
    else:
        st.info("No gradable distress inside the measurable band.")

    if result.excluded:
        st.markdown('<div class="sr-note">Excluded: '
                    + ", ".join(f"{k} ×{v}" for k, v in result.excluded.items())
                    + "</div>", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────── footer
st.divider()
st.markdown(
    '<div class="sr-partner"><b>Project partner —</b> '
    '<a href="https://github.com/BeEngineer-UZ">Raximjon Soataliyev</a>, road '
    'engineer and lecturer at Tashkent State Transport University. The ASTM '
    'D6433 framing this is built on is his, as is the hand-measured survey of '
    '1,810 m of Yangizamon street that every result is validated against.'
    '</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sr-note" style="margin-top:.7rem">'
    f'<a href="{GITHUB_URL}">github.com/uzbtrust/smart-road</a> · '
    f'<a href="https://huggingface.co/{HF_REPO}">{HF_REPO}</a> · '
    f'running on <code>{device}</code></div>', unsafe_allow_html=True)
