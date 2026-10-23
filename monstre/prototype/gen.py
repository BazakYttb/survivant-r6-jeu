"""Monstre de tendons noirs pour Roblox : génération procédurale (numpy seulement).

Repère Roblox : Y vers le haut, le monstre regarde vers -Z, sa droite est +X, sol à Y = 0, unités en studs.
Posture de repos = la pose de l'image : dos voûté, tête basse en avant, genoux fléchis, longs bras qui
pendent jusqu'aux genoux. Le corps est découpé en pièces rigides (rig sur mesure : colonne en trois segments,
mâchoire, doigts articulés). Chaque pièce reçoit un ou plusieurs maillages (au plus MAX_TRIS triangles chacun)
faits de tendons (tubes torsadés), de filaments qui pendent, de gouttes, de griffes et de crocs.

usage : python gen.py <dossier de sortie> [--glb fichier.glb]
"""
import json
import math
import os
import struct
import sys

import numpy as np

MAX_TRIS = 19500
TAU = 2.0 * math.pi
SEED = 1666

# ----------------------------------------------------------------------------------------------------------------
# géométrie de base


def unit(v):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def catmull(P, n=10):
    """Catmull-Rom centripète à travers les points P -> polyligne dense."""
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


def resample(path, ds):
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(3, int(math.ceil(s[-1] / ds)) + 1)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, path[:, k]) for k in range(3)], 1)


def frames(path):
    """Repères à rotation minimale (double réflexion) : T, N, B avec B = T x N."""
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


def tube(path, radius, sides, cap0=True, cap1=True):
    """Tube le long de path (rayon par point). Faces vers l'extérieur (ordre direct vu de dehors)."""
    path = np.asarray(path, float)
    radius = np.broadcast_to(np.asarray(radius, float), (len(path),))
    T, N, B = frames(path)
    a = np.linspace(0.0, TAU, sides, endpoint=False)
    d = np.cos(a)[None, :, None] * N[:, None, :] + np.sin(a)[None, :, None] * B[:, None, :]
    v = (path[:, None, :] + radius[:, None, None] * d).reshape(-1, 3)
    n = d.reshape(-1, 3)
    m = len(path)
    i = np.arange(m - 1)[:, None]
    j = np.arange(sides)[None, :]
    a0 = i * sides + j
    a1 = i * sides + (j + 1) % sides
    b0, b1 = a0 + sides, a1 + sides
    f = [np.stack([a0, a1, b1], -1).reshape(-1, 3), np.stack([a0, b1, b0], -1).reshape(-1, 3)]
    vs, ns = [v], [n]
    nv = len(v)
    if cap0:
        vs.append(path[:1]); ns.append(-T[:1])
        jj = np.arange(sides)
        f.append(np.stack([np.full(sides, nv), (jj + 1) % sides, jj], -1))
        nv += 1
    if cap1:
        vs.append(path[-1:]); ns.append(T[-1:])
        jj = np.arange(sides)
        base = (m - 1) * sides
        f.append(np.stack([np.full(sides, nv), base + jj, base + (jj + 1) % sides], -1))
        nv += 1
    return np.vstack(vs), np.vstack(f).astype(np.int64), np.vstack(ns)


def ellipsoid(c, axes, radii, nu=10, nv=7):
    """Ellipsoïde (axes : 3 vecteurs unitaires, radii : 3 demi-axes)."""
    c = np.asarray(c, float)
    u = np.linspace(0.0, TAU, nu, endpoint=False)
    w = np.linspace(0.0, math.pi, nv + 1)[1:-1]
    U, W = np.meshgrid(u, w, indexing='ij')
    d = np.stack([np.sin(W) * np.cos(U), np.sin(W) * np.sin(U), np.cos(W)], -1).reshape(-1, 3)
    d = np.vstack([d, [[0, 0, 1.0]], [[0, 0, -1.0]]])
    A = np.stack([np.asarray(x, float) * r for x, r in zip(axes, radii)])          # lignes : axes mis à l'échelle
    v = c + d @ A
    Ainv = np.stack([np.asarray(x, float) / r for x, r in zip(axes, radii)])
    n = unit(d @ Ainv)
    k = nv - 1
    faces = []
    for iu in range(nu):
        iu2 = (iu + 1) % nu
        for iw in range(k - 1):
            p00, p01 = iu * k + iw, iu * k + iw + 1
            p10, p11 = iu2 * k + iw, iu2 * k + iw + 1
            faces += [(p00, p11, p10), (p00, p01, p11)]
        top, bot = nu * k, nu * k + 1
        faces += [(top, iu2 * k, iu * k), (bot, iu * k + k - 1, iu2 * k + k - 1)]
    f = np.array(faces, np.int64)
    # orientation : vers l'extérieur
    e = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    if np.einsum('ij,ij->i', e, v[f[:, 0]] - c).sum() < 0:
        f = f[:, ::-1].copy()
    return v, f, n


def smooth_noise(rng, t, n=3, fmin=0.5, fmax=3.0):
    out = np.zeros_like(np.asarray(t, float))
    for _ in range(n):
        out = out + rng.uniform(0.3, 1.0) * np.sin(TAU * rng.uniform(fmin, fmax) * t + rng.uniform(0, TAU))
    return out / n


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def rot(axis, ang):
    """Matrice de rotation (Rodrigues)."""
    axis = unit(axis)
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


# ----------------------------------------------------------------------------------------------------------------
# couleurs

TAR = np.array([0.030, 0.028, 0.031])        # goudron noir
BROWN = np.array([0.060, 0.044, 0.034])
BLUE = np.array([0.030, 0.036, 0.050])
BONE = np.array([0.30, 0.26, 0.20])          # crocs
GUM = np.array([0.20, 0.030, 0.025])         # intérieur de la gueule
CLAW = np.array([0.045, 0.042, 0.040])


def tendril_color(rng, n, depth=1.0, base=None):
    """Couleur d'un tendon : noir goudron, nuances brunes ou bleutées, plus sombre en profondeur."""
    if base is None:
        r = rng.random()
        base = TAR if r < 0.7 else (BROWN if r < 0.85 else BLUE)
    c = base * rng.uniform(0.55, 1.9) * (0.45 + 0.55 * depth)
    var = 1.0 + 0.25 * rng.standard_normal(n)
    return np.clip(np.outer(np.clip(var, 0.5, 1.6), c), 0.0, 1.0)


# ----------------------------------------------------------------------------------------------------------------
# accumulation des maillages par pièce du rig


