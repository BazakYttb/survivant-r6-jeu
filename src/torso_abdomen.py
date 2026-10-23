"""Abdominal & pelvic organs: liver, gallbladder & bile ducts, stomach, duodenum, pancreas, spleen, kidneys,
ureters, adrenal glands, bladder, small intestine (relaxation-packed coils), large intestine.
Torso cm coordinates (landmarks.py), TorsoMap."""
import numpy as np
import sdf as S
from sdf import (sphere, ellipsoid, round_cone, capsule, box, ecyl, smooth_union_all, smooth_union, smooth_subtract,
                 subtract, intersect, smooth_intersect, union, halfspace, frame, tube, displace, perlin, fbm, rot_xyz)
from maps import TorsoMap
from parts import Part
import colors as C
import landmarks as LM
from sweep import tube_mesh, catmull, resample, arclen

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


def domes(off=0.0):
    (cr, rr), (cl, rl) = LM.DIAPHRAGM_DOMES['right'], LM.DIAPHRAGM_DOMES['left']
    return smooth_union(E(cr, np.array(rr) + off), E(cl, np.array(rl) + off), 3.0)


# =================================================================== shared organ shapes
STOMACH = [((5.8, -1.6, 117.4), 1.6), ((6.4, -2.4, 115.3), 3.5), ((6.9, -4.0, 111.5), 3.8), ((7.0, -5.8, 107.5), 3.4),
           ((5.6, -7.6, 103.8), 2.8), ((2.8, -8.4, 102.0), 2.35), ((0.0, -7.9, 102.7), 1.85), ((-2.0, -6.8, 104.2), 1.05)]
DUODENUM = [((-2.0, -6.8, 104.2), 1.05), ((-3.2, -5.8, 104.7), 1.5), ((-4.6, -4.2, 103.2), 1.35), ((-4.9, -3.9, 100.6), 1.3),
            ((-3.6, -5.2, 99.0), 1.25), ((-1.0, -6.4, 98.8), 1.2), ((1.6, -6.3, 99.4), 1.2), ((3.0, -5.9, 101.0), 1.2),
            ((3.4, -5.4, 102.6), 1.15)]
COLON1 = [((-7.0, -4.6, 91.6), 2.6), ((-7.6, -5.0, 93.6), 3.0), ((-9.4, -3.6, 97.0), 2.6), ((-9.8, -2.8, 102.0), 2.5),
          ((-9.2, -4.0, 105.2), 2.4), ((-6.2, -8.6, 103.4), 2.35), ((-2.2, -10.0, 99.0), 2.3), ((2.4, -10.0, 99.2), 2.3),
          ((6.4, -9.0, 103.4), 2.25), ((10.2, -4.8, 107.0), 2.2), ((11.2, -1.6, 106.6), 2.15)]
COLON2 = [((11.2, -1.6, 106.6), 2.15), ((11.2, -1.2, 102.0), 2.1), ((10.8, -1.6, 96.4), 2.0), ((9.2, -3.8, 92.6), 1.85),
          ((5.2, -6.6, 93.4), 1.8), ((2.0, -4.2, 91.0), 1.8), ((0.7, 0.4, 90.0), 1.9), ((0.4, 2.2, 87.6), 2.3),
          ((0.2, 1.9, 85.0), 1.7), ((0.0, 1.2, 82.8), 1.0)]
KIDNEY = {1: (6.0, 0.2, 105.0), -1: (-6.0, 0.2, 103.0)}
BLADDER = ((0, -4.2, 88.4), (3.4, 3.0, 2.8))


def chain_sdf(chain, grow=0.0):
    return tube([c for c, r in chain], [r + grow for c, r in chain])


def kidney_shape(s):
    c = np.array(KIDNEY[s])
    R = rot_xyz(0, -s * 12, s * 25)
    k = E(c, (3.0, 1.7, 5.5), R)
    hil = E(c + np.array([-s * 3.0, -0.6, -0.3]), (1.4, 1.0, 2.1), R)
    k = smooth_subtract(k, hil, 0.6)
    pelvis = round_cone(c + np.array([-s * 1.2, -0.25, 0.0]), c + np.array([-s * 2.9, -0.5, -0.5]), 1.2, 0.55)
    return smooth_union(k, pelvis, 0.4)


