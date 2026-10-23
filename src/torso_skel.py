"""Torso skeleton: vertebrae C3-L5, intervertebral discs, sacrum, coccyx, ribs, costal cartilages,
sternum, clavicles, scapulae, hip bones and joint cartilages.
Real cm torso coordinates (landmarks.py): x left, y back, z height."""
import numpy as np
import sdf as S
from sdf import (sphere, ellipsoid, round_cone, capsule, box, ecyl, plate, smooth_union_all, smooth_union,
                 smooth_subtract, subtract, intersect, union, halfspace, rot_xyz, frame, flip_x, torus, tube)
from maps import TorsoMap, LegMap, ArmMap, smoothstep
from parts import Part, stud_shape
import colors as C
import landmarks as LM
from sweep import catmull, resample, tube_mesh
from torso_skel_lib import Fr, custom, vbody_fn, Swept

TM = TorsoMap()
GM = TorsoMap(girdle=True)
SIDES = (1, -1)


class SoftGirdle(TorsoMap):
    """Like the girdle map but spread over x 5..18 cm: keeps the scapula on the back of the rib cage
    while its glenoid reaches the R6 arm."""

    def __init__(self):
        super().__init__(False)
        self.girdle = True
        xr = np.linspace(0, 40, 4001)
        self._xr, self._xs = xr, self.sx * xr + 0.30 * smoothstep(5, 18, xr)


SG = SoftGirdle()


def sdist(a, b):
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


# ============================================================================ spine frames
ORDER = LM.SPINE_ORDER
_ctr = {n: np.array([0.0, *LM.SPINE[n]]) for n in ORDER}
_S1 = np.array([0.0, *LM.SACRUM[0]])


def _tangent(i):
    pts = [_ctr[n] for n in ORDER] + [_S1]
    up = pts[i - 1] if i > 0 else pts[0] + (pts[0] - pts[1])
    t = up - pts[i + 1]
    return t / np.linalg.norm(t)


FR, BH = {}, {}
for _i, _n in enumerate(ORDER):
    z = _tangent(_i)
    x = np.array([1.0, 0, 0])
    y = np.cross(z, x)
    FR[_n] = np.stack([x, y / np.linalg.norm(y), z])
    zs = [_ctr[n][2] for n in ORDER]
    gaps = []
    if _i > 0:
        gaps.append(zs[_i - 1] - zs[_i])
    if _i < len(ORDER) - 1:
        gaps.append(zs[_i] - zs[_i + 1])
    BH[_n] = float(np.mean(gaps)) - LM.disc_thickness(_n)
BH['L5'] = min(BH['L5'], 2.3)

# spinous process (length, angle below horizontal); transverse params
SPIN = {'C3': (1.35, 12), 'C4': (1.45, 14), 'C5': (1.5, 16), 'C6': (1.7, 18), 'C7': (2.7, 22),
        'T1': (3.2, 28), 'T2': (3.5, 36), 'T3': (3.7, 45), 'T4': (3.9, 55), 'T5': (4.0, 60), 'T6': (4.0, 62),
        'T7': (4.0, 62), 'T8': (3.9, 58), 'T9': (3.7, 50), 'T10': (3.4, 40), 'T11': (3.0, 30), 'T12': (2.7, 18),
        'L1': (2.7, 6), 'L2': (2.8, 4), 'L3': (2.8, 2), 'L4': (2.6, 4), 'L5': (2.3, 10)}


def canal_cy(name):
    d = LM.vertebra_dims(name)
    return d['bd'] / 2 + d['cry'] + 0.1