class Piece:
    def __init__(self, name):
        self.name = name
        self.chunks = []           # (v, f, n, c)

    def add(self, v, f, n, c):
        self.chunks.append((np.asarray(v, np.float64), np.asarray(f, np.int64), np.asarray(n, np.float64),
                            np.asarray(c, np.float64)))

    @property
    def tris(self):
        return sum(len(ch[1]) for ch in self.chunks)


PIECES = {}


def P(name):
    if name not in PIECES:
        PIECES[name] = Piece(name)
    return PIECES[name]


def add_tube(piece, path, radius, sides, color, cap0=True, cap1=True):
    v, f, n = tube(path, radius, sides, cap0, cap1)
    if callable(color):
        c = color(len(v))
    else:
        c = np.broadcast_to(np.asarray(color, float), (len(v), 3))
    piece.add(v, f, n, c)


# ----------------------------------------------------------------------------------------------------------------
# squelette (pose de repos = pose menaçante de l'image)

def mirror(p):
    return np.array([-p[0], p[1], p[2]])


J = {
    'Pelvis': np.array([0.0, 5.40, 0.22]),
    'SpineLow': np.array([0.0, 5.95, 0.26]),
    'SpineMid': np.array([0.0, 6.80, 0.16]),
    'SpineHigh': np.array([0.0, 7.55, -0.14]),
    'NeckBase': np.array([0.0, 8.08, -0.55]),
    'HeadJoint': np.array([0.0, 8.36, -0.98]),
    'Hip_R': np.array([0.60, 5.20, 0.20]),
    'Knee_R': np.array([0.82, 3.00, -0.30]),
    'Ankle_R': np.array([0.92, 0.72, 0.14]),
    'Shoulder_R': np.array([1.32, 7.80, -0.24]),
    'Elbow_R': np.array([1.76, 5.52, -0.62]),
    'Wrist_R': np.array([1.97, 3.44, -0.94]),
}
for _k in list(J):
    if _k.endswith('_R'):
        J[_k[:-2] + '_L'] = mirror(J[_k])

# tête : inclinée de 32° vers le bas, crâne allongé vers l'avant
HEAD_PITCH = math.radians(32)
FH = np.array([0.0, -math.sin(HEAD_PITCH), -math.cos(HEAD_PITCH)])      # avant de la tête
UH = np.array([0.0, math.cos(HEAD_PITCH), -math.sin(HEAD_PITCH)])       # haut de la tête
XH = np.array([1.0, 0.0, 0.0])
HEAD_C = J['HeadJoint'] + UH * 0.30 + FH * 0.52
JAW_HINGE = J['HeadJoint'] + FH * 0.18 - UH * 0.02
JAW_OPEN = math.radians(13)


def seg_frame(A, B, fwd=(0.0, 0.0, -1.0)):
    T = unit(np.asarray(B, float) - np.asarray(A, float))
    f = np.asarray(fwd, float) - (np.asarray(fwd, float) @ T) * T
    if np.linalg.norm(f) < 1e-3:
        f = np.array([0.0, 1.0, 0.0]) - T[1] * T
    F = unit(f)
    return T, F, np.cross(T, F)


# ----------------------------------------------------------------------------------------------------------------
# faisceaux de tendons


def bundle(piece, A, B, n, r_prof, rng, aspect=(1.0, 1.0), twist=(-0.35, 0.35), rad=(0.03, 0.10),
           rf=(0.62, 1.0), ext=0.10, partial=0.25, ds=0.075, fwd=(0.0, 0.0, -1.0), theta=None, base=None,
           bend=None):
    """n tendons torsadés autour de l'axe A -> B ; r_prof(u, th) = rayon du faisceau (u dans [0, 1])."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    L = float(np.linalg.norm(B - A))
    for k in range(n):
        th0 = rng.uniform(0, TAU) if theta is None else theta(k, rng)
        tw = rng.uniform(*twist)
        r_f = rng.uniform(*rf)
        tr = math.exp(rng.uniform(math.log(rad[0]), math.log(rad[1])))
        if rng.random() < partial:
            s0 = rng.uniform(-ext / L, 0.65)
            s1 = min(1 + ext / L, s0 + rng.uniform(0.25, 0.9))
            tapered = True
        else:
            s0 = -ext / L * rng.uniform(0.3, 1.0)
            s1 = 1 + ext / L * rng.uniform(0.3, 1.0)
            tapered = False
        m = max(6, int((s1 - s0) * L / ds) + 1)
        s = np.linspace(s0, s1, m)
        u = np.clip(s, 0.0, 1.0)
        th = th0 + TAU * tw * s + 0.35 * smooth_noise(rng, s)
        rr = r_prof(u, th) * r_f * (1 + 0.07 * smooth_noise(rng, s, fmin=1, fmax=5))
        Pp = (A[None] + np.outer(s * L, T)
              + rr[:, None] * (aspect[0] * np.cos(th)[:, None] * X[None] + aspect[1] * np.sin(th)[:, None] * F[None]))
        if bend is not None:
            Pp = Pp + bend(u)
        radius = tr * (0.82 + 0.18 * smooth_noise(rng, s, fmin=2, fmax=9))
        if tapered:
            radius = radius * smoothstep((s - s0) / 0.12) * smoothstep((s1 - s) / 0.18) + 0.004
        sides = 6 if tr > 0.055 else (5 if tr > 0.03 else 4)
        depth = (r_f - rf[0]) / max(rf[1] - rf[0], 1e-6)
        add_tube(piece, Pp, radius, sides, lambda nv: tendril_color(rng, nv, 0.4 + 0.6 * depth, base))


def braid(piece, center, rng, strands=3, rb=0.035, turns=3.0, tube_r=0.028, ds=0.05, base=None, taper=True):
    """Tresse de quelques tendons autour d'une ligne centrale (côtes, doigts, racines)."""
    C = resample(np.asarray(center, float), ds)
    T, N, B = frames(C)
    m = len(C)
    t = np.linspace(0.0, 1.0, m)
    radius_scale = np.ones(m)
    if taper is True:
        radius_scale = 1.0 - 0.75 * t ** 1.5
    elif callable(taper):
        radius_scale = taper(t)
    for j in range(strands):
        ph = TAU * j / strands + rng.uniform(-0.3, 0.3)
        a = ph + TAU * turns * t + 0.3 * smooth_noise(rng, t)
        off = rb * radius_scale * (1 + 0.15 * smooth_noise(rng, t, fmin=2, fmax=6))
        Pp = C + off[:, None] * (np.cos(a)[:, None] * N + np.sin(a)[:, None] * B)
        r = tube_r * rng.uniform(0.75, 1.25) * radius_scale * (0.85 + 0.15 * smooth_noise(rng, t, fmin=3, fmax=9)) + 0.004
        sides = 6 if tube_r > 0.05 else 5 if tube_r > 0.025 else 4
        add_tube(piece, Pp, r, sides, lambda nv: tendril_color(rng, nv, 0.9, base))


