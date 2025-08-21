import streamlit as st
from PIL import Image, ImageDraw
import easyocr
import numpy as np
import json
import os

st.set_page_config(page_title="Banner QA – Text Zone Validation", layout="wide")

st.title("Banner QA – Text Zone Validation")

# --- File uploader ---
uploaded_file = st.file_uploader("Upload a banner", type=["png", "jpg", "jpeg"])

# --- OCR Reader (cache to avoid reloading) ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(["en"])
reader = load_reader()

# --- Overlap helper function ---
def box_overlap(b1, b2, threshold=0.3):
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    ix1 = max(x1, x2)
    iy1 = max(y1, y2)
    ix2 = min(x1 + w1, x2 + w2)
    iy2 = min(y1 + h1, y2 + h2)
    if ix2 <= ix1 or iy2 <= iy1:
        return False
    inter_area = (ix2 - ix1) * (iy2 - iy1)
    ocr_area = w1 * h1
    return inter_area / ocr_area >= threshold

# --- Save/Load Zone Presets ---
CONFIG_FILE = "zone_presets.json"
def save_presets(zones):
    with open(CONFIG_FILE, "w") as f:
        json.dump(zones, f, indent=4)
def load_presets():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

# --- Persistent Ignore List ---
IGNORE_FILE = "ignore_terms.json"
def save_ignore_terms():
    with open(IGNORE_FILE, "w") as f:
        json.dump(st.session_state["ignore_terms"], f, indent=4)
def load_ignore_terms():
    if os.path.exists(IGNORE_FILE):
        with open(IGNORE_FILE, "r") as f:
            return json.load(f)
    # defaults if no file yet
    return ["oled", "trademark", "draft"]

# Initialize ignore terms in session state
if "ignore_terms" not in st.session_state:
    st.session_state["ignore_terms"] = load_ignore_terms()
if "ignore_input" not in st.session_state:
    st.session_state["ignore_input"] = ""

# --- Default zones (normalized 0–1) ---
default_zone_defs = {
    "Eyebrow Copy": (0.125, 0.1042, 0.3047, 0.021),
    "Headline Copy": (0.125, 0.1458, 0.3047, 0.1458),
    "Body Copy": (0.125, 0.3027, 0.3047, 0.05),
}
loaded_presets = load_presets()
if loaded_presets:
    default_zone_defs = loaded_presets

st.sidebar.title("⚙️ Zone Settings")

# --- Overlap Threshold Control ---
with st.sidebar.expander("🔎 Detection Settings", expanded=False):
    overlap_threshold = st.slider(
        "Minimum overlap (%) for text to count as inside a zone",
        min_value=0.0, max_value=1.0, value=0.8, step=0.01, format="%.2f"
    )

# --- Zone Inputs ---
zones = {}
with st.sidebar.expander("📐 Define Text Zones", expanded=False):
    for zone_name, defaults in default_zone_defs.items():
        dx, dy, dw, dh = defaults
        st.markdown(f"**{zone_name}** (normalized 0–1 for width & height)")
        col1, col2 = st.columns(2)
        with col1:
            x = st.number_input(f"{zone_name} X", key=f"{zone_name}_x", min_value=0.0, max_value=1.0, value=dx, step=0.01, format="%.4f")
            w = st.number_input(f"{zone_name} W", key=f"{zone_name}_w", min_value=0.0, max_value=1.0, value=dw, step=0.01, format="%.4f")
        with col2:
            y = st.number_input(f"{zone_name} Y", key=f"{zone_name}_y", min_value=0.0, max_value=1.0, value=dy, step=0.01, format="%.4f")
            h = st.number_input(f"{zone_name} H", key=f"{zone_name}_h", min_value=0.0, max_value=1.0, value=dh, step=0.01, format="%.4f")
        zones[zone_name] = (x, y, w, h)

