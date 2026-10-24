"""Outils communs (numpy) pour le monstre : courbes, repères, bruit, couleurs, conversion de repère.

Repère de travail = repère Roblox : Y vers le haut, le monstre regarde vers -Z, sa droite est +X, sol à Y = 0,
1 unité = 1 stud. Blender (Z vers le haut) : (x, y, z)_Blender = (X, -Z, Y)_Roblox, donc le monstre regarde
vers +Y dans Blender. L'export glTF/FBX (+Y vers le haut, avant -Z) redonne exactement le repère Roblox.
"""
import math
import numpy as np

TAU = 2.0 * math.pi


def to_blender(p):
    p = np.asarray(p, float)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], -1)


def from_blender(p):
    p = np.asarray(p, float)
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)


def unit(v):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def rot(axis, ang):
    """Matrice de rotation (Rodrigues) d'angle ang (radians) autour de axis."""
    axis = unit(axis)
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def catmull(P, n=10):
    """Catmull-Rom centripète à travers les points P -> polyligne dense (n points par segment)."""
    P = np.asarray(P, float)
    if len(P) == 2:
        t = np.linspace(0.0, 1.0, n + 1)[:, None]
        return P[0] + (P[1] - P[0]) * t
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-6) ** 0.5
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-6) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-6) ** 0.5
        ts = np.linspace(t1, t2, n, endpoint=False)[:, None]
        A1 = (t1 - ts) / (t1 - t0) * p0 + (ts - t0) / (t1 - t0) * p1
        A2 = (t2 - ts) / (t2 - t1) * p1 + (ts - t1) / (t2 - t1) * p2
        A3 = (t3 - ts) / (t3 - t2) * p2 + (ts - t2) / (t3 - t2) * p3
        B1 = (t2 - ts) / (t2 - t0) * A1 + (ts - t0) / (t2 - t0) * A2
        B2 = (t3 - ts) / (t3 - t1) * A2 + (ts - t1) / (t3 - t1) * A3
        out.append((t2 - ts) / (t2 - t1) * B1 + (ts - t1) / (t2 - t1) * B2)
    out.append(Q[-2][None])
    return np.vstack(out)


def arclen(path):
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def resample(path, ds, extra=None):
    """Rééchantillonne une polyligne à pas constant ; extra = tableaux (N,) ou (N,k) interpolés pareil."""
    path = np.asarray(path, float)
    s = arclen(path)
    n = max(3, int(math.ceil(s[-1] / ds)) + 1)
    t = np.linspace(0.0, s[-1], n)
    out = np.stack([np.interp(t, s, path[:, k]) for k in range(3)], 1)
    if extra is None:
        return out
    ex = []
    for e in extra:
        e = np.asarray(e, float)
        if e.ndim == 1:
            ex.append(np.interp(t, s, e))
        else:
            ex.append(np.stack([np.interp(t, s, e[:, k]) for k in range(e.shape[1])], 1))
    return out, ex


