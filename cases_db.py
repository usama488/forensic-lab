"""Case management with a tamper-evident (hash-chained) chain of custody, stored in SQLite."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "forensic_cases.db"
STATUSES = ["Received", "In analysis", "Technical review", "Reported", "Closed"]
SECTIONS = ["DNA / Biology", "Toxicology", "Digital forensics", "Fingerprints", "Firearms & toolmarks", "Trace / chemistry", "Documents"]
EVIDENCE_TYPES = ["Buccal swab (reference)", "Blood stain", "Touch DNA swab", "Hair", "Clothing", "Firearm", "Cartridge case",
                  "Mobile phone", "Laptop / hard drive", "USB drive", "Photograph / video", "Latent print lift", "Blood sample (tox)",
                  "Urine sample (tox)", "Document", "Fibres / glass / paint"]
ACTIONS = ["Collected", "Sealed & packaged", "Transferred", "Received at lab", "Opened for analysis", "Analysed", "Resealed",
           "Stored (evidence room)", "Released to court", "Returned / destroyed"]


def con() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init(seed_demo=True):
    with con() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY, title TEXT, agency TEXT, offence TEXT, section TEXT, status TEXT,
            priority TEXT, opened TEXT, due TEXT, investigator TEXT, analyst TEXT, description TEXT, closed TEXT);
        CREATE TABLE IF NOT EXISTS evidence(item_id TEXT PRIMARY KEY, case_id TEXT, description TEXT, type TEXT, collected_by TEXT,
            collected_at TEXT, location TEXT, sha256 TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS custody(id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, ts TEXT, action TEXT, from_person TEXT,
            to_person TEXT, location TEXT, notes TEXT, prev_hash TEXT, entry_hash TEXT);
        CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, item_id TEXT, section TEXT, summary TEXT,
            details TEXT, ts TEXT, analyst TEXT);
        """)
        n = c.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    if seed_demo and n == 0:
        seed()


def _hash(entry: dict, prev: str) -> str:
    payload = json.dumps({k: entry[k] for k in ("item_id", "ts", "action", "from_person", "to_person", "location", "notes")},
                         sort_keys=True) + prev
    return hashlib.sha256(payload.encode()).hexdigest()


def add_custody(item_id, action, from_person, to_person, location, notes="", ts=None):
    ts = ts or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with con() as c:
        last = c.execute("SELECT entry_hash FROM custody WHERE item_id=? ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
        prev = last[0] if last else "GENESIS"
        e = {"item_id": item_id, "ts": ts, "action": action, "from_person": from_person, "to_person": to_person,
             "location": location, "notes": notes}
        c.execute("INSERT INTO custody(item_id,ts,action,from_person,to_person,location,notes,prev_hash,entry_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                  (item_id, ts, action, from_person, to_person, location, notes, prev, _hash(e, prev)))


def verify_chain(item_id) -> tuple[bool, int | None]:
    """Recompute every hash; returns (ok, id of first broken entry)."""
    prev = "GENESIS"
    for r in custody(item_id).to_dict("records"):
        if r["prev_hash"] != prev or _hash(r, prev) != r["entry_hash"]:
            return False, r["id"]
        prev = r["entry_hash"]
    return True, None


def tamper_demo(item_id):
    """Simulates someone editing the log directly in the database (for teaching)."""
    with con() as c:
        row = c.execute("SELECT id FROM custody WHERE item_id=? ORDER BY id LIMIT 1", (item_id,)).fetchone()
        if row:
            c.execute("UPDATE custody SET to_person='(edited) Unknown person' WHERE id=?", (row[0],))


def q(sql, *args) -> pd.DataFrame:
    with con() as c:
        return pd.read_sql_query(sql, c, params=args)


def cases() -> pd.DataFrame:
    return q("SELECT * FROM cases ORDER BY opened DESC")


def evidence(case_id=None) -> pd.DataFrame:
    return q("SELECT * FROM evidence WHERE case_id=? ORDER BY item_id", case_id) if case_id else q("SELECT * FROM evidence")


def custody(item_id) -> pd.DataFrame:
    return q("SELECT * FROM custody WHERE item_id=? ORDER BY id", item_id)


def results(case_id=None) -> pd.DataFrame:
    return q("SELECT * FROM results WHERE case_id=? ORDER BY ts DESC", case_id) if case_id else q("SELECT * FROM results ORDER BY ts DESC")


def next_case_id() -> str:
    year = dt.date.today().year
    n = q("SELECT COUNT(*) AS n FROM cases WHERE case_id LIKE ?", f"FL-{year}-%").n[0]
    return f"FL-{year}-{n + 1:04d}"


def create_case(**kw) -> str:
    cid = kw.pop("case_id", None) or next_case_id()
    cols = ["title", "agency", "offence", "section", "status", "priority", "opened", "due", "investigator", "analyst", "description"]
    kw.setdefault("status", "Received")
    kw.setdefault("opened", dt.date.today().isoformat())
    with con() as c:
        c.execute(f"INSERT INTO cases(case_id,{','.join(cols)}) VALUES(?,{','.join('?' * len(cols))})", (cid, *[kw.get(k, "") for k in cols]))
    return cid


def add_evidence(case_id, description, type_, collected_by, collected_at, location, sha256="", first_action=True) -> str:
    n = q("SELECT COUNT(*) AS n FROM evidence WHERE case_id=?", case_id).n[0]
    item = f"{case_id}-E{n + 1:02d}"
    with con() as c:
        c.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?)", (item, case_id, description, type_, collected_by, collected_at, location,
                                                                       sha256, "In custody"))
    if first_action:
        add_custody(item, "Collected", "-", collected_by, location, "Item collected at scene", ts=f"{collected_at} 09:00:00")
    return item


