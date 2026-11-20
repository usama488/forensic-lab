import random

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import cases_db as C
import reports
import str_stats as S
import ui

METHODS = ["NRC II 4.1", "Balding-Nichols NRC II 4.10", "Product rule (HWE)"]


def _settings():
    with st.expander("⚙️ Statistics settings", expanded=False):
        a, b, c, d = st.columns(4)
        pop = a.selectbox("Population database", S.populations(), index=S.populations().index("Middle Asia"), key="fx_pop",
                          help="norSTR v2023 (Oslo University Hospital). 'Middle Asia' / 'West Asia' are the closest to South-Asian casework here.")
        kit = b.selectbox("Loci set", list(S.KITS), key="fx_kit")
        method = c.selectbox("Match statistic", METHODS, key="fx_method")
        theta = d.select_slider("θ (FST)", [0.0, .01, .02, .03], .01, key="fx_theta",
                                help="Co-ancestry correction: 0.01 for most populations, 0.03 for small/isolated ones.")
        mf = a.select_slider("Minimum allele frequency", [.001, .002, .005, .01], .002, key="fx_minf")
    return (st.session_state.get("fx_pop", "Middle Asia"), S.KITS[st.session_state.get("fx_kit", list(S.KITS)[0])],
            st.session_state.get("fx_method", METHODS[0]), st.session_state.get("fx_theta", .01), st.session_state.get("fx_minf", .002))


def _save_to_case(section, summary, details, key):
    cs = C.cases()
    with st.expander("💾 Save result to a case"):
        cid = st.selectbox("Case", list(cs.case_id), key=f"{key}_c", format_func=lambda x: f"{x} — {cs.set_index('case_id').title[x]}")
        ev = C.evidence(cid)
        item = st.selectbox("Evidence item", list(ev.item_id) or ["-"], key=f"{key}_i")
        an = st.text_input("Analyst", "Reporting scientist", key=f"{key}_a")
        if st.button("Save", key=f"{key}_s"):
            C.add_result(cid, item, section, summary, details, an)
            st.success(f"Saved to {cid}")


