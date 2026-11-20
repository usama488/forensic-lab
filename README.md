# ⚖️ Forensic Science Laboratory (Streamlit)

An educational forensic-lab website in one Streamlit app. All files are flat (no folders).

| Page | What it does |
|---|---|
| 🏛️ Laboratory portal | Lab dashboard, services, KPIs, charts, submit a new case |
| 🗂️ Cases & custody | Case management, evidence register, **SHA-256 hash-chained chain of custody** (verify + tamper demo), results, case-report PDF |
| 🧬 DNA laboratory | STR profile comparison (RMP / LR, NRC II 4.1 & 4.10, θ), paternity (PI, CPI, W, mutations), kinship LR, mixtures (CPI/RMNE), CODIS-style database search, EPG, allele frequencies; PDF reports |
| 💻 Digital forensics | MD5/SHA-1/SHA-256, file-signature mismatch, entropy, strings & IOCs, EXIF/GPS, JPEG error-level analysis |
| 🧪 Toxicology & pathology | Widmark BAC curve, retrograde extrapolation, Henssge nomogram time of death, Glaister rule |
| 🖐️ Fingerprints | Enhancement, skeleton, minutiae (crossing number), alignment and match score |
| 📚 Learning hub | Branches of forensics, glossary, landmark cases, quiz |

**Data:** STR allele frequencies from norSTR (Oslo University Hospital, MIT licence, see `LICENSE_norSTR.md`), 7 populations.
Demo cases, the DNA database and fingerprints are simulated/synthetic. For education and training only — not for real casework.

## Deploy (Streamlit Cloud)
1. GitHub → new repo → **Add file → Upload files** → select all files → **Commit changes**.
2. share.streamlit.io → **Create app** → repo, branch `main`, main file `app.py` → Advanced settings → Python 3.12 → **Deploy**.