# =================================================================== liver & biliary
LIVER_P1 = np.array((-14.0, -8.0, 104.5)); LIVER_N = nrm(np.cross(np.array((6, -8, 112.5)) - LIVER_P1,
                                                                    np.array((-6, 6, 106.0)) - LIVER_P1))
FALCIFORM = [(-0.4, -9.4, 121.0), (-0.3, -10.2, 117.0), (-0.3, -9.8, 112.5), (-0.4, -9.0, 110.6)]


def liver():
    lv = smooth_union_all([E((-7.0, -2.0, 113.5), (6.6, 6.4, 7.0)),
                           E((1.8, -5.4, 115.0), (5.4, 3.4, 2.8)),
                           E((5.8, -5.0, 116.0), (2.2, 2.4, 1.3)),
                           E((-1.4, 0.2, 114.5), (1.4, 1.5, 2.0))], 2.2)
    lv = smooth_intersect(lv, domes(-0.35), 0.8)
    lv = smooth_intersect(lv, halfspace(LIVER_P1, -LIVER_N), 1.0)
    lv = smooth_subtract(lv, chain_sdf(STOMACH, 0.45), 1.2)                          # gastric impression
    lv = smooth_subtract(lv, kidney_shape(-1).offset(0.4), 1.0)                     # renal impression
    lv = smooth_subtract(lv, chain_sdf(COLON1[3:6], 0.4), 1.0)                      # colic impression
    lv = smooth_subtract(lv, capsule((-2.5, -0.8, 117.5), (-2.3, -1.6, 107.0), 1.25), 0.4)   # IVC groove
    lv = smooth_subtract(lv, round_cone((-4.5, -8.4, 106.0), (-3.3, -4.6, 108.8), 1.5, 0.7), 0.4)   # GB fossa

    def notch(p):
        return 0.5 * np.exp(-(polyline_dist(p, FALCIFORM) / 0.35) ** 2)
    return displace(lv, notch, 0.55)


def liver_color(ctx):
    col = C.liver(ctx)
    d = polyline_dist(ctx['pc'], FALCIFORM)
    return C.mix(col, C.C(0.85, 0.80, 0.70), np.exp(-(d / 0.3) ** 2) * 0.5)


def gallbladder():
    return smooth_union(round_cone((-4.4, -8.3, 106.2), (-3.3, -4.6, 108.8), 1.4, 0.6),
                        capsule((-3.3, -4.6, 108.8), (-3.0, -3.8, 108.3), 0.45), 0.4)


def biliary_tubes():
    duct = lambda pts, r, r1=None: tube_mesh(np.array(pts, float), TM, r, r_end_cm=r1, ds=0.005, sides=8) + (bile_color,)
    return [duct([(-3.0, -3.8, 108.3), (-2.6, -3.0, 107.4), (-2.6, -2.4, 106.4)], 0.22),                      # cystic
            duct([(-2.0, -1.4, 109.8), (-2.4, -2.0, 108.2), (-2.6, -2.4, 106.4), (-3.6, -2.9, 103.6),
                  (-4.1, -3.3, 101.8)], 0.32, 0.26),                                                             # hepatic -> CBD
            duct([(-1.2, -1.6, 110.2), (-2.0, -1.4, 109.8), (-3.2, -1.4, 110.4)], 0.22),                       # L/R hepatic
            duct([(3.2, -4.0, 105.6), (0.5, -5.0, 104.0), (-2.6, -4.6, 102.4), (-4.1, -3.4, 101.6)], 0.16)]     # pancreatic duct


def bile_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.52, 0.62, 0.26), C.C(0.40, 0.50, 0.18), np.clip(perlin(p * 1.0) + 0.5, 0, 1) * 0.5)
    return C.shade(col, ctx, 0.3, 0.3, 0.2)


