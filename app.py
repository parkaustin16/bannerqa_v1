import streamlit as st
import json
from PIL import Image, ImageDraw
import os

IGNORE_TERMS_FILE = "ignore_terms.json"
IGNORE_ZONES_FILE = "ignore_zones.json"

# ----------------- Persistence Helpers -----------------
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ----------------- Initialize Session -----------------
if "ignore_terms" not in st.session_state:
    st.session_state["ignore_terms"] = load_json(IGNORE_TERMS_FILE, [])

if "ignore_zones" not in st.session_state:
    st.session_state["ignore_zones"] = load_json(IGNORE_ZONES_FILE, [])

# ----------------- Sidebar UI -----------------
st.sidebar.header("Ignore Settings")

# ---- Ignore Terms ----
with st.sidebar.expander("Manage Ignore Terms"):
    with st.form("add_ignore_term"):
        term = st.text_input("New Ignore Term")
        submitted = st.form_submit_button("Add Term")
    if submitted and term:
        st.session_state["ignore_terms"].append(term)
        save_json(IGNORE_TERMS_FILE, st.session_state["ignore_terms"])
        st.success(f"Added term: {term}")

    if st.session_state["ignore_terms"]:
        st.write("### Current Ignore Terms")
        for i, t in enumerate(st.session_state["ignore_terms"]):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"- {t}")
            with col2:
                if st.button("🗑️", key=f"del_term_{i}"):
                    st.session_state["ignore_terms"].pop(i)
                    save_json(IGNORE_TERMS_FILE, st.session_state["ignore_terms"])
                    st.experimental_rerun()

# ---- Ignore Zones ----
with st.sidebar.expander("Manage Ignore Zones"):
    with st.form("add_ignore_zone"):
        name = st.text_input("Zone name")
        x = st.number_input("X (%)", 0, 100, 10)
        y = st.number_input("Y (%)", 0, 100, 10)
        w = st.number_input("Width (%)", 1, 100, 30)
        h = st.number_input("Height (%)", 1, 100, 30)
        submitted = st.form_submit_button("Add Ignore Zone")

    if submitted and name:
        new_zone = {"name": name, "x": x, "y": y, "w": w, "h": h}
        st.session_state["ignore_zones"].append(new_zone)
        save_json(IGNORE_ZONES_FILE, st.session_state["ignore_zones"])
        st.success(f"Added ignore zone: {name}")

    if st.session_state["ignore_zones"]:
        st.write("### Current Ignore Zones")
        for i, zone in enumerate(st.session_state["ignore_zones"]):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(
                    f"**{zone['name']}** → (X:{zone['x']}%, Y:{zone['y']}%, "
                    f"W:{zone['w']}%, H:{zone['h']}%)"
                )
            with col2:
                if st.button("🗑️", key=f"del_zone_{i}"):
                    st.session_state["ignore_zones"].pop(i)
                    save_json(IGNORE_ZONES_FILE, st.session_state["ignore_zones"])
                    st.experimental_rerun()

# ----------------- Image Upload -----------------
uploaded_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    draw = ImageDraw.Draw(image)
    w, h = image.size

    # ----------------- Draw Saved Ignore Zones -----------------
    for zone in st.session_state["ignore_zones"]:
        ix = int(zone["x"] / 100 * w)
        iy = int(zone["y"] / 100 * h)
        iw = int(zone["w"] / 100 * w)
        ih = int(zone["h"] / 100 * h)
        draw.rectangle([ix, iy, ix + iw, iy + ih], outline="blue", width=3)
        draw.text((ix, max(0, iy - 15)), f"Ignore: {zone['name']}", fill="blue")

    # ----------------- Dummy OCR Simulation (Replace with real OCR) -----------------
    results = [
        ((50, 50, 150, 80), "Detected Headline", 0.95),
        ((200, 300, 300, 340), "Detected Body Copy", 0.90),
        ((100, 200, 250, 240), "Confidential Text", 0.85),
    ]

    for (bbox, text, prob) in results:
        tx, ty, tw, th = bbox
        ignored = False

        # Ignore by terms
        for term in st.session_state["ignore_terms"]:
            if term.lower() in text.lower():
                ignored = True
                draw.rectangle([tx, ty, tx + tw, ty + th], outline="blue", width=2)
                draw.text((tx, max(0, ty - 15)), f"Ignored Term: {text}", fill="blue")
                break

        # Ignore by zones
        if not ignored:
            for zone in st.session_state["ignore_zones"]:
                ix = int(zone["x"] / 100 * w)
                iy = int(zone["y"] / 100 * h)
                iw = int(zone["w"] / 100 * w)
                ih = int(zone["h"] / 100 * h)
                if tx >= ix and ty >= iy and (tx + tw) <= (ix + iw) and (ty + th) <= (iy + ih):
                    ignored = True
                    draw.rectangle([tx, ty, tx + tw, ty + th], outline="blue", width=2)
                    draw.text((tx, max(0, ty - 15)), f"Ignored Zone: {zone['name']}", fill="blue")
                    break

        # Draw OCR in red if not ignored
        if not ignored:
            draw.rectangle([tx, ty, tx + tw, ty + th], outline="red", width=2)
            draw.text((tx, max(0, ty - 15)), f"OCR: {text}", fill="red")

    # ----------------- Show Final Image -----------------
    st.image(image, caption="Processed Image", use_column_width=True)