def render():
    ui.hero("Forensic DNA laboratory", "Autosomal STR interpretation with real population allele frequencies (norSTR, 7 populations).",
            ["20 CODIS CORE LOCI", "LIKELIHOOD RATIOS", "ENFSI VERBAL SCALE"])
    pop, loci, method, theta, mf = _settings()
    tabs = st.tabs(["🔎 Profile comparison", "👨‍👧 Paternity", "🧑‍🤝‍🧑 Kinship", "🧪 Mixture", "🗄️ Database search", "📈 Electropherogram",
                    "📊 Allele frequencies"])
    rng = random.Random(st.session_state.get("fx_seed", 11))

    # ------------------------------------------------------------ comparison
    with tabs[0]:
        c1, c2 = st.columns([1, 3])
        demo = c1.radio("Demo scenario", ["Suspect matches crime scene", "Suspect excluded", "Partial / degraded profile"], key="fx_cmp_demo")
        if c1.button("Load demo profiles", key="fx_cmp_load") or "fx_cmp" not in st.session_state:
            r = random.Random(sum(map(ord, demo)))
            q = S.random_profile(pop, loci, r)
            k = dict(q) if demo != "Suspect excluded" else S.random_profile(pop, loci, r)
            if demo.startswith("Partial"):
                for l in list(q)[::3]:
                    q[l] = ""
                l2 = list(q)[1]
                q[l2] = S.parse_genotype(q[l2])[0] + "," + S.parse_genotype(q[l2])[0]  # drop-out → apparent homozygote
            st.session_state.fx_cmp = pd.DataFrame({"locus": loci, "crime scene (questioned)": [q.get(l, "") for l in loci],
                                                    "reference (suspect)": [k.get(l, "") for l in loci]})
        with c2:
            ed = st.data_editor(st.session_state.fx_cmp, hide_index=True, key="fx_cmp_ed", num_rows="fixed", height=400)
        q = dict(zip(ed.locus, ed["crime scene (questioned)"]))
        k = dict(zip(ed.locus, ed["reference (suspect)"]))
        cmp = S.compare(q, k)
        concl = S.conclusion(cmp)
        st.markdown(f"#### Conclusion: **{concl}**")
        cnt = cmp.result.value_counts().reset_index()
        cnt.columns = ["result", "loci"]
        x1, x2 = st.columns([2, 3])
        x1.plotly_chart(px.pie(cnt, names="result", values="loci", hole=.5, color="result",
                               color_discrete_map={"match": "#1E7B45", "EXCLUSION": "#B42318", "not typed": "#BBBBBB",
                                                   "inconclusive (possible drop-out)": "#C9A227"}), key="fx_cmp_pie")
        x2.dataframe(cmp, hide_index=True, height=340)
        if concl.startswith("INCLUDED"):
            matched = {l: g for l, g in q.items() if cmp.set_index("locus").result.get(l) == "match"}
            tab = S.rmp(matched, pop, theta, method, mf)
            p = S.combined(tab)
            lr = 1 / p
            ui.kpis([("Loci used", len(tab)), ("Random match probability", f"1 in {S.fmt_big(lr)}"), ("Likelihood ratio", S.fmt_big(lr)),
                     ("Verbal scale (ENFSI)", S.verbal(lr).split(" support")[0].title())])
            st.write("")
            statement = (f"The DNA profile from the crime-scene sample matches the reference profile at {len(tab)} loci. The probability "
                         f"that an unrelated person chosen at random from the {pop} population would share this profile is approximately "
                         f"1 in {S.fmt_big(lr)}. The DNA results are {S.fmt_big(lr)} times more probable if the suspect is the source "
                         f"than if an unknown, unrelated person is the source — {S.verbal(lr)} for the proposition that the suspect is the source.")
            st.info(statement)
            st.plotly_chart(px.bar(tab, x="locus", y="1 in", log_y=True, title="Per-locus rarity (1 in …) — the product gives the RMP"),
                            key="fx_rmp_bar")
            st.dataframe(tab, hide_index=True)
            pdf = reports.dna_report("DNA profile comparison report", "—", pop, method, theta, tab.round(6), statement,
                                     {"Loci compared": len(cmp), "Conclusion": concl}, "Forensic Science Laboratory")
            st.download_button("⬇️ DNA statistical report (PDF)", pdf, "DNA_comparison_report.pdf", "application/pdf")
            _save_to_case("DNA / Biology", f"Profile match at {len(tab)} loci; RMP 1 in {S.fmt_big(lr)} ({pop}).", {"LR": lr}, "fx_cmp_save")
        elif concl == "EXCLUDED":
            st.error("The reference donor is **excluded** as the source of the crime-scene DNA (different alleles at ≥ 2 loci).")
            _save_to_case("DNA / Biology", "Reference excluded as source of crime-scene DNA.", {}, "fx_cmp_save")

    # ------------------------------------------------------------ paternity
    with tabs[1]:
        c1, c2 = st.columns([1, 3])
        demo = c1.radio("Demo", ["True father (trio)", "Not the father (trio)", "True father, mother not tested", "True father with 1 mutation"],
                        key="fx_pat_demo")
        if c1.button("Load demo", key="fx_pat_load") or "fx_pat" not in st.session_state:
            r = random.Random(sum(map(ord, demo)) + 5)
            m, f = S.random_profile(pop, loci, r), S.random_profile(pop, loci, r)
            ch = S.child_of(m, f, r)
            af = f if not demo.startswith("Not") else S.random_profile(pop, loci, r)
            if "mutation" in demo:
                l = loci[3]
                g = list(S.parse_genotype(ch[l]))
                pat = [a for a in g if a in S.parse_genotype(f[l])][0]
                g[g.index(pat)] = S.norm_allele(float(pat) + 1)  # one-step paternal mutation
                ch[l] = ",".join(sorted(g, key=S._akey))
            st.session_state.fx_pat = pd.DataFrame({"locus": loci, "child": [ch[l] for l in loci],
                                                    "mother": ["" if "not tested" in demo else m[l] for l in loci],
                                                    "alleged father": [af[l] for l in loci]})
        with c2:
            ed = st.data_editor(st.session_state.fx_pat, hide_index=True, key="fx_pat_ed", height=400)
        mu = st.select_slider("Mutation rate per locus", [0.0, .001, .002, .005], .002, key="fx_mu")
        prior = st.slider("Prior probability of paternity", .01, .99, .5, .01, key="fx_prior")
        rows = [S.paternity_locus(r.child, r.mother or None, r._4, pop, r.locus, mu, mf) for r in ed.itertuples()]
        pt = pd.DataFrame(rows)
        cpi = float(np.prod(pt.PI))
        W = cpi * prior / (cpi * prior + (1 - prior))
        incons = int((pt.note.str.startswith("incons")).sum())
        ui.kpis([("Combined Paternity Index", S.fmt_big(cpi)), ("Probability of paternity", f"{W * 100:.6f}%" if W > .99 else f"{W * 100:.2f}%"),
                 ("Inconsistent loci", incons), ("Verbal", S.verbal(cpi).split(" support")[0].title())])
        st.write("")
        if incons >= 3 or cpi < 1:
            st.error("**Exclusion:** the alleged father is excluded as the biological father (inconsistencies at several loci / CPI < 1).")
        elif incons:
            st.warning(f"{incons} inconsistent locus — consistent with a single-step mutation; included with the mutation model.")
        else:
            st.success("The alleged father **cannot be excluded**; he carries the obligate paternal allele at every locus.")
        st.plotly_chart(px.bar(pt, x="locus", y="PI", log_y=True, color="note", title="Paternity index per locus"), key="fx_pi")
        st.dataframe(pt, hide_index=True)
        stmt = (f"Combined paternity index {S.fmt_big(cpi)}; probability of paternity {W:.8%} (prior {prior:.0%}). The genetic results are "
                f"{S.fmt_big(cpi)} times more probable if the alleged father is the biological father than if an unrelated man from the "
                f"{pop} population is.")
        pdf = reports.dna_report("Paternity test report", "—", pop, "Paternity index (equal mutation model)", 0.0, pt.round(6), stmt,
                                 {"Mutation rate": mu, "Prior": prior, "Inconsistent loci": incons}, "Forensic Science Laboratory")
        st.download_button("⬇️ Paternity report (PDF)", pdf, "Paternity_report.pdf", "application/pdf")
        _save_to_case("DNA / Biology", f"Paternity: CPI {S.fmt_big(cpi)}, W {W:.6%}.", {"CPI": cpi}, "fx_pat_save")

    # ------------------------------------------------------------ kinship
    with tabs[2]:
        rel = st.selectbox("Tested relationship", [k for k in S.IBD if k != "Unrelated"], key="fx_rel")
        truth = st.radio("Demo pair actually is", ["the tested relationship", "unrelated"], horizontal=True, key="fx_kin_truth")
        r = random.Random(42 + len(rel) + len(truth))
        m, f = S.random_profile(pop, loci, r), S.random_profile(pop, loci, r)
        a = S.child_of(m, f, r)
        if truth == "unrelated":
            b = S.random_profile(pop, loci, r)
        elif rel == "Full siblings":
            b = S.child_of(m, f, r)
        elif rel == "Parent-child":
            b = f
        elif rel.startswith("Half"):
            b = S.child_of(m, S.random_profile(pop, loci, r), r)
        else:  # first cousins: children of two siblings
            sib = S.child_of(m, f, r)
            a = S.child_of(S.child_of(m, f, r), S.random_profile(pop, loci, r), r)
            b = S.child_of(sib, S.random_profile(pop, loci, r), r)
        kin = pd.DataFrame({"locus": loci, "person 1": [a[l] for l in loci], "person 2": [b[l] for l in loci]})
        kin = st.data_editor(kin, hide_index=True, key=f"fx_kin_ed_{rel}_{truth}", height=300)
        kin["LR"] = [S.kinship_locus(r_.p1, r_.p2, pop, r_.locus, rel, mf) for r_ in kin.rename(columns={"person 1": "p1", "person 2": "p2"}).itertuples()]
        lr = float(np.prod(kin.LR))
        ui.kpis([("Kinship LR", S.fmt_big(lr)), ("Verbal", S.verbal(lr).title()), ("IBD (k0,k1,k2)", str(S.IBD[rel]))])
        st.caption("LR = P(DNA | tested relationship) / P(DNA | unrelated), using identity-by-descent probabilities. Missing-person "
                   "identification and immigration family-reunification tests use the same mathematics.")
        st.plotly_chart(px.bar(kin, x="locus", y="LR", log_y=True, title=f"Per-locus LR — {rel}"), key="fx_kin")

    # ------------------------------------------------------------ mixture
    with tabs[3]:
        r = random.Random(77)
        v, s_ = S.random_profile(pop, loci, r), S.random_profile(pop, loci, r)
        poi_in = st.radio("Demo person of interest", ["contributor", "non-contributor"], horizontal=True, key="fx_mix_poi")
        poi = s_ if poi_in == "contributor" else S.random_profile(pop, loci, r)
        mix = pd.DataFrame({"locus": loci, "mixture alleles": [",".join(sorted(set(S.parse_genotype(v[l])) | set(S.parse_genotype(s_[l])), key=S._akey)) for l in loci],
                            "person of interest": [poi[l] for l in loci]})
        mix = st.data_editor(mix, hide_index=True, key=f"fx_mix_ed_{poi_in}", height=330)
        mx = S.mixture(dict(zip(mix.locus, mix["mixture alleles"])), pop, mf)
        inc = S.poi_included(dict(zip(mix.locus, mix["person of interest"])), mx)
        cpi = float(np.prod(mx["PI (inclusion)"]))
        noc = int(np.ceil(mx.n_alleles.max() / 2))
        n_out = int((inc.status == "NOT present").sum())
        ui.kpis([("Min. contributors", noc), ("Combined prob. of inclusion", f"1 in {S.fmt_big(1 / cpi)}"),
                 ("POI alleles missing at", f"{n_out} loci")])
        st.write("")
        (st.error if n_out else st.success)("POI is **excluded** as a contributor." if n_out else
                                            f"POI **cannot be excluded**. The probability that a random person would also be included is 1 in {S.fmt_big(1 / cpi)} (CPI/RMNE).")
        st.dataframe(mx.merge(inc[["locus", "POI", "status"]], on="locus"), hide_index=True)
        st.caption("CPI ignores peak heights and allele drop-out; modern labs use probabilistic genotyping software (STRmix, "
                   "EuroForMix, TrueAllele) for complex mixtures.")

    # ------------------------------------------------------------ database
    with tabs[4]:
        n = st.select_slider("Database size (simulated offender / reference index)", [1000, 5000, 20000], 5000, key="fx_dbn")
        dbk = f"fx_db_{pop}_{n}_{len(loci)}"
        if dbk not in st.session_state:
            with st.spinner("Building simulated database from population allele frequencies..."):
                db = S.make_database(pop, n, loci)
                q = dict(zip(st.session_state.fx_cmp.locus, st.session_state.fx_cmp["reference (suspect)"]))
                plant = {l: q.get(l, "") for l in loci}
                db.loc[n // 3, loci] = [plant[l] for l in loci]
                db.loc[n // 3, "category"] = "convicted offender"
                st.session_state[dbk] = db
        db = st.session_state[dbk]
        query = dict(zip(st.session_state.fx_cmp.locus, st.session_state.fx_cmp["crime scene (questioned)"]))
        a, b = st.columns(2)
        string = a.radio("Search stringency", ["high", "moderate", "low"], index=1, horizontal=True, key="fx_str")
        minl = b.slider("Minimum loci", 6, len(loci), min(10, len(loci)), key="fx_minl")
        hits = S.search(db, query, string, minl)
        st.write(f"Searched **{len(db):,}** profiles with the crime-scene profile from the comparison tab "
                 f"({sum(bool(S.parse_genotype(v)) for v in query.values())} typed loci).")
        if len(hits):
            st.success(f"{len(hits)} candidate(s) — confirm with a new reference sample before reporting (CODIS 'hit confirmation').")
            st.dataframe(hits, hide_index=True)
        else:
            st.info("No candidates at this stringency.")
        st.caption("Simulated database (random genotypes drawn from real allele frequencies) — contains no real people.")

    # ------------------------------------------------------------ EPG
    with tabs[5]:
        prof = dict(zip(st.session_state.fx_cmp.locus, st.session_state.fx_cmp["crime scene (questioned)"]))
        prof = {k_: v_ for k_, v_ in prof.items() if S.parse_genotype(v_)}
        x, traces, labels = S.epg_traces(prof, seed=3)
        fig = go.Figure()
        dyes = list(S.DYE_COL)
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=len(dyes), cols=1, shared_xaxes=True, vertical_spacing=.02, subplot_titles=[d.upper() + " dye" for d in dyes])
        for i, d in enumerate(dyes, 1):
            fig.add_scatter(x=x, y=traces[d], line=dict(color=S.DYE_COL[d], width=1.2), name=d, row=i, col=1, showlegend=False)
            for lab in [l_ for l_ in labels if l_["dye"] == d]:
                fig.add_annotation(x=lab["bp"], y=lab["height"], text=lab["label"], showarrow=False, yshift=14, font=dict(size=8), row=i, col=1)
        fig.update_layout(height=820, title="Electropherogram (illustrative, generated from the profile — not instrument data)",
                          xaxis5_title="fragment size (bp)")
        fig.update_yaxes(title_text="RFU")
        st.plotly_chart(fig, key="fx_epg")
        st.caption("Peaks = alleles (repeat number); small peaks one repeat shorter = stutter artefacts; heterozygote peaks of similar "
                   "height, homozygote ≈ double height.")

    # ------------------------------------------------------------ frequencies
    with tabs[6]:
        l = st.selectbox("Locus", sorted(S.DB()[pop]), index=sorted(S.DB()[pop]).index("D18S51") if "D18S51" in S.DB()[pop] else 0, key="fx_fl")
        pops = st.multiselect("Populations", S.populations(), default=["Europe", "Africa", "Middle Asia", "East Asia"], key="fx_fp")
        rows = [{"population": p_, "allele": a_, "frequency": f_} for p_ in pops for a_, f_ in S.DB()[p_].get(l, {}).items()]
        fdf = pd.DataFrame(rows)
        fdf["n"] = fdf.allele.map(S._akey)
        st.plotly_chart(px.bar(fdf.sort_values("n"), x="allele", y="frequency", color="population", barmode="group",
                               title=f"{l} allele frequencies"), key="fx_freq")
        stats = []
        for p_ in S.populations():
            d = S.DB()[p_]
            for loc in loci:
                if loc in d:
                    f_ = np.array(list(d[loc].values()))
                    het = 1 - (f_ ** 2).sum()
                    pm = (f_ ** 2).sum() ** 2 + sum(2 * (f_[i] * f_[j]) ** 2 for i in range(len(f_)) for j in range(i + 1, len(f_)))
                    stats.append({"population": p_, "locus": loc, "expected heterozygosity": het, "power of discrimination": 1 - pm})
        sd = pd.DataFrame(stats)
        st.plotly_chart(px.box(sd, x="population", y="power of discrimination", points="all", hover_data=["locus"],
                               title="Power of discrimination of each locus by population"), key="fx_pd")
        st.caption("Source: norSTR v2023 allele frequency databases (Department of Forensic Sciences, Oslo University Hospital), MIT licence.")