def drip(piece, P0, out, rng, length, r0, droplet=True, base=None):
    """Filament visqueux qui pend : part un peu vers l'extérieur puis tombe, s'affine, finit par une goutte."""
    P0 = np.asarray(P0, float)
    out = unit(np.asarray(out, float) * np.array([1.0, 0.3, 1.0]))
    down = np.array([0.0, -1.0, 0.0])
    m = max(8, int(length / 0.045))
    t = np.linspace(0.0, 1.0, m)
    side = unit(np.cross(out, down)) if np.linalg.norm(np.cross(out, down)) > 1e-3 else np.array([1.0, 0, 0])
    Pp = (P0[None] + out[None] * (0.16 * length * np.sin(0.5 * math.pi * np.minimum(t * 2.2, 1.0)))[:, None]
          + down[None] * (length * t ** 1.4)[:, None]
          + side[None] * (0.06 * length * smooth_noise(rng, t, fmin=0.5, fmax=1.5) * t)[:, None])
    radius = r0 * (1 - t) ** 0.85 + 0.0045
    add_tube(piece, Pp, radius, 5 if r0 > 0.03 else 4, lambda nv: tendril_color(rng, nv, 0.8, base), cap1=False)
    if droplet:
        rd = max(0.016, r0 * rng.uniform(0.55, 0.9))
        v, f, n = ellipsoid(Pp[-1] + down * rd * 0.8, (np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), down),
                            (rd, rd, rd * 1.6), nu=7, nv=5)
        piece.add(v, f, n, tendril_color(rng, len(v), 1.0, base))


def claw(piece, base_p, direction, curl_axis, rng, length=0.4, r0=0.06, curl=0.9):
    """Griffe : cône courbé et pointu."""
    m = 14
    t = np.linspace(0.0, 1.0, m)
    d = unit(direction)
    pts = [np.asarray(base_p, float)]
    step = length / (m - 1)
    for k in range(1, m):
        d = rot(curl_axis, curl / (m - 1)) @ d
        pts.append(pts[-1] + d * step)
    Pp = np.array(pts)
    radius = r0 * (1 - t) ** 1.15 + 0.002
    col = np.clip(np.outer(1.0 + 1.8 * t ** 3, CLAW * rng.uniform(0.8, 1.3)), 0, 1)        # pointe plus claire
    v, f, n = tube(Pp, radius, 6, True, True)
    c = np.vstack([np.repeat(col, 6, axis=0), col[:1], col[-1:]])
    piece.add(v, f, n, c)


def fang(piece, base_p, direction, rng, length, r0, inward):
    """Croc en aiguille, légèrement recourbé vers l'intérieur de la gueule."""
    m = 7
    t = np.linspace(0.0, 1.0, m)
    d = unit(direction)
    Pp = np.asarray(base_p, float)[None] + np.outer(t * length, d) + np.outer((t ** 2) * length * 0.25, unit(inward))
    radius = r0 * (1 - t) ** 1.2 + 0.0015
    col = np.clip(np.outer(0.75 + 0.5 * t, BONE * rng.uniform(0.7, 1.1)), 0, 1)
    v, f, n = tube(Pp, radius, 5, True, True)
    c = np.vstack([np.repeat(col, 5, axis=0), col[:1], col[-1:]])
    piece.add(v, f, n, c)


def spike(piece, base_p, direction, rng, length, r0):
    """Épine noire (vertèbres, épaules)."""
    claw(piece, base_p, direction, np.cross(unit(direction), [1.0, 0, 0]) if abs(unit(direction)[0]) < 0.9
         else np.array([0, 0, 1.0]), rng, length=length, r0=r0, curl=rng.uniform(0.2, 0.6))


# ----------------------------------------------------------------------------------------------------------------
# régions du corps


