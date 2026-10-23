"""Head: skull (calvaria / base / face), mandible, teeth, brain, eyes, tongue, C1-C2, vessels.
Coordinates in cm, origin = midpoint of the ear canals (porion), x left, y back, z up."""
import numpy as np
import sdf as S
from sdf import (plate, sphere, ellipsoid, round_cone, capsule, box, ecyl, smooth_union_all, smooth_union,
                 smooth_subtract, subtract, intersect, smooth_intersect, halfspace, rot_xyz, frame,
                 transformed, perlin, fbm, union, displace, torus, capped_torus)
from maps import HeadMap
from parts import Part, project
import colors as C
from sweep import tube_mesh

HM = HeadMap()
SIDES = (1, -1)


def E(c, r, rx=0, ry=0, rz=0):
    return ellipsoid(c, r, rot_xyz(rx, ry, rz) if (rx or ry or rz) else None)


def polyline_dist(p, pts):
    pts = np.asarray(pts, float)
    d = np.full(len(p), 1e9)
    for a, b in zip(pts[:-1], pts[1:]):
        ba = b - a
        t = np.clip(((p - a) @ ba) / (ba @ ba), 0, 1)
        q = p - a - np.outer(t, ba)
        d = np.minimum(d, np.sqrt((q * q).sum(1)))
    return d


# ------------------------------------------------------------------ brain envelope
def hemi_env(s):
    return smooth_union_all([
        E((s * 3.1, -3.2, 6.8), (3.3, 4.6, 4.2)),
        E((s * 3.2, 2.0, 7.4), (3.2, 5.2, 4.3)),
        E((s * 2.6, 6.6, 4.8), (2.8, 3.0, 3.2)),
        E((s * 4.6, -0.6, 1.5), (1.8, 4.2, 2.2), rx=10),
    ], 2.0)


def cerebellum_env():
    return smooth_union_all([E((2.5, 6.1, 0.0), (2.9, 2.6, 1.9)), E((-2.5, 6.1, 0.0), (2.9, 2.6, 1.9)),
                             E((0, 5.8, 0.2), (1.3, 2.3, 1.7))], 1.0)


def brainstem_env():
    return smooth_union_all([E((0, 1.6, 2.4), (1.3, 1.2, 1.0)), E((0, 2.2, 0.2), (1.5, 1.4, 1.3)),
                             round_cone((0, 2.6, -0.8), (0, 2.9, -3.6), 1.0, 0.72)], 0.8)


_ENV = None


def brain_env():
    global _ENV
    if _ENV is None:
        _ENV = smooth_union_all([hemi_env(1), hemi_env(-1), cerebellum_env(), brainstem_env()], 1.2)
    return _ENV


# ------------------------------------------------------------------ gyri
SYLVIAN = [(4.6, -4.4, 2.6), (6.0, -2.2, 3.1), (6.6, 0.5, 3.8), (6.3, 2.6, 5.0), (5.6, 3.8, 6.3)]
CENTRAL = [(0.4, 1.2, 11.5), (3.0, 0.6, 10.8), (5.2, -0.4, 8.2), (6.3, -1.0, 5.3)]
PARIETO_OCC = [(0.3, 6.8, 9.0), (1.5, 7.2, 8.4)]
CALCARINE = [(0.3, 8.8, 4.5), (0.3, 6.0, 4.0)]


def _zero_dist(w, freq, seed):
    """Approximate distance (cm) from w to the zero set of perlin(w*freq)."""
    n = perlin(w * freq, seed)
    e = 0.03
    g = np.stack([(perlin((w + np.array(d)) * freq, seed) - n) / e
                  for d in ((e, 0, 0), (0, e, 0), (0, 0, e))], 1)
    return np.abs(n) / (np.linalg.norm(g, axis=1) + 1e-3)


def gyri_groove(p, s):
    """Returns (crown height 0..1 profile, major sulcus factor)."""
    seed = 3 if s > 0 else 21
    w = p + 1.0 * np.stack([fbm(p * 0.16, 2, seed=seed + k) for k in range(3)], 1)
    d1 = _zero_dist(w, 0.50, seed + 4)
    d2 = _zero_dist(w, 0.47, seed + 9) * 1.25
    kk = 0.12
    dist = -kk * np.log(np.exp(-d1 / kk) + np.exp(-d2 / kk))
    dist = np.maximum(dist, 0)
    q = p.copy(); q[:, 0] *= s
    dmaj = np.minimum(polyline_dist(q, SYLVIAN), polyline_dist(q, CENTRAL))
    dmaj = np.minimum(dmaj, np.minimum(polyline_dist(q, PARIETO_OCC), polyline_dist(q, CALCARINE)))
    dist = np.minimum(dist, dmaj * 0.9)
    gm = np.exp(-(dmaj / 0.30) ** 2)
    return dist, gm


