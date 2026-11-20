"""Fingerprint workbench: enhancement, skeletonisation, minutiae (crossing number), pattern/core estimate and
a simple minutiae alignment-and-count comparison. Educational - not an AFIS."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def synthetic(pattern="whorl", seed=0, rotate=0.0, shift=(0, 0), noise=.25, size=320) -> np.ndarray:
    """Generate a synthetic fingerprint-like ridge image (clearly artificial demo data)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(float)
    cx, cy = size / 2 + rng.normal(0, 6), size * .48 + rng.normal(0, 6)
    th = np.deg2rad(rotate)
    xr = (x - cx - shift[0]) * np.cos(th) + (y - cy - shift[1]) * np.sin(th)
    yr = -(x - cx - shift[0]) * np.sin(th) + (y - cy - shift[1]) * np.cos(th)
    lam = 8.5 + rng.normal(0, .3)
    warp = 6 * np.sin(xr / 37 + seed) + 5 * np.cos(yr / 29 + 2 * seed)
    if pattern == "whorl":
        phase = np.sqrt((xr / 1.0) ** 2 + (yr / 1.25) ** 2)
    elif pattern == "loop":
        phase = np.sqrt(xr ** 2 + (yr * 1.3) ** 2) * (yr < 0) + (np.abs(xr) + 0.002 * yr ** 2) * (yr >= 0) * 1.0 + 0 * xr
    else:  # arch
        phase = yr + 18 * np.exp(-(xr ** 2) / 4000)
    # minutiae: phase dislocations (spiral terms) create real ridge endings / bifurcations, fixed in the finger's frame
    disloc = np.zeros_like(xr)
    for _ in range(int(rng.integers(26, 36))):
        px, py = rng.uniform(-size * .3, size * .3), rng.uniform(-size * .36, size * .36)
        if px * px + py * py < 30 ** 2:
            continue
        disloc += rng.choice([-1, 1]) * np.arctan2(yr - py, xr - px)
    ridges = np.cos(2 * np.pi * (phase + warp) / lam + disloc)
    img = (ridges + np.random.default_rng(int(seed * 1000 + rotate * 7 + 3)).normal(0, noise, ridges.shape))
    mask = (((x - size / 2) / (size * .38)) ** 2 + ((y - size * .5) / (size * .46)) ** 2) < 1
    out = np.where(mask, 128 - 100 * img, 245)
    return np.clip(ndi.gaussian_filter(out, .8), 0, 255).astype(np.uint8)


def load(data: bytes) -> np.ndarray:
    im = Image.open(io.BytesIO(data)).convert("L")
    im.thumbnail((500, 500))
    return np.asarray(im)


def enhance(img: np.ndarray) -> dict:
    from skimage import exposure, filters, morphology
    g = img.astype(float) / 255
    g = exposure.equalize_adapthist(g, clip_limit=.02)
    g = filters.gaussian(g, 1.0)
    mask = ndi.binary_fill_holes(filters.gaussian(np.abs(filters.sobel(g)), 6) > .02)
    mask = ndi.binary_erosion(mask, structure=morphology.disk(10))
    th = filters.threshold_local(g, 21, offset=0)
    ridges = (g < th) & mask
    ridges = morphology.remove_small_objects(ridges, max_size=30)
    skel = morphology.skeletonize(ridges)
    return {"enhanced": (g * 255).astype(np.uint8), "binary": ridges, "skeleton": skel, "mask": mask}


def minutiae(skel: np.ndarray, mask: np.ndarray, border=12, min_dist=8) -> list[dict]:
    s = skel.astype(np.uint8)
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    pts = []
    inner = ndi.binary_erosion(mask, iterations=border)
    ys, xs = np.nonzero(s[1:-1, 1:-1])
    for y, x in zip(ys + 1, xs + 1):
        if not inner[y, x]:
            continue
        ring = [s[y + dy, x + dx] for dy, dx in nb]
        cn = sum(abs(int(ring[i]) - int(ring[(i + 1) % 8])) for i in range(8)) // 2
        if cn == 1:
            pts.append({"x": int(x), "y": int(y), "type": "ridge ending"})
        elif cn == 3:
            pts.append({"x": int(x), "y": int(y), "type": "bifurcation"})
    # remove clusters (spurs / breaks produce close pairs)
    keep = []
    for p in pts:
        close = [q for q in pts if q is not p and (q["x"] - p["x"]) ** 2 + (q["y"] - p["y"]) ** 2 < min_dist ** 2]
        if not close:
            keep.append(p)
    return keep


def core_point(img: np.ndarray) -> tuple[int, int]:
    """Rough core estimate from the orientation field's point of maximum curvature."""
    g = ndi.gaussian_filter(img.astype(float), 2)
    gx, gy = ndi.sobel(g, 1), ndi.sobel(g, 0)
    gxx, gyy, gxy = ndi.gaussian_filter(gx * gx, 8), ndi.gaussian_filter(gy * gy, 8), ndi.gaussian_filter(gx * gy, 8)
    coh = np.sqrt((gxx - gyy) ** 2 + 4 * gxy ** 2) / (gxx + gyy + 1e-6)
    h, w = img.shape
    sub = coh[h // 5: 4 * h // 5, w // 5: 4 * w // 5]
    y, x = np.unravel_index(np.argmin(sub), sub.shape)
    return int(x + w // 5), int(y + h // 5)


def compare(m1: list[dict], m2: list[dict], tol=10, angles=range(-24, 25, 3)) -> dict:
    """Generalised-Hough alignment (rotation + translation) then count paired minutiae."""
    if len(m1) < 4 or len(m2) < 4:
        return {"paired": 0, "score": 0.0, "angle": 0, "dx": 0, "dy": 0}
    A = np.array([[p["x"], p["y"]] for p in m1], float)
    B = np.array([[p["x"], p["y"]] for p in m2], float)
    ta = np.array([p["type"] for p in m1])
    tb = np.array([p["type"] for p in m2])
    best = (0, 0, 0.0, 0.0)
    ca = A.mean(0)
    for ang in angles:
        th = np.deg2rad(ang)
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        Ar = (A - ca) @ R.T + ca
        d = (B[None, :, :] - Ar[:, None, :]).reshape(-1, 2)
        same = (ta[:, None] == tb[None, :]).reshape(-1)
        d = d[same]
        if not len(d):
            continue
        bins = np.round(d / tol).astype(int)
        keys, cnt = np.unique(bins, axis=0, return_counts=True)
        k = keys[cnt.argmax()] * tol
        moved = Ar + k
        dist = np.sqrt(((moved[:, None, :] - B[None, :, :]) ** 2).sum(-1))
        paired, used = 0, set()
        for i in np.argsort(dist.min(1)):
            j = int(dist[i].argmin())
            if dist[i, j] <= tol and j not in used and ta[i] == tb[j]:
                used.add(j)
                paired += 1
        if paired > best[0]:
            best = (paired, ang, float(k[0]), float(k[1]))
    score = 2 * best[0] / (len(m1) + len(m2))
    return {"paired": best[0], "score": score, "angle": best[1], "dx": best[2], "dy": best[3]}