def vertebra(name):
    y0, z0 = LM.SPINE[name]
    d = LM.vertebra_dims(name)
    bw, bd, crx, cry = d['bw'], d['bd'], d['crx'], d['cry']
    hz = BH[name] / 2
    fr = Fr((0, y0, z0), FR[name])
    kind, i = name[0], int(name[1:])
    cy = canal_cy(name)
    F, H = [], []
    # ---------------- body
    if kind == 'C':
        bf = vbody_fn(bw / 2, bd / 2, hz, n=2.3, waist=0.05, rnd=0.18)
    elif kind == 'T':
        bf = vbody_fn(bw / 2, bd / 2, hz, n=2.0, heart=0.16, waist=0.09, rnd=0.25, kidney=0.12)
    else:
        bf = vbody_fn(bw / 2, bd / 2, hz, n=2.4, waist=0.11, rnd=0.32, kidney=0.25)
    F.append(custom(bf, fr, (-bw / 2 - 0.1, -bd / 2 - 0.1, -hz - 0.1), (bw / 2 + 0.1, bd / 2 + 0.1, hz + 0.1)))
    if kind == 'C':
        for s in SIDES:   # uncinate processes
            F.append(fr.E((s * (bw / 2 - 0.12), -0.05, hz - 0.02), (0.17, bd * 0.38, 0.22)))
    # ---------------- pedicles & laminae
    pr = {'C': 0.27, 'T': 0.36, 'L': 0.52}[kind]
    ph = {'C': 0.42, 'T': 0.62, 'L': 0.72}[kind]
    lam_h = min(hz * 0.95, {'C': 0.55, 'T': 0.85, 'L': 1.05}[kind])
    for s in SIDES:
        a = (s * (crx * 0.82 + 0.12), bd / 2 - 0.4, 0.15 * hz)
        b = (s * (crx + 0.2), cy + 0.15, 0.15 * hz)
        F.append(fr.Eax(a, b, ph, pr, xhint=(0, 0, 1), ext=0.22))
        a2 = (s * (crx + 0.2), cy + 0.15, 0.0)
        b2 = (s * 0.1, cy + cry + 0.32, -0.12 * hz)
        F.append(fr.Eax(a2, b2, lam_h, 0.26, xhint=(0, 0, 1), ext=0.2))
    # ---------------- spinous process
    L, ang = SPIN[name]
    root = np.array((0, cy + cry + 0.25, -0.15 * hz))
    dv = np.array((0, np.cos(np.radians(ang)), -np.sin(np.radians(ang))))
    tip = root + dv * L
    if kind == 'L':
        F.append(fr.Eax(root, tip, 0.95, 0.33, xhint=(0, 0, 1), ext=0.15))
        F.append(fr.E(tip - dv * 0.15, (0.42, 0.45, 1.05)))
    elif kind == 'C' and name != 'C7':
        F.append(fr.Eax(root, tip, 0.36, 0.26, xhint=(0, 0, 1), ext=0.1))
        for s in SIDES:
            F.append(fr.sph(tip + np.array((s * 0.32, -0.05, 0)), 0.27))
    else:
        F.append(fr.Eax(root, tip, 0.55, 0.28, xhint=(0, 0, 1), ext=0.1))
        F.append(fr.E(tip, (0.42, 0.42, 0.5)))
    # ---------------- transverse & articular processes
    if kind == 'C':
        tipx = bw / 2 + (1.0 if name != 'C7' else 1.45)
        for s in SIDES:
            F.append(fr.Eax((s * (bw / 2 - 0.25), -0.15, 0), (s * tipx, 0.25, 0), 0.30, 0.21, xhint=(0, 0, 1), ext=0.1))
            F.append(fr.Eax((s * (crx + 0.15), cy - 0.25, 0), (s * tipx, 0.55, 0), 0.30, 0.21, xhint=(0, 0, 1), ext=0.1))
            F.append(fr.sph((s * tipx, -0.05, 0), 0.27))
            F.append(fr.sph((s * tipx, 0.7, -0.05), 0.27))
            F.append(fr.E((s * (crx + 0.32), cy - 0.05, 0), (0.42, 0.55, hz * 1.15)))      # articular pillar
            H.append(fr.ecyl((s * (bw / 2 + 0.42), 0.22, 0), 0.26 if name != 'C7' else 0.18, 0.24, 2.0))
    elif kind == 'T':
        t = (i - 1) / 11
        tpx, tpy = 3.5 - 1.0 * t, 1.0 - 0.3 * t
        for s in SIDES:
            a = (s * (crx + 0.25), cy - 0.05, 0.2 * hz)
            b = (s * tpx, cy + tpy, 0.2 * hz)
            F.append(fr.Eax(a, b, 0.46, 0.38, xhint=(0, 0, 1), ext=0.05))
            F.append(fr.E(b, (0.5, 0.45, 0.52)))
            H.append(fr.sph(np.array(b) + np.array((0, -0.5, 0)), 0.3))                      # transverse costal facet
            H.append(fr.sph((s * (bw / 2 + 0.1), bd / 2 - 0.45, hz), 0.34))                  # superior costal facet
            F.append(fr.Eax((s * (crx + 0.1), cy + 0.0, 0.3 * hz), (s * (crx + 0.15), cy + 0.25, hz + 0.75),
                            0.32, 0.26, xhint=(1, 0, 0), ext=0.1))
            F.append(fr.Eax((s * (crx - 0.05), cy + 0.35, -0.2 * hz), (s * (crx - 0.15), cy + 0.6, -hz - 0.75),
                            0.32, 0.26, xhint=(1, 0, 0), ext=0.1))
    else:
        tpx = [3.3, 3.6, 3.9, 3.7, 3.5][i - 1]
        rv = 0.42 if i < 5 else 0.68
        for s in SIDES:
            a = (s * (crx + 0.3), cy - 0.45, 0.05 * hz)
            b = (s * tpx, cy - 0.15, 0.05 * hz)
            F.append(fr.Eax(a, b, rv, 0.26, xhint=(0, 0, 1), ext=0.15))
            F.append(fr.Eax((s * (crx + 0.2), cy + 0.05, 0.25 * hz), (s * (crx + 0.45), cy + 0.45, hz + 0.85),
                            0.45, 0.32, xhint=(1, 0, 0), ext=0.1))
            F.append(fr.sph((s * (crx + 0.62), cy + 0.55, hz + 0.25), 0.3))                  # mammillary process
            F.append(fr.Eax((s * (crx - 0.05), cy + 0.45, -0.2 * hz), (s * (crx - 0.2), cy + 0.7, -hz - 0.85),
                            0.42, 0.3, xhint=(1, 0, 0), ext=0.1))
    v = smooth_union_all(F, 0.2 if kind == 'C' else (0.24 if kind == 'T' else 0.3))
    H.append(fr.ecyl((0, cy, 0), crx, cry, 4.0))
    return subtract(v, *H)


