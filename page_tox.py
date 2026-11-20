import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import tox_path as T
import ui


def render():
    ui.hero("Toxicology & pathology", "Blood-alcohol estimation, back-calculation and time-since-death estimation.", ["WIDMARK", "HENSSGE"])
    t1, t2 = st.tabs(["🍺 Blood alcohol (Widmark)", "⚰️ Time since death"])
    with t1:
        a, b, c, d = st.columns(4)
        sex = a.selectbox("Sex", ["Male", "Female"])
        w = b.number_input("Body weight (kg)", 30.0, 250.0, 80.0)
        h = c.number_input("Height (cm)", 120.0, 220.0, 175.0)
        age = d.number_input("Age", 16, 100, 35)
        method = a.radio("Distribution factor r", ["Widmark (classic)", "Watson (body water)"], horizontal=True)
        beta = b.slider("Elimination rate β (‰ per hour)", .10, .25, .15, .01, help="Population range ≈ 0.10-0.25 g/kg/h; 0.15 typical.")
        fed = c.radio("Stomach", ["Empty", "After a meal"], horizontal=True)
        r = T.widmark_r(sex, w, h, age, method)
        st.markdown("**Drinks consumed**")
        dr = st.data_editor(pd.DataFrame({"drink": ["Beer 330 mL (5%)", "Spirits shot 40 mL (40%)"], "count": [3, 2]}),
                            column_config={"drink": st.column_config.SelectboxColumn(options=list(T.DRINKS))}, num_rows="dynamic", hide_index=True)
        g = sum(T.grams(*T.DRINKS[x.drink]) * x.count for x in dr.dropna().itertuples() if x.drink in T.DRINKS)
        hours = st.slider("Hours to plot", 2, 16, 8)
        t, bac = T.bac_curve(g, w, r, hours, beta, ka=4.0 if fed == "Empty" else 1.5)
        peak = bac.max()
        ui.kpis([("Pure ethanol", f"{g:.0f} g"), ("Widmark r", f"{r:.2f}"), ("Peak BAC", f"{peak:.2f} ‰ ≈ {peak / 10:.3f} g/100 mL"),
                 ("Sober (≈0) after", f"{t[np.argmax((bac < .01) & (t > t[np.argmax(bac)]))]:.1f} h" if (bac < .01)[np.argmax(bac):].any() else f"> {hours} h")])
        fig = go.Figure()
        fig.add_scatter(x=t, y=bac / 10, name="estimated BAC", line=dict(color="#0B1F3A", width=3))
        for name, lim in T.LIMITS.items():
            fig.add_hline(y=lim, line_dash="dot", annotation_text=name, annotation_position="top left", line_color="#C9A227")
        fig.update_layout(title="Estimated blood-alcohol curve", xaxis_title="hours since drinking started", yaxis_title="g/100 mL (%)", height=420)
        st.plotly_chart(fig, key="fx_bac")
        st.subheader("Back-calculation to the time of an incident")
        x1, x2 = st.columns(2)
        meas = x1.number_input("Measured BAC (g/100 mL)", 0.0, .6, .06, .005, format="%.3f")
        dt_ = x2.number_input("Hours between incident and blood sample", 0.0, 12.0, 2.0, .25)
        lo, hi = T.retrograde(meas, dt_)
        st.info(f"Estimated BAC at the incident: **{lo:.3f} – {hi:.3f} g/100 mL** (β 0.10–0.25 ‰/h). Valid only if absorption was "
                "complete before the incident; drinking after the incident ('hip-flask defence') invalidates it.")
        st.caption("Widmark: C = A / (r × W) − β × t. Individual variation is large; courts use ranges, not a single value.")
    with t2:
        a, b, c = st.columns(3)
        rt = a.number_input("Rectal temperature (°C)", 5.0, 42.0, 30.0, .1)
        at = b.number_input("Ambient temperature (°C)", -10.0, 40.0, 15.0, .5)
        wt = c.number_input("Body weight (kg)", 10.0, 200.0, 70.0)
        cond = st.selectbox("Clothing / environment (corrective factor)", list(T.CORRECTIVE))
        cf = T.CORRECTIVE[cond]
        r = T.henssge(rt, at, wt, cf)
        gl = T.glaister(rt)
        if r["hours"] is None:
            st.warning(r["note"])
        else:
            ui.kpis([("Henssge estimate", f"{r['hours']:.1f} h"), ("95% interval", f"{max(r['hours'] - r.get('ci95', 0), 0):.1f} – {r['hours'] + r.get('ci95', 0):.1f} h"),
                     ("Glaister (rough)", f"{gl:.1f} h"), ("Corrective factor", cf)])
            st.write("")
            tt = np.linspace(0, max(r["hours"] * 1.8, 12), 200)
            B = r.get("B", -.05)
            qq = 1.25 * np.exp(B * tt) - .25 * np.exp(5 * B * tt) if at <= 23 else 1.11 * np.exp(B * tt) - .11 * np.exp(10 * B * tt)
            fig = go.Figure()
            fig.add_scatter(x=tt, y=at + qq * (37.2 - at), name="Henssge cooling curve", line=dict(color="#0B1F3A", width=3))
            fig.add_scatter(x=[r["hours"]], y=[rt], mode="markers", marker=dict(size=14, color="#C9A227"), name="measured")
            fig.add_vrect(x0=max(r["hours"] - r.get("ci95", 0), 0), x1=r["hours"] + r.get("ci95", 0), fillcolor="#C9A227", opacity=.15, line_width=0)
            fig.update_layout(title="Body cooling (Newtonian double-exponential, Henssge 1988)", xaxis_title="hours since death",
                              yaxis_title="rectal temperature °C", height=420)
            st.plotly_chart(fig, key="fx_pmi")
            st.caption(r["note"] + " Glaister: hours ≈ (98.4 − rectal °F) / 1.5 — historical rule of thumb, ignores environment.")
        st.subheader("Post-mortem changes — reference")
        st.dataframe(pd.DataFrame(T.POSTMORTEM_SIGNS, columns=["sign", "typical course", "useful window"]), hide_index=True)
        st.caption("Combine several methods (temperature, rigor, lividity, entomology, scene evidence); each alone is imprecise.")