def hemisphere(s):
    base = smooth_intersect(hemi_env(s), halfspace((s * 0.18, 0, 0), (-s, 0, 0)), 0.5)
    base = smooth_subtract(base, cerebellum_env().offset(0.2), 0.4)
    base = subtract(base, brainstem_env().offset(0.05))

    def disp(p):
        dist, gm = gyri_groove(p, s)
        crown = 1 - np.exp(-(dist / 0.38) ** 2)
        pinch = np.exp(-(dist / 0.07) ** 2)
        return 0.40 * (1 - crown) + 0.14 * pinch + 0.9 * gm
    return displace(base.offset(-0.02), disp, 1.2)


_CS_Z = np.array([5.3, 8.2, 10.8, 11.5, 14.0]); _CS_Y = np.array([-1.0, -0.4, 0.6, 1.2, 1.4])
_SY_Y = np.array([-9.0, -4.4, -2.2, 0.5, 2.6, 3.8, 9.0]); _SY_Z = np.array([2.6, 2.6, 3.1, 3.8, 5.0, 6.3, 6.3])


def frontal_region():
    """Negative inside the frontal lobe region: in front of the central sulcus and above the
    lateral (Sylvian) fissure, so the seam between the two meshes hides in those deep sulci."""
    def f(p, l, h):
        a = p[:, 1] - np.interp(p[:, 2], _CS_Z, _CS_Y)
        b = np.interp(p[:, 1], _SY_Y, _SY_Z) - p[:, 2]
        return np.maximum(a, b)
    return S.SDF(f, np.full(3, -1e4), np.full(3, 1e4))


def brain_lobe(s, frontal):
    hemi = hemisphere(s)
    reg = frontal_region()
    if frontal:
        return intersect(hemi, reg)
    neg = S.SDF(lambda p, l, h: -reg.ev(p), reg.lo, reg.hi)
    return intersect(hemi, neg)


def brain_color(s):
    def f(ctx):
        dist, gm = gyri_groove(ctx['pc'], s)
        g = np.exp(-(dist / 0.18) ** 2)
        return C.brain(ctx, np.clip(g * 0.85 + gm, 0, 1), vessel_seed=11 if s > 0 else 17)
    return f


def folia(p):
    c0 = np.array([0.0, 3.6, 0.4])
    q = p - c0
    t = np.sqrt((q[:, 0] * 0.8) ** 2 + q[:, 1] ** 2 + (q[:, 2] * 1.25) ** 2)
    t = t + 0.10 * fbm(p * 0.6, 2, seed=31) + 0.03 * perlin(p * 2.5, 33)
    per = 0.23
    dist = np.abs((t / per + 0.5) % 1.0 - 0.5) * per
    g = np.exp(-(dist / 0.045) ** 2)
    hf = np.exp(-((p[:, 2] + 0.25 + 0.15 * np.abs(p[:, 0]) * 0.1) / 0.08) ** 2) * (q[:, 1] > 1.0)
    return g, hf, dist


def cerebellum():
    def disp(p):
        g, hf, dist = folia(p)
        return 0.05 * g + 0.04 * np.exp(-(dist / 0.09) ** 2) + 0.3 * hf
    return displace(cerebellum_env().offset(-0.1), disp, 0.45)


def cerebellum_color(ctx):
    g, hf, dist = folia(ctx['pc'])
    return C.brain(ctx, np.clip(g * 0.7 + hf, 0, 1) * 0.9, vessel_seed=23)


def brainstem():
    b = brainstem_env()
    # optic chiasm & tracts + olfactory bulbs on the underside
    extra = [capsule((0.9, -2.6, 1.7), (-0.9, -2.6, 1.7), 0.28)]
    for s in SIDES:
        extra.append(capsule((s * 0.9, -2.6, 1.7), (s * 1.8, -0.6, 2.2), 0.22))
        extra.append(round_cone((s * 0.9, -7.0, 3.1), (s * 0.8, -4.0, 2.7), 0.3, 0.15))
    return smooth_union_all([b] + extra, 0.25)


def brainstem_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.90, 0.82, 0.74), C.C(0.80, 0.68, 0.60), np.clip(np.sin(p[:, 2] * 9 + fbm(p * 0.5) * 4) * 0.5 + 0.5, 0, 1) * 0.4)
    return C.shade(col, ctx, 0.4, 0.4)


# ------------------------------------------------------------------ skull
UPPER_ARCH = [(0, -9.75), (0.9, -9.6), (1.7, -9.15), (2.35, -8.45), (2.75, -7.6), (2.95, -6.6),
              (3.05, -5.6), (3.1, -4.6), (3.12, -3.8)]


def arch_points(arch, step=0.5, xs=1.0, dy=0.0):
    from sweep import catmull, resample
    a = np.array([(x * xs, y + dy, 0) for x, y in arch])
    full = np.vstack([a[::-1] * np.array([-1, 1, 1]), a[1:]])
    d = resample(catmull(full, 12), ds=step)
    return d[:, :2]


