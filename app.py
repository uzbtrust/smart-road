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
from smartroad.pci.from_detections import CLASS_TO_DISTRESS, pci_from_detections

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
HF_REPO = "uzbtrust/smart-road-pci-yolo11"
WEIGHTS = "yolo11l_640_best.pt"

#: Only the first eight heads were trained; see the model card.
TRAINED_CLASSES = tuple(range(8))

COLOURS = {
    "longitudinal_transverse_crack": "#ff5a5a",
    "alligator_crack": "#4fb8ff",
    "block_crack": "#ffc93c",
    "patching": "#7bed7b",
    "pothole": "#ff5aff",
    "weathering_raveling": "#ff9a3c",
    "lane_shoulder_drop_off": "#b0b0ff",
    "marking_manhole": "#9aa0a6",
}

RATING_COLOUR = {
    "Good": "#1a9850", "Satisfactory": "#66bd63", "Fair": "#fee08b",
    "Poor": "#fdae61", "Very Poor": "#f46d43", "Serious": "#d73027",
    "Failed": "#a50026",
}

st.set_page_config(page_title="Smart Road — PCI", page_icon="🛣️", layout="wide")


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
    d = ImageDraw.Draw(canvas)
    d.rectangle(roi, outline="#00d26a", width=3)
    for det in dets:
        name = names.get(det.class_id, str(det.class_id))
        colour = COLOURS.get(name, "#ffffff")
        d.rectangle(det.as_xyxy(), outline=colour, width=4)
        tag = f"{name} {det.confidence:.2f}" + (" ·seam" if det.on_seam else "")
        d.text((det.x1 + 5, max(det.y1 - 14, 0)), tag, fill=colour)
    return canvas


st.title("Smart Road")
st.caption(
    "Road-surface distresses detected and graded through **ASTM D6433** — the "
    "standard that turns a distress survey into a Pavement Condition Index."
)

with st.sidebar:
    st.header("Image")
    samples = sorted(SAMPLES.glob("*.jpg")) if SAMPLES.is_dir() else []
    source = st.radio("Source", ["Sample", "Upload"], horizontal=True,
                      disabled=not samples, index=0 if samples else 1)
    image = None
    if source == "Sample" and samples:
        choice = st.selectbox("Sample", samples, format_func=lambda p: p.stem)
        image = Image.open(choice).convert("RGB")
    else:
        up = st.file_uploader("Road image", type=["jpg", "jpeg", "png"])
        if up:
            image = Image.open(io.BytesIO(up.read())).convert("RGB")

    st.header("Detection")
    conf = st.slider("Confidence", 0.05, 0.9, 0.25, 0.05)
    tiled = st.toggle("Tiled inference", value=True,
                      help="Detect on overlapping 640 px tiles instead of "
                           "resizing the whole frame down to 640.")
    overlap = st.slider("Tile overlap", 0.0, 0.5, 0.2, 0.05, disabled=not tiled)
    top = st.slider("Sky cut-off", 0.0, 0.9, 0.45, 0.05,
                    help="Fraction of the frame height ignored as sky and horizon.")

    st.header("Camera")
    st.caption("Ground area goes as height², so this is the largest single "
               "source of error in the PCI below.")
    height_m = st.number_input("Height above road (m)", 0.5, 4.0, 1.95, 0.05)
    focal_35 = st.number_input("Focal length, 35 mm equiv. (mm)", 10.0, 100.0, 25.0, 1.0)
    horizon = st.slider("Horizon row (fraction of height)", 0.0, 0.9, 0.139, 0.005)
    far_m = st.slider("Measure out to (m)", 4.0, 25.0, 15.0, 1.0)

    st.header("ASTM")
    severity = st.select_slider("Severity applied to every detection",
                                ["low", "medium", "high"], value="medium")
    st.caption("The detector has no severity head — the training data carried "
               "no consistent L/M/H labels. Move this to see the range.")

if image is None:
    st.info("Choose a sample or upload a road image to begin.")
    st.stop()

