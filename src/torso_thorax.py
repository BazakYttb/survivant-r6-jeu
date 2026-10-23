"""Thorax organs: heart (+coronary vessels, great vessel roots), lungs (5 lobes), trachea & bronchial tree,
larynx, thyroid, esophagus, diaphragm.  Torso cm coordinates (landmarks.py), TorsoMap."""
import numpy as np
import sdf as S
from sdf import (sphere, ellipsoid, round_cone, capsule, box, ecyl, smooth_union_all, smooth_union, smooth_subtract,
                 subtract, intersect, smooth_intersect, union, halfspace, frame, tube, torus, shell, displace, perlin,
                 fbm, rot_xyz)
from maps import TorsoMap
from parts import Part, project
import colors as C
import landmarks as LM
from sweep import tube_mesh, catmull, resample

TM = TorsoMap()
E = ellipsoid
SIDES = (1, -1)


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def polyline_dist(p, pts):
    pts = np.asarray(pts, float)
    d = np.full(len(p), 1e9)
    for a, b in zip(pts[:-1], pts[1:]):
        ba = b - a
        t = np.clip(((p - a) @ ba) / (ba @ ba), 0, 1)
        q = p - a - np.outer(t, ba)
        d = np.minimum(d, np.sqrt((q * q).sum(1)))
    return d


# =================================================================== heart
AXIS = nrm(np.array(LM.HEART['apex']) - np.array(LM.HEART['base']))
HR = frame(AXIS, (1.0, 0.6, 0.6))
AV_C = np.array((1.2, -3.4, 126.2))
ANT_IV = [(1.4, -7.3, 126.6), (2.8, -8.2, 124.2), (4.6, -8.4, 121.6), (6.4, -7.9, 119.3)]
POST_IV = [(2.6, -1.0, 123.6), (3.6, -2.4, 121.0), (5.4, -4.6, 119.0), (6.5, -6.9, 118.8)]


def _av_ring(n=40):
    u, v = HR[0], HR[1]
    a = np.linspace(0, 2 * np.pi, n)
    return AV_C + 4.1 * np.outer(np.cos(a), u) + 3.6 * np.outer(np.sin(a), v)


AV_RING = _av_ring()


def heart_parts():
    return [E((3.2, -5.2, 122.5), (4.4, 3.3, 5.6), HR),                     # ventricular mass
         round_cone((3.2, -5.2, 122.5), (6.6, -7.2, 118.9), 3.5, 0.9),    # apex
         E((1.1, -6.6, 123.4), (3.2, 2.0, 3.3)),                         # right ventricle
         E((4.5, -3.9, 121.9), (3.0, 2.8, 3.6)),                         # left ventricle
         E((-2.4, -2.7, 126.0), (2.4, 2.6, 3.0)),                        # right atrium
         E((1.2, 0.1, 127.0), (3.0, 2.0, 2.2)),                          # left atrium
         E((-1.2, -5.3, 129.3), (1.7, 1.0, 0.9), rot_xyz(0, 20, -35)),   # right auricle
         E((3.6, -4.3, 128.9), (1.6, 0.9, 0.8), rot_xyz(0, -20, 30))]    # left auricle


def heart_proxy():
    return smooth_union_all(heart_parts(), 1.2)


def heart_body():
    h = smooth_union_all(heart_parts(), 1.2)

    def grooves(p):
        d1 = polyline_dist(p, ANT_IV); d2 = polyline_dist(p, POST_IV); d3 = polyline_dist(p, AV_RING)
        g = np.exp(-(np.minimum(np.minimum(d1, d2), d3) / 0.45) ** 2)
        wr = 0.06 * np.clip(perlin(p * 3.0, 5), 0, 1)                      # fine epicardial texture
        return 0.28 * g + wr
    return displace(h, grooves, 0.4)


