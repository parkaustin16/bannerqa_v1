import streamlit as st
from PIL import Image, ImageDraw
import easyocr
import numpy as np
import json
import os

st.set_page_config(page_title="Banner QA – Text Zone Validation", layout="wide")
st.title("📐 Banner QA – Text Zone Validation")

# -----------------------------
# Utility functions
# -----------------------------
SETTINGS_FILE = "zone_presets.json"

def load_presets():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_presets(presets):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(presets, f, indent=4)

def preprocess_image(uploaded_file):
    img = Image.open(uploaded_file).convert("RGB")
    w, h = img.size
    aspect_ratio = round(w / h, 2)
    if abs(aspect_ratio - (8 / 3)) > 0.01:
        st.warning(f"⚠️ Image aspect ratio {w}:{h} ({aspect_ratio}) does not match required 8:3 ratio.")
    return img

# -----------------------------
# Sidebar Controls
# -----------------------------
st.sidebar.header("⚙️ Settings")

# Load/Save zone presets
presets = load_presets()
preset_name = st.sidebar.text_input("Preset Name")
if st.sidebar.button("💾 Save Current Zones"):
    presets[preset_name] = st.session_state.get("zones", {})
    save_presets(presets)
    st.sidebar.success(f"Preset '{preset_name}' saved!")

if presets:
    chosen_preset = st.sidebar.selectbox("📂 Load Preset", ["None"] + list(presets.keys()))
    if chosen_preset != "None":
        st.session_state["zones"] = presets[chosen_preset]
        st.sidebar.info(f"Loaded preset: {chosen_preset}")

# Ignore terms
ignore_input = st.sidebar.text_area("Ignore text containing (comma separated)", "")
ignore_terms = [t.strip().lower() for t in ignore_input.split(",") if t.strip()]

# -----------------------------
# File Upload
# -----------------------------
uploaded_file = st.file_uploader("Upload a banner", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = preprocess_image(uploaded_file)

    # -----------------------------
    # Define text zones (normalized 0-1)
    # -----------------------------
    if "zones" not in st.session_state:
        st.session_state["zones"] = {
            "Eyebrow Copy": (0.125, 0.1042, 0.3047, 0.021),
            "Headline Copy": (0.125, 0.1458, 0.3047, 0.1458),
            "Body Copy": (0.125, 0.3027, 0.3047, 0.05),
        }

    zones = {}
    with st.sidebar.expander("✏️ Edit Zones", expanded=True):
        for zone_name, params in st.session_state["zones"].items():
            st.markdown(f"**{zone_name}**")
            col1, col2 = st.columns(2)
            x = col1.number_input(f"{zone_name} X", 0.0, 1.0, params["x"], 0.0001, format="%.4f", key=f"{zone_name}_x")
            y = col2.number_input(f"{zone_name} Y", 0.0, 1.0, params["y"], 0.0001, format="%.4f", key=f"{zone_name}_y")
            w = col1.number_input(f"{zone_name} Width", 0.0, 1.0, params["w"], 0.0001, format="%.4f", key=f"{zone_name}_w")
            h = col2.number_input(f"{zone_name} Height", 0.0, 1.0, params["h"], 0.0001, format="%.4f", key=f"{zone_name}_h")
            zones[zone_name] = {"x": x, "y": y, "w": w, "h": h}

        # Update session state with latest edits
        st.session_state["zones"] = zones

    # -----------------------------
    # OCR + Zone Validation
    # -----------------------------
    image = img.copy()
    draw = ImageDraw.Draw(image)
    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(np.array(image))

    penalties = []
    score = 100
    ignored_texts = []

    img_w, img_h = image.size

    for (bbox, text, prob) in results:
        detected_text = text.lower().strip()

        xs = [int(p[0]) for p in bbox]
        ys = [int(p[1]) for p in bbox]
        tx, ty, tw, th = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

        # --- Ignore terms check ---
        if any(term in detected_text for term in ignore_terms):
            draw.rectangle([tx, ty, tx + tw, ty + th], outline="blue", width=3)
            ignored_texts.append(text)
            continue

        # Normal detection (red if outside, green if inside zone)
        inside_any = False
        for zone_name, z in zones.items():
            zx, zy, zw, zh = z["x"] * img_w, z["y"] * img_h, z["w"] * img_w, z["h"] * img_h
            if zx <= tx and ty >= zy and (tx + tw) <= (zx + zw) and (ty + th) <= (zy + zh):
                inside_any = True
                draw.rectangle([tx, ty, tx + tw, ty + th], outline="green", width=3)
                break

        if not inside_any:
            draw.rectangle([tx, ty, tx + tw, ty + th], outline="red", width=2)
            penalties.append(("Text outside allowed zones", 20))
            score -= 20

    # Draw zone boxes
    for zone_name, z in zones.items():
        zx, zy, zw, zh = z["x"] * img_w, z["y"] * img_h, z["w"] * img_w, z["h"] * img_h
        draw.rectangle([zx, zy, zx + zw, zy + zh], outline="yellow", width=2)

    score = max(score, 0)

    # -----------------------------
    # Output
    # -----------------------------
    st.image(image, caption=f"QA Result – Score: {score}", use_container_width=True)

    if penalties:
        st.error("Infractions:")
        for p, pts in penalties:
            st.write(f"- {p} (-{pts})")
    else:
        st.success("✅ No infractions found!")

    if ignored_texts:
        st.info("Ignored Texts (shown in blue):")
        for t in ignored_texts:
            st.write(f"- {t}")
