"""Digital forensics utilities: hashing, file-signature analysis, entropy, strings, EXIF/GPS, JPEG error level analysis."""
from __future__ import annotations

import hashlib
import io
import math
import re
from collections import Counter

import numpy as np
from PIL import ExifTags, Image, ImageChops

SIGNATURES = [  # (magic bytes, offset, file type, expected extensions)
    (b"\xFF\xD8\xFF", 0, "JPEG image", {"jpg", "jpeg", "jpe", "jfif"}),
    (b"\x89PNG\r\n\x1a\n", 0, "PNG image", {"png"}),
    (b"GIF87a", 0, "GIF image", {"gif"}), (b"GIF89a", 0, "GIF image", {"gif"}),
    (b"%PDF", 0, "PDF document", {"pdf"}),
    (b"PK\x03\x04", 0, "ZIP container (zip / docx / xlsx / pptx / apk / jar)", {"zip", "docx", "xlsx", "pptx", "apk", "jar", "odt", "epub"}),
    (b"Rar!\x1a\x07", 0, "RAR archive", {"rar"}), (b"7z\xBC\xAF\x27\x1C", 0, "7-Zip archive", {"7z"}),
    (b"\x1f\x8b", 0, "GZIP archive", {"gz", "tgz"}),
    (b"MZ", 0, "Windows executable (PE)", {"exe", "dll", "sys", "scr"}),
    (b"\x7fELF", 0, "Linux executable (ELF)", {"elf", "so", "bin", ""}),
    (b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", 0, "MS Office 97-2003 (OLE2: doc / xls / ppt / msg)", {"doc", "xls", "ppt", "msg"}),
    (b"ID3", 0, "MP3 audio", {"mp3"}), (b"ftyp", 4, "MP4 / MOV / HEIC media", {"mp4", "m4a", "mov", "heic", "3gp"}),
    (b"RIFF", 0, "RIFF container (WAV / AVI / WEBP)", {"wav", "avi", "webp"}),
    (b"SQLite format 3\x00", 0, "SQLite database (app data, browser history, WhatsApp msgstore...)", {"db", "sqlite", "sqlite3"}),
    (b"BM", 0, "BMP image", {"bmp"}), (b"II*\x00", 0, "TIFF image", {"tif", "tiff", "dng"}), (b"MM\x00*", 0, "TIFF image", {"tif", "tiff"}),
    (b"DICM", 128, "DICOM medical image", {"dcm"}), (b"{\\rtf", 0, "Rich Text Format", {"rtf"}),
]


def hashes(data: bytes) -> dict:
    return {"MD5": hashlib.md5(data).hexdigest(), "SHA-1": hashlib.sha1(data).hexdigest(), "SHA-256": hashlib.sha256(data).hexdigest()}


def signature(data: bytes, name: str) -> dict:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    for magic, off, kind, exts in SIGNATURES:
        if data[off:off + len(magic)] == magic:
            return {"detected": kind, "extension": ext or "(none)", "magic (hex)": data[off:off + len(magic)].hex(" "),
                    "mismatch": ext not in exts}
    text_like = sum(32 <= b < 127 or b in (9, 10, 13) for b in data[:2048]) / max(len(data[:2048]), 1) > .95
    return {"detected": "plain text" if text_like else "unknown binary", "extension": ext or "(none)",
            "magic (hex)": data[:8].hex(" "), "mismatch": (not text_like and ext in ("txt", "csv", "log"))}


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def entropy_profile(data: bytes, block=4096) -> list[float]:
    return [entropy(data[i:i + block]) for i in range(0, len(data), block)][:2000]


PATTERNS = {"Email": rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "URL": rb"https?://[^\s\"'<>]{4,200}",
            "IPv4": rb"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
            "Phone (intl)": rb"\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}", "Bitcoin address": rb"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b"}


def strings(data: bytes, min_len=5, limit=3000) -> list[str]:
    return [m.decode("latin-1") for m in re.findall(rb"[\x20-\x7e]{%d,}" % min_len, data)[:limit]]


def iocs(data: bytes) -> dict:
    return {k: sorted({m.decode("latin-1") for m in re.findall(p, data)})[:200] for k, p in PATTERNS.items()}


def _ratio(x):
    try:
        return float(x)
    except Exception:
        try:
            return x[0] / x[1]
        except Exception:
            return None


def exif(data: bytes) -> tuple[dict, dict | None]:
    try:
        im = Image.open(io.BytesIO(data))
    except Exception:
        return {}, None
    out = {"Format": im.format, "Size": f"{im.width}×{im.height}", "Mode": im.mode}
    ex = im.getexif()
    for k, v in ex.items():
        out[ExifTags.TAGS.get(k, k)] = str(v)[:120]
    try:
        for k, v in ex.get_ifd(0x8769).items():  # Exif sub-IFD: DateTimeOriginal, camera settings
            out[ExifTags.TAGS.get(k, k)] = str(v)[:120]
    except Exception:
        pass
    gps = None
    try:
        g = ex.get_ifd(0x8825)
        if g:
            gd = {ExifTags.GPSTAGS.get(k, k): v for k, v in g.items()}

            def dms(v, ref):
                d, m, s = (_ratio(x) for x in v)
                val = d + m / 60 + s / 3600
                return -val if ref in ("S", "W") else val
            gps = {"lat": dms(gd["GPSLatitude"], gd.get("GPSLatitudeRef", "N")), "lon": dms(gd["GPSLongitude"], gd.get("GPSLongitudeRef", "E"))}
            out["GPS"] = f"{gps['lat']:.6f}, {gps['lon']:.6f}"
    except Exception:
        gps = None
    return out, gps


def ela(data: bytes, quality=90, scale=15) -> Image.Image:
    """Error level analysis: re-save at a known JPEG quality; edited regions often compress differently."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    diff = ImageChops.difference(im, Image.open(io.BytesIO(buf.getvalue())))
    arr = np.asarray(diff, np.float32) * scale
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def make_demo_photo() -> bytes:
    """A synthetic JPEG with fake camera EXIF + GPS (Islamabad) and a pasted (tampered) region, for the demo."""
    rng = np.random.default_rng(3)
    h, w = 480, 720
    y, x = np.mgrid[0:h, 0:w]
    sky = np.stack([120 + 60 * (1 - y / h), 160 + 50 * (1 - y / h), 230 - 20 * (y / h)], -1)
    ground = np.stack([70 + 30 * np.sin(x / 40), 120 + 20 * np.cos(y / 30), 60 + 0 * x], -1)
    img = np.where((y > h * .6)[..., None], ground, sky) + rng.normal(0, 6, (h, w, 3))
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    base.save(buf, "JPEG", quality=70)
    base = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    patch = Image.fromarray(np.clip(rng.normal(0, 4, (90, 140, 3)) + np.array([200, 40, 40]), 0, 255).astype(np.uint8))
    base.paste(patch, (420, 300))  # pasted object never went through the 70% compression -> stands out in ELA
    ex = Image.Exif()
    ex[0x010F] = "DemoCam"
    ex[0x0110] = "DC-100 (fictional)"
    ex[0x0132] = "2026:03:14 16:42:10"
    ex[0x0131] = "PhotoEditor 9.1"
    gps = {1: "N", 2: (33.0, 41.0, 2.4), 3: "E", 4: (73.0, 3.0, 39.6)}
    ex[0x8825] = gps
    out = io.BytesIO()
    base.save(out, "JPEG", quality=92, exif=ex)
    return out.getvalue()