def vertebra_color(name):
    seed = ORDER.index(name) + 40

    def f(ctx):
        col = C.bone(ctx, seed=seed)
        return col
    return f


# ============================================================================ discs
def body_end(name, top):
    c = _ctr[name]
    t = FR[name][2]
    return c + t * (BH[name] / 2) * (1 if top else -1)


def disc_list(region):
    out = []
    names = [n for n in ORDER if n[0] == region]
    for n in names:
        i = ORDER.index(n)
        if i + 1 < len(ORDER):
            lower = ORDER[i + 1]
            lo_top = body_end(lower, True)
            dl = LM.vertebra_dims(lower)
        else:
            lower = 'S1'
            lo_top = _S1 + np.array([0, -0.25, 1.05])
            dl = dict(bw=5.0, bd=3.4)
        up_bot = body_end(n, False)
        du = LM.vertebra_dims(n)
        out.append((n, lower, up_bot, lo_top, (du['bw'] + dl['bw']) / 4, (du['bd'] + dl['bd']) / 4))
    return out


def discs(region):
    F = []
    for (n, lower, a, b, rx, ry) in disc_list(region):
        c = (a + b) / 2
        ax = a - b
        th = np.linalg.norm(ax)
        z = ax / th
        x = np.array([1.0, 0, 0]); y = np.cross(z, x); y /= np.linalg.norm(y)
        fr = Fr(c, np.stack([x, y, z]))
        bf = vbody_fn(rx * 1.03, ry * 1.03, th / 2 + 0.06, n=2.1, waist=-0.06, rnd=min(0.25, th / 2))
        F.append(custom(bf, fr, (-rx - 0.3, -ry - 0.3, -th), (rx + 0.3, ry + 0.3, th)))
    return union(*F)


def disc_color(ctx):
    p = ctx['pc']
    yc = np.interp(-p[:, 2], [-_ctr[n][2] for n in ORDER] + [-_S1[2]], [_ctr[n][1] for n in ORDER] + [_S1[1]])
    r = np.sqrt(p[:, 0] ** 2 + ((p[:, 1] - yc) * 1.3) ** 2)
    rings = np.sin(r * 11.0 + S.perlin(p * 1.5) * 1.5) * 0.5 + 0.5
    col = C.mix(C.C(0.86, 0.88, 0.86), C.C(0.74, 0.79, 0.84), rings * 0.45)
    col = C.mix(col, C.C(0.90, 0.86, 0.78), np.clip(S.perlin(p * 0.8, 3) + 0.2, 0, 1) * 0.3)
    return C.shade(col, ctx, 0.4, 0.3, 0.15)


# ============================================================================ sacrum & coccyx
SAC_W = [2.6, 2.2, 1.8, 1.3, 0.9]
SAC_T = [1.8, 1.4, 1.1, 0.9, 0.7]


def sacrum_frames():
    pts = np.array([(0, y, z) for y, z in LM.SACRUM])
    frs = []
    for i in range(5):
        up = pts[i - 1] if i > 0 else pts[0] + (pts[0] - pts[1])
        t = up - pts[i + 1]; t /= np.linalg.norm(t)
        x = np.array([1.0, 0, 0]); y = np.cross(t, x); y /= np.linalg.norm(y)
        frs.append(Fr(pts[i], np.stack([x, y, t])))
    return frs