def skull_features():
    F = [E((0, -7.4, 1.0), (1.5, 1.9, 2.2)),          # interorbital pillar
         E((0, -7.0, 3.6), (4.4, 2.0, 1.6)),          # brow mass / frontal sinus
         E((0, -6.8, -2.9), (3.9, 3.0, 3.1)),         # maxilla body
         E((0, -6.0, -4.75), (2.5, 3.5, 0.45)),       # palate
         E((0, 10.1, 2.4), (1.0, 0.5, 0.6)),          # external occipital protuberance
         ]
    for s in SIDES:
        F += [capsule((s * 0.9, -8.75, 3.05), (s * 4.5, -7.9, 2.85), 0.62),       # supraorbital margin
              capsule((s * 5.0, -6.9, -0.4), (s * 5.1, -7.1, 2.7), 0.55),         # lateral orbital rim
              capsule((s * 1.7, -8.45, -0.85), (s * 4.7, -7.25, -0.95), 0.5),     # infraorbital rim
              E((s * 5.0, -6.4, -0.9), (1.35, 1.5, 1.25)),                         # zygomatic body
              E((s * 6.3, -4.3, -0.95), (0.38, 1.4, 0.55), rz=-s * 26),            # zygomatic arch
              E((s * 6.85, -2.3, -0.75), (0.38, 1.3, 0.52), rz=-s * 5),
              E((s * 6.7, -0.9, -0.5), (0.40, 0.9, 0.5), rz=s * 15),
              E((s * 3.4, -6.6, -2.6), (1.5, 2.2, 2.0)),                           # maxilla lateral
              E((s * 5.4, 1.6, -2.3), (0.9, 1.1, 1.6)),                            # mastoid
              E((s * 5.6, 0.2, -1.0), (1.4, 1.5, 1.2)),                            # temporal (tympanic)
              E((s * 1.25, 1.5, -3.0), (0.55, 1.1, 0.45), rz=s * 25),              # occipital condyle
              capsule((s * 0.32, -8.95, 1.3), (s * 0.55, -10.05, -0.85), 0.36),   # nasal bone
              round_cone((s * 4.2, 0.4, -2.0), (s * 3.4, -1.0, -4.8), 0.18, 0.07),  # styloid
              capsule((s * 1.8, -3.6, -2.2), (s * 1.95, -3.3, -5.0), 0.28),       # pterygoid plate
              E((s * 5.0, -2.4, -1.35), (0.9, 0.55, 0.45)),                        # articular eminence
              capsule((s * 0.5, 10.1, 2.3), (s * 4.5, 8.6, 1.6), 0.25),           # superior nuchal line
              ]
    for (x, y) in arch_points(UPPER_ARCH, 0.55):
        F.append(capsule((x, y, -3.4), (x, y, -4.55), 0.72))                      # alveolar process
    F.append(round_cone((0, -9.9, -3.3), (0, -10.6, -3.45), 0.3, 0.08))           # anterior nasal spine
    return F


def skull_holes():
    H = [smooth_union(E((0, -9.6, -2.6), (1.3, 1.8, 1.1)), E((0, -9.6, -1.3), (0.75, 1.8, 1.3)), 0.4),  # nasal aperture
         E((0, -6.5, -2.0), (1.3, 3.2, 1.7)),                                     # nasal cavity
         E((0, 2.4, -2.7), (1.5, 1.85, 1.2)),                                     # foramen magnum
         ]
    for s in SIDES:
        H += [capsule((s * 7.6, 0.1, -0.4), (s * 5.0, 0.1, -0.4), 0.45),         # ext. acoustic meatus
              sphere((s * 2.6, 1.0, -2.7), 0.45),                                  # jugular foramen
              capsule((s * 2.4, -0.2, -2.9), (s * 2.3, -0.4, -1.8), 0.3),         # carotid canal
              capsule((s * 2.0, -4.6, 0.75), (s * 1.0, -3.0, 1.3), 0.3),          # optic canal
              capsule((s * 2.3, -9.3, 2.7), (s * 2.3, -8.3, 2.7), 0.15),          # supraorbital foramen
              capsule((s * 2.6, -9.4, -1.75), (s * 2.6, -8.3, -1.6), 0.18),       # infraorbital foramen
              ]
    return H


def orbit(s):
    return smooth_union(round_cone((s * 3.35, -10.2, 1.0), (s * 2.0, -4.4, 0.7), 2.15, 0.45),
                        E((s * 3.3, -9.3, 1.0), (1.95, 1.3, 1.7)), 0.5)


_SKULL = None


_SENV = None


def skull_env():
    global _SENV
    if _SENV is None:
        _SENV = smooth_union_all([brain_env(), E((0, 1.4, 6.0), (6.0, 8.3, 5.7))], 1.5)
    return _SENV