# =================================================================== stomach / duodenum / pancreas / spleen
GREATER = [(9.6, -3.0, 115.0), (10.5, -4.4, 110.8), (10.2, -6.6, 106.4), (7.8, -9.4, 101.8), (3.6, -10.5, 99.6), (0.3, -9.7, 100.6)]
LESSER = [(3.5, -3.6, 112.4), (3.9, -5.6, 107.6), (2.4, -6.6, 105.4), (-0.4, -6.2, 105.8)]


def stomach():
    st = tube([c for c, r in STOMACH], [r for c, r in STOMACH])
    st = smooth_union(st, round_cone((3.0, -2.6, 110.6), (4.6, -3.2, 110.6), 0.95, 1.4), 0.6)   # cardia
    return displace(st, lambda p: 0.05 * perlin(p * 1.6, 5), 0.06)


def stomach_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.88, 0.62, 0.54), C.C(0.76, 0.48, 0.44), np.clip(fbm(p * 0.6, 3, seed=31) + 0.5, 0, 1) * 0.6)
    dg = polyline_dist(p, GREATER); dl = polyline_dist(p, LESSER)
    fat = np.exp(-(dg / 1.4) ** 2) * (0.6 + 0.4 * np.clip(perlin(p * 1.4, 33) + 0.5, 0, 1))
    col = C.mix(col, C.C(0.95, 0.85, 0.52), np.clip(fat * 0.9, 0, 1))
    ves = np.exp(-(dg / 0.35) ** 2) + np.exp(-(dl / 0.3) ** 2)
    branch = np.exp(-(perlin(p * np.array([0.9, 0.9, 2.2]), 34) / 0.04) ** 2) * np.clip(1.2 - np.minimum(dg, dl) / 3.0, 0, 1)
    col = C.mix(col, C.C(0.62, 0.10, 0.10), np.clip(ves + branch * 0.8, 0, 1) * 0.75)
    return C.shade(col, ctx, 0.4, 0.35, 0.2)


def duodenum_tubes():
    pts = np.array([c for c, r in DUODENUM]); rr = np.array([r for c, r in DUODENUM])
    s = np.linspace(0, 1, len(rr))
    v, f, prm = tube_mesh(pts, TM, 1.0, rprofile=lambda t: np.interp(t, s, rr), ds=0.005, sides=14, n=12,
                          mod=lambda s01, phi: 1 + 0.035 * np.cos(s01 * 70) ** 6)
    return [(v, f, prm, gut_color((0.86, 0.62, 0.52)))]


def gut_color(base, stripes=0.0):
    base = np.asarray(base, float)

    def f(ctx):
        p = ctx['pc']
        col = C.mix(base, base * 0.78, np.clip(fbm(p * 0.7, 3, seed=41) + 0.5, 0, 1) * 0.55)
        if stripes and ctx.get('prm') is not None:
            prm = ctx['prm']
            st = np.exp(-((np.sin(prm[:, 0] * stripes) + 1) / 0.08)) * 0.0
            vas = np.exp(-(perlin(np.stack([prm[:, 0] * stripes * 0.5, np.cos(prm[:, 1]) * 2, np.sin(prm[:, 1]) * 2], 1), 42) / 0.05) ** 2)
            col = C.mix(col, C.C(0.66, 0.14, 0.13), np.clip(vas, 0, 1) * 0.6)
        return C.shade(col, ctx, 0.4, 0.35, 0.25)
    return f


def pancreas():
    pts = [(-3.0, -5.0, 101.5), (-0.5, -6.6, 103.4), (3.0, -4.4, 105.6), (7.2, 0.0, 108.6), (8.4, 1.8, 110.0)]
    pc = tube(pts, [2.0, 1.5, 1.45, 1.1, 0.8])
    pc = smooth_union(pc, E((-2.4, -4.0, 99.8), (1.4, 1.2, 1.2)), 0.6)              # uncinate process
    pc = subtract(pc, chain_sdf(DUODENUM, 0.15))

    def lob(p):
        f1, f2 = S.worley(p * 1.5, 7)
        return 0.18 * np.clip(1 - (f2 - f1) / 0.25, 0, 1) - 0.04
    return displace(pc, lob, 0.2)


