import pandas as pd
import plotly.express as px
import streamlit as st

import cases_db as C
import digital as D
import ui


def render():
    ui.hero("Digital forensics", "Acquire → verify → examine: hashing, file signatures, entropy, artefacts, EXIF / GPS and image "
            "tampering analysis. Files are processed in memory and never leave the server.", ["WRITE-BLOCK MINDSET", "HASH VERIFIED"])
    a, b = st.columns([3, 2])
    up = a.file_uploader("Exhibit file (any type)")
    if b.button("Load demo exhibit (photo with EXIF/GPS, renamed .pdf, edited region)", type="primary"):
        st.session_state.fx_dig = ("IMG_2026_evidence.pdf", D.make_demo_photo())
    if up is not None:
        st.session_state.fx_dig = (up.name, up.getvalue())
    if "fx_dig" not in st.session_state:
        st.info("Upload a file or load the demo exhibit.")
        return
    name, data = st.session_state.fx_dig
    h = D.hashes(data)
    sig = D.signature(data, name)
    ent = D.entropy(data)
    ui.kpis([("File", name[:28]), ("Size", f"{len(data):,} B"), ("Detected type", sig["detected"].split(" (")[0]), ("Entropy (bits/byte)", f"{ent:.2f}")])
    st.write("")
    if sig["mismatch"]:
        st.error(f"⚠️ **Extension mismatch:** named `.{sig['extension']}` but the file header (magic bytes `{sig['magic (hex)']}`) says "
                 f"**{sig['detected']}**. Renaming files is a common way to hide content.")
    t = st.tabs(["#️⃣ Hashes & verification", "📈 Entropy", "🔤 Strings & IOCs", "📷 EXIF & GPS", "🖼️ Tampering (ELA)", "💾 Save to case"])
    with t[0]:
        st.dataframe(pd.DataFrame(h.items(), columns=["algorithm", "digest"]), hide_index=True)
        ref = st.text_input("Verify against an acquisition hash (paste MD5 / SHA-1 / SHA-256)")
        if ref:
            ok = ref.strip().lower() in h.values()
            ui.status_badge(ok, "✔ Hash matches — the exhibit is unchanged since acquisition" if ok else "✖ Hash does NOT match — integrity cannot be confirmed")
        st.caption("Investigators hash media at acquisition and re-hash before analysis and in court. MD5/SHA-1 have known collisions; "
                   "SHA-256 is the current standard.")
    with t[1]:
        prof = D.entropy_profile(data)
        st.plotly_chart(px.line(y=prof, labels={"x": "block (4 KB)", "y": "Shannon entropy (bits/byte)"},
                                title="Entropy by block — ~8 = compressed or encrypted, low = text / empty space", range_y=[0, 8.1]), key="fx_ent")
        st.write("High, flat entropy across a whole file suggests encryption (e.g. a VeraCrypt container or ransomware output); "
                 "JPEG/ZIP are also high because they are compressed.")
    with t[2]:
        io_ = D.iocs(data)
        st.dataframe(pd.DataFrame([{"type": k, "count": len(v), "examples": ", ".join(v[:5])} for k, v in io_.items()]), hide_index=True)
        n = st.slider("Minimum string length", 4, 20, 6)
        ss = D.strings(data, n)
        st.text_area(f"{len(ss)} printable strings", "\n".join(ss[:400]), height=220)
    with t[3]:
        ex, gps = D.exif(data)
        if len(ex) > 3:
            st.dataframe(pd.DataFrame(ex.items(), columns=["tag", "value"]).astype(str), hide_index=True)
            if "Software" in ex:
                st.warning(f"Software tag = **{ex['Software']}** — the image was processed by editing software after capture.")
        else:
            st.info("No EXIF metadata (not an image, or metadata stripped — social media usually strips it).")
        if gps:
            st.success(f"📍 GPS location embedded: {gps['lat']:.6f}, {gps['lon']:.6f}")
            st.map(pd.DataFrame([gps]), latitude="lat", longitude="lon", zoom=12)
    with t[4]:
        try:
            q = st.slider("Re-save quality", 70, 98, 90)
            sc = st.slider("Amplification", 5, 40, 15)
            c1, c2 = st.columns(2)
            c1.image(data, caption="Original", width="stretch")
            c2.image(D.ela(data, q, sc), caption="Error level analysis", width="stretch")
            st.caption("Regions pasted from another image (or edited) often show a different error level — bright edges/blocks. "
                       "ELA is a screening tool: always confirm with other methods (noise analysis, metadata, source camera).")
        except Exception:
            st.info("ELA works on images (JPEG best).")
    with t[5]:
        cs = C.cases()
        cid = st.selectbox("Case", list(cs.case_id), format_func=lambda x: f"{x} — {cs.set_index('case_id').title[x]}")
        if st.button("Register as evidence item with SHA-256 and save findings"):
            iid = C.add_evidence(cid, f"Digital exhibit {name}", "Photograph / video" if "image" in sig["detected"].lower() else "USB drive",
                                 "Digital examiner", pd.Timestamp.today().date().isoformat(), "Lab - digital", h["SHA-256"])
            C.add_result(cid, iid, "Digital forensics", f"{sig['detected']}; extension mismatch: {sig['mismatch']}; entropy {ent:.2f}"
                         + (f"; GPS {gps['lat']:.5f},{gps['lon']:.5f}" if (gps := D.exif(data)[1]) else ""), {"hashes": h}, "Digital examiner")
            st.success(f"Saved as {iid}")