def heart_fat(p):
    d = np.minimum(np.minimum(polyline_dist(p, ANT_IV), polyline_dist(p, POST_IV)), polyline_dist(p, AV_RING))
    f = np.exp(-(d / 1.0) ** 2) + 0.35 * np.exp(-(polyline_dist(p, [LM.HEART['apex'], (5.0, -8.3, 120.5)]) / 1.2) ** 2)
    return np.clip(f * (0.75 + 0.5 * fbm(p * 0.8, 2, seed=4)), 0, 1)


def heart_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.56, 0.12, 0.11), C.C(0.42, 0.07, 0.08), np.clip(fbm(p * 0.7, 3, seed=2) + 0.5, 0, 1) * 0.7)
    fib = np.sin((p @ AXIS) * 9 + fbm(p * 0.6, 2, seed=6) * 4) * 0.5 + 0.5
    col = C.mix(col, col * 0.82, fib * 0.3)
    fat = heart_fat(p)
    fatc = C.mix(C.C(0.95, 0.84, 0.48), C.C(0.88, 0.72, 0.35), np.clip(perlin(p * 2.2, 8) + 0.5, 0, 1))
    col = C.mix(col, fatc, np.clip(fat * 1.2, 0, 1))
    return C.shade(col, ctx, 0.45, 0.4, 0.2)


_HB = None


def heart_node():
    global _HB
    if _HB is None:
        _HB = heart_body()
    return _HB


def coronary_tubes():
    hb = heart_body()
    out = []

    def on(pts, off):
        return project(np.array(pts, float), hb, off, iters=5)
    rca = [(-0.3, -4.6, 127.6), (-1.8, -5.9, 126.4), (-3.4, -4.9, 124.6), (-3.6, -2.6, 123.0), (-1.4, -0.6, 122.6),
           (1.0, -0.4, 122.8), (2.6, -1.0, 123.6)]
    pda = POST_IV
    lad = [(1.2, -4.8, 128.2), (1.6, -6.9, 126.8)] + ANT_IV[1:]
    cx = [(1.4, -4.6, 128.0), (3.6, -3.4, 127.2), (5.4, -2.4, 125.0), (5.2, -0.6, 123.6), (3.6, 0.0, 123.0)]
    diag1 = [(2.8, -8.0, 124.4), (4.6, -7.4, 124.8), (6.2, -6.0, 122.6)]
    diag2 = [(4.6, -8.3, 121.8), (6.0, -7.4, 121.6), (7.0, -6.0, 120.2)]
    marg = [(-3.5, -4.6, 124.2), (-2.2, -7.2, 122.4), (0.4, -8.3, 120.8)]
    for pts, r, r1 in ((rca, 0.32, 0.22), (pda, 0.22, 0.12), (lad, 0.32, 0.14), (cx, 0.28, 0.16),
                       (diag1, 0.18, 0.1), (diag2, 0.16, 0.09), (marg, 0.16, 0.09)):
        out.append(tube_mesh(on(pts, r * 0.5), TM, r, r_end_cm=r1, ds=0.004, sides=8) + (C.artery,))
    gcv = [(6.0, -7.4, 119.4), (4.2, -8.0, 122.0), (2.4, -7.6, 125.2), (2.0, -5.2, 127.6), (4.6, -2.6, 126.2),
           (4.0, -0.4, 124.4), (1.0, 0.2, 123.2)]
    sinus = [(3.6, 0.2, 123.4), (1.0, 0.3, 123.0), (-1.6, -0.6, 122.8)]
    mcv = [(6.2, -6.4, 118.9), (5.0, -4.2, 119.4), (3.2, -1.6, 121.6), (1.6, -0.2, 122.9)]
    for pts, r, r1 in ((gcv, 0.24, 0.3), (sinus, 0.45, 0.5), (mcv, 0.2, 0.28)):
        out.append(tube_mesh(on(pts, r * 0.5), TM, r, r_end_cm=r1, ds=0.004, sides=8) + (C.vein,))
    return out


