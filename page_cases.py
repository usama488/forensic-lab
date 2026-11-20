import datetime as dt

import plotly.express as px
import streamlit as st

import cases_db as C
import digital
import reports
import ui


def render():
    ui.hero("Cases & chain of custody", "Evidence register with a tamper-evident, SHA-256 hash-chained custody log.", ["CASE MANAGEMENT"])
    cs = C.cases()
    a, b, c = st.columns(3)
    fs = a.multiselect("Status", C.STATUSES)
    fsec = b.multiselect("Section", C.SECTIONS)
    q = c.text_input("Search", placeholder="title, agency, case number")
    v = cs
    if fs:
        v = v[v.status.isin(fs)]
    if fsec:
        v = v[v.section.isin(fsec)]
    if q:
        v = v[v.astype(str).apply(lambda r: r.str.contains(q, case=False)).any(axis=1)]
    st.dataframe(v[["case_id", "title", "section", "status", "priority", "opened", "due", "agency", "analyst"]], hide_index=True)
    if v.empty:
        return
    cid = st.selectbox("Open case", list(v.case_id), format_func=lambda x: f"{x} — {cs.set_index('case_id').title[x]}")
    case = cs.set_index("case_id").loc[cid].to_dict() | {"case_id": cid}
    st.markdown(f"### {case['title']}")
    x = st.columns(4)
    x[0].metric("Status", case["status"])
    x[1].metric("Priority", case["priority"])
    x[2].metric("Opened", case["opened"])
    x[3].metric("Due", case.get("due") or "-")
    s1, s2 = st.columns([3, 1])
    new = s1.select_slider("Workflow", C.STATUSES, value=case["status"])
    if s2.button("Update status") and new != case["status"]:
        C.set_status(cid, new)
        st.rerun()
    ev = C.evidence(cid)
    t1, t2, t3, t4 = st.tabs(["📦 Evidence", "🔗 Chain of custody", "🧾 Results", "📄 Case report"])
    with t1:
        st.dataframe(ev, hide_index=True)
        with st.expander("➕ Register evidence item"):
            with st.form(f"ev_{cid}"):
                y = st.columns(3)
                d = y[0].text_input("Description")
                typ = y[1].selectbox("Type", C.EVIDENCE_TYPES)
                by = y[2].text_input("Collected by", "SOCO")
                z = st.columns(2)
                when = z[0].date_input("Collected on", dt.date.today())
                loc = z[1].text_input("Location", "Scene")
                f = st.file_uploader("Digital exhibit / photo (optional) — SHA-256 will be recorded")
                if st.form_submit_button("Register") and d:
                    sha = digital.hashes(f.getvalue())["SHA-256"] if f else ""
                    iid = C.add_evidence(cid, d, typ, by, when.isoformat(), loc, sha)
                    st.success(f"Registered {iid}" + (f" (SHA-256 {sha[:16]}…)" if sha else ""))
                    st.rerun()
    with t2:
        if ev.empty:
            st.info("No evidence items.")
        else:
            item = st.selectbox("Item", list(ev.item_id), format_func=lambda i: f"{i} — {ev.set_index('item_id').description[i]}")
            cd = C.custody(item)
            ok, bad = C.verify_chain(item)
            ui.status_badge(ok, "✔ Chain intact — every SHA-256 link verifies" if ok else f"✖ Chain BROKEN at entry #{bad} — the log was altered")
            st.write("")
            st.dataframe(cd.assign(entry_hash=cd.entry_hash.str[:16] + "…", prev_hash=cd.prev_hash.str[:16] + "…"), hide_index=True)
            cd2 = cd.assign(t=lambda d: d.ts.str[:16])
            st.plotly_chart(px.scatter(cd2, x="ts", y="to_person", color="action", size=[12] * len(cd2), title="Custody timeline",
                                       hover_data=["location", "notes"]), key=f"tl_{item}")
            with st.form(f"cu_{item}"):
                y = st.columns(4)
                act = y[0].selectbox("Action", C.ACTIONS)
                frm = y[1].text_input("From", cd.to_person.iloc[-1] if len(cd) else "")
                to = y[2].text_input("To")
                loc = y[3].text_input("Location", "Lab")
                notes = st.text_input("Notes / seal number")
                if st.form_submit_button("Add custody entry") and to:
                    C.add_custody(item, act, frm, to, loc, notes)
                    st.rerun()
            if st.button("🧪 Demo: simulate someone editing the log in the database"):
                C.tamper_demo(item)
                st.rerun()
            st.caption("Each entry's hash = SHA-256(entry contents + previous hash). Editing any past entry changes its hash and breaks "
                       "every link after it — the same idea as a blockchain or a write-once audit log.")
    with t3:
        r = C.results(cid)
        if len(r):
            st.dataframe(r, hide_index=True)
        else:
            st.info("No results yet — add them from the DNA, digital, toxicology or fingerprint pages ('Save to case').")
    with t4:
        lab = st.text_input("Laboratory name", "Forensic Science Laboratory")
        cust = {i: C.custody(i) for i in ev.item_id}
        okd = {i: C.verify_chain(i)[0] for i in ev.item_id}
        pdf = reports.case_report(case, ev, cust, okd, C.results(cid), lab)
        st.download_button("⬇️ Download case report (PDF)", pdf, f"{cid}_case_report.pdf", "application/pdf", type="primary")
    st.divider()
    if st.button("♻️ Reset demo database"):
        C.reset()
        st.rerun()