model = load_model()
names = {i: n for i, n in model.names.items()}
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
        dets = [Detection(*map(float, b.xyxy[0].tolist()), float(b.conf), int(b.cls))
                for b in res.boxes]
        dets = [d for d in dets if d.y2 >= roi[1]]

left, right = st.columns([3, 2], gap="large")

with left:
    st.image(draw(image, dets, names, roi), use_container_width=True)
    st.caption(f"{len(dets)} detections · green box is the surface searched · "
               f"`seam` marks a box touching a tile edge, i.e. possibly a fragment")

camera = Camera.create(width=w, height=h, height_m=height_m,
                       focal_35mm=focal_35, horizon_row=horizon * h)

with right:
    try:
        result = pci_from_detections(dets, camera, severity=severity,
                                     class_names=names, roi=roi, near_m=3.0, far_m=far_m)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    colour = RATING_COLOUR.get(result.rating, "#888")
    st.markdown(
        f"<div style='background:{colour};color:#000;padding:1.1rem 1.3rem;"
        f"border-radius:12px'><div style='font-size:.85rem;opacity:.75'>"
        f"PAVEMENT CONDITION INDEX</div>"
        f"<div style='font-size:3rem;font-weight:700;line-height:1'>{result.pci:.0f}</div>"
        f"<div style='font-size:1.1rem;font-weight:600'>{result.rating}</div></div>",
        unsafe_allow_html=True)

    st.metric("Surface measured", f"{result.inspected_area_m2:.0f} m²",
              help="Ground area of the searched region, by inverse perspective "
                   "mapping. ASTM's asphalt sample unit is 232 ± 93 m².")

    if result.quantities:
        st.subheader("Distress densities")
        st.dataframe(
            [{"Distress": q.distress.replace("_", " "),
              "n": q.detections,
              "Amount": f"{q.amount:.1f} " + {"area": "m²", "linear": "m", "count": "×"}[q.unit],
              "Density": f"{q.density_pct:.2f} %"} for q in result.quantities],
            hide_index=True, use_container_width=True)

        st.subheader("ASTM deduct values")
        st.write(", ".join(f"{d:.1f}" for d in result.deduct_values) or "—")
        st.caption(f"max CDV {result.max_cdv:.1f} from q = {result.q} · "
                   f"PCI = 100 − CDV")
    else:
        st.info("No gradable distress found in the measurable band.")

    if result.excluded:
        st.caption("Excluded: " + ", ".join(f"{k} ×{v}" for k, v in result.excluded.items()))

with st.expander("How this number is produced, and what it assumes"):
    st.markdown(f"""
Detections become square metres and metres on the road plane by inverse
perspective mapping, those become densities over the measured surface, and ASTM
D6433's deduct-value curves turn the densities into a PCI between 0 and 100.

The engine reproduces the worked example printed in ASTM D6433-07 (the standard
gives max CDV 51 and PCI 49; this implementation gives 51.4 and 48.6).

What this figure is **not**:

- **A certified sample-unit PCI.** ASTM's asphalt sample unit is 232 ± 93 m²;
  this frame covers {result.inspected_area_m2:.0f} m². A real survey aggregates
  frames into sample units, which needs frame-to-frame deduplication.
- **Severity-aware.** Every detection is graded `{severity}` because the model
  does not predict severity. Moving that slider moves the PCI substantially,
  which is the honest picture of the uncertainty.
- **Insensitive to camera height.** Ground area goes as height², so a 10 % error
  in the {height_m:.2f} m above becomes a 21 % error in every density here.

`marking_manhole` is detected but never graded — road markings and manhole
covers are not pavement distresses. They are in the class list because they are
what a detector most often mistakes for one.
""")

st.divider()
st.caption(
    f"Model: [{HF_REPO}](https://huggingface.co/{HF_REPO}) · "
    f"Code: [github.com/uzbtrust/smart-road](https://github.com/uzbtrust/smart-road) · "
    f"running on `{device}`"
)