def spleen():
    R = rot_xyz(-15, 0, -32)
    sp = E((9.6, 2.4, 111.2), (2.0, 5.0, 3.3), R)
    sp = smooth_subtract(sp, E((7.6, 1.6, 111.0), (1.0, 2.6, 1.6), R), 0.8)        # hilum
    sp = subtract(sp, kidney_shape(1).offset(0.3), chain_sdf(STOMACH, 0.3))

    def notches(p):
        return 0.35 * np.exp(-((np.sin(p[:, 1] * 1.6 + p[:, 2] * 0.3) - 0.92) / 0.06) ** 2) * (p[:, 2] > 112.5)
    return displace(sp, notches, 0.4)


# =================================================================== kidneys, adrenals, ureters, bladder
def kidney_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.56, 0.20, 0.14), C.C(0.44, 0.13, 0.10), np.clip(fbm(p * 0.8, 3, seed=51) + 0.5, 0, 1) * 0.6)
    s = np.sign(p[:, 0])
    pel = np.zeros(len(p))
    for sd in SIDES:
        c = np.array(KIDNEY[sd])
        d = np.linalg.norm(p - (c + np.array([-sd * 2.4, -0.4, -0.3])), axis=1)
        pel = np.maximum(pel, np.exp(-(d / 1.2) ** 2) * (s == sd))
    col = C.mix(col, C.C(0.90, 0.80, 0.62), pel * 0.8)
    return C.shade(col, ctx, 0.4, 0.35, 0.25)


def ureter_tubes():
    out = []
    for s in SIDES:
        c = np.array(KIDNEY[s])
        st = c + np.array([-s * 2.9, -0.5, -0.5])
        pts = [st, (s * 4.1, -0.6, c[2] - 3.5), (s * 4.4, -0.6, 97.0), (s * 4.6, -1.2, 92.8), (s * 5.2, -0.4, 90.0),
               (s * 4.4, -1.8, 88.4), (s * 2.6, -2.8, 87.8)]
        out.append(tube_mesh(np.array(pts, float), TM, 0.32, ds=0.005, sides=8) + (ureter_color,))
    return out


def ureter_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.90, 0.78, 0.64), C.C(0.80, 0.64, 0.52), np.clip(perlin(p * 1.2) + 0.5, 0, 1) * 0.5)
    return C.shade(col, ctx, 0.3, 0.3, 0.2)


def adrenals():
    l = smooth_union(E((5.0, 0.3, 111.0), (1.4, 0.55, 1.2), rot_xyz(0, 20, 20)), E((4.4, 0.0, 110.0), (0.7, 0.4, 0.9)), 0.4)
    r = smooth_union(E((-5.0, 0.4, 109.4), (1.2, 0.55, 1.4), rot_xyz(0, -15, -20)), E((-4.5, 0.2, 110.3), (0.6, 0.4, 0.7)), 0.4)
    k = union(kidney_shape(1), kidney_shape(-1)).offset(0.12)
    return subtract(union(l, r), k)


def bladder():
    b = smooth_union_all([E(*BLADDER), E((0, -6.2, 90.2), (1.4, 1.0, 1.2)),          # apex
                          E((0, -2.6, 86.8), (2.2, 1.4, 1.2))], 1.0)                 # base / trigone
    return displace(b, lambda p: 0.06 * perlin(p * 1.2, 61), 0.08)


def bladder_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.88, 0.76, 0.66), C.C(0.78, 0.62, 0.55), np.clip(fbm(p * 0.8, 3, seed=62) + 0.5, 0, 1) * 0.6)
    ves = np.exp(-(perlin(p * 0.9, 63) / 0.03) ** 2) + 0.6 * np.exp(-(perlin(p * 2.0, 64) / 0.03) ** 2)
    col = C.mix(col, C.C(0.66, 0.16, 0.15), np.clip(ves, 0, 1) * 0.55)
    return C.shade(col, ctx, 0.4, 0.3, 0.25)