def build_legs(rng):
    for side, s in (('R', 1.0), ('L', -1.0)):
        hip, knee, ankle = J['Hip_' + side], J['Knee_' + side], J['Ankle_' + side]
        thigh, shin, foot = P('Thigh_' + side), P('Shin_' + side), P('Foot_' + side)
        # cuisse : grosse en haut, nerveuse au genou
        rth = lambda u, th: 0.40 - 0.16 * u + 0.05 * np.sin(math.pi * u) * np.maximum(0, np.cos(th))
        bundle(thigh, hip + np.array([0, 0.25, 0]), knee, 34, rth, rng, rad=(0.03, 0.12), twist=(-0.45, 0.45))
        bundle(thigh, hip, knee, 14, lambda u, th: 0.42 - 0.15 * u, rng, rad=(0.012, 0.03), rf=(0.98, 1.06),
               twist=(-1.6, 1.6), partial=0.4)                                         # fibres croisées en surface
        # genou noueux
        Tk, Fk, Xk = seg_frame(hip, knee)
        for _ in range(5):
            a = rng.uniform(-1.2, 1.2)
            c = knee + Fk * 0.16 + Xk * 0.1 * math.sin(a)
            v, f, n = ellipsoid(c, (Xk, Fk, Tk), np.array([0.11, 0.07, 0.14]) * rng.uniform(0.7, 1.2), nu=8, nv=6)
            shin.add(v, f, n, tendril_color(rng, len(v), 1.0))
        # tibia : mollet à l'arrière, cheville très fine
        Ts, Fs, Xs = seg_frame(knee, ankle)

        def rsh(u, th):
            calf = 0.11 * np.exp(-((u - 0.28) / 0.16) ** 2) * np.maximum(0, -np.sin(th)) ** 1.5
            return 0.25 - 0.14 * u + calf
        bundle(shin, knee, ankle, 30, rsh, rng, rad=(0.025, 0.10), twist=(-0.5, 0.5))
        bundle(shin, knee, ankle, 12, lambda u, th: 0.26 - 0.13 * u, rng, rad=(0.01, 0.025), rf=(0.98, 1.05),
               twist=(-1.8, 1.8), partial=0.5)
        # filaments qui pendent de la cuisse et du genou
        for _ in range(9):
            u = rng.uniform(0.2, 0.95)
            th = rng.uniform(0, TAU)
            Tt, Ft, Xt = seg_frame(hip, knee)
            p0 = hip + (knee - hip) * u + (0.4 - 0.16 * u) * (math.cos(th) * Xt + math.sin(th) * Ft)
            drip(thigh, p0, math.cos(th) * Xt + math.sin(th) * Ft, rng, rng.uniform(0.4, 1.6), rng.uniform(0.02, 0.05))
        for _ in range(6):
            u = rng.uniform(0.1, 0.7)
            th = rng.uniform(0, TAU)
            p0 = knee + (ankle - knee) * u + (0.24 - 0.12 * u) * (math.cos(th) * Xs + math.sin(th) * Fs)
            drip(shin, p0, math.cos(th) * Xs + math.sin(th) * Fs, rng, rng.uniform(0.3, 0.9), rng.uniform(0.015, 0.035))
        # pied : racines qui s'étalent au sol depuis la cheville
        ground = 0.03
        ank = ankle + np.array([0, -0.05, 0])
        for k in range(11):
            back = k >= 8
            ang = (rng.uniform(-1.1, 1.1) if not back else rng.uniform(2.3, 3.9))
            dirg = np.array([s * math.sin(ang) * 0.9, 0.0, -math.cos(ang)])
            length = rng.uniform(0.9, 1.9) if not back else rng.uniform(0.4, 0.9)
            spread = ank + np.array([s * 0.05, -0.45, 0])
            pts = [ank + np.array([rng.uniform(-0.06, 0.06), 0.05, rng.uniform(-0.06, 0.06)]),
                   spread + dirg * 0.15 + np.array([0, -0.12, 0]),
                   np.array([spread[0], ground + 0.04, spread[2]]) + dirg * (0.45 * length),
                   np.array([spread[0], ground + rng.uniform(0.0, 0.05), spread[2]]) + dirg * length
                   + np.array([rng.uniform(-0.15, 0.15), 0, rng.uniform(-0.15, 0.15)])]
            path = resample(catmull(pts, 10), 0.05)
            t = np.linspace(0, 1, len(path))
            r = rng.uniform(0.04, 0.085) * (1 - 0.85 * t ** 1.2) + 0.004
            add_tube(foot, path, r, 5, lambda nv: tendril_color(rng, nv, 0.9), cap1=False)
            if rng.random() < 0.6:                                  # radicelles
                q = path[int(len(path) * rng.uniform(0.45, 0.8))]
                d2 = unit(dirg + np.array([rng.uniform(-0.8, 0.8), 0, rng.uniform(-0.8, 0.8)]))
                pts2 = [q, q + d2 * 0.25 + np.array([0, -0.01, 0]), np.array([q[0], ground, q[2]]) + d2 * 0.55]
                p2 = resample(catmull(pts2, 8), 0.04)
                t2 = np.linspace(0, 1, len(p2))
                add_tube(foot, p2, 0.025 * (1 - 0.8 * t2) + 0.003, 4, lambda nv: tendril_color(rng, nv, 0.8), cap1=False)
        # cheville : faisceau serré qui descend dans le pied
        bundle(foot, ankle + np.array([0, 0.12, 0]), ankle + np.array([s * 0.04, -0.55, -0.08]), 14,
               lambda u, th: 0.14 + 0.09 * u, rng, rad=(0.025, 0.06), twist=(-0.6, 0.6), ext=0.04)