def sacrum():
    frs = sacrum_frames()
    F, H = [], []
    for i, fr in enumerate(frs):
        w, t = SAC_W[i], SAC_T[i]
        F.append(fr.E((0, 0, 0), (w, t, 0.95 if i else 1.05)))
        if i <= 2:   # lateral masses / alae
            lw = [2.1, 1.6, 1.1][i]
            F.append(fr.E((3.5 if i == 0 else 2.9 - 0.4 * i, 0.45, 0.25 if i == 0 else 0.0), (lw, [1.6, 1.25, 1.0][i], [1.35, 1.0, 0.9][i])))
            F.append(fr.E((-(3.5 if i == 0 else 2.9 - 0.4 * i), 0.45, 0.25 if i == 0 else 0.0), (lw, [1.6, 1.25, 1.0][i], [1.35, 1.0, 0.9][i])))
        F.append(fr.E((0, t + 0.35, 0), (0.35, 0.45, 0.6)))                       # median sacral crest
        for s in SIDES:
            F.append(fr.E((s * (w * 0.75), t * 0.75, 0), (0.45, 0.45, 0.65)))      # intermediate crest
    f0 = frs[0]
    for s in SIDES:
        F.append(f0.E((s * 1.6, 2.4, 1.1), (0.55, 0.6, 0.6)))                    # superior articular processes
    F.append(f0.E((0, -1.75, 0.85), (2.3, 0.35, 0.3)))                           # promontory lip
    sac = smooth_union_all(F, 0.55)
    # foramina (between segments) and canal
    for i in range(4):
        a, b = frs[i], frs[i + 1]
        cpt = (a.c + b.c) / 2
        fr = Fr(cpt, (a.R + b.R) / 2)
        for s in SIDES:
            xx = s * (1.55 - 0.12 * i)
            H.append(fr.cap((xx, -3.0, 0), (xx, 3.0, 0), 0.36 - 0.03 * i))
    cpts = [fr.w((0, SAC_T[i] * 0.45, 0)) for i, fr in enumerate(frs)]
    cpts = [frs[0].w((0, 0.7, 1.6))] + cpts
    H.append(tube(cpts, [0.85, 0.8, 0.65, 0.5, 0.4, 0.35]))
    H.append(frs[4].E((0, 0.9, -0.1), (0.45, 0.6, 0.9)))                         # sacral hiatus
    return subtract(sac, *H)


def coccyx():
    y5, z5 = LM.SACRUM[4]
    pts = [(5.6, 87.55, 1.05, 0.5, 0.42), (5.4, 86.95, 0.78, 0.42, 0.36), (5.1, 86.45, 0.58, 0.36, 0.3),
           (4.75, 86.05, 0.4, 0.28, 0.24)]
    F = [ellipsoid((0, y, z), (rx, ry, rz)) for (y, z, rx, ry, rz) in pts]
    F.append(ellipsoid((0, 5.75, 87.85), (0.35, 0.3, 0.3)))
    for s in SIDES:
        F.append(ellipsoid((s * 0.75, 5.7, 87.75), (0.3, 0.25, 0.3)))   # cornua
    return smooth_union_all(F, 0.12)


# ============================================================================ ribs & costal cartilage
def rib_points(k, s):
    a, b, yc, zp, zcc, thc, cend = LM.RIBS[k]
    nm = f'T{k}'
    y0, z0 = LM.SPINE[nm]
    d = LM.vertebra_dims(nm)
    bh = BH[nm]
    cy = canal_cy(nm)
    t = (k - 1) / 11
    tpx, tpy = 3.5 - 1.0 * t, 1.0 - 0.3 * t
    head = (s * (d['bw'] / 2 + 0.15), y0 + d['bd'] / 2 - 0.45, z0 + bh * 0.45)
    tub = (s * (tpx - 0.15), y0 + cy + tpy - 0.4, z0 + 0.1)
    t0 = np.arcsin(min(0.97, (tpx + 1.5) / a))
    ts = np.linspace(t0, thc, 12)
    u = (ts - t0) / (thc - t0)
    zt = tub[2] - 0.3 - (tub[2] - 0.3 - zcc) * u ** 1.25
    ell = np.stack([s * a * np.sin(ts), yc + b * np.cos(ts), zt], 1)
    return np.vstack([head, tub, ell]), (a, b, yc, thc, zcc)


def cartilage_points(k, s, prev=None):
    a, b, yc, zp, zcc, thc, cend = LM.RIBS[k]
    if k <= 7:
        tx, ty, tz = cend
    else:
        tx, ty, tz = prev
    tx = abs(tx)
    te = np.pi - np.arcsin(min(0.99, tx / a))
    ts = np.linspace(thc, te, 10)
    u = (ts - thc) / (te - thc)
    z = zcc + (tz - zcc) * (u ** 1.6 if k >= 3 else u)
    pts = np.stack([s * a * np.sin(ts), yc + b * np.cos(ts), z], 1)
    pts[-1] = (s * tx, ty, tz)
    return pts