# =================================================================== large intestine
def colon_points(chain, ds=0.6):
    pts = np.array([c for c, r in chain], float); rr = np.array([r for c, r in chain])
    dense = catmull(pts, 16)
    s = arclen(dense); t = s / s[-1]
    knot_t = arclen(pts); knot_t = knot_t / knot_t[-1]
    return dense, np.interp(t, knot_t, rr), s[-1]


def colon_tube(chain, haustra=True, rectal_tail=False):
    pts = np.array([c for c, r in chain], float); rr = np.array([r for c, r in chain])
    kt = arclen(pts); kt = kt / kt[-1]
    L = arclen(catmull(pts, 16))[-1]
    nh = L / 3.0

    def mod(s01, phi):
        u = (s01 * nh) % 1.0
        crease = np.exp(-((u - 0.5) / 0.09) ** 2)
        tae = np.zeros_like(phi + s01)
        for k in range(3):
            tae = np.maximum(tae, np.exp(-((np.angle(np.exp(1j * (phi - k * 2 * np.pi / 3)))) / 0.22) ** 2))
        h = (1 - 0.17 * crease) * (1 - 0.10 * tae) + 0.05 * tae
        if rectal_tail:
            w = np.clip((s01 - 0.55) / 0.15, 0, 1)        # sigmoid->rectum: haustra fade out
            h = h * (1 - w) + (1 + 0.0 * phi) * w
        return h if haustra else np.ones_like(h)

    def col(ctx):
        prm = ctx['prm']
        p = ctx['pc']
        base = C.mix(C.C(0.84, 0.64, 0.52), C.C(0.72, 0.52, 0.42), np.clip(fbm(p * 0.7, 3, seed=71) + 0.5, 0, 1) * 0.6)
        tae = np.zeros(len(p))
        for k in range(3):
            tae = np.maximum(tae, np.exp(-((np.angle(np.exp(1j * (prm[:, 1] - k * 2 * np.pi / 3)))) / 0.2) ** 2))
        c = C.mix(base, C.C(0.93, 0.86, 0.72), tae * 0.7)
        u = (prm[:, 0] * nh) % 1.0
        c = C.mix(c, c * 0.72, np.exp(-((u - 0.5) / 0.08) ** 2) * 0.6)
        return C.shade(c, ctx, 0.4, 0.35, 0.25)
    v, f, prm = tube_mesh(pts, TM, 1.0, rprofile=lambda t: np.interp(t, kt, rr), ds=0.0065, sides=16, n=16, mod=mod)
    return v, f, prm, col


def epiploic_tubes(chain, n=14, seed=0):
    rng = np.random.RandomState(seed)
    dense, rr, L = colon_points(chain)
    out = []
    for i in np.linspace(0.08, 0.92, n):
        j = int(i * (len(dense) - 1))
        c = dense[j]; t = nrm(dense[min(j + 1, len(dense) - 1)] - dense[max(j - 1, 0)])
        d = nrm(np.cross(t, rng.normal(size=3)))
        a = c + d * (rr[j] * 0.95); b = a + d * rng.uniform(0.8, 1.3) + t * rng.uniform(-0.3, 0.3)
        out.append(tube_mesh(np.array([a, (a + b) / 2 + rng.normal(size=3) * 0.15, b]), TM, 0.32, r_end_cm=0.42,
                             ds=0.006, sides=6) + (fat_color,))
    return out


def fat_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.96, 0.86, 0.50), C.C(0.88, 0.74, 0.38), np.clip(perlin(p * 2.5, 81) + 0.5, 0, 1) * 0.6)
    return C.shade(col, ctx, 0.3, 0.3, 0.2)


def appendix_tube():
    pts = np.array([(-6.6, -4.0, 91.2), (-6.0, -3.0, 89.6), (-5.0, -3.6, 88.2), (-4.4, -4.9, 88.6), (-4.0, -5.6, 89.6)])
    return tube_mesh(pts, TM, 0.45, r_end_cm=0.36, ds=0.005, sides=8) + (gut_color((0.84, 0.62, 0.52)),)


# =================================================================== small intestine (relaxation packing)
SI_START = np.array((3.4, -5.4, 102.6)); SI_END = np.array((-4.9, -5.3, 94.2))
SI_R = 1.0


