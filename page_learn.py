import pandas as pd
import streamlit as st

import ui

BRANCHES = [
    ("Forensic biology / DNA", "Body fluids, STR profiling, Y-STR and mtDNA, kinship, investigative genetic genealogy."),
    ("Forensic toxicology", "Alcohol, drugs and poisons in blood, urine, vitreous, hair; impaired driving and cause of death."),
    ("Forensic pathology", "Autopsy, cause and manner of death, injuries, time since death."),
    ("Digital forensics", "Acquisition and analysis of phones, computers, cloud and network evidence."),
    ("Fingerprints & impressions", "Friction-ridge, footwear and tyre marks."),
    ("Firearms & toolmarks", "Matching bullets/cartridge cases to weapons; distance and trajectory."),
    ("Trace evidence", "Fibres, glass, paint, soil, gunshot residue (SEM-EDX)."),
    ("Questioned documents", "Handwriting, ink, paper, forgery and alteration."),
    ("Forensic anthropology & odontology", "Skeletal remains, age/sex/ancestry estimation, dental identification."),
    ("Forensic entomology", "Insect evidence to estimate the minimum post-mortem interval."),
]
CASES = [
    ("1986-88 · Colin Pitchfork (UK)", "First conviction using DNA profiling (Alec Jeffreys' technique). The same DNA work also cleared "
     "an innocent suspect who had confessed."),
    ("2004 · Brandon Mayfield (USA/Spain)", "FBI fingerprint misidentification in the Madrid train bombings; led to reforms in "
     "verification and awareness of contextual bias."),
    ("2018 · Golden State Killer (USA)", "Joseph DeAngelo identified by investigative genetic genealogy using a public genealogy "
     "database, decades after the crimes."),
    ("1990s-2000s · The Innocence Project", "Hundreds of wrongful convictions overturned by post-conviction DNA testing, many "
     "originally based on eyewitness error or flawed forensic testimony."),
]
GLOSSARY = {
    "Chain of custody": "Documented, unbroken record of who handled evidence, when, where and why — without it evidence can be inadmissible.",
    "Locard's exchange principle": "Every contact leaves a trace: the perpetrator takes something from the scene and leaves something behind.",
    "STR": "Short tandem repeat — a 2-6 bp DNA motif repeated a variable number of times; the number of repeats is the allele.",
    "Random match probability": "Chance that an unrelated random person would have the same DNA profile.",
    "Likelihood ratio": "P(evidence | prosecution proposition) / P(evidence | defence proposition) — the recommended way to report weight of evidence.",
    "Prosecutor's fallacy": "Confusing 'the chance of a match if innocent is 1 in a million' with 'the chance of being innocent is 1 in a million'.",
    "θ (FST)": "Correction for shared ancestry within sub-populations; makes match statistics more conservative.",
    "Mixture": "DNA from more than one person; interpretation needs number of contributors, peak heights and drop-out models.",
    "Drop-out / drop-in": "Allele missing because of low DNA amount / spurious allele from contamination.",
    "Stutter": "PCR artefact peak usually one repeat shorter than the true allele.",
    "ACE-V": "Analysis, Comparison, Evaluation, Verification - standard fingerprint examination method.",
    "Minutiae": "Ridge endings and bifurcations (Galton details) used to compare fingerprints.",
    "Hash value": "Digital fingerprint of a file (SHA-256); any single-bit change gives a different hash.",
    "Write blocker": "Hardware/software that prevents any write to evidence media during acquisition.",
    "Widmark formula": "Estimates blood alcohol from alcohol consumed, body weight, distribution factor r and elimination rate β.",
    "Henssge nomogram": "Estimates time since death from rectal and ambient temperature, body weight and clothing.",
    "ISO/IEC 17025": "International standard for the competence of testing and calibration laboratories (forensic lab accreditation).",
}
QUIZ = [
    ("A DNA profile has a random match probability of 1 in 1 billion. What does this mean?",
     ["The suspect is guilty with 99.9999999% certainty", "A random unrelated person has a 1 in 1 billion chance of sharing the profile",
      "Only one person on Earth can have this profile"], 1),
    ("Which statistic is reported for a paternity test?", ["Combined paternity index", "Tumour mutational burden", "Phred score"], 0),
    ("Why are custody log entries hash-chained in this app?", ["To compress the log", "So any later edit is detectable", "To encrypt names"], 1),
    ("A file named report.pdf starts with bytes FF D8 FF. It is actually…", ["a PDF", "a JPEG image", "a Windows program"], 1),
    ("Which method estimates time since death from body temperature?", ["Widmark", "Henssge", "ACE-V"], 1),
]


def render():
    ui.hero("Forensic science learning hub", "Branches, key concepts, landmark cases and a quick self-test.", ["EDUCATION"])
    st.subheader("Branches of forensic science")
    for i in range(0, len(BRANCHES), 2):
        cols = st.columns(2)
        for col, (t, d) in zip(cols, BRANCHES[i:i + 2]):
            ui.card(col, t, d)
        st.write("")
    st.subheader("Glossary")
    q = st.text_input("Search", placeholder="e.g. likelihood ratio, hash, stutter")
    st.dataframe(pd.DataFrame([(k, v) for k, v in GLOSSARY.items() if not q or q.lower() in (k + v).lower()], columns=["term", "meaning"]),
                 hide_index=True)
    st.subheader("Landmark cases")
    for t, d in CASES:
        st.markdown(f"**{t}** — {d}")
    st.subheader("Quick quiz")
    score = 0
    for i, (qq, opts, ans) in enumerate(QUIZ):
        a = st.radio(qq, opts, index=None, key=f"fxq{i}")
        if a is not None:
            if opts.index(a) == ans:
                score += 1
                st.success("Correct")
            else:
                st.error(f"Not quite — answer: {opts[ans]}")
    st.metric("Score", f"{score} / {len(QUIZ)}")