def rib_tube(k, s):
    pts, (a, b, yc, thc, zcc) = rib_points(k, s)
    if k == 1:
        rn = lambda t: np.interp(t, [0, 0.12, 0.3, 1], [0.45, 0.5, 0.95, 0.85])
        rb = lambda t: np.interp(t, [0, 0.12, 0.3, 1], [0.45, 0.42, 0.33, 0.32])
    elif k >= 11:
        rn = lambda t: np.interp(t, [0, 0.15, 0.6, 1], [0.42, 0.33, 0.27, 0.16])
        rb = lambda t: np.interp(t, [0, 0.15, 0.6, 1], [0.42, 0.5, 0.48, 0.2])
    else:
        hmax = 0.62 + 0.08 * min(k, 7) / 7
        rn = lambda t: np.interp(t, [0, 0.07, 0.15, 0.5, 1], [0.45, 0.36, 0.33, 0.27, 0.32])
        rb = lambda t: np.interp(t, [0, 0.07, 0.15, 0.35, 1], [0.45, 0.5, 0.62, hmax, hmax * 0.85])
    yc_s = yc * TM.sy

    def nfn(ps):
        n = np.stack([ps[:, 0], ps[:, 1] - yc_s, np.zeros(len(ps))], 1)
        n[:, 0] *= 1.0
        return n
    v, f, prm = tube_mesh(pts, TM, 1.0, ds=0.0135, sides=12, n=14, rprofile=rn, rb_cm=rb, normal_fn=nfn)
    return v, f, prm


def rib_color(seed, yc):
    def f(ctx):
        col = C.bone(ctx, seed=seed)
        ps, n = ctx['ps'], ctx['n']
        rad = np.stack([ps[:, 0], ps[:, 1] - yc * TM.sy, np.zeros(len(ps))], 1)
        rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
        inward = -(n * rad).sum(1)
        g = np.clip(inward * 0.9 - n[:, 2] * 0.9 - 0.7, 0, 1)      # costal groove (inner lower edge)
        if ctx.get('prm') is not None:
            g *= np.clip((ctx['prm'][:, 0] - 0.15) * 4, 0, 1)
        return C.mix(col, C.C(0.62, 0.52, 0.40), g * 0.5)
    return f


def cartilage_tubes(s):
    out = []
    prev = None
    for k in range(1, 11):
        a, b, yc, zp, zcc, thc, cend = LM.RIBS[k]
        if k >= 8:
            # join the cartilage above at ~55% of its length, slightly below it
            q = prev_pts[int(len(prev_pts) * 0.55)]
            target = (abs(q[0]), q[1] + 0.15, q[2] - 0.75)
            pts = cartilage_points(k, s, target)
        else:
            pts = cartilage_points(k, s)
        prev_pts = pts
        r0 = 0.62 if k > 1 else 0.75
        v, f, prm = tube_mesh(pts, TM, r0, r_end_cm=0.5 if k <= 7 else 0.42, ds=0.012, sides=10, n=12,
                              rb_cm=lambda t: 0.55 - 0.1 * t)
        out.append((v, f, prm, C.cartilage))
    return out


# ============================================================================ sternum
def sternum():
    phi = np.radians(0.0)
    O = np.array([0, -10.45, 133.5])
    xl = np.array([1.0, 0, 0]); yl = np.array([0, np.sin(phi), np.cos(phi)]); zl = np.cross(xl, yl)
    R = np.stack([xl, yl, zl])
    half = [(0, 12.75), (1.1, 12.95), (2.3, 12.65), (2.95, 11.7), (2.65, 10.2), (1.95, 8.6), (1.5, 7.6),
            (1.6, 7.0), (1.9, 4.5), (2.15, 1.0), (2.05, -2.5), (1.8, -5.5), (1.3, -7.6), (0.75, -8.4),
            (0.48, -10.5), (0.18, -12.4), (0, -12.7)]
    poly = [(x, y) for x, y in half] + [(-x, y) for x, y in half[::-1][1:-1]]

    def th(x, y):
        return np.interp(y, [-12.8, -8.0, -7.2, 7.0, 8.0, 13.0], [0.25, 0.33, 0.55, 0.6, 0.78, 0.8])
    st = plate(O, R, poly, 0.8, rnd=0.22, bend=(0.025, 0.0), thick_fn=th)
    H = [sphere((0, -10.25, 146.6), 1.0)]
    for s in SIDES:
        H.append(ellipsoid((s * 2.75, -10.15, 145.55), (0.7, 0.9, 0.75)))
        for k in range(1, 8):
            cx, cy_, cz = LM.RIBS[k][6]
            H.append(sphere((s * (abs(cx) + 0.35), cy_ - 0.2, cz), 0.42))
    st = subtract(st, *H)
    ridge = [capsule((0, -11.0, 140.95), (s * 1.45, -10.95, 140.95), 0.22) for s in SIDES]   # sternal angle
    return smooth_union_all([st] + ridge, 0.2)