def build_torso(rng):
    pelvis, low, mid, high, neck = J['Pelvis'], J['SpineLow'], J['SpineMid'], J['SpineHigh'], J['NeckBase']
    Ppel, Pabd, Pche, Pupc = P('Pelvis'), P('Abdomen'), P('Chest'), P('UpperChest')
    # bassin
    bot = pelvis + np.array([0, -0.55, 0.02])
    bundle(Ppel, bot, low, 40, lambda u, th: 0.62 + 0.06 * np.sin(math.pi * u), rng, aspect=(1.0, 0.62),
           rad=(0.03, 0.11), twist=(-0.3, 0.3), ext=0.05)
    for side, s in (('R', 1.0), ('L', -1.0)):                       # attaches des hanches
        hip = J['Hip_' + side]
        bundle(Ppel, low + np.array([s * 0.35, 0.0, 0.0]), hip + np.array([s * 0.05, -0.15, 0]), 10,
               lambda u, th: 0.2 + 0.08 * u, rng, rad=(0.03, 0.08), ext=0.03)
    # lambeaux qui pendent du bassin (devant et côtés)
    Tp, Fp, Xp = seg_frame(bot, low)
    for _ in range(26):
        th = rng.uniform(-0.6 * math.pi, 1.6 * math.pi)
        p0 = bot + Tp * rng.uniform(0.0, 0.25) + 0.62 * (math.cos(th) * Xp + 0.62 * math.sin(th) * Fp)
        drip(Ppel, p0, math.cos(th) * Xp + math.sin(th) * Fp, rng, rng.uniform(0.5, 2.2), rng.uniform(0.02, 0.06))
    # abdomen : taille étroite, treillis ajouré (on voit au travers)
    bundle(Pabd, low, mid, 18, lambda u, th: 0.47 + 0.04 * np.sin(math.pi * u), rng, aspect=(1.0, 0.72),
           rad=(0.04, 0.10), twist=(-0.7, 0.7), ext=0.12, partial=0.1)
    bundle(Pabd, low, mid, 14, lambda u, th: 0.30, rng, aspect=(1.0, 0.8), rad=(0.05, 0.12), rf=(0.4, 0.8),
           twist=(-0.25, 0.25), ext=0.12)                            # masse sombre au centre (profondeur)
    bundle(Pabd, low, mid, 8, lambda u, th: 0.50, rng, aspect=(1.0, 0.72), rad=(0.012, 0.025), rf=(1.0, 1.05),
           twist=(-1.5, 1.5), partial=0.3)
    Ta, Fa, Xa = seg_frame(low, mid)
    for _ in range(14):
        th = rng.uniform(0, TAU)
        p0 = low + (mid - low) * rng.uniform(0.0, 0.7) + 0.48 * (math.cos(th) * Xa + 0.72 * math.sin(th) * Fa)
        drip(Pabd, p0, math.cos(th) * Xa + math.sin(th) * Fa, rng, rng.uniform(0.4, 1.8), rng.uniform(0.02, 0.05))
    # poitrine : cage thoracique de côtes tressées + sternum + masse intérieure
    Tc, Fc, Xc = seg_frame(mid, high)
    bundle(Pche, mid, high, 16, lambda u, th: 0.34 + 0.05 * u, rng, aspect=(1.0, 0.85), rad=(0.05, 0.12),
           rf=(0.3, 0.8), ext=0.1)
    for i in range(7):
        u = 0.08 + 0.13 * i
        c0 = mid + (high - mid) * u
        a_half, b_half = 0.66 + 0.12 * u - 0.05 * max(0, i - 4), 0.47
        for side, s in (('R', 1.0), ('L', -1.0)):
            phis = np.linspace(-1.35, 1.25, 26)                # du dos (-F) vers l'avant (+F) en passant par le côté
            drop = -0.22 * (phis + 1.35) / 2.6                 # les côtes descendent vers l'avant
            pts = c0[None] + (s * a_half * np.cos(phis))[:, None] * Xc[None] + (b_half * np.sin(phis))[:, None] * Fc[None] \
                + drop[:, None] * Tc[None]
            braid(Pche, pts, rng, strands=3, rb=0.03, turns=2.5, tube_r=0.026, taper=lambda t: 1.0 - 0.3 * t)
    bundle(Pche, mid + Fc * 0.42, high + Fc * 0.46, 6, lambda u, th: 0.06, rng, rad=(0.03, 0.06), twist=(-1, 1))
    bundle(Pche, mid - Fc * 0.42, high - Fc * 0.46, 10, lambda u, th: 0.16, rng, aspect=(1.6, 0.6),
           rad=(0.04, 0.09), twist=(-0.3, 0.3))                      # muscles du dos de part et d'autre de la colonne
    for _ in range(12):
        th = rng.uniform(0, TAU)
        p0 = mid + (high - mid) * rng.uniform(0.0, 0.8) + 0.66 * math.cos(th) * Xc + 0.47 * math.sin(th) * Fc
        drip(Pche, p0, math.cos(th) * Xc + math.sin(th) * Fc, rng, rng.uniform(0.4, 1.4), rng.uniform(0.02, 0.045))
    # haut du dos : trapèzes, clavicules, épaules
    bundle(Pupc, high, neck, 30, lambda u, th: 0.66 - 0.36 * u, rng, aspect=(1.0, 0.7), rad=(0.035, 0.11),
           twist=(-0.4, 0.4), ext=0.08)
    for side, s in (('R', 1.0), ('L', -1.0)):
        sh = J['Shoulder_' + side]
        bundle(Pupc, high + np.array([s * 0.2, 0.15, -0.25]), sh + np.array([-s * 0.05, 0.02, -0.05]), 9,
               lambda u, th: 0.09, rng, rad=(0.03, 0.06), twist=(-0.8, 0.8), ext=0.05)         # clavicule
        bundle(Pupc, neck + np.array([s * 0.12, -0.05, 0.25]), sh + np.array([-s * 0.12, 0.12, 0.12]), 12,
               lambda u, th: 0.16 - 0.04 * u, rng, rad=(0.03, 0.08), twist=(-0.4, 0.4), ext=0.05)   # trapèze
    # colonne : vertèbres saillantes et épines le long du dos
    spine = resample(catmull([J['Pelvis'] + np.array([0, 0.2, 0.42]), low + np.array([0, 0, 0.42]),
                              mid + np.array([0, 0, 0.48]), high + np.array([0, 0.05, 0.42]),
                              neck + np.array([0, -0.05, 0.3]), J['HeadJoint'] + np.array([0, -0.05, 0.22])], 12), 0.16)
    owners = [Ppel, Pabd, Pche, Pupc]
    ys = [low[1], mid[1], high[1]]
    for q in spine:
        owner = owners[sum(q[1] > y for y in ys)] if q[1] < neck[1] else Pupc
        back = unit(np.array([0, 0.35, 1.0]))
        v, f, n = ellipsoid(q, (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])),
                            np.array([0.09, 0.07, 0.08]) * rng.uniform(0.8, 1.2), nu=8, nv=6)
        owner.add(v, f, n, tendril_color(rng, len(v), 1.0))
        if rng.random() < 0.75:
            spike(owner, q + back * 0.05, back + np.array([0, rng.uniform(-0.2, 0.3), 0]), rng,
                  length=rng.uniform(0.12, 0.3), r0=0.035)


def build_arms(rng):
    for side, s in (('R', 1.0), ('L', -1.0)):
        sh, el, wr = J['Shoulder_' + side], J['Elbow_' + side], J['Wrist_' + side]
        up, fo = P('UpperArm_' + side), P('Forearm_' + side)
        # bras : deltoïde noueux puis biceps fin
        rua = lambda u, th: 0.27 - 0.08 * u + 0.12 * np.exp(-((u - 0.06) / 0.12) ** 2)
        bundle(up, sh + np.array([0, 0.18, 0]), el, 30, rua, rng, rad=(0.03, 0.10), twist=(-0.5, 0.5))
        bundle(up, sh, el, 10, lambda u, th: 0.27 - 0.07 * u, rng, rad=(0.01, 0.022), rf=(0.98, 1.06),
               twist=(-1.8, 1.8), partial=0.5)
        Tu, Fu, Xu = seg_frame(sh, el)
        for k in range(3):                                           # épines d'épaule
            d = unit(np.array([s * 0.6, 1.0, 0.25]) + rng.uniform(-0.35, 0.35, 3))
            spike(up, sh + np.array([s * 0.12, 0.2, 0]) + d * 0.18, d, rng, length=rng.uniform(0.15, 0.35), r0=0.04)
        # avant-bras : épais au coude, poignet décharné
        Tf, Ff, Xf = seg_frame(el, wr)
        rfa = lambda u, th: 0.22 - 0.11 * u + 0.05 * np.exp(-((u - 0.15) / 0.14) ** 2)
        bundle(fo, el, wr, 28, rfa, rng, rad=(0.025, 0.09), twist=(-0.55, 0.55))
        bundle(fo, el, wr, 10, lambda u, th: 0.21 - 0.1 * u, rng, rad=(0.01, 0.02), rf=(0.98, 1.06),
               twist=(-2.0, 2.0), partial=0.5)
        v, f, n = ellipsoid(el + Tu * 0.02 - Fu * 0.12, (Xu, Fu, Tu), (0.13, 0.1, 0.15), nu=8, nv=6)   # coude osseux
        fo.add(v, f, n, tendril_color(rng, len(v), 1.0))
        # filaments qui pendent des bras (beaucoup sous les avant-bras)
        for _ in range(8):
            u = rng.uniform(0.15, 0.95)
            th = rng.uniform(0, TAU)
            p0 = sh + (el - sh) * u + (0.25 - 0.07 * u) * (math.cos(th) * Xu + math.sin(th) * Fu)
            drip(up, p0, math.cos(th) * Xu + math.sin(th) * Fu, rng, rng.uniform(0.3, 1.4), rng.uniform(0.018, 0.045))
        for _ in range(14):
            u = rng.uniform(0.05, 0.95)
            th = rng.uniform(0, TAU)
            p0 = el + (wr - el) * u + (0.2 - 0.1 * u) * (math.cos(th) * Xf + math.sin(th) * Ff)
            drip(fo, p0, math.cos(th) * Xf + math.sin(th) * Ff, rng, rng.uniform(0.4, 2.3), rng.uniform(0.015, 0.04))


