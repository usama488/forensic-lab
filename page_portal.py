import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

import cases_db as C
import ui

SERVICES = [
    ("🧬 Forensic DNA", "STR profiling (20 CODIS core loci), match statistics, paternity & kinship, mixtures, database searches."),
    ("💻 Digital forensics", "Evidence hashing, file-signature & entropy analysis, artefact/IOC extraction, EXIF-GPS, image tampering (ELA)."),
    ("🧪 Toxicology", "Blood-alcohol estimation (Widmark), back-calculation to the time of an incident, interpretation support."),
    ("⚰️ Forensic pathology", "Time-since-death estimation (Henssge nomogram, Glaister), post-mortem change reference."),
    ("🖐️ Fingerprints", "Ridge enhancement, minutiae extraction, alignment and comparison under ACE-V principles."),
    ("🗂️ Case & evidence management", "Case intake, evidence register, tamper-evident chain of custody, results and court reports."),
]


def render():
    ui.hero("Forensic Science Laboratory", "Integrated case management and analysis — biology, digital, toxicology, pathology and "
            "fingerprints, from evidence intake to court-ready report.", ["CHAIN OF CUSTODY", "ISO/IEC 17025-STYLE WORKFLOW", "DEMO"])
    cs, ev = C.cases(), C.evidence()
    closed = cs.dropna(subset=["closed"])
    tat = (pd.to_datetime(closed.closed) - pd.to_datetime(closed.opened)).dt.days.mean() if len(closed) else float("nan")
    overdue = ((pd.to_datetime(cs.due) < pd.Timestamp(dt.date.today())) & ~cs.status.isin(["Reported", "Closed"])).sum()
    ui.kpis([("Open cases", int((~cs.status.isin(["Closed"])).sum())), ("Evidence items", len(ev)), ("Reports issued",
             int(cs.status.isin(["Reported", "Closed"]).sum())), ("Avg. turnaround (days)", "—" if pd.isna(tat) else f"{tat:.0f}"),
             ("Overdue", int(overdue))])
    st.write("")
    st.subheader("Laboratory services")
    for i in range(0, len(SERVICES), 3):
        cols = st.columns(3)
        for col, (t, d) in zip(cols, SERVICES[i:i + 3]):
            ui.card(col, t, d)
        st.write("")
    a, b = st.columns(2)
    with a:
        st.plotly_chart(px.bar(cs.groupby(["section", "status"]).size().reset_index(name="cases"), x="section", y="cases", color="status",
                               title="Caseload by section and status", category_orders={"status": C.STATUSES}), key="p1")
    with b:
        cs["month"] = pd.to_datetime(cs.opened).dt.to_period("M").astype(str)
        st.plotly_chart(px.pie(cs, names="priority", hole=.55, title="Cases by priority",
                               color_discrete_sequence=["#0B1F3A", "#C9A227", "#24507F", "#9FB3C8"]), key="p2")
    st.subheader("📥 Submit a new case")
    with st.form("submit"):
        x = st.columns(3)
        title = x[0].text_input("Case title", "Suspicious death - apartment 4B")
        agency = x[1].text_input("Submitting agency", "City Police")
        offence = x[2].text_input("Offence / matter", "Unexplained death")
        y = st.columns(4)
        section = y[0].selectbox("Primary section", C.SECTIONS)
        priority = y[1].selectbox("Priority", ["Routine", "High", "Urgent"])
        inv = y[2].text_input("Investigating officer", "")
        due = y[3].date_input("Required by", dt.date.today() + dt.timedelta(days=30))
        desc = st.text_area("Circumstances", "")
        st.markdown("**First evidence item**")
        z = st.columns(4)
        item = z[0].text_input("Item description", "Swab from door handle")
        typ = z[1].selectbox("Evidence type", C.EVIDENCE_TYPES)
        by = z[2].text_input("Collected by", "SOCO")
        loc = z[3].text_input("Collection location", "Scene")
        if st.form_submit_button("Submit case", type="primary"):
            cid = C.create_case(title=title, agency=agency, offence=offence, section=section, priority=priority, investigator=inv,
                                due=due.isoformat(), description=desc)
            iid = C.add_evidence(cid, item, typ, by, dt.date.today().isoformat(), loc)
            st.success(f"Case **{cid}** created with item **{iid}**. Open it in 🗂️ Cases & custody.")
    st.caption("All cases shown are fictional demonstration data. This software illustrates forensic workflows for education; "
               "operational use requires validated methods, accreditation and qualified examiners.")