def great_vessel_tubes():
    T = []
    art = lambda pts, r, r1=None, sides=14, col=C.artery: tube_mesh(np.array(pts, float), TM, r, r_end_cm=r1, ds=0.006, sides=sides) + (col,)
    T.append(art([(0.6, -3.6, 126.8), (0.4, -3.6, 129.5), (0.1, -3.2, 131.6), (0.0, -3.0, 133.2)], 1.35, 1.25, 16))   # ascending aorta
    T.append(art([(1.7, -6.0, 126.8), (1.8, -5.6, 129.3), (1.7, -4.0, 131.4), (1.6, -3.3, 131.8)], 1.35, 1.3, 16, C.vein))  # pulmonary trunk
    T.append(art([(1.6, -3.3, 131.8), (3.4, -2.0, 131.6), (5.0, -0.8, 130.9), (6.4, 0.1, 129.9)], 0.95, 0.8, 12, C.vein))  # LPA
    T.append(art([(1.6, -3.3, 131.8), (0.4, -1.0, 131.4), (-2.4, -0.4, 131.0), (-4.6, 0.0, 130.3), (-6.0, 0.2, 129.7)],
                 0.95, 0.8, 12, C.vein))                                                                                   # RPA
    T.append(art([(-3.0, -2.7, 127.0), (-3.0, -2.5, 130.0), (-3.0, -2.3, 133.2)], 1.05, 1.0, 14, C.vein))               # SVC (lower)
    T.append(art([(-2.5, -2.1, 122.8), (-2.5, -1.4, 119.5), (-2.5, -0.8, 116.8)], 1.2, 1.2, 14, C.vein))                # IVC stub
    for (tx, ty, tz) in ((-5.2, 0.6, 129.0), (-5.2, 1.2, 126.0), (5.6, 0.9, 128.8), (5.6, 1.4, 125.9)):                  # pulmonary veins
        T.append(art([(np.sign(tx) * 1.6, 0.6, 127.0 + (tz - 127.4) * 0.5), (tx * 0.65, ty * 0.8, tz), (tx, ty, tz)],
                     0.62, 0.55, 10))
    return T


# =================================================================== lungs
SPZ = [LM.SPINE[n][1] for n in LM.SPINE_ORDER]
SPY = [LM.SPINE[n][0] for n in LM.SPINE_ORDER]


def cavity_sdf(shrink=0.45):
    zs = np.array([149.8, 148.0, 146, 140, 130, 120, 112, 104])
    A = np.array([1.2, 3.8, 6.0, 9.5, 12.6, 13.4, 13.4, 12.5]) - shrink
    B = np.array([1.2, 3.2, 4.5, 6.6, 8.0, 8.5, 8.5, 8.0]) - shrink
    Y = np.array([-0.5, -1.6, -2.5, -1.8, -1.2, -1.0, -0.8, -0.5])

    def f(p, l, h):
        z = p[:, 2]
        a = np.interp(z, zs[::-1], A[::-1]); b = np.interp(z, zs[::-1], B[::-1]); yc = np.interp(z, zs[::-1], Y[::-1])
        a = np.maximum(a, 0.3); b = np.maximum(b, 0.3)
        e = np.sqrt((p[:, 0] / a) ** 2 + ((p[:, 1] - yc) / b) ** 2)
        d = (e - 1) * np.minimum(a, b)
        return np.maximum(d, z - 150.2)
    return S.SDF(f, (-14, -10, 104), (14, 10, 151))


def spine_column():
    def f(p, l, h):
        z = p[:, 2]
        ys = np.interp(-z, -np.array(SPZ), SPY)
        return np.sqrt((p[:, 0] / 3.4) ** 2 + ((p[:, 1] - ys - 0.9) / 2.6) ** 2) * 2.6 - 2.6
    return S.SDF(f, (-4, -3, 100), (4, 7, 160))


def domes(off=0.0):
    (cr, rr), (cl, rl) = LM.DIAPHRAGM_DOMES['right'], LM.DIAPHRAGM_DOMES['left']
    return smooth_union(E(cr, np.array(rr) + off), E(cl, np.array(rl) + off), 3.0)