def skull_shell():
    global _SKULL
    if _SKULL is not None:
        return _SKULL
    env = skull_env()
    solid = smooth_union_all([env.offset(0.95)] + skull_features(), 0.7)
    for s in SIDES:
        solid = smooth_subtract(solid, orbit(s), 0.35)
        solid = smooth_subtract(solid, E((s * 5.0, -1.2, -0.95), (1.1, 0.7, 0.55)), 0.2)   # glenoid fossa
        solid = smooth_subtract(solid, E((s * 2.9, -9.75, -3.0), (1.1, 0.8, 1.0)), 0.6)    # canine fossa
    solid = subtract(solid, *skull_holes())
    solid = subtract(solid, env.offset(0.3))
    inner = [E((0, -6.2, 2.9), (0.18, 0.9, 0.7)),                                  # crista galli
             box((0, -8.0, -1.6), (0.12, 2.0, 1.5), rnd=0.1)]                      # nasal septum
    for s in SIDES:
        inner.append(E((s * 0.95, -7.4, -2.6), (0.35, 2.2, 0.45)))                # inferior concha
    _SKULL = union(solid, *inner)
    return _SKULL


CUT_N = np.array([0, 0.11, 0.994]); CUT_N = CUT_N / np.linalg.norm(CUT_N)
CUT_P = np.array([0, -8, 6.3])


def calvaria():
    return intersect(skull_shell(), halfspace(CUT_P + CUT_N * 0.04, -CUT_N))


def skull_base_part(front):
    b = intersect(skull_shell(), halfspace(CUT_P - CUT_N * 0.04, CUT_N))
    return intersect(b, halfspace((0, -4.0, 0), (0, 1, 0)) if front else halfspace((0, -4.0, 0), (0, -1, 0)))


def suture_mask(p):
    w1 = 0.25 * perlin(p * 2.2, 41) + 0.10 * perlin(p * 6.0, 42)
    yc = -2.0 - (12.3 - p[:, 2]) * 0.19
    cor = np.exp(-((p[:, 1] - yc + w1) / 0.10) ** 2) * (p[:, 2] > 2.6)
    sag = np.exp(-((p[:, 0] + w1) / 0.09) ** 2) * (p[:, 1] > -2.2) * (p[:, 1] < 8.2) * (p[:, 2] > 7.5)
    nl = np.array([0, 0.949, -0.316])
    dl = (p - np.array([0, 8.0, 9.8])) @ nl
    lam = np.exp(-((dl + w1) / 0.10) ** 2) * (p[:, 1] > 3) * (p[:, 2] > 0.5)
    return np.clip(cor + sag + lam, 0, 1)


def skull_color(ctx):
    col = C.bone(ctx, seed=2)
    m = suture_mask(ctx['pc']) * np.clip(ctx['ao'] * 1.2, 0, 1)
    return C.mix(col, C.C(0.40, 0.33, 0.24), m * 0.7)


# ------------------------------------------------------------------ mandible & teeth
def mandible():
    body_pts = [(4.7, -0.9, -8.0, -8.7, 0.5), (4.4, -3.5, -7.85, -9.1, 0.52), (3.8, -5.8, -7.85, -9.5, 0.55),
                (2.7, -7.8, -7.85, -10.0, 0.56), (1.4, -9.1, -7.85, -10.5, 0.6), (0.0, -9.5, -7.85, -10.75, 0.62)]
    from sweep import catmull, resample
    P = np.array([(x, y, 0) for x, y, *_ in body_pts])
    full = np.vstack([P[::-1] * np.array([-1, 1, 1]), P[1:]])
    dense = resample(catmull(full, 12), ds=0.45)
    # interpolate heights by |x|,y nearest along original list
    src = np.array([(x, y) for x, y, *_ in body_pts])
    F = []
    for (x, y, _) in dense:
        d = np.linalg.norm(src - np.array([abs(x), y]), axis=1)
        w = 1 / (d + 0.05) ** 2; w /= w.sum()
        ztop = (w * np.array([b[2] for b in body_pts])).sum()
        zbot = (w * np.array([b[3] for b in body_pts])).sum()
        r = (w * np.array([b[4] for b in body_pts])).sum()
        F.append(capsule((x, y, ztop), (x, y, zbot), r))
    F.append(E((0, -9.75, -10.3), (1.4, 0.6, 0.8)))                              # mental protuberance
    for s in SIDES:
        F += [capsule((s * 4.8, -0.8, -8.2), (s * 5.0, -1.1, -2.2), 0.55),       # posterior ramus border
              capsule((s * 4.5, -3.8, -7.0), (s * 4.6, -3.6, -2.7), 0.4),        # coronoid
              plate((s * 4.75, 0, 0), np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0.]]),
                    [(-0.75, -8.4), (-1.05, -2.4), (-3.55, -2.75), (-4.3, -7.2), (-4.0, -8.4)], 0.22, rnd=0.18),
              E((s * 5.0, -1.2, -1.25), (1.0, 0.5, 0.45)),                       # condyle
              E((s * 4.8, -0.6, -8.3), (0.45, 0.9, 0.7)),                        # angle flare
              E((s * 1.2, -9.55, -10.6), (0.6, 0.5, 0.4))]                       # mental tubercle
    m = smooth_union_all(F, 0.45)
    holes = []
    for s in SIDES:
        holes += [E((s * 4.8, -2.4, -2.2), (1.2, 0.95, 1.1)),                     # mandibular notch
                  capsule((s * 2.4, -8.6, -8.9), (s * 2.4, -7.6, -8.9), 0.18),   # mental foramen
                  capsule((s * 4.0, -2.0, -5.6), (s * 4.8, -2.0, -5.6), 0.2)]    # mandibular foramen
    m = smooth_subtract(m, holes[0], 0.3)
    m = smooth_subtract(m, holes[3], 0.3)
    return subtract(m, holes[1], holes[2], holes[4], holes[5])


