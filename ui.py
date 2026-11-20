"""Look & feel shared by all forensic pages."""
import streamlit as st

NAVY, GOLD = "#0B1F3A", "#C9A227"

CSS = f"""
<style>
.fx-hero {{background: linear-gradient(120deg, {NAVY} 0%, #17375E 60%, #24507F 100%); color: #fff; padding: 28px 32px;
  border-radius: 14px; margin-bottom: 18px; border-bottom: 4px solid {GOLD};}}
.fx-hero h1 {{color: #fff; margin: 0 0 6px 0; font-size: 2.1rem; letter-spacing: .3px;}}
.fx-hero p {{color: #D6E2F0; margin: 0; font-size: 1.02rem;}}
.fx-badge {{display:inline-block; background:{GOLD}; color:{NAVY}; font-weight:700; padding:2px 10px; border-radius:20px;
  font-size:.75rem; margin-right:6px; letter-spacing:.4px;}}
.fx-kpi {{background:#fff; border:1px solid #E3E8EF; border-left:5px solid {GOLD}; border-radius:10px; padding:14px 16px;
  box-shadow:0 1px 3px rgba(11,31,58,.08);}}
.fx-kpi .v {{font-size:1.9rem; font-weight:800; color:{NAVY}; line-height:1.1;}}
.fx-kpi .l {{color:#5B6B7F; font-size:.85rem; text-transform:uppercase; letter-spacing:.6px;}}
.fx-card {{background:#fff; border:1px solid #E3E8EF; border-radius:12px; padding:16px 18px; height:100%;
  box-shadow:0 1px 3px rgba(11,31,58,.06);}}
.fx-card h4 {{margin:0 0 6px 0; color:{NAVY};}}
.fx-card p {{color:#44546A; font-size:.9rem; margin:0;}}
.fx-ok {{background:#E8F7EE; color:#1E7B45; padding:6px 12px; border-radius:8px; font-weight:700; display:inline-block;}}
.fx-bad {{background:#FDECEC; color:#B42318; padding:6px 12px; border-radius:8px; font-weight:700; display:inline-block;}}
</style>
"""


def style():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, badges=()):
    b = "".join(f"<span class='fx-badge'>{x}</span>" for x in badges)
    st.markdown(f"<div class='fx-hero'>{b}<h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def kpis(items):
    cols = st.columns(len(items))
    for c, (label, value) in zip(cols, items):
        c.markdown(f"<div class='fx-kpi'><div class='v'>{value}</div><div class='l'>{label}</div></div>", unsafe_allow_html=True)


def card(col, title, text):
    col.markdown(f"<div class='fx-card'><h4>{title}</h4><p>{text}</p></div>", unsafe_allow_html=True)


def status_badge(ok: bool, text: str):
    st.markdown(f"<span class='{'fx-ok' if ok else 'fx-bad'}'>{text}</span>", unsafe_allow_html=True)