def mediastinum():
    return smooth_union_all([heart_proxy().offset(0.55),
                             box((0, -3.6, 139.0), (2.2, 5.0, 8.0), rnd=1.5),                   # superior mediastinum
                             capsule((0.0, -3.0, 133.0), (2.6, 2.0, 135.5), 1.8),             # arch
                             capsule((2.4, 2.4, 133), (1.4, 0.0, 114), 1.6),                  # descending aorta + esophagus
                             capsule((0, -0.8, 133), (0, -3.4, 150), 1.4)], 0.8)


OBL_P = np.array((0, 6.0, 137.0)); OBL_N = nrm((0, 0.826, -0.565))


def lung(s):
    L = intersect(cavity_sdf(), halfspace((s * 0.9, 0, 0), (-s, 0, 0)))
    L = smooth_subtract(L, spine_column(), 0.8)
    L = smooth_subtract(L, domes(0.5), 0.8)
    L = smooth_subtract(L, halfspace((0, 0, 109.5), (0, 0, 1)), 0.8)          # costodiaphragmatic recess floor
    L = smooth_subtract(L, mediastinum(), 0.7)
    hil = (s * 5.0, 0.6, 129.0)
    L = smooth_subtract(L, E(hil, (1.2, 1.9, 2.4)), 0.6)
    if s > 0:   # cardiac notch & lingula
        L = smooth_subtract(L, E((4.8, -8.4, 123.2), (3.0, 2.4, 3.6)), 1.0)
    return L


def oblique_field(s):
    def f(p, l, h):
        d = (p - OBL_P) @ OBL_N
        d = d + 0.6 * np.sin(p[:, 0] * 0.25 * s) + 0.35 * perlin(p * 0.18, 12 if s > 0 else 13)
        return d
    return S.SDF(f, np.full(3, -1e4), np.full(3, 1e4))


def horizontal_field():
    def f(p, l, h):
        return p[:, 2] - (131.0 + 0.05 * p[:, 1] + 0.3 * perlin(p * 0.2, 14))
    return S.SDF(f, np.full(3, -1e4), np.full(3, 1e4))


def neg(node):
    return S.SDF(lambda p, l, h: -node.ev(p, l, h), node.lo, node.hi, (node,))


GAP = 0.18


def lobe(s, which):
    L = lung(s)
    ob = oblique_field(s)
    if which == 'Lower':
        return intersect(L, neg(ob.offset(GAP)))
    upper = intersect(L, ob.offset(-GAP))
    if s > 0:
        return upper
    hz = horizontal_field()
    if which == 'Upper':
        return intersect(upper, neg(hz.offset(GAP)))
    return intersect(upper, hz.offset(-GAP))


def lung_color(ctx):
    p = ctx['pc']
    base = C.mix(C.C(0.88, 0.56, 0.58), C.C(0.74, 0.44, 0.50), np.clip(fbm(p * 0.35, 3, seed=21) + 0.5, 0, 1))
    f1, f2 = S.worley(p * 1.1, 4)
    lob = np.clip(1 - (f2 - f1) / 0.07, 0, 1)                                   # secondary lobules
    col = C.mix(base, C.C(0.50, 0.32, 0.38), lob * 0.55)
    blot = np.clip((fbm(p * 0.6, 3, seed=22) - 0.15) * 3, 0, 1)                 # darker congested patches
    col = C.mix(col, C.C(0.58, 0.34, 0.40), blot * 0.45)
    spk = np.clip((perlin(p * 3.2, 23) - 0.38) * 6, 0, 1) * np.clip(fbm(p * 0.25, 2, seed=24) + 0.3, 0, 1)
    col = C.mix(col, C.C(0.22, 0.20, 0.23), spk * 0.8)                          # anthracotic specks
    return C.shade(col, ctx, 0.45, 0.4, 0.15)