UPPER_TEETH = [('I1', 0.85), ('I2', 0.66), ('C', 0.76), ('P1', 0.70), ('P2', 0.66), ('M1', 1.0), ('M2', 0.92), ('M3', 0.85)]
LOWER_TEETH = [('I1', 0.52), ('I2', 0.58), ('C', 0.68), ('P1', 0.70), ('P2', 0.71), ('M1', 1.10), ('M2', 1.05), ('M3', 1.0)]


def tooth_local(kind, w, upper):
    """Tooth in local frame: x along arch, y bucco-lingual (+ = lingual), z = occlusal->root (+ into bone)."""
    hw = w / 2
    if kind in ('I1', 'I2'):
        crown = smooth_union(E((0, 0.05, 0.55), (hw * 0.95, 0.33, 0.62)), box((0, 0.1, 0.25), (hw * 0.9, 0.18, 0.25), rnd=0.12), 0.15)
        crown = intersect(crown, halfspace((0, 0, 0.02), (0, 0, -1)))
        root = round_cone((0, 0.1, 0.9), (0, 0.15, 2.3 if kind == 'I1' else 2.1), hw * 0.55, 0.08)
        shape = smooth_union(crown, root, 0.15)
    elif kind == 'C':
        crown = smooth_union(round_cone((0, 0.1, 0.95), (0, 0.05, 0.12), hw * 0.95, 0.12), E((0, 0.12, 0.65), (hw * 0.9, 0.42, 0.5)), 0.2)
        root = round_cone((0, 0.1, 1.0), (0, 0.15, 2.8), hw * 0.65, 0.08)
        shape = smooth_union(crown, root, 0.15)
    elif kind in ('P1', 'P2'):
        crown = smooth_union_all([E((0, 0.1, 0.5), (hw * 0.95, 0.48, 0.45)),
                                  sphere((0, -0.18, 0.18), 0.24), sphere((0, 0.36, 0.22), 0.21)], 0.15)
        crown = subtract(crown, capsule((-hw, 0.1, -0.05), (hw, 0.1, -0.05), 0.08))
        root = round_cone((0, 0.1, 0.8), (0, 0.12, 2.2), hw * 0.6, 0.1)
        shape = smooth_union(crown, root, 0.15)
    else:
        crown = smooth_union_all([box((0, 0.1, 0.45), (hw * 0.95, 0.52, 0.36), rnd=0.22)]
                                 + [sphere((sx * hw * 0.42, 0.1 + sy * 0.25, 0.14), 0.24) for sx in (-1, 1) for sy in (-1, 1)], 0.12)
        crown = subtract(crown, capsule((-hw, 0.1, -0.08), (hw, 0.1, -0.08), 0.07),
                         capsule((0, -0.6, -0.08), (0, 0.8, -0.08), 0.07))
        roots = [round_cone((sx * hw * 0.45, 0.1, 0.7), (sx * hw * 0.5, 0.15, 1.9), 0.25, 0.08) for sx in (-1, 1)]
        shape = smooth_union_all([crown] + roots, 0.15)
    return shape


def teeth(upper):
    arch = UPPER_ARCH
    table = UPPER_TEETH if upper else LOWER_TEETH
    xs, dy = (1.0, 0.0) if upper else (0.95, 0.28)
    from sweep import catmull, resample, arclen
    a = np.array([(x * xs, y + dy, 0) for x, y in arch])
    dense = catmull(a, 20)
    s_ = arclen(dense)
    zocc = -6.3 if upper else -6.36
    items = []
    for side in SIDES:
        acc = 0.0
        for kind, w in table:
            mid = acc + w / 2 + 0.02
            acc += w + 0.04
            p = np.array([np.interp(mid, s_, dense[:, k]) for k in range(2)])
            t = np.array([np.interp(mid + 0.05, s_, dense[:, k]) for k in range(2)]) - np.array(
                [np.interp(mid - 0.05, s_, dense[:, k]) for k in range(2)])
            t = t / np.linalg.norm(t)
            p[0] *= side; t[0] *= side
            tx = np.array([t[0], t[1], 0.0])
            zdir = np.array([0, 0, 1.0]) if upper else np.array([0, 0, -1.0])
            lingual = np.array([-p[0], -p[1] - 5.0, 0]); lingual -= tx * (lingual @ tx); lingual /= np.linalg.norm(lingual)
            R = np.stack([tx, lingual, zdir])
            # slight labial inclination of incisors
            if kind.startswith('I'):
                ang = np.radians(14 if upper else 8)
                yv = np.cos(ang) * R[1] + np.sin(ang) * R[2] * (-1)
                zv = np.cross(R[0], yv)
                R = np.stack([R[0], yv, zv])
            c = np.array([p[0], p[1], zocc])
            items.append(transformed(tooth_local(kind, w, upper), c, R))
    return union(*items)


