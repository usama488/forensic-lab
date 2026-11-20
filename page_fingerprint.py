import numpy as np
import plotly.graph_objects as go
import streamlit as st

import cases_db as C
import fingerprint as F
import ui

DEMOS = {"Same finger (latent vs. ten-print, rotated & noisier)": (("whorl", 1, 0, (0, 0), .25), ("whorl", 1, 8, (6, -5), .38)),
         "Different fingers (both whorls)": (("whorl", 1, 0, (0, 0), .25), ("whorl", 5, 0, (0, 0), .25)),
         "Different pattern (loop vs. whorl)": (("loop", 2, 0, (0, 0), .25), ("whorl", 1, 0, (0, 0), .25))}


@st.cache_data(show_spinner=False)
def _process(img_bytes: bytes, shape):
    img = np.frombuffer(img_bytes, np.uint8).reshape(shape)
    e = F.enhance(img)
    return e, F.minutiae(e["skeleton"], e["mask"]), F.core_point(img)


def _fig(img, m, core, title, show_skel=None):
    fig = go.Figure(go.Heatmap(z=(show_skel * 255 if show_skel is not None else img)[::-1], colorscale="gray", showscale=False,
                               reversescale=show_skel is not None))
    h = img.shape[0]
    for typ, col, sym in (("ridge ending", "#E74C3C", "circle-open"), ("bifurcation", "#2E86C1", "square-open")):
        pts = [p for p in m if p["type"] == typ]
        fig.add_scatter(x=[p["x"] for p in pts], y=[h - p["y"] for p in pts], mode="markers", name=f"{typ} ({len(pts)})",
                        marker=dict(color=col, size=11, symbol=sym, line=dict(width=2)))
    fig.add_scatter(x=[core[0]], y=[h - core[1]], mode="markers", name="core (est.)", marker=dict(symbol="x", size=14, color="#C9A227"))
    fig.update_layout(title=title, height=440, xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.02), margin=dict(l=0, r=0, t=40, b=0))
    return fig


def render():
    ui.hero("Fingerprint examination", "Ridge enhancement, minutiae extraction and comparison following the ACE-V method "
            "(Analysis, Comparison, Evaluation, Verification).", ["ACE-V", "MINUTIAE"])
    src = st.radio("Source", ["Demo prints (synthetic)", "Upload two images"], horizontal=True)
    if src.startswith("Demo"):
        demo = st.selectbox("Demo scenario", list(DEMOS))
        (p1, s1, r1, sh1, n1), (p2, s2, r2, sh2, n2) = DEMOS[demo]
        a = F.synthetic(p1, s1, r1, sh1, n1)
        b = F.synthetic(p2, s2, r2, sh2, n2)
        st.caption("Synthetic ridge patterns generated in the app (not real people's fingerprints).")
    else:
        u1, u2 = st.columns(2)
        f1 = u1.file_uploader("Questioned / latent print", type=["png", "jpg", "jpeg", "bmp", "tif"])
        f2 = u2.file_uploader("Known / ten-print", type=["png", "jpg", "jpeg", "bmp", "tif"])
        if not (f1 and f2):
            st.info("Upload both prints (grey-scale scans, ~500 dpi, dark ridges on light background work best).")
            return
        a, b = F.load(f1.getvalue()), F.load(f2.getvalue())
    ea, ma, ca = _process(a.tobytes(), a.shape)
    eb, mb, cb = _process(b.tobytes(), b.shape)
    view = st.radio("Display", ["Original + minutiae", "Skeleton + minutiae"], horizontal=True)
    c1, c2 = st.columns(2)
    sk = view.startswith("Skeleton")
    c1.plotly_chart(_fig(a, ma, ca, "Questioned print", ea["skeleton"] if sk else None), key="fp1")
    c2.plotly_chart(_fig(b, mb, cb, "Known print", eb["skeleton"] if sk else None), key="fp2")
    res = F.compare(ma, mb)
    ui.kpis([("Minutiae (questioned)", len(ma)), ("Minutiae (known)", len(mb)), ("Corresponding minutiae", res["paired"]),
             ("Similarity score", f"{res['score']:.2f}")])
    st.write("")
    if res["paired"] >= 12 and res["score"] >= .5:
        st.success(f"**Strong correspondence:** {res['paired']} minutiae align after rotating {res['angle']}° and shifting "
                   f"({res['dx']:.0f}, {res['dy']:.0f}) px. In ACE-V this would go to Evaluation and independent Verification.")
    elif res["paired"] >= 7:
        st.warning("Some correspondence — insufficient for a conclusion; examine more detail (level-3 features) or seek more prints.")
    else:
        st.error("Little or no correspondence — consistent with different sources (exclusion requires examiner assessment).")
    st.caption("Many countries no longer use a fixed point standard (e.g. 12 or 16 points); conclusions are holistic examiner "
               "judgements. The 2004 Madrid-bombing misidentification (Brandon Mayfield) shows why independent verification matters.")
    cs = C.cases()
    with st.expander("💾 Save comparison to a case"):
        cid = st.selectbox("Case", list(cs.case_id), key="fp_c")
        if st.button("Save", key="fp_s"):
            C.add_result(cid, "-", "Fingerprints", f"Minutiae comparison: {res['paired']} corresponding, score {res['score']:.2f}", res, "Fingerprint examiner")
            st.success("Saved")