def frames(path):
    """Repères à rotation minimale (double réflexion) : T, N, B avec B = T x N."""
    path = np.asarray(path, float)
    T = unit(np.gradient(path, axis=0))
    N = np.zeros_like(path)
    a = np.array([0.0, 1.0, 0.0]) if abs(T[0, 1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n0 = a - T[0] * (a @ T[0])
    N[0] = n0 / np.linalg.norm(n0)
    for i in range(len(path) - 1):
        v1 = path[i + 1] - path[i]
        c1 = v1 @ v1
        if c1 < 1e-16:
            N[i + 1] = N[i]
            continue
        rL = N[i] - (2.0 / c1) * (v1 @ N[i]) * v1
        tL = T[i] - (2.0 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        Ni = rL - (2.0 / c2) * (v2 @ rL) * v2 if c2 > 1e-16 else rL
        Ni = Ni - T[i + 1] * (Ni @ T[i + 1])
        N[i + 1] = Ni / max(np.linalg.norm(Ni), 1e-12)
    return T, N, np.cross(T, N)


def seg_frame(A, B, fwd=(0.0, 0.0, -1.0)):
    """Repère d'un segment A -> B : T (axe), F (avant projeté), X = T x F."""
    T = unit(np.asarray(B, float) - np.asarray(A, float))
    f = np.asarray(fwd, float) - (np.asarray(fwd, float) @ T) * T
    if np.linalg.norm(f) < 1e-3:
        f = np.array([0.0, 1.0, 0.0]) - T[1] * T
    F = unit(f)
    return T, F, np.cross(T, F)


class Noise1D:
    """Bruit 1D lisse (somme de sinus à phases aléatoires), reproductible."""

    def __init__(self, rng, n=3, fmin=0.5, fmax=3.0):
        self.a = rng.uniform(0.3, 1.0, n)
        self.f = rng.uniform(fmin, fmax, n)
        self.p = rng.uniform(0, TAU, n)
        self.norm = 1.0 / max(self.a.sum(), 1e-9)

    def __call__(self, t):
        t = np.asarray(t, float)
        return (self.a[:, None] * np.sin(TAU * self.f[:, None] * t[None] + self.p[:, None])).sum(0) * self.norm


def snoise(rng, t, n=3, fmin=0.5, fmax=3.0):
    return Noise1D(rng, n, fmin, fmax)(t)


def simplify(P, R, tol_rel=0.12, tol_abs=0.004, max_seg=0.35):
    """Garde les points nécessaires d'une polyligne (Douglas-Peucker sur la position et le rayon).

    L'écart toléré est proportionnel au rayon local (un fil fin garde moins de points qu'un gros tendon sur une
    ligne droite, mais ses courbes restent fidèles). max_seg limite la longueur d'un segment."""
    P = np.asarray(P, float)
    R = np.asarray(R, float)
    n = len(P)
    if n <= 2:
        return np.arange(n)
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = P[i], P[j]
        ab = b - a
        L2 = ab @ ab
        idx = np.arange(i + 1, j)
        if L2 < 1e-14:
            d = np.linalg.norm(P[idx] - a, axis=1)
            t = np.zeros(len(idx))
        else:
            t = np.clip(((P[idx] - a) @ ab) / L2, 0, 1)
            d = np.linalg.norm(P[idx] - (a + t[:, None] * ab), axis=1)
        rr = R[i] + (R[j] - R[i]) * t
        dr = np.abs(R[idx] - rr)
        tol = np.maximum(tol_abs, tol_rel * np.maximum(R[idx], 1e-4))
        err = np.maximum(d, dr * 1.5) / tol
        k = int(np.argmax(err))
        if err[k] > 1.0 or math.sqrt(L2) > max_seg:
            m = idx[k] if err[k] > 1.0 else (i + j) // 2
            keep[m] = True
            stack.append((i, m))
            stack.append((m, j))
    return np.nonzero(keep)[0]


# ----------------------------------------------------------------------------------------------------------------
# couleurs (sRGB, converties en linéaire pour Blender)

def srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, float), 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


TAR = np.array([0.045, 0.040, 0.043])        # goudron noir
TAR_DEEP = np.array([0.022, 0.019, 0.021])   # creux, intérieur
BROWN = np.array([0.078, 0.058, 0.046])      # nuances brunes
OXBLOOD = np.array([0.095, 0.042, 0.036])    # brun-rouge des creux
BLUE = np.array([0.040, 0.046, 0.062])       # reflet bleuté froid
BONE = np.array([0.62, 0.55, 0.40])          # crocs
GUM = np.array([0.30, 0.055, 0.045])         # intérieur de la gueule
CLAW = np.array([0.060, 0.055, 0.052])       # griffes (pointe plus claire)
CLAW_TIP = np.array([0.42, 0.38, 0.32])
GLOW = np.array([1.0, 0.45, 0.10])           # lueur de la gueule


def tendon_color(rng, depth=1.0, base=None):
    """Couleur (sRGB) d'un tendon : noir goudron, parfois brun ou bleuté ; plus sombre en profondeur."""
    if base is None:
        r = rng.random()
        base = TAR if r < 0.68 else (BROWN if r < 0.86 else (BLUE if r < 0.95 else OXBLOOD))
    c = base * rng.uniform(0.7, 1.35) * (0.55 + 0.45 * depth)
    return np.clip(c, 0, 1)