# ------------------------------------------------------------------ eyes / tongue / muscles
EYE_C = {s: np.array([s * 3.1, -7.75, 1.0]) for s in SIDES}


def eye(s):
    c = EYE_C[s]
    return smooth_union(sphere(c, 1.15), sphere(c + np.array([0, -0.48, 0]), 0.75), 0.12)


def eye_color(s, iris=(0.42, 0.27, 0.12)):
    def f(ctx):
        p = ctx['pc']; c = EYE_C[s]
        v = p - c; r = np.linalg.norm(v, axis=1)
        cosang = -v[:, 1] / np.maximum(r, 1e-6)
        ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        az = np.arctan2(v[:, 2], v[:, 0])
        streak = perlin(np.stack([np.cos(az) * 6, np.sin(az) * 6, ang * 0.35], 1), 7)
        irc = np.array(iris)
        iris_col = C.mix(irc * 1.25, irc * 0.55, np.clip(streak * 0.9 + 0.5, 0, 1))
        iris_col = C.mix(iris_col, C.C(0.62, 0.50, 0.22), np.exp(-((ang - 14) / 2.5) ** 2) * 0.6)
        sclera = C.mix(C.C(0.96, 0.95, 0.91), C.C(0.90, 0.84, 0.80), np.clip((ang - 60) / 80, 0, 1))
        q = p * 1.4
        ves = np.exp(-(perlin(q, 12) / 0.04) ** 2) * np.clip((ang - 35) / 30, 0, 1)
        sclera = C.mix(sclera, C.C(0.75, 0.15, 0.15), ves * 0.7)
        col = sclera.copy()
        m_iris = ang < 31
        col[m_iris] = iris_col[m_iris]
        limb = np.exp(-((ang - 30) / 2.0) ** 2)
        col = C.mix(col, C.C(0.12, 0.08, 0.05), limb * 0.8)
        col[ang < 10] = C.C(0.02, 0.02, 0.02)
        return C.shade(col, ctx, 0.2, 0.1, 0.0)
    return f


def tongue():
    t = smooth_union_all([E((0, -5.4, -6.35), (2.2, 3.6, 1.3)), E((0, -2.8, -7.4), (1.8, 1.8, 1.5))], 0.8)
    t = smooth_subtract(t, capsule((0, -8.8, -4.95), (0, -3.5, -4.95), 0.18), 0.2)

    def bumps(p):
        return 0.04 * np.clip(perlin(p * 5.0, 3), 0, 1)
    return displace(t, bumps, 0.05)


def tongue_color(ctx):
    p = ctx['pc']
    col = C.mix(C.C(0.82, 0.44, 0.44), C.C(0.68, 0.30, 0.32), np.clip(fbm(p * 1.2) + 0.5, 0, 1) * 0.6)
    sp = np.clip((perlin(p * 6, 9) - 0.3) * 4, 0, 1)
    col = C.mix(col, C.C(0.90, 0.62, 0.60), sp * 0.5)
    return C.shade(col, ctx, 0.4, 0.3)


def hyoid():
    return smooth_union_all([capped_torus((0, -2.6, -9.6), 1.9, 0.26, 115, rot_xyz(0, 0, 180)),
                             E((0, -4.45, -9.6), (0.9, 0.35, 0.5))], 0.2)


# ------------------------------------------------------------------ atlas / axis
def atlas():
    F = [E((0, 0.08, -3.9), (0.55, 0.35, 0.5)), E((0, 4.1, -3.85), (0.5, 0.4, 0.45))]
    for s in SIDES:
        F += [E((s * 1.4, 1.5, -3.95), (0.75, 1.1, 0.6), rz=s * 20),
              capsule((s * 1.1, 0.55, -3.9), (0, 0.18, -3.9), 0.35),
              capsule((s * 1.3, 2.4, -3.9), (s * 1.0, 3.6, -3.82), 0.33),
              capsule((s * 1.0, 3.6, -3.82), (0, 4.0, -3.82), 0.33),
              round_cone((s * 1.9, 1.5, -3.95), (s * 3.6, 1.7, -4.0), 0.55, 0.45)]
    a = smooth_union_all(F, 0.3)
    holes = []
    for s in SIDES:
        holes += [E((s * 1.3, 1.4, -3.15), (0.6, 1.1, 0.5)), ecyl((s * 2.4, 1.55, -3.95), 0.28, 0.28, 1.5)]
    return subtract(a, *holes)