def si_allowed():
    region = E((0.3, -6.3, 95.6), (7.6, 4.0, 6.2)).offset(-SI_R)
    block = union(chain_sdf(COLON1, SI_R + 0.25), chain_sdf(COLON2, SI_R + 0.25), chain_sdf(DUODENUM, SI_R + 0.2),
                  E(*BLADDER).offset(SI_R + 0.2), chain_sdf(STOMACH, SI_R + 0.2),
                  capsule((0.8, -3.6, 104.0), (0.5, -3.9, 98.0), 1.1 + SI_R + 0.2),           # aorta
                  capsule((-1.6, -3.0, 104.0), (-0.8, -3.4, 98.0), 1.2 + SI_R + 0.2))         # IVC
    return subtract(region, block)


def si_path(L=128.0, seed=5, iters=2600):
    from scipy.spatial import cKDTree
    rng = np.random.RandomState(seed)
    allowed = si_allowed()
    S.set_far(1e9)
    # serpentine initialisation: 4 layers x 2 rows, top -> bottom, alternating x direction
    way = [SI_START]
    zs = [100.2, 97.6, 95.0, 92.4]
    for li, z in enumerate(zs):
        rows = (-4.4, -8.4) if li % 2 == 0 else (-8.4, -4.4)
        for ri, y in enumerate(rows):
            xs = (5.6, -5.6) if (li * 2 + ri) % 2 == 0 else (-5.6, 5.6)
            way += [np.array((xs[0], y, z)), np.array((xs[1], y, z))]
    way.append(SI_END)
    init = resample(catmull(np.array(way), 10), n=int(L / 1.0) + 1)
    P = init + rng.normal(scale=0.3, size=init.shape)
    N = len(P)
    ds0 = L / (N - 1)
    dmin = 2 * SI_R + 0.2
    eps = 0.05
    for it in range(iters):
        F = np.zeros_like(P)
        d = P[1:] - P[:-1]
        l = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
        fs = (l - ds0) / l * d
        F[:-1] += fs; F[1:] -= fs
        F[1:-1] += 0.12 * (P[:-2] + P[2:] - 2 * P[1:-1])
        tree = cKDTree(P)
        pr = tree.query_pairs(dmin, output_type='ndarray')
        if len(pr):
            pr = pr[np.abs(pr[:, 0] - pr[:, 1]) > 2]
            v = P[pr[:, 0]] - P[pr[:, 1]]
            dist = np.linalg.norm(v, axis=1, keepdims=True) + 1e-9
            push = (dmin - dist) / dist * v * 0.5
            np.add.at(F, pr[:, 0], push); np.add.at(F, pr[:, 1], -push)
        a = allowed.ev(P)
        out = a > -0.05
        if out.any():
            q = P[out]
            g = np.stack([(allowed.ev(q + np.array(e)) - allowed.ev(q - np.array(e))) / (2 * eps)
                          for e in ((eps, 0, 0), (0, eps, 0), (0, 0, eps))], 1)
            g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-9
            F[out] -= g * (a[out, None] + 0.05) * 1.0
        if it < iters * 0.6:
            F += rng.normal(scale=0.04 * (1 - it / iters), size=F.shape)
        P += 0.45 * F
        P[0], P[-1] = SI_START, SI_END
    return P


_SI = None


def si_tubes(part):
    global _SI
    if _SI is None:
        _SI = si_path()
    P = _SI
    n = len(P)
    cut = int(n * 0.47)
    seg = P[:cut + 2] if part == 1 else P[cut:]
    r0, r1 = (1.08, 1.0) if part == 1 else (1.0, 0.9)
    base = (0.92, 0.66, 0.58) if part == 1 else (0.90, 0.68, 0.60)
    v, f, prm = tube_mesh(seg, TM, r0 * SI_R, r_end_cm=r1 * SI_R, ds=0.0055, sides=14, n=6,
                          mod=lambda s01, phi: 1 + 0.025 * np.sin(s01 * 200) ** 2)
    return [(v, f, prm, gut_color(base, stripes=260))]