def set_status(case_id, status):
    with con() as c:
        c.execute("UPDATE cases SET status=?, closed=? WHERE case_id=?", (status, dt.date.today().isoformat() if status == "Closed" else None, case_id))


def add_result(case_id, item_id, section, summary, details: dict, analyst):
    with con() as c:
        c.execute("INSERT INTO results(case_id,item_id,section,summary,details,ts,analyst) VALUES(?,?,?,?,?,?,?)",
                  (case_id, item_id, section, summary, json.dumps(details, default=str), dt.datetime.now().strftime("%Y-%m-%d %H:%M"), analyst))


def reset():
    DB_PATH.unlink(missing_ok=True)
    init()


def seed():
    """Fictional demo cases (names/places invented) so the dashboards are not empty."""
    rng = random.Random(4)
    analysts = ["A. Khan (DNA)", "S. Ahmed (Toxicology)", "R. Malik (Digital)", "F. Yusuf (Fingerprints)", "H. Raza (Firearms)"]
    demo = [
        ("Burglary - Green Valley residence", "Metro Police - Division 3", "Burglary", "DNA / Biology", "Reported", "Routine"),
        ("Hit-and-run - Ring Road", "Traffic Police", "Fatal road traffic collision", "Toxicology", "Technical review", "Urgent"),
        ("Online fraud - phishing ring", "Cyber Crime Wing", "Fraud / identity theft", "Digital forensics", "In analysis", "Routine"),
        ("Armed robbery - fuel station", "Metro Police - Division 1", "Armed robbery", "Firearms & toolmarks", "In analysis", "Urgent"),
        ("Paternity dispute - family court", "Family Court referral", "Civil paternity", "DNA / Biology", "Closed", "Routine"),
        ("Unidentified remains - river bank", "Rural Police", "Missing person / identification", "DNA / Biology", "Received", "High"),
        ("Vehicle theft - car park", "Metro Police - Division 2", "Theft", "Fingerprints", "Reported", "Routine"),
    ]
    base = dt.date.today() - dt.timedelta(days=75)
    for i, (title, agency, off, sec, st, pr) in enumerate(demo):
        opened = base + dt.timedelta(days=i * 9 + rng.randint(0, 4))
        cid = f"FL-{opened.year}-D{i + 1:03d}"
        create_case(case_id=cid, title=f"[DEMO] {title}", agency=agency, offence=off, section=sec, status=st, priority=pr,
                    opened=opened.isoformat(), due=(opened + dt.timedelta(days=30)).isoformat(),
                    investigator=rng.choice(["Insp. N. Iqbal", "SI T. Shah", "Insp. M. Ali", "DSP K. Javed"]),
                    analyst=next(a for a in analysts if sec.split()[0].lower() in a.lower()) if any(sec.split()[0].lower() in a.lower() for a in analysts) else analysts[0],
                    description="Fictional demonstration case.")
        if st == "Closed":
            with con() as c:
                c.execute("UPDATE cases SET closed=? WHERE case_id=?", ((opened + dt.timedelta(days=21)).isoformat(), cid))
        items = {"DNA / Biology": [("Swab from window frame", "Touch DNA swab"), ("Reference buccal swab - suspect", "Buccal swab (reference)")],
                 "Toxicology": [("Femoral blood - driver", "Blood sample (tox)"), ("Urine - driver", "Urine sample (tox)")],
                 "Digital forensics": [("Seized smartphone", "Mobile phone"), ("Laptop", "Laptop / hard drive")],
                 "Firearms & toolmarks": [("9 mm cartridge case", "Cartridge case"), ("Recovered pistol", "Firearm")],
                 "Fingerprints": [("Latent lift - driver door", "Latent print lift")]}.get(sec, [("Item", "Document")])
        for desc, typ in items:
            item = add_evidence(cid, desc, typ, "SOCO " + rng.choice(["Z. Bibi", "U. Farooq", "Q. Anwar"]), opened.isoformat(), "Scene")
            t = dt.datetime.combine(opened, dt.time(11))
            for act, frm, to, loc in (("Sealed & packaged", "SOCO", "SOCO", "Scene"), ("Transferred", "SOCO", "Evidence courier", "In transit"),
                                      ("Received at lab", "Evidence courier", "Evidence reception", "Lab - reception"),
                                      ("Opened for analysis", "Evidence reception", "Analyst", f"Lab - {sec}")):
                t += dt.timedelta(hours=rng.randint(2, 30))
                add_custody(item, act, frm, to, loc, "Seal intact" if act != "Opened for analysis" else "Seal number recorded", ts=t.strftime("%Y-%m-%d %H:%M:%S"))
        if st in ("Reported", "Closed", "Technical review"):
            add_result(cid, f"{cid}-E01", sec, {"DNA / Biology": "Single-source male profile obtained; matches reference sample (RMP < 1 in 10^20).",
                                                 "Toxicology": "Blood alcohol 0.14 g/100 mL; no other drugs detected in screen.",
                                                 "Fingerprints": "Latent lift identified to suspect's right index finger (verified).",
                                                 }.get(sec, "Analysis complete."), {}, "Demo analyst")