def bronchi_tubes(side):
    out = []
    ring = lambda s01, phi: 1 + 0.05 * np.cos(s01 * 60) ** 8
    br = lambda pts, r, r1: tube_mesh(np.array(pts, float), TM, r, r_end_cm=r1, ds=0.0058, sides=7, mod=ring) + (bronch_color,)
    carina = (0.0, -0.6, 133.0)
    R_h = (-4.8, 0.5, 129.8); L_h = (5.2, 0.8, 129.0)
    if side < 0:
        out.append(br([carina, (-2.4, 0.0, 131.2), R_h], 0.8, 0.65))
    else:
        out.append(br([carina, (2.5, 0.0, 131.6), L_h], 0.72, 0.6))
    tree = {  # lobar bronchus -> segmental tips
        (R_h, (-6.4, 0.5, 132.4)): [(-5.8, 0.4, 141.0), (-8.6, 4.2, 135.6), (-8.4, -3.6, 133.6)],
        (R_h, (-5.6, 1.0, 127.4), (-7.0, -2.6, 126.4)): [(-8.8, -4.8, 127.6), (-6.4, -6.4, 124.0)],
        (R_h, (-5.6, 1.0, 127.4), (-6.2, 2.4, 123.8)): [(-7.4, 5.6, 128.6), (-9.6, -1.6, 117.4), (-10.6, 3.0, 116.4),
                                                       (-7.4, 5.6, 116.0), (-4.6, 6.2, 117.6)],
        (L_h, (6.6, 0.4, 131.6)): [(6.0, 1.6, 140.4), (8.4, -3.4, 133.6), (8.6, -5.2, 125.4), (7.4, -6.2, 122.4)],
        (L_h, (6.4, 2.0, 125.4)): [(7.2, 5.4, 128.4), (9.6, 0.0, 116.8), (9.6, 4.0, 115.6), (6.0, 6.0, 116.4)],
    }
    rng = np.random.RandomState(7)
    for path, tips in tree.items():
        if np.sign(path[0][0]) != side:
            continue
        out.append(br(list(path), 0.5, 0.42))
        root = np.array(path[-1])
        for t in tips:
            t = np.array(t)
            mid = root * 0.5 + t * 0.5 + rng.uniform(-0.4, 0.4, 3)
            out.append(br([root, mid, t], 0.36, 0.22))
            for k in range(2):     # sub-segmental branches
                d = nrm(t - root) + rng.uniform(-0.6, 0.6, 3)
                out.append(br([t * 0.7 + mid * 0.3, t + nrm(d) * 2.4], 0.2, 0.12))
    return out


def bronch_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.90, 0.80, 0.74), C.C(0.80, 0.58, 0.55), np.clip(perlin(p * 2.0, 3) + 0.5, 0, 1) * 0.5)
    return C.shade(col, ctx, 0.3, 0.3, 0.2)


# =================================================================== trachea, larynx, thyroid, esophagus
def trachea_tube():
    pts = np.array([(0.0, -3.4, 148.9)] + list(LM.TRACHEA[1:]), float)
    nr = 18

    def mod(s01, phi):
        rings = 0.5 + 0.5 * np.cos(2 * np.pi * s01 * nr)
        post = np.exp(-((np.mod(phi + np.pi, 2 * np.pi) - np.pi) / 0.7) ** 2)       # phi=0 -> posterior
        return (1 + 0.07 * rings ** 3 * (1 - post)) * (1 - 0.12 * post)

    def col(ctx):
        prm = ctx['prm']
        rings = 0.5 + 0.5 * np.cos(2 * np.pi * prm[:, 0] * nr)
        post = np.exp(-((np.mod(prm[:, 1] + np.pi, 2 * np.pi) - np.pi) / 0.7) ** 2)
        c = C.mix(C.C(0.84, 0.62, 0.58), C.C(0.93, 0.90, 0.84), (rings ** 2) * (1 - post))
        c = C.mix(c, C.C(0.78, 0.45, 0.43), post * 0.8)
        return C.shade(c, ctx, 0.3, 0.3, 0.2)
    v, f, prm = tube_mesh(pts, TM, 1.0, ds=0.0025, sides=20, mod=mod,
                          normal_fn=lambda ps: np.tile([0, 1.0, 0], (len(ps), 1)))
    return [(v, f, prm, col)]