# ============================================================================ clavicle
def clavicle(s):
    pts = np.array(LM.CLAVICLE) * np.array([s, 1, 1])
    sw = Swept(pts, rn=[(0, 1.2), (0.1, 0.95), (0.4, 0.75), (0.7, 0.62), (0.92, 0.5), (1, 0.55)],
               rb=[(0, 1.15), (0.1, 0.92), (0.4, 0.78), (0.7, 0.95), (0.92, 1.35), (1, 1.2)],
               nhint=(0, 0, 1), ds=0.12, cap0=0.55, cap1=0.5)
    node = sw.sdf()
    p_con = sw.point(0.78)
    extra = [ellipsoid(p_con + np.array([0, 0.25, -0.4]), (0.55, 0.45, 0.35))]   # conoid tubercle
    p_med = sw.point(0.02)
    extra.append(ellipsoid(p_med + np.array([0, 0, -0.1]), (0.6, 0.85, 0.85)))
    return smooth_union_all([node] + extra, 0.3)


# ============================================================================ scapula
SC = {k: (np.array(v) + np.array([0, 0, 1.2]) if np.ndim(v) == 1 else [np.array(q) + np.array([0, 0, 1.2]) for q in v])
      for k, v in LM.SCAPULA.items()}
HUM_C = {s: ArmMap(s).fwd(np.zeros((1, 3)))[0] for s in SIDES}            # humeral head centre (studs)
HUM_R = np.array([2.3 * ArmMap.sh, 2.3 * ArmMap.sh, 2.3 * ArmMap.sv])
FEM_C = {s: LegMap(s).fwd(np.zeros((1, 3)))[0] for s in SIDES}            # femoral head centre (studs)
FEM_R = np.array([2.4 * LegMap.sx, 2.4 * LegMap.sy, 2.4 * LegMap.sv])


def scapula_left():
    sup, inf, gle = SC['sup_angle'], SC['inf_angle'], SC['glenoid']
    y = sup - inf; y /= np.linalg.norm(y)
    x = (gle - inf) - y * ((gle - inf) @ y); x /= np.linalg.norm(x)
    z = np.cross(x, y)
    O = (sup + inf + gle) / 3
    R = np.stack([x, y, z])
    outline = [sup, (10.5, 4.8, 147.2), SC['notch'], (14.0, 1.5, 145.4), (15.8, 0.6, 144.8), (15.6, 0.8, 141.2),
               (13.5, 4.0, 137.2), (11.6, 6.2, 132.7), inf, (8.6, 7.8, 134.2), (7.6, 7.9, 138.7),
               SC['medial_spine_root'], (7.6, 7.0, 145.7)]
    poly = [((np.array(p) - O) @ x, (np.array(p) - O) @ y) for p in outline]
    body = plate(O, R, poly, 0.22, rnd=0.15, bend=(0.022, 0.006))
    F = [body]
    lat = [(15.6, 0.8, 141.2), (13.5, 4.0, 137.2), (11.6, 6.2, 132.7), inf]
    F.append(tube(lat, [0.62, 0.5, 0.42, 0.45]))                            # lateral (axillary) border
    F.append(tube([sup, (7.6, 7.0, 145.7), SC['medial_spine_root'], (7.6, 7.9, 138.7), (8.6, 7.8, 134.2), inf], 0.26))
    F.append(tube([sup, (10.5, 4.8, 147.2), SC['notch']], 0.25))
    sp = SC['spine']
    for (a, b, hgt) in ((sp[0], sp[1], 1.0), (sp[1], sp[2], 1.6)):
        a = np.array(a) - z * 0.8; b = np.array(b) - z * 1.1
        d = b - a; L = np.linalg.norm(d)
        F.append(ellipsoid((a + b) / 2, (hgt, 0.42, L / 2 + 0.4), frame(d, z)))
    F.append(ellipsoid(sp[2] - z * 0.9, (1.3, 0.55, 1.0), frame(SC['acromion'] - sp[2], z)))
    ac = SC['acromion']
    F.append(ellipsoid(ac, (0.6, 1.35, 1.9), frame(ac - sp[2], (0, 0, 1))))    # flat acromion
    cor = SC['coracoid']
    F.append(tube([cor[0], np.array([14.8, -1.5, 144.6 + 1.2 - 1.2]), cor[1]], [0.72, 0.6, 0.42]))
    F.append(ellipsoid(gle + np.array([0.5, 0, 0]), (1.35, 1.1, 1.75)))      # glenoid
    F.append(ellipsoid(gle + np.array([-1.0, 0.6, 0]), (1.0, 1.0, 1.4)))      # neck
    sc = smooth_union_all(F, 0.38)
    sock = stud_shape(ellipsoid(HUM_C[1], HUM_R + 0.007), SG)
    return subtract(sc, sock)


