import streamlit as st
import easyocr
import json
import os
import cv2
import numpy as np
from PIL import Image

# ===================== Persistent Storage =====================
SETTINGS_FILE = "zones.json"
IGNORE_TERMS_FILE = "ignore_terms.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

def load_ignore_terms():
    if os.path.exists(IGNORE_TERMS_FILE):
        with open(IGNORE_TERMS_FILE, "r") as f:
            return json.load(f)
    return []

def save_ignore_terms(terms):
    with open(IGNORE_TERMS_FILE, "w") as f:
        json.dump(terms, f, indent=4)

# ===================== OCR =====================
reader = easyocr.Reader(['en'], gpu=False)

# ===================== Sidebar =====================
st.sidebar.title("⚙️ Settings")

# Zones config
with st.sidebar.expander("📐 Zone Settings", expanded=False):
    if "zones" not in st.session_state:
        st.session_state["zones"] = load_settings()

    for zone_name in ["Eyebrow Copy", "Headline Copy", "Body Copy"]:
        if zone_name not in st.session_state["zones"]:
            st.session_state["zones"][zone_name] = {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.1}

        st.markdown(f"**{zone_name}**")
        col1, col2 = st.columns(2)
        x = col1.number_input(f"{zone_name} X", 0.0, 1.0, st.session_state["zones"][zone_name]["x"], 0.0001, format="%.4f", key=f"{zone_name}_x")
        y = col2.number_input(f"{zone_name} Y", 0.0, 1.0, st.session_state["zones"][zone_name]["y"], 0.0001, format="%.4f", key=f"{zone_name}_y")
        w = col1.number_input(f"{zone_name} W", 0.0, 1.0, st.session_state["zones"][zone_name]["w"], 0.0001, format="%.4f", key=f"{zone_name}_w")
        h = col2.number_input(f"{zone_name} H", 0.0, 1.0, st.session_state["zones"][zone_name]["h"], 0.0001, format="%.4f", key=f"{zone_name}_h")

        st.session_state["zones"][zone_name] = {"x": x, "y": y, "w": w, "h": h}

    if st.button("💾 Save Zone Settings"):
        save_settings(st.session_state["zones"])
        st.success("Zone settings saved!")

# Ignore settings
with st.sidebar.expander("🛑 Ignore Settings", expanded=False):

    # Load persistent ignore terms
    if "persistent_ignore_terms" not in st.session_state:
        st.session_state["persistent_ignore_terms"] = load_ignore_terms()
    if "ignore_input" not in st.session_state:
        st.session_state["ignore_input"] = ""

    ignore_input = st.text_area(
        "Enter words/phrases to ignore (comma separated):",
        value=st.session_state["ignore_input"],
        key="ignore_input_widget"
    )

    if st.button("Apply Ignore Terms"):
        new_terms = [t.strip().lower() for t in ignore_input.split(",") if t.strip()]
        st.session_state["persistent_ignore_terms"].extend(new_terms)
        st.session_state["persistent_ignore_terms"] = sorted(set(st.session_state["persistent_ignore_terms"]))
        save_ignore_terms(st.session_state["persistent_ignore_terms"])
        # safely clear input
        st.session_state["ignore_input"] = ""
        st.session_state["ignore_input_widget"] = ""
        st.experimental_rerun()

    if st.session_state["persistent_ignore_terms"]:
        st.markdown("**Ignored Texts (Persistent):**")
        for term in st.session_state["persistent_ignore_terms"]:
            st.write(f"- {term}")

    # Ignore Zone
    if "ignore_zone" not in st.session_state:
        st.session_state["ignore_zone"] = {"x": 0.0, "y": 0.0, "w": 0.2, "h": 0.1}

    st.markdown("**Ignore Zone**")
    col1, col2 = st.columns(2)
    ix = col1.number_input("Ignore Zone X", 0.0, 1.0, st.session_state["ignore_zone"]["x"], 0.1149, format="%.4f", key="ignore_zone_x")
    iy = col2.number_input("Ignore Zone Y", 0.0, 1.0, st.session_state["ignore_zone"]["y"], 0.8958, format="%.4f", key="ignore_zone_y")
    iw = col1.number_input("Ignore Zone W", 0.0, 1.0, st.session_state["ignore_zone"]["w"], 0.8041, format="%.4f", key="ignore_zone_w")
    ih = col2.number_input("Ignore Zone H", 0.0, 1.0, st.session_state["ignore_zone"]["h"], 0.1959, format="%.4f", key="ignore_zone_h")
    st.session_state["ignore_zone"] = {"x": ix, "y": iy, "w": iw, "h": ih}

# ===================== Main App =====================
st.title("📊 Banner QA Tool (Aspect Ratio 8:3)")

uploaded_file = st.file_uploader("Upload a banner image", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file).convert("RGB")
    img_array = np.array(image)
    h, w, _ = img_array.shape

    results = reader.readtext(img_array)

    annotated = img_array.copy()

    # Draw zones
    for zone_name, params in st.session_state["zones"].items():
        zx, zy, zw, zh = params["x"], params["y"], params["w"], params["h"]
        x1, y1 = int(zx * w), int(zy * h)
        x2, y2 = int((zx + zw) * w), int((zy + zh) * h)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)  # green box

    # Draw ignore zone
    ix, iy, iw, ih = st.session_state["ignore_zone"].values()
    ix1, iy1 = int(ix * w), int(iy * h)
    ix2, iy2 = int((ix + iw) * w), int((iy + ih) * h)
    cv2.rectangle(annotated, (ix1, iy1), (ix2, iy2), (255, 0, 0), 2)  # blue box

    # Draw OCR results
    ignored_texts = []
    for (bbox, text, prob) in results:
        text_lower = text.lower()

        # bounding box points
        (tl, tr, br, bl) = bbox
        tl = tuple(map(int, tl))
        br = tuple(map(int, br))

        # Check if inside ignore zone
        cx, cy = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        inside_ignore_zone = ix1 <= cx <= ix2 and iy1 <= cy <= iy2

        # Check ignore terms
        ignore_term_match = any(term in text_lower for term in st.session_state["persistent_ignore_terms"])

        if inside_ignore_zone or ignore_term_match:
            cv2.rectangle(annotated, tl, br, (255, 0, 0), 2)
            ignored_texts.append(text)
        else:
            cv2.rectangle(annotated, tl, br, (0, 0, 255), 2)

    st.image(annotated, caption="Processed Image", use_container_width=True)

    if ignored_texts:
        st.subheader("📌 Ignored Texts:")
        for t in ignored_texts:
            st.write(f"- {t}")