HAND = {}            # frames des mains (pour le rig)


def build_hands(rng):
    for side, s in (('R', 1.0), ('L', -1.0)):
        el, wr = J['Elbow_' + side], J['Wrist_' + side]
        hand = P('Hand_' + side)
        Tf = unit(wr - el)
        D = unit(rot([1.0, 0, 0], math.radians(-14)) @ Tf)                # main un peu tournée vers l'avant
        palm_n = unit(np.array([-s * 1.0, 0.0, 0.55]) - D * (np.array([-s * 1.0, 0.0, 0.55]) @ D))   # paume vers l'intérieur-arrière
        W = unit(np.cross(D, palm_n))                                        # largeur de la main (doigts écartés)
        palm_len = 0.55
        knuck = wr + D * palm_len
        HAND[side] = dict(D=D, N=palm_n, W=W, knuckles=knuck)
        bundle(hand, wr - D * 0.08, knuck, 16, lambda u, th: 0.13 + 0.07 * u, rng, aspect=(1.0, 0.5),
               rad=(0.025, 0.06), twist=(-0.3, 0.3), ext=0.04, fwd=-palm_n)
        fingers = []
        for i, off in enumerate((-0.17, -0.06, 0.05, 0.16)):
            base = knuck + W * off * s * 1.0
            fan = math.radians((-14, -5, 4, 13)[i]) * s
            d0 = unit(rot(palm_n, fan) @ D)
            lens = (0.62, 0.55) if i in (1, 2) else (0.55, 0.48)
            curl_axis = unit(np.cross(d0, palm_n))
            a = base
            d = rot(curl_axis, math.radians(22)) @ d0
            segs = []
            for j, Lseg in enumerate(lens):
                b = a + d * Lseg
                segs.append((a.copy(), b.copy(), d.copy()))
                a = b
                d = rot(curl_axis, math.radians(34 if j == 0 else 30)) @ d
            fingers.append((segs, curl_axis, d))
        # pouce : du côté avant de la paume
        tb = wr + D * 0.18 + W * (-0.16) * s
        dt = unit(D * 0.6 - palm_n * 0.5 + W * (-0.4) * s)
        ct = unit(np.cross(dt, palm_n))
        fingers.append(([(tb, tb + dt * 0.42, dt)], ct, rot(ct, math.radians(30)) @ dt))
        HAND[side]['fingers'] = fingers
        names = ['Index', 'Middle', 'Ring', 'Pinky', 'Thumb']
        for i, (segs, cax, dend) in enumerate(fingers):
            for j, (a, b, d) in enumerate(segs):
                part = P('%s%d_%s' % (names[i], j + 1, side))
                r0 = 0.07 - 0.012 * j
                bundle(part, a - d * 0.03, b, 6, lambda u, th, r0=r0: r0 - 0.012 * u, rng, rad=(0.02, 0.045),
                       twist=(-0.6, 0.6), ext=0.03, partial=0.0, ds=0.05)
                v, f, n = ellipsoid(a, (cax, unit(np.cross(d, cax)), d), np.array([0.075, 0.07, 0.08]) * (1 - 0.15 * j), nu=8, nv=6)
                part.add(v, f, n, tendril_color(rng, len(v), 1.0))                # jointure
            last = P('%s%d_%s' % (names[i], len(segs), side))
            claw(last, segs[-1][1], dend, cax, rng, length=0.42 if i < 4 else 0.3, r0=0.055, curl=1.0)
            for _ in range(2 if i < 4 else 1):                              # fils qui pendent des doigts
                a, b, d = segs[rng.integers(len(segs))]
                drip(last if rng.random() < 0.5 else P('%s1_%s' % (names[i], side)), a + (b - a) * rng.uniform(0.2, 0.9),
                     -palm_n, rng, rng.uniform(0.2, 0.9), rng.uniform(0.012, 0.025))


def head_radius(d):
    """Rayon de la tête dans la direction d (repère de la tête : colonnes F, X, U)."""
    df, dx, du = d[:, 0], d[:, 1], d[:, 2]
    aF = np.where(df > 0, 0.96, 0.60)
    aU = np.where(du > 0, 0.54, 0.40)
    aX = 0.47 * (1 - 0.28 * np.clip(df, 0, 1) ** 1.5) * (1 + 0.1 * np.clip(du, 0, 1))
    r = 1.0 / np.sqrt((df / aF) ** 2 + (dx / aX) ** 2 + (du / aU) ** 2)
    # crête au sommet, vers l'arrière
    r = r * (1 + 0.10 * np.exp(-((dx / 0.18) ** 2)) * np.clip(du, 0, 1) * np.clip(0.4 - df, 0, 1))
    # rainures de tendons moulées dans le crâne, d'avant en arrière
    psi = np.arctan2(dx, du)
    r = r * (1 + 0.016 * np.sin(13 * psi + 3 * df) * np.clip(du + 0.3, 0, 1))
    # orbites creuses (pas d'yeux)
    for sx in (1, -1):
        e = (df - 0.72) ** 2 / 0.02 + (dx - sx * 0.36) ** 2 / 0.012 + (du - 0.32) ** 2 / 0.02
        r = r * (1 - 0.13 * np.exp(-e))
    # joues creuses
    r = r * (1 - 0.06 * np.exp(-((df - 0.35) ** 2 / 0.05 + (np.abs(dx) - 0.8) ** 2 / 0.05 + (du + 0.25) ** 2 / 0.06)))
    return r