with st.sidebar.expander("💾 Save / Load Presets", expanded=False):
    if st.button("Save Current Preset"):
        save_presets(zones)
        st.success("✅ Preset saved!")
    if st.button("Load Preset"):
        loaded = load_presets()
        if loaded:
            for k, v in loaded.items():
                st.session_state[f"{k}_x"] = v[0]
                st.session_state[f"{k}_y"] = v[1]
                st.session_state[f"{k}_w"] = v[2]
                st.session_state[f"{k}_h"] = v[3]
            st.success("✅ Preset loaded!")
        else:
            st.warning("⚠️ No preset found.")

# --- Image Handling ---
if uploaded_file:
    img = Image.open(uploaded_file).convert("RGB")
    w, h = img.size
    aspect_ratio = w / h
    if abs(aspect_ratio - (8 / 3)) > 0.01:
        st.warning(f"⚠️ Image aspect ratio {w}:{h} ({aspect_ratio:.2f}) is not 8:3. No scaling applied.")
    else:
        st.info("✅ Image aspect ratio is 8:3.")
    draw = ImageDraw.Draw(img)

    abs_zones = {}
    for name, (zx, zy, zw, zh) in zones.items():
        abs_zones[name] = (int(zx * w), int(zy * h), int(zw * w), int(zh * h))

    results = reader.readtext(np.array(img))
    penalties = []
    score = 100
    used_zones = {z: False for z in abs_zones}

    # --- Ignore text rules ---
    with st.sidebar.expander("🚫 Ignore Text Rules", expanded=False):
        st.text_area(
            "Enter words/phrases to ignore (comma separated):",
            key="ignore_input",
            value=st.session_state["ignore_input"],
            help="Example: OLED, Trademark, Draft"
        )
        if st.button("Apply Ignore Terms"):
            new_terms = [term.strip().lower() for term in st.session_state["ignore_input"].split(",") if term.strip()]
            st.session_state["ignore_terms"].extend(new_terms)
            st.session_state["ignore_terms"] = list(set(st.session_state["ignore_terms"]))
            st.session_state["ignore_input"] = ""  # clear
            save_ignore_terms()
            st.success("✅ Ignore terms updated and saved!")

        if st.session_state["ignore_terms"]:
            st.markdown("**Currently Ignored:**")
            st.write(", ".join(st.session_state["ignore_terms"]))

    # Draw zones
    for zone_name, used in used_zones.items():
        zx, zy, zw, zh = abs_zones[zone_name]
        draw.rectangle([zx, zy, zx + zw, zy + zh], outline="green", width=3)

    if st.session_state["ignore_terms"]:
        st.info(f"🔎 Ignoring text matches for: {', '.join(st.session_state['ignore_terms'])}")

    score = max(score, 0)

    for (bbox, text, prob) in results:
        detected_text = text.lower().strip()

        # --- Ignored terms ---
        if any(term in detected_text for term in st.session_state["ignore_terms"]):
            xs = [int(p[0]) for p in bbox]
            ys = [int(p[1]) for p in bbox]
            tx, ty, tw, th = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            draw.rectangle([tx, ty, tx + tw, ty + th], outline="blue", width=3)
            continue

        xs = [int(p[0]) for p in bbox]
        ys = [int(p[1]) for p in bbox]
        tx, ty, tw, th = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        draw.rectangle([tx, ty, tx + tw, ty + th], outline="red", width=2)

        inside_any = False
        for zone_name, (zx, zy, zw, zh) in abs_zones.items():
            if zx <= tx and ty >= zy and (tx + tw) <= (zx + zw) and (ty + th) <= (zy + zh):
                inside_any = True
                used_zones[zone_name] = True
                break
        if not inside_any:
            penalties.append(("Text outside allowed zones", 20))
            score -= 20

    st.image(img, caption=f"QA Result – Score: {score}", use_container_width=True)
    if penalties:
        st.error("Infractions:")
        for p, pts in penalties:
            st.write(f"- {p} (-{pts})")
    else:
        st.success("Perfect score! ✅ All text inside zones.")