def axis():
    F = [ecyl((0, 1.2, -5.5), 0.95, 0.8, 0.6, rnd=0.25),
         round_cone((0, 1.05, -4.8), (0, 1.05, -3.45), 0.55, 0.42),
         round_cone((0, 4.0, -5.5), (0, 5.3, -6.1), 0.55, 0.4)]
    for s in SIDES:
        F += [E((s * 1.2, 1.3, -4.75), (0.8, 0.9, 0.35)),
              capsule((s * 0.9, 1.9, -5.3), (s * 1.0, 2.7, -5.4), 0.38),
              capsule((s * 1.0, 2.7, -5.4), (0, 4.0, -5.5), 0.35),
              capsule((s * 1.6, 1.8, -5.3), (s * 2.4, 2.0, -5.4), 0.35),
              capsule((s * 1.1, 2.6, -5.9), (s * 1.1, 2.9, -6.4), 0.32),
              sphere((s * 0.35, 5.4, -6.15), 0.33)]
    a = smooth_union_all(F, 0.3)
    return subtract(a, ecyl((0, 2.9, -5.4), 1.0, 0.85, 2.0))


# ------------------------------------------------------------------ tubes
def head_vessels():
    out = []
    skull = skull_shell()

    def on_skull(pts, off):
        p = np.array(pts, float)
        return project(p, skull, off)
    for s in SIDES:
        sx = np.array([s, 1, 1])
        ica = np.array([(2.0, -0.5, -8.6), (2.1, -0.4, -6.0), (2.3, -0.3, -3.6), (2.35, -0.25, -2.6)]) * sx
        out.append(tube_mesh(ica, HM, 0.26, ds=0.006, sides=10) + (C.artery,))
        eca = np.array([(2.2, -1.1, -8.6), (3.3, -1.6, -6.0), (4.4, -0.8, -3.8), (5.9, -0.7, -1.6)]) * sx
        sta = on_skull(np.array([(7.0, -0.6, 0.2), (7.5, -0.6, 2.4), (7.4, -0.4, 4.5)]) * sx, 0.25)
        out.append(tube_mesh(np.vstack([eca, sta]), HM, 0.2, r_end_cm=0.14, ds=0.006, sides=8) + (C.artery,))
        fr = on_skull(np.array([(7.4, -0.4, 4.5), (6.8, -3.2, 6.6), (5.2, -5.6, 8.0)]) * sx, 0.2)
        out.append(tube_mesh(fr, HM, 0.13, r_end_cm=0.09, ds=0.006, sides=7) + (C.artery,))
        par = on_skull(np.array([(7.4, -0.4, 4.5), (7.2, 1.8, 7.2), (6.0, 3.5, 9.5)]) * sx, 0.2)
        out.append(tube_mesh(par, HM, 0.13, r_end_cm=0.09, ds=0.006, sides=7) + (C.artery,))
        fac = np.array([(3.0, -2.2, -7.6), (4.2, -4.6, -9.4), (4.4, -5.6, -8.4), (3.9, -7.3, -5.4),
                        (3.0, -8.6, -3.3), (2.0, -9.6, -0.6)]) * sx
        out.append(tube_mesh(on_skull(fac, 0.15), HM, 0.16, r_end_cm=0.1, ds=0.006, sides=7) + (C.artery,))
        ijv = np.array([(2.6, 1.0, -2.8), (2.9, 0.4, -4.8), (2.7, -0.1, -7.0), (2.6, -0.3, -8.6)]) * sx
        out.append(tube_mesh(ijv, HM, 0.42, r_end_cm=0.5, ds=0.006, sides=10) + (C.vein,))
        vert = np.array([(2.0, 1.8, -7.6), (2.1, 1.7, -5.6), (2.4, 1.55, -4.2), (2.0, 2.9, -3.55), (0.8, 1.9, -2.9)]) * sx
        out.append(tube_mesh(vert, HM, 0.17, ds=0.006, sides=8) + (C.artery,))
    return out


def optic_nerves():
    out = []
    for s in SIDES:
        sx = np.array([s, 1, 1])
        pts = np.array([(3.0, -6.9, 0.95), (2.4, -5.5, 0.8), (1.6, -4.0, 1.0), (1.0, -3.0, 1.3), (0.55, -2.6, 1.65)]) * sx
        out.append(tube_mesh(pts, HM, 0.24, ds=0.005, sides=10) + (C.nerve,))
    return out


def eye_muscles():
    out = []
    for s in SIDES:
        c = EYE_C[s]
        apex = np.array([s * 2.1, -4.7, 0.8])
        ins = [c + np.array([0, -0.75, 1.0]), c + np.array([0, -0.75, -1.0]),
               c + np.array([-s * 1.0, -0.75, 0]), c + np.array([s * 1.0, -0.75, 0])]
        for q in ins:
            d = q - c; d /= np.linalg.norm(d)
            mid = c + d * 1.45 + np.array([0, 1.2, 0])
            out.append(tube_mesh(np.array([apex, mid, q]), HM, 0.16, r_end_cm=0.28, rb_cm=0.12, ds=0.005, sides=8)
                       + (lambda ctx: C.muscle(ctx, C.C(0.62, 0.18, 0.16)),))
    return out


def head_cord():
    pts = np.array([(0, 2.9, -2.6), (0, 2.95, -4.5), (0, 2.9, -6.4), (0, 2.85, -7.6)])
    return [tube_mesh(pts, HM, 0.55, ds=0.005, sides=12) + (C.spinal_cord,)]