def build_head(rng):
    head, jaw, neckp = P('Head'), P('Jaw'), P('Neck')
    M = np.stack([FH, XH, UH], 1)                     # repère tête -> monde (colonnes)
    # coque du crâne (mâchoire supérieure comprise) : sphère déformée, latitude depuis le haut
    nlat, nlon = 46, 64
    lat = np.linspace(0.0, math.pi, nlat)
    lon = np.linspace(0.0, TAU, nlon, endpoint=False)
    LA, LO = np.meshgrid(lat, lon, indexing='ij')
    dl = np.stack([np.sin(LA) * np.cos(LO), np.sin(LA) * np.sin(LO), np.cos(LA)], -1).reshape(-1, 3)   # (F, X, U)
    # la gueule : bas de l'avant découpé (ligne des lèvres), le reste fermé
    lip = (dl[:, 2] < -0.05 + 0.22 * (1 - dl[:, 0])) & (dl[:, 0] > 0.15)
    r = head_radius(dl)
    vloc = dl * r[:, None]
    # palais : la partie découpée remonte en voûte sombre à l'intérieur
    vloc[lip] = vloc[lip] * np.array([0.92, 0.85, 0.3])[None] + np.array([0, 0, -0.06])
    V = HEAD_C + vloc @ M.T
    C = np.tile(TAR * 0.8, (len(V), 1)) * (0.75 + 0.5 * rng.random((len(V), 1)))
    C[lip] = GUM * (0.6 + 0.6 * rng.random((lip.sum(), 1)))
    faces = []
    for i in range(nlat - 1):
        for j in range(nlon):
            j2 = (j + 1) % nlon
            a0, a1, b0, b1 = i * nlon + j, i * nlon + j2, (i + 1) * nlon + j, (i + 1) * nlon + j2
            faces += [(a0, b1, a1), (a0, b0, b1)]
    F = np.array(faces, np.int64)
    e = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.einsum('ij,ij->i', e, V[F[:, 0]] - HEAD_C).sum() < 0:
        F = F[:, ::-1].copy()
        e = -e                                     # normales vers l'extérieur, comme les faces
    Nn = np.zeros_like(V)
    np.add.at(Nn, F[:, 0], e); np.add.at(Nn, F[:, 1], e); np.add.at(Nn, F[:, 2], e)
    head.add(V, F, unit(Nn + 1e-12), C)
    # crocs du haut le long de la ligne des lèvres (en U)
    for k in range(18):
        a = math.radians(-62 + 124 * k / 17)
        dloc = np.array([[math.cos(a) * 0.92, math.sin(a) * 0.92, -0.18]])
        rr = head_radius(unit(dloc))[0] * 0.9
        pl = HEAD_C + (unit(dloc)[0] * rr) @ M.T
        L = 0.07 + 0.11 * math.cos(a) ** 2 * rng.uniform(0.7, 1.3)
        fang(head, pl, -UH + FH * 0.1, rng, L, 0.022, -(FH * math.cos(a) + XH * math.sin(a)))
    # mâchoire inférieure : coque en U sous la gueule, entrouverte (articulée à la charnière)
    Rj = rot(XH, JAW_OPEN)
    nl, nu = 18, 36
    tt = np.linspace(-1.0, 1.0, nl)                                     # gauche -> droite (en U)
    ww = np.linspace(0.0, 1.0, nu)
    V2, C2 = [], []
    for w in ww:                                                        # w : de la lèvre (0) au menton (1)
        for t in tt:
            a = t * math.radians(80)
            fwd = 0.62 * math.cos(a) * (1 - 0.15 * w)
            lat = 0.40 * math.sin(a) * (1 - 0.2 * w)
            up = -0.08 - 0.22 * math.sin(math.pi * 0.5 * w) - 0.04 * w
            inward = 1 - 0.7 * w ** 2
            V2.append(HEAD_C + FH * (fwd * inward + 0.08) + XH * lat * inward + UH * (up - 0.05))
            C2.append(TAR * (0.7 + 0.5 * rng.random()))
    V2 = np.array(V2)
    V2 = JAW_HINGE + (V2 - JAW_HINGE) @ Rj.T
    F2 = []
    for i in range(nu - 1):
        for j in range(nl - 1):
            a0, a1, b0, b1 = i * nl + j, i * nl + j + 1, (i + 1) * nl + j, (i + 1) * nl + j + 1
            F2 += [(a0, a1, b1), (a0, b1, b0)]
    F2 = np.array(F2, np.int64)
    e2 = np.cross(V2[F2[:, 1]] - V2[F2[:, 0]], V2[F2[:, 2]] - V2[F2[:, 0]])
    if (e2 @ (-UH)).sum() < 0:
        F2 = F2[:, ::-1].copy()
        e2 = -e2
    N2 = np.zeros_like(V2)
    np.add.at(N2, F2[:, 0], e2); np.add.at(N2, F2[:, 1], e2); np.add.at(N2, F2[:, 2], e2)
    jaw.add(V2, F2, unit(N2 + 1e-12), np.array(C2))
    # dessus de la mâchoire (langue, gencives) vu par la gueule : même coque décalée, faces vers le haut
    V3 = V2 + (UH @ Rj.T) * 0.015
    jaw.add(V3, F2[:, ::-1].copy(), -unit(N2 + 1e-12), np.tile(GUM, (len(V3), 1)) * (0.5 + 0.6 * rng.random((len(V3), 1))))
    # crocs du bas
    for k in range(16):
        t = -1 + 2 * k / 15
        idx = int(round((t + 1) / 2 * (nl - 1)))
        pl = V2[idx]
        L = 0.06 + 0.1 * (1 - abs(t)) * rng.uniform(0.7, 1.3)
        fang(jaw, pl, (UH @ Rj.T) + (FH @ Rj.T) * 0.15, rng, L, 0.02, -(pl - HEAD_C) * np.array([1, 0, 1]))
    # tendons du crâne : partent du sommet et de l'arrière, coulent vers la nuque et le cou
    for k in range(34):
        lo0 = rng.uniform(math.radians(100), math.radians(260))
        la0 = rng.uniform(math.radians(15), math.radians(85))
        pts = []
        for w in np.linspace(0, 1, 7):
            la = la0 + (math.radians(150) - la0) * w
            lo = lo0 + (math.pi - lo0) * w * 0.5
            dd = np.array([[math.sin(la) * math.cos(lo), math.sin(la) * math.sin(lo), math.cos(la)]])
            rr = head_radius(dd)[0] + 0.02
            pts.append(HEAD_C + (dd[0] * rr) @ M.T)
        tail = J['NeckBase'] + np.array([rng.uniform(-0.22, 0.22), rng.uniform(-0.15, 0.1), rng.uniform(0.0, 0.25)])
        pts.append(tail)
        path = resample(catmull(np.array(pts), 8), 0.06)
        t = np.linspace(0, 1, len(path))
        r = rng.uniform(0.025, 0.06) * (1 - 0.5 * t) + 0.005
        add_tube(head, path, r, 5, lambda nv: tendril_color(rng, nv, 0.9), cap0=True, cap1=True)
    # filaments qui pendent du menton et des joues
    for k in range(10):
        t = rng.uniform(-0.9, 0.9)
        idx = int(round((t + 1) / 2 * (nl - 1))) + (nu - rng.integers(1, 6)) * nl
        drip(jaw, V2[idx], -(UH @ Rj.T) + FH * 0.3, rng, rng.uniform(0.3, 1.5), rng.uniform(0.012, 0.03))
    # cou : faisceau torsadé
    bundle(neckp, J['NeckBase'] - np.array([0, 0.12, -0.08]), J['HeadJoint'] + FH * 0.1, 22,
           lambda u, th: 0.21 - 0.03 * u, rng, rad=(0.03, 0.08), twist=(-0.6, 0.6), ext=0.06)