# =================================================================== registry
def parts():
    gl = lambda b: C.simple(b, var=0.12, freq=0.9)
    P = [Part('Torso_Liver', TM, sdf=liver, color=liver_color, target=19000, h=0.0026, far=1.0, cat='organ',
              base=(0.48, 0.15, 0.10), smooth=3, info='Foie (lobes droit, gauche, caudé, ligament falciforme, empreintes)'),
         Part('Torso_Gallbladder', TM, sdf=gallbladder, color=gl((0.32, 0.50, 0.24)), target=3000, h=0.0011, far=0.4,
              cat='organ', base=(0.32, 0.5, 0.24), info='Vésicule biliaire'),
         Part('Torso_BileDucts', TM, tubes=biliary_tubes, target=4000, cat='organ', base=(0.5, 0.6, 0.25),
              info='Voies biliaires (canaux hépatiques, cystique, cholédoque) et canal pancréatique'),
         Part('Torso_Stomach', TM, sdf=stomach, color=stomach_color, target=15000, h=0.0022, far=0.8, cat='organ',
              base=(0.86, 0.6, 0.52), info='Estomac (fundus, corps, antre, pylore, vaisseaux des courbures)'),
         Part('Torso_Duodenum', TM, tubes=duodenum_tubes, target=8000, cat='organ', base=(0.86, 0.62, 0.52),
              info='Duodénum (bulbe, portions descendante, horizontale et ascendante)'),
         Part('Torso_Pancreas', TM, sdf=pancreas, color=C.lobulated((0.92, 0.78, 0.55), 1.5), target=9000, h=0.0014,
              far=0.6, cat='gland', base=(0.92, 0.78, 0.55), info='Pancréas (tête, crochet, corps, queue)'),
         Part('Torso_Spleen', TM, sdf=spleen, color=gl((0.46, 0.12, 0.20)), target=7000, h=0.0016, far=0.6, cat='organ',
              base=(0.46, 0.12, 0.2), info='Rate'),
         Part('Torso_Ureters', TM, tubes=ureter_tubes, target=4000, cat='organ', base=(0.88, 0.76, 0.62), info='Uretères'),
         Part('Torso_Adrenals', TM, sdf=adrenals, color=C.lobulated((0.86, 0.62, 0.26), 2.0), target=3000, h=0.0011,
              far=0.4, cat='gland', base=(0.86, 0.62, 0.26), info='Glandes surrénales'),
         Part('Torso_Bladder', TM, sdf=bladder, color=bladder_color, target=6000, h=0.0016, far=0.5, cat='organ',
              base=(0.86, 0.74, 0.64), info='Vessie'),
         Part('Torso_SmallIntestine_1', TM, tubes=lambda: si_tubes(1), target=19000, cat='organ', base=(0.92, 0.66, 0.58),
              info='Intestin grêle - jéjunum'),
         Part('Torso_SmallIntestine_2', TM, tubes=lambda: si_tubes(2), target=19000, cat='organ', base=(0.9, 0.68, 0.6),
              info='Intestin grêle - iléon'),
         Part('Torso_Colon_1', TM, tubes=lambda: [colon_tube(COLON1), appendix_tube()] + epiploic_tubes(COLON1, 12, 1),
              target=19000, cat='organ', base=(0.82, 0.62, 0.5),
              info='Côlon ascendant, caecum, appendice et côlon transverse (haustrations, bandelettes)'),
         Part('Torso_Colon_2', TM, tubes=lambda: [colon_tube(COLON2, rectal_tail=True)] + epiploic_tubes(COLON2[:6], 8, 2),
              target=19000, cat='organ', base=(0.82, 0.62, 0.5),
              info='Côlon descendant, sigmoïde, rectum et canal anal')]
    for s, t, side in ((1, 'L', 'gauche'), (-1, 'R', 'droit')):
        P.append(Part(f'Torso_Kidney_{t}', TM, sdf=lambda s=s: kidney_shape(s), color=kidney_color, target=7000,
                      h=0.0013, far=0.5, cat='organ', base=(0.56, 0.2, 0.14), info=f'Rein {side} et bassinet'))
    return P