# ============================================================================ hip bone
def hip_bone_left():
    P = LM.PELVIS
    A = np.array(P['asis']); Ps = np.array(P['psis']); Cc = np.array((9.8, -3.0, 92.8))
    xax = A - Ps; xax /= np.linalg.norm(xax)
    n = np.cross(A - Ps, Cc - Ps); n /= np.linalg.norm(n)
    if n[0] < 0:
        n = -n
    yax = np.cross(n, xax)
    outline = [A] + [np.array(q) for q in P['crest'][1:]] + [np.array(P['piis']), np.array(P['sciatic_notch']),
                                                             np.array((8.6, 0.5, 91.6)), Cc,
                                                             np.array(P['aiis']), np.array((11.3, -7.6, 96.0))]
    O = np.mean(outline, axis=0)
    R = np.stack([xax, yax, n])
    poly = [((q - O) @ xax, (q - O) @ yax) for q in outline]
    ys = [p[1] for p in poly]
    ytop, ybot = max(ys), min(ys)

    def th(xx, yy):
        u = np.clip((ytop - yy) / (ytop - ybot), 0, 1)
        return 0.3 + 1.1 * np.clip((u - 0.55) / 0.45, 0, 1) ** 1.5
    F = [plate(O, R, poly, 1.4, rnd=0.25, bend=(-0.012, -0.012), thick_fn=th)]
    crest = [np.array(q) for q in P['crest']]
    F.append(tube(crest, [0.7, 0.85, 0.95, 0.8, 0.7, 0.75]))
    F.append(sphere(P['asis'], 0.75)); F.append(sphere(P['aiis'], 0.65))
    F.append(sphere(P['psis'], 0.8)); F.append(sphere(P['piis'], 0.6))
    F.append(ellipsoid((5.4, 3.6, 95.6), (1.2, 1.9, 2.6)))                    # auricular region
    F.append(ellipsoid((8.0, -2.3, 91.5), (2.5, 2.9, 2.6)))                   # acetabular mass
    F.append(round_cone((8.0, -1.0, 89.0), (6.1, 0.1, 84.4), 1.35, 1.35))     # ischial body
    F.append(ellipsoid((6.0, 0.35, 84.0), (1.3, 1.65, 1.1)))                  # ischial tuberosity
    sp = P['ischial_spine']
    F.append(round_cone((6.9, 1.3, 88.4), sp[1], 0.6, 0.25))
    F.append(tube(P['ischiopubic'], [1.0, 0.7, 0.62, 0.7]))
    F.append(ellipsoid((1.6, -8.15, 88.6), (1.3, 1.0, 1.6)))                  # pubic body
    sup_r = [(1.6, -8.3, 89.2), (2.6, -8.45, 89.45), (5.5, -6.6, 90.3), (7.8, -4.5, 90.9)]
    F.append(tube(sup_r, [0.85, 0.8, 0.85, 1.0]))
    F.append(sphere((2.6, -8.7, 89.5), 0.5))                                  # pubic tubercle
    hb = smooth_union_all(F, 0.7)
    hb = subtract(hb, ellipsoid((5.1, -3.9, 86.6), (1.75, 2.0, 1.75), frame((0.55, -0.6, 0.55), (0, 0, 1))))   # obturator foramen
    hb = subtract(hb, halfspace((0.42, 0, 0), (1, 0, 0)))                     # symphysis plane
    sock = stud_shape(ellipsoid(FEM_C[1], FEM_R + 0.007), TM)
    notch = stud_shape(ellipsoid(FEM_C[1] + np.array([0.012, -0.012, -0.05]), (0.03, 0.035, 0.03)), TM)
    return subtract(hb, sock, notch)


# ============================================================================ joint cartilage
def glenoid_labrum(s):
    c = HUM_C[s] + np.array([-s * (HUM_R[0] + 0.004), 0, 0])
    R = np.stack([np.array([0, 0, 1.0]), np.array([0, 1.0, 0]), np.array([s * 1.0, 0, 0])])
    return stud_shape(torus(c, 0.040, 0.0085, R, sx=1.35), TM)


def acetabular_labrum(s):
    nac = np.array([s * 0.8, -0.35, -0.48]); nac /= np.linalg.norm(nac)
    c = FEM_C[s] + nac * 0.042
    R = frame(nac, (0, 0, 1))
    return stud_shape(torus(c, 0.058, 0.0095, R, sx=1.0), TM)


def jc_color(ctx):
    return C.cartilage(ctx, seed=3)


# ============================================================================ registry
def bone_part(name, fn, target, h, info, mp=TM, seed=0, far=0.8):
    return Part(name, mp, sdf=fn, color=lambda c, seed=seed: C.bone(c, seed=seed), target=target, h=h, far=far,
                info=info)