def build_all():
    rng = np.random.default_rng(SEED)
    build_legs(rng)
    build_torso(rng)
    build_arms(rng)
    build_hands(rng)
    build_head(rng)


# ----------------------------------------------------------------------------------------------------------------
# rig : pièces, articulations (pivot monde), parent

def rig_spec():
    """Pièces du rig : parent, pivot de l'articulation qui la relie à son parent (monde)."""
    R = {'Pelvis': ('HumanoidRootPart', J['Pelvis'], 'Root'),
         'Abdomen': ('Pelvis', J['SpineLow'], 'SpineLow'),
         'Chest': ('Abdomen', J['SpineMid'], 'SpineMid'),
         'UpperChest': ('Chest', J['SpineHigh'], 'SpineHigh'),
         'Neck': ('UpperChest', J['NeckBase'], 'NeckBase'),
         'Head': ('Neck', J['HeadJoint'], 'HeadJoint'),
         'Jaw': ('Head', JAW_HINGE, 'JawHinge')}
    names = ['Index', 'Middle', 'Ring', 'Pinky', 'Thumb']
    for side in ('R', 'L'):
        R['Thigh_' + side] = ('Pelvis', J['Hip_' + side], 'Hip_' + side)
        R['Shin_' + side] = ('Thigh_' + side, J['Knee_' + side], 'Knee_' + side)
        R['Foot_' + side] = ('Shin_' + side, J['Ankle_' + side], 'Ankle_' + side)
        R['UpperArm_' + side] = ('UpperChest', J['Shoulder_' + side], 'Shoulder_' + side)
        R['Forearm_' + side] = ('UpperArm_' + side, J['Elbow_' + side], 'Elbow_' + side)
        R['Hand_' + side] = ('Forearm_' + side, J['Wrist_' + side], 'Wrist_' + side)
        for i, (segs, _, _) in enumerate(HAND[side]['fingers']):
            for j, (a, b, d) in enumerate(segs):
                part = '%s%d_%s' % (names[i], j + 1, side)
                parent = 'Hand_' + side if j == 0 else '%s%d_%s' % (names[i], j, side)
                R[part] = (parent, a, '%s%dJoint_%s' % (names[i], j + 1, side))
    return R


# ----------------------------------------------------------------------------------------------------------------
# sorties


def mesh_chunks():
    """Découpe chaque pièce en maillages d'au plus MAX_TRIS triangles : [(nom, pièce, v, f, n, c)]."""
    out = []
    for name in sorted(PIECES):
        piece = PIECES[name]
        groups, cur, tris = [], [], 0
        for ch in piece.chunks:
            if cur and tris + len(ch[1]) > MAX_TRIS:
                groups.append(cur)
                cur, tris = [], 0
            cur.append(ch)
            tris += len(ch[1])
        if cur:
            groups.append(cur)
        for gi, g in enumerate(groups):
            vs, fs, ns, cs, off = [], [], [], [], 0
            for v, f, n, c in g:
                vs.append(v); fs.append(f + off); ns.append(n); cs.append(c)
                off += len(v)
            mname = 'MON_%s_%d' % (name, gi + 1)
            out.append((mname, name, np.vstack(vs), np.vstack(fs), unit(np.vstack(ns)), np.vstack(cs)))
    return out


def export_preview(chunks, folder):
    """Un fichier binaire par maillage (pour l'aperçu EditableMesh dans Studio) + manifeste JSON."""
    os.makedirs(folder, exist_ok=True)
    man = []
    for mname, part, v, f, n, c in chunks:
        lo, hi = v.min(0), v.max(0)
        center = (lo + hi) / 2
        data = struct.pack('<II', len(v), len(f))
        data += (v - center).astype('<f4').tobytes()
        data += np.clip(np.round(n * 127), -127, 127).astype('i1').tobytes()
        data += np.clip(np.round(c * 255), 0, 255).astype('u1').tobytes()
        data += f.astype('<u4').tobytes()
        with open(os.path.join(folder, mname + '.bin'), 'wb') as fh:
            fh.write(data)
        man.append(dict(name=mname, part=part, center=[round(float(x), 5) for x in center],
                        size=[round(float(x), 5) for x in (hi - lo)], verts=int(len(v)), tris=int(len(f))))
    rig = {k: dict(parent=p, pivot=[round(float(x), 5) for x in piv], joint=jn) for k, (p, piv, jn) in rig_spec().items()}
    with open(os.path.join(folder, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(meshes=man, rig=rig, head=dict(center=HEAD_C.tolist(), fwd=FH.tolist(), up=UH.tolist(),
                                                     jaw_hinge=JAW_HINGE.tolist())), fh)
    return man


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'out')
    build_all()
    chunks = mesh_chunks()
    man = export_preview(chunks, out)
    tot = sum(m['tris'] for m in man)
    print('%d maillages, %d triangles, %d pièces de rig' % (len(man), tot, len(rig_spec())))
    for m in man:
        print('  %-22s %6d tris  %6d sommets' % (m['name'], m['tris'], m['verts']))