# ------------------------------------------------------------------ registry
def parts():
    P = []
    P.append(Part('Head_Skull_Calvaria', HM, sdf=calvaria, color=skull_color, target=17000, far=1.2, h=0.0042,
                  info='Calotte crânienne (amovible pour voir le cerveau)'))
    P.append(Part('Head_Skull_Face', HM, sdf=lambda: skull_base_part(True), color=skull_color, target=19000, far=1.2, h=0.0028,
                  info='Massif facial: orbites, maxillaires, os zygomatiques, os nasaux'))
    P.append(Part('Head_Skull_Base', HM, sdf=lambda: skull_base_part(False), color=skull_color, target=19000, far=1.2, h=0.0032,
                  info='Base du crâne: temporaux, occipital, foramen magnum, mastoïdes'))
    P.append(Part('Head_Mandible', HM, sdf=mandible, color=lambda c: C.bone(c, seed=4), target=12000, far=0.9, h=0.0026, info='Mandibule (corps, branches, condyles, processus coronoïdes, foramens mentonniers)'))
    P.append(Part('Head_Teeth_Upper', HM, sdf=lambda: teeth(True), color=C.teeth, target=14000, far=0.4, h=0.0011,
                  cat='tooth', base=(0.96, 0.94, 0.86), min_faces=30, info='Dents supérieures (16 : incisives, canines, prémolaires, molaires)'))
    P.append(Part('Head_Teeth_Lower', HM, sdf=lambda: teeth(False), color=C.teeth, target=14000, far=0.4, h=0.0011,
                  cat='tooth', base=(0.96, 0.94, 0.86), min_faces=30, info='Dents inférieures (16)'))
    for s, tag, side in ((1, 'L', 'gauche'), (-1, 'R', 'droit')):
        for front in (True, False):
            P.append(Part(f'Head_Brain_{tag}_{"Frontal" if front else "Posterior"}', HM,
                          sdf=lambda s=s, front=front: brain_lobe(s, front), color=brain_color(s),
                          target=19000, far=1.2, h=0.0026 if front else 0.0030, cat='brain', base=(0.85, 0.70, 0.66),
                          smooth=2, info=(f'Lobe frontal {side}' if front else
                                          f'Lobes pariétal, temporal et occipital {side}')))
        P.append(Part(f'Head_Eye_{tag}', HM, sdf=lambda s=s: eye(s), color=eye_color(s), target=5000, far=0.6, h=0.0012,
                      cat='eye', base=(0.95, 0.94, 0.9), info=f'Globe oculaire {side} (sclère, iris, pupille, cornée)'))
    P.append(Part('Head_Cerebellum', HM, sdf=cerebellum, color=cerebellum_color, target=19000, far=0.8, h=0.0020,
                  cat='brain', base=(0.82, 0.66, 0.62), smooth=2, info='Cervelet (hémisphères, vermis, lamelles)'))
    P.append(Part('Head_Brainstem', HM, sdf=brainstem, color=brainstem_color, target=7000, far=0.8,
                  cat='brain', base=(0.9, 0.82, 0.74), info='Tronc cérébral (mésencéphale, pont, bulbe), chiasma et bandelettes optiques, bulbes olfactifs'))
    P.append(Part('Head_Tongue', HM, sdf=tongue, color=tongue_color, target=6000, far=0.6, h=0.0025, cat='organ',
                  base=(0.8, 0.42, 0.42), info='Langue'))
    P.append(Part('Head_Hyoid', HM, sdf=hyoid, color=lambda c: C.bone(c, seed=6), target=2500, far=0.5, info='Os hyoïde'))
    P.append(Part('Head_Atlas_C1', HM, sdf=atlas, color=lambda c: C.bone(c, seed=7), target=6000, far=0.6, h=0.0016, info='Atlas (1re vertèbre cervicale)'))
    P.append(Part('Head_Axis_C2', HM, sdf=axis, color=lambda c: C.bone(c, seed=8), target=6000, far=0.6, h=0.0016, info="Axis (2e vertèbre cervicale, dent de l'axis)"))
    P.append(Part('Head_Vessels', HM, tubes=head_vessels, target=20000, cat='vessel', base=(0.7, 0.1, 0.1), info='Vaisseaux de la tête (carotides interne et externe, temporale superficielle, faciale, vertébrales, jugulaires internes)'))
    P.append(Part('Head_OpticNerves', HM, tubes=optic_nerves, target=5000, cat='nerve', base=(0.96, 0.88, 0.55), info='Nerfs optiques'))
    P.append(Part('Head_EyeMuscles', HM, tubes=eye_muscles, target=8000, cat='muscle', base=(0.6, 0.17, 0.15), info="Muscles droits de l'œil (supérieur, inférieur, médial, latéral)"))
    P.append(Part('Head_SpinalCord', HM, tubes=head_cord, target=3000, cat='nerve', base=(0.93, 0.88, 0.78), info='Moelle épinière cervicale haute'))
    return P