def larynx():
    F = []
    for s in SIDES:   # thyroid cartilage laminae
        F.append(E((s * 1.25, -3.7, 150.9), (0.2, 1.6, 1.2), rot_xyz(0, 0, s * 35)))
        F.append(capsule((s * 1.95, -2.4, 150.0), (s * 2.05, -2.2, 152.6), 0.18))       # superior horn
        F.append(capsule((s * 1.95, -2.4, 150.0), (s * 1.9, -2.5, 149.2), 0.16))        # inferior horn
        F.append(E((s * 0.55, -2.15, 149.4), (0.35, 0.3, 0.5)))                        # arytenoids
    F.append(E((0, -4.75, 151.3), (0.45, 0.3, 0.9)))                                   # laryngeal prominence
    thy = smooth_union_all(F, 0.25)
    thy = smooth_subtract(thy, E((0, -5.0, 152.4), (0.45, 0.6, 0.4)), 0.15)            # superior thyroid notch
    cric = smooth_union(torus((0, -3.3, 148.8), 1.2, 0.28), E((0, -2.15, 149.0), (0.95, 0.3, 0.8)), 0.3)
    epi = E((0, -3.45, 152.3), (0.95, 0.18, 1.1), rot_xyz(-20, 0, 0))                 # epiglottis
    return union(thy, cric, epi)


def thyroid():
    g = smooth_union_all([E((1.75, -3.0, 146.6), (0.9, 1.05, 2.0), rot_xyz(0, -10, 0)),
                          E((-1.75, -3.0, 146.6), (0.9, 1.05, 2.0), rot_xyz(0, 10, 0)),
                          E((0, -4.35, 146.0), (1.4, 0.45, 0.6))], 0.5)
    return subtract(g, capsule((0, -3.4, 150), (0, -2.6, 141), 1.2))


def esophagus_tube():
    pts = np.array(LM.ESOPHAGUS, float)

    def col(ctx):
        prm = ctx['prm']
        fold = np.sin(prm[:, 1] * 6 + perlin(ctx['pc'] * 0.6, 2) * 2) * 0.5 + 0.5
        c = C.mix(C.C(0.82, 0.55, 0.50), C.C(0.70, 0.42, 0.40), fold * 0.5)
        return C.shade(c, ctx, 0.3, 0.3, 0.2)
    v, f, prm = tube_mesh(pts, TM, 0.95, rb_cm=0.65, ds=0.005, sides=14,
                          normal_fn=lambda ps: np.tile([1.0, 0, 0], (len(ps), 1)),
                          mod=lambda s01, phi: 1 + 0.04 * np.sin(phi * 6))
    return [(v, f, prm, col)]


# =================================================================== diaphragm
def diaphragm():
    sheet = shell(domes(0.25), 0.5)
    inside = cavity_sdf(shrink=-0.2)
    lower = halfspace((0, -8.0, 113.0), nrm((0, -0.45, -0.89)))     # negative above the costal attachment line
    d = intersect(sheet, inside, lower)
    crura = union(round_cone((-1.6, -1.2, 113.0), (-1.2, -0.9, 104.2), 0.9, 0.5),
                  round_cone((1.8, -0.8, 112.0), (1.3, -0.8, 105.4), 0.75, 0.42))
    d = smooth_union(d, crura, 0.6)
    holes = [capsule((-2.5, -1.4, 119), (-2.5, -0.6, 114), 1.25),              # caval opening
             capsule((2.0, -1.7, 116), (2.2, -1.0, 110), 1.0),                 # esophageal hiatus
             capsule((1.0, -0.6, 116), (1.0, -1.6, 108), 1.25)]                # aortic hiatus
    return subtract(d, *holes)


def diaphragm_color(ctx):
    p = ctx['pc']
    tendon = np.exp(-(((p[:, 0] - 0.3) / 4.2) ** 2 + ((p[:, 1] + 3.0) / 3.6) ** 2) ** 1.5)
    tendon = np.clip(tendon * 1.4 * (p[:, 2] > 113), 0, 1)
    ang = np.arctan2(p[:, 1] + 3.0, p[:, 0])
    fib = np.sin(ang * 40 + perlin(p * 0.5) * 3) * 0.5 + 0.5
    m = C.mix(C.C(0.62, 0.16, 0.14), C.C(0.48, 0.10, 0.10), fib * 0.5)
    t = C.mix(C.C(0.90, 0.88, 0.82), C.C(0.80, 0.78, 0.72), np.clip(perlin(p * 1.5, 4) + 0.5, 0, 1) * 0.5)
    col = C.mix(m, t, tendon)
    return C.shade(col, ctx, 0.4, 0.3, 0.2)