def parts():
    P = []
    lab = {'C': 'cervicale', 'T': 'thoracique', 'L': 'lombaire'}
    for n in ORDER:
        k = n[0]
        P.append(Part(f'Torso_Vertebra_{n}', TM, sdf=lambda n=n: vertebra(n), color=vertebra_color(n),
                      target={'C': 3800, 'T': 4300, 'L': 4800}[k], h={'C': 0.0012, 'T': 0.0015, 'L': 0.0019}[k],
                      far=0.6, info=f'Vertèbre {lab[k]} {n} (corps, pédicules, lames, processus épineux, transverses et articulaires)'))
    for reg, nm, tgt in (('C', 'Cervical', 3000), ('T', 'Thoracic', 7000), ('L', 'Lumbar', 4000)):
        P.append(Part(f'Torso_Discs_{nm}', TM, sdf=lambda reg=reg: discs(reg), color=disc_color, target=tgt,
                      h=0.0015 if reg != 'L' else 0.002, far=0.5, cat='disc', base=(0.84, 0.87, 0.87),
                      info=f'Disques intervertébraux {lab[reg]}s (anneau fibreux)'))
    P.append(bone_part('Torso_Sacrum', sacrum, 13000, 0.0021, 'Sacrum (ailes, promontoire, foramens sacrés, crête sacrale)', seed=5))
    P.append(bone_part('Torso_Coccyx', coccyx, 2500, 0.0012, 'Coccyx (4 vertèbres soudées)', seed=6))
    for s, t in ((1, 'L'), (-1, 'R')):
        side = 'gauche' if s > 0 else 'droite'
        for k in range(1, 13):
            P.append(Part(f'Torso_Rib_{t}{k:02d}', TM, tubes=lambda k=k, s=s: [rib_tube(k, s) + (rib_color(60 + k, LM.RIBS[k][2]),)],
                          target=2600, info=f'Côte {k} {side}' + (' (flottante)' if k >= 11 else '')))
        P.append(Part(f'Torso_CostalCartilage_{t}', TM, tubes=lambda s=s: cartilage_tubes(s), target=16000,
                      cat='cartilage', base=(0.8, 0.86, 0.9), info=f'Cartilages costaux {side}s (côtes 1 à 10, rebord costal)'))
        P.append(Part(f'Torso_Clavicle_{t}', GM, sdf=lambda s=s: clavicle(s), color=lambda c: C.bone(c, seed=8),
                      target=5000, h=0.0018, far=0.8, info=f'Clavicule {side}'))
        P.append(Part(f'Torso_Scapula_{t}', SG, sdf=(scapula_left if s > 0 else (lambda: flip_x(scapula_left()))),
                      color=lambda c: C.bone(c, seed=9), target=13000, h=0.0021, far=0.8,
                      info=f'Omoplate {side} (épine, acromion, processus coracoïde, cavité glénoïde)'))
        P.append(Part(f'Torso_HipBone_{t}', TM, sdf=(hip_bone_left if s > 0 else (lambda: flip_x(hip_bone_left()))),
                      color=lambda c: C.bone(c, seed=10), target=18000, h=0.0024, far=1.0,
                      info=f'Os coxal {side} (ilium, ischium, pubis, cotyle, trou obturé)'))
        P.append(Part(f'Torso_GlenoidLabrum_{t}', TM, sdf=lambda s=s: glenoid_labrum(s), color=jc_color, target=1500,
                      h=0.0012, far=0.3, cat='cartilage', base=(0.8, 0.86, 0.9),
                      info=f'Bourrelet glénoïdien {side} (articulation de l\'épaule)'))
        P.append(Part(f'Torso_AcetabularLabrum_{t}', TM, sdf=lambda s=s: acetabular_labrum(s), color=jc_color,
                      target=2000, h=0.0012, far=0.3, cat='cartilage', base=(0.8, 0.86, 0.9),
                      info=f'Bourrelet cotyloïdien {side} (articulation de la hanche)'))
    P.append(Part('Torso_Sternum', TM, sdf=sternum, color=lambda c: C.bone(c, seed=7), target=7000, h=0.0016, far=0.6,
                  info='Sternum (manubrium, corps, processus xiphoïde)'))
    P.append(Part('Torso_PubicSymphysis', TM, sdf=lambda: ellipsoid((0, -8.2, 88.6), (0.5, 0.95, 1.5)), color=jc_color,
                  target=800, h=0.0012, far=0.3, cat='cartilage', base=(0.8, 0.86, 0.9), info='Symphyse pubienne (disque fibrocartilagineux)'))
    P.append(Part('Torso_SacroiliacCartilage', TM, sdf=lambda: union(*[ellipsoid((s * 5.05, 3.35, 95.3), (0.25, 1.6, 2.4)) for s in SIDES]),
                  color=jc_color, target=1500, h=0.0013, far=0.3, cat='cartilage', base=(0.8, 0.86, 0.9),
                  info='Cartilages des articulations sacro-iliaques'))
    P.append(Part('Torso_SternoclavicularDiscs', TM, sdf=lambda: union(*[ellipsoid((s * 2.45, -9.75, 145.5), (0.22, 0.65, 0.65)) for s in SIDES]),
                  color=jc_color, target=800, h=0.0011, far=0.3, cat='cartilage', base=(0.8, 0.86, 0.9),
                  info='Disques articulaires sterno-claviculaires'))
    return P