# =================================================================== registry
def parts():
    P = [Part('Torso_Heart', TM, sdf=heart_node, color=heart_color, target=19000, h=0.0021, far=0.8, cat='organ',
              base=(0.55, 0.13, 0.12), smooth=3,
              info='Cœur (ventricules, oreillettes, auricules, graisse épicardique dans les sillons)'),
         Part('Torso_CoronaryVessels', TM, tubes=coronary_tubes, target=12000, cat='vessel', base=(0.7, 0.1, 0.1),
              info='Artères coronaires (droite, interventriculaire antérieure, circonflexe) et veines cardiaques'),
         Part('Torso_GreatVessels', TM, tubes=great_vessel_tubes, target=14000, cat='vessel', base=(0.7, 0.1, 0.1),
              info='Aorte ascendante, tronc et artères pulmonaires (bleu), veines caves, veines pulmonaires (rouge)'),
         Part('Torso_Bronchi_R', TM, tubes=lambda: bronchi_tubes(-1), target=19000, cat='organ', base=(0.9, 0.78, 0.72),
              info='Arbre bronchique droit (souche, lobaires, segmentaires) - visible si les poumons sont transparents'),
         Part('Torso_Bronchi_L', TM, tubes=lambda: bronchi_tubes(1), target=19000, cat='organ', base=(0.9, 0.78, 0.72),
              info='Arbre bronchique gauche (souche, lobaires, segmentaires) - visible si les poumons sont transparents'),
         Part('Torso_Trachea', TM, tubes=trachea_tube, target=12000, cat='organ', base=(0.88, 0.75, 0.70),
              info='Trachée (anneaux cartilagineux et paroi membraneuse postérieure)'),
         Part('Torso_Larynx', TM, sdf=larynx, color=C.cartilage, target=5000, h=0.001, far=0.4, cat='cartilage',
              base=(0.82, 0.86, 0.86), info='Larynx (cartilage thyroïde / pomme d\'Adam, cricoïde, aryténoïdes, épiglotte)'),
         Part('Torso_Thyroid', TM, sdf=thyroid, color=C.lobulated((0.62, 0.22, 0.18), 1.6), target=4000, h=0.0012, far=0.4,
              cat='gland', base=(0.62, 0.22, 0.18), info='Glande thyroïde (deux lobes et isthme)'),
         Part('Torso_Esophagus', TM, tubes=esophagus_tube, target=8000, cat='organ', base=(0.8, 0.52, 0.48),
              info='Œsophage'),
         Part('Torso_Diaphragm', TM, sdf=diaphragm, color=diaphragm_color, target=14000, h=0.0035, far=0.6, cat='muscle',
              base=(0.6, 0.16, 0.14), info='Diaphragme (coupoles, centre tendineux, piliers, orifices)')]
    for s, t, side in ((-1, 'R', 'droit'), (1, 'L', 'gauche')):
        lobes = ('Upper', 'Middle', 'Lower') if s < 0 else ('Upper', 'Lower')
        fr = {'Upper': 'supérieur', 'Middle': 'moyen', 'Lower': 'inférieur'}
        for lb in lobes:
            P.append(Part(f'Torso_Lung_{t}_{lb}', TM, sdf=lambda s=s, lb=lb: lobe(s, lb), color=lung_color,
                          target=16000, h=0.003, far=1.0, cat='organ', base=(0.84, 0.55, 0.56), smooth=3,
                          info=f'Poumon {side} - lobe {fr[lb]}' + (' (avec la lingula)' if (s > 0 and lb == 'Upper') else '')))
    return P
