"""Torso vessels and nerves: aorta and branches, venae cavae and tributaries, portal system, azygos,
intercostal bundles, spinal cord & cauda equina, spinal nerve roots, sympathetic chains, brachial plexus,
lumbosacral plexus (femoral, obturator, sciatic), phrenic and vagus nerves.
End points that continue into the head, arms and legs are computed from those regions' maps."""
import numpy as np
from maps import TorsoMap, HeadMap, ArmMap, LegMap
from parts import Part
import colors as C
import landmarks as LM
from sweep import tube_mesh

TM = TorsoMap()
GM = TorsoMap(girdle=True)
HM = HeadMap()
SIDES = (1, -1)


def from_head(p):
    return TM.inv(HM.fwd(np.array([p], float)))[0]


def from_arm(s, p):
    return GM.inv(ArmMap(s).fwd(np.array([p], float)))[0]


def from_leg(s, p):
    return TM.inv(LegMap(s).fwd(np.array([p], float)))[0]


def T(m, pts, r, r1=None, col=C.artery, sides=10, ds=0.0065, mod=None):
    return tube_mesh(np.array(pts, float), m, r, r_end_cm=r1, ds=ds, sides=sides, mod=mod) + (col,)


def mir(pts, s):
    return [np.array(p, float) * np.array([s, 1, 1]) for p in pts]


# =================================================================== arteries
def arteries_thorax():
    m = GM
    out = [T(m, [(0.0, -3.0, 133.2), (0.5, -3.3, 135.0), (1.4, -3.0, 136.2), (2.8, -0.8, 136.6), (3.0, 1.4, 135.6),
                 (2.8, 3.0, 133.0), (2.5, 2.4, 127.0), (2.1, 1.0, 121.0), (1.6, -0.2, 116.5), (1.0, -0.8, 113.6)],
               1.25, 1.1, sides=18)]
    bct = (-2.4, -1.8, 140.6)
    out.append(T(m, [(0.4, -3.2, 136.0), (-1.2, -2.6, 138.8), bct], 0.68, 0.6, sides=12))
    for s in SIDES:
        ica = from_head((s * 2.0, -0.5, -8.6)); eca = from_head((s * 2.2, -1.1, -8.6))
        fork = (ica + eca) / 2 + np.array([0, 0, -1.2])
        root = bct if s < 0 else (1.6, -2.6, 136.6)
        out.append(T(m, [root, (s * 2.4, -1.4, 144.0), (s * 2.3, -0.9, 151.0), fork], 0.38, 0.36))
        out.append(T(m, [fork, ica], 0.3, 0.27, sides=8))
        out.append(T(m, [fork, eca], 0.24, 0.22, sides=8))
        sub_root = bct if s < 0 else (2.6, -0.4, 136.6)
        ax = from_arm(s, (-3.0, 0.8, 0.9))
        sub = [sub_root, (s * 5.5, -0.8, 143.0), (s * 9.0, -0.2, 144.0), (s * 13.0, 0.3, 143.3), ax]
        out.append(T(m, sub, 0.48, 0.42, sides=12))
        vert = from_head((s * 2.0, 1.8, -7.6))
        out.append(T(m, [(s * 5.0, -0.6, 142.9), (s * 3.2, 0.4, 147.0), (s * 1.6, 1.5, 151.6), (s * 1.6, 1.7, 153.7),
                         (s * 1.65, 1.9, 155.8), vert], 0.2, 0.18, sides=8))
        out.append(T(m, [(s * 4.6, -0.9, 142.9), (s * 3.2, -8.4, 139.0), (s * 2.9, -9.2, 131.0), (s * 3.2, -8.8, 122.5)],
                     0.16, 0.12, sides=6))                                                   # internal thoracic
    return out


def arteries_abdomen():
    m = TM
    out = [T(m, [(1.0, -0.8, 113.6), (1.0, -2.0, 110.0), (1.0, -3.0, 107.0), (0.8, -3.6, 103.0), (0.5, -3.9, 100.5)],
             1.1, 0.95, sides=16)]
    # celiac trunk and branches
    out.append(T(m, [(1.0, -3.6, 110.6), (1.0, -5.0, 110.4)], 0.35, 0.33))
    out.append(T(m, [(1.0, -5.0, 110.4), (-1.0, -5.0, 109.8), (-2.2, -3.4, 109.6), (-2.4, -2.2, 110.2)], 0.26, 0.22))
    out.append(T(m, [(1.0, -5.0, 110.4), (3.6, -3.8, 109.6), (5.4, -2.6, 110.4), (6.8, -0.4, 109.8), (8.4, 1.4, 110.8)],
                 0.26, 0.22))
    out.append(T(m, [(1.0, -5.0, 110.4), (2.4, -5.0, 111.8), (3.4, -4.2, 112.4)], 0.18, 0.14))
    # superior mesenteric artery and jejunal/ileal fan
    sma = [(0.9, -4.0, 108.8), (0.6, -6.4, 106.0), (0.0, -7.6, 101.0), (-1.6, -7.6, 96.5), (-3.6, -6.6, 94.0)]
    out.append(T(m, sma, 0.38, 0.22))
    for tip in ((3.6, -8.8, 100.5), (5.0, -8.0, 96.5), (3.2, -9.6, 93.5), (-0.4, -9.8, 92.5), (-4.6, -8.4, 96.5),
                (-6.0, -6.6, 99.5)):
        a = np.array(sma[2]) * 0.6 + np.array(sma[3]) * 0.4
        out.append(T(m, [a, (a + np.array(tip)) / 2 + np.array([0, -0.6, 0]), tip], 0.14, 0.09, sides=6))
    out.append(T(m, [(0.6, -4.4, 102.0), (2.4, -5.0, 99.0), (3.8, -4.4, 95.0), (2.0, -1.4, 91.0)], 0.22, 0.14))   # IMA
    for s in SIDES:
        hil = np.array((s * 3.0, -0.4, 104.7 if s > 0 else 102.7))
        out.append(T(m, [(s * 0.9, -3.1, 106.6), (s * 2.0, -2.0, 105.6 if s > 0 else 104.0), hil], 0.3, 0.26))     # renal
        out.append(T(m, [(s * 0.9, -4.0, 104.4), (s * 3.6, -3.8, 99.0), (s * 5.8, -4.6, 93.0), (s * 7.4, -6.0, 89.4)],
                     0.1, 0.08, sides=6))                                                              # gonadal
        fem = from_leg(s, (-0.6, -5.5, 1.7))
        out.append(T(m, [(0.5, -3.9, 100.5), (s * 2.2, -4.0, 98.6), (s * 3.8, -4.0, 97.0)], 0.6, 0.55, sides=12))
        out.append(T(m, [(s * 3.8, -4.0, 97.0), (s * 5.4, -4.4, 95.0), (s * 6.8, -5.0, 92.8), fem], 0.5, 0.46))   # ext. iliac
        out.append(T(m, [(s * 3.8, -4.0, 97.0), (s * 4.6, -1.2, 93.6), (s * 5.2, 0.8, 91.0), (s * 5.6, 2.2, 89.6)],
                     0.38, 0.25))                                                                      # int. iliac
    out.append(T(m, [(0.5, -3.2, 100.4), (0.2, -0.6, 95.4), (0.0, 1.8, 90.6)], 0.1, 0.08, sides=6))   # median sacral
    return out


# =================================================================== veins
def veins_thorax():
    m = GM
    V = lambda pts, r, r1=None, sides=10: T(m, pts, r, r1, C.vein, sides)
    out = [V([(-3.0, -2.3, 133.2), (-3.0, -2.1, 136.0), (-3.0, -2.0, 138.0)], 1.0, 0.95, 14)]
    for s in SIDES:
        jun = (s * 5.2, -1.0, 143.5)
        if s < 0:
            out.append(V([(-3.0, -2.0, 138.0), (-4.4, -1.4, 141.6), jun], 0.75, 0.7, 12))
        else:
            out.append(V([(-3.0, -2.0, 138.0), (-0.4, -3.8, 139.4), (2.8, -3.0, 141.4), jun], 0.68, 0.65, 12))
        ijv = from_head((s * 2.6, -0.3, -8.6))
        out.append(V([jun, (s * 3.8, -0.5, 148.0), (s * 2.9, -0.2, 153.0), ijv], 0.62, 0.52, 12))
        ax = from_arm(s, (-3.1, 1.2, 0.9))
        out.append(V([jun, (s * 9.0, -1.0, 144.4), (s * 13.0, -0.6, 143.4), ax], 0.55, 0.5, 12))
    # azygos (right) & hemiazygos (left)
    az = [(-1.0, 1.0, 108.0)] + [(-1.7, LM.SPINE[n][0] - 1.0, LM.SPINE[n][1]) for n in
                                  ('T12', 'T10', 'T8', 'T6', 'T5')] + [(-2.4, 0.6, 132.6), (-3.0, -1.6, 133.4)]
    out.append(V(az, 0.38, 0.45, 8))
    out.append(V([(1.6, 0.6, 108.5), (1.7, 0.6, 114.5), (1.6, 1.2, 120.0), (0.0, 1.0, 122.6), (-1.6, 1.5, 123.2)], 0.25, 0.28, 8))
    return out


def veins_abdomen():
    m = TM
    V = lambda pts, r, r1=None, sides=10: T(m, pts, r, r1, C.vein, sides)
    out = [V([(-2.5, -0.8, 116.8), (-2.4, -2.2, 110.0), (-2.0, -2.9, 104.0), (-1.8, -3.0, 101.5), (-0.6, -3.4, 99.0)],
             1.2, 1.05, 16)]
    for (a, b) in (((-6.5, -2.0, 116.0), (-2.7, -1.0, 116.4)), ((-3.2, -4.4, 117.0), (-2.5, -1.4, 116.8)),
                   ((0.6, -4.6, 116.4), (-2.3, -1.4, 116.6))):
        out.append(V([a, (np.array(a) + np.array(b)) / 2 + np.array([0, 0, 0.4]), b], 0.5, 0.55, 8))   # hepatic veins
    out.append(V([(3.0, -0.4, 104.7), (1.2, -4.8, 105.0), (-1.9, -3.2, 105.2)], 0.42, 0.42, 10))       # left renal
    out.append(V([(-3.0, -0.4, 102.7), (-2.2, -2.4, 103.0)], 0.42, 0.42, 10))                          # right renal
    out.append(V([(8.4, 1.4, 110.6), (6.0, -1.2, 108.2), (3.6, -3.6, 106.4), (0.0, -5.6, 104.6), (-0.8, -5.6, 104.2)],
                 0.35, 0.4, 10))                                                                         # splenic
    out.append(V([(-1.6, -8.0, 96.4), (-0.8, -7.4, 100.0), (-0.6, -6.4, 102.6), (-0.8, -5.6, 104.2)], 0.38, 0.42, 10))   # SMV
    out.append(V([(-0.8, -5.6, 104.2), (-1.8, -4.2, 107.0), (-2.4, -2.6, 109.4), (-2.6, -1.8, 110.4)], 0.62, 0.6, 12))   # portal
    for s in SIDES:
        fem = from_leg(s, (-1.5, -5.3, 1.7))
        out.append(V([(-0.6, -3.4, 99.0), (s * 2.0, -3.4, 97.6) if s < 0 else (1.2, -2.6, 97.8), (s * 3.6, -3.4, 96.0),
                      (s * 5.2, -4.0, 94.4), (s * 6.4, -4.6, 92.6), fem], 0.62, 0.58, 12))
    return out


# =================================================================== intercostal bundles
def intercostals(s):
    import torso_skel as TS
    out = []
    for k in range(3, 12):
        pts, (a, b, yc, thc, zcc) = TS.rib_points(k, s)
        ell = pts[2:]
        n = max(4, int(len(ell) * (0.75 if k < 11 else 0.95)))
        ell = ell[:n]
        rad = np.stack([ell[:, 0], ell[:, 1] - yc, np.zeros(len(ell))], 1)
        rad /= np.linalg.norm(rad, axis=1, keepdims=True)
        base = ell - rad * 0.45
        y0, z0 = LM.SPINE[f'T{k}']
        start = np.array((s * 1.6, y0 - 0.4, z0 - 0.6))
        for off, r, col in ((-0.35, 0.13, C.vein), (-0.62, 0.11, C.artery), (-0.9, 0.09, C.nerve)):
            path = np.vstack([start + np.array([0, 0, off]), base + np.array([0, 0, off - 0.2])])
            out.append(tube_mesh(path, TM, r, r_end_cm=r * 0.7, ds=0.011, sides=5) + (col,))
    return out


# =================================================================== spinal cord, roots, autonomic chains
def canal_pts():
    return [LM.canal_centre(n) for n in LM.SPINE_ORDER]


def spinal_cord():
    cc = canal_pts()
    top = from_head((0, 2.85, -7.6))
    path = [top] + [c for c in cc if c[2] >= 108.0] + [np.array((0, 2.6, 107.6))]
    zs = np.array([p[2] for p in path])

    def prof(t):
        z = np.interp(t, np.linspace(0, 1, len(zs)), zs)
        r = 0.48 + 0.12 * np.exp(-((z - 152.5) / 3.0) ** 2) + 0.06 * np.exp(-((z - 113.0) / 2.5) ** 2)
        return r * np.clip((z - 107.6) / 1.6, 0.25, 1.0)
    out = [tube_mesh(np.array(path), TM, 1.0, rprofile=prof, ds=0.004, sides=14) + (C.spinal_cord,)]
    # cauda equina & filum terminale
    sac = [np.array((0, y + 0.45 - 0.9, z)) for (y, z) in LM.SACRUM[:4]]
    lower = [c for c in cc if c[2] < 108.0]
    rng = np.random.RandomState(3)
    for i in range(12):
        dx = (i - 5.5) * 0.12
        pts = [np.array((dx * 0.3, 2.6, 107.6))] + [c + np.array([dx, 0.05 * rng.randn(), 0]) for c in lower] + \
              [p + np.array([dx * 0.8, 0, 0]) for p in sac[:2 + i % 3]]
        out.append(tube_mesh(np.array(pts), TM, 0.07, ds=0.006, sides=5) + (C.nerve,))
    out.append(tube_mesh(np.array([(0, 2.6, 107.6)] + list(lower) + sac + [(0, 4.6, 86.8)]), TM, 0.05, ds=0.006, sides=5)
               + (C.spinal_cord,))
    return out


def spinal_roots():
    import torso_skel as TS
    out = []
    names = LM.SPINE_ORDER
    for i, n in enumerate(names):
        cc = LM.canal_centre(n)
        d = LM.vertebra_dims(n)
        zf = cc[2] - TS.BH[n] / 2 - 0.25            # intervertebral foramen below the pedicle
        for s in SIDES:
            a = cc + np.array([s * 0.4, 0, -0.2])
            f = np.array((s * (d['crx'] + 0.55), cc[1] - 0.35, zf))
            out_dir = np.array((s * 1.0, -0.55, -0.35 if n[0] != 'C' else -0.15))
            e = f + out_dir * (1.6 if n[0] != 'T' else 1.0)
            pts = np.array([a, (a + f) / 2, f, e])
            mod = lambda s01, phi: 1 + 0.9 * np.exp(-((s01 - 0.62) / 0.12) ** 2)      # dorsal root ganglion
            out.append(tube_mesh(pts, TM, 0.14, r_end_cm=0.16, ds=0.0045, sides=6, mod=mod) + (C.nerve,))
    # sympathetic trunks with ganglia
    for s in SIDES:
        pts = []
        for n in names:
            y0, z0 = LM.SPINE[n]
            d = LM.vertebra_dims(n)
            pts.append((s * (d['bw'] / 2 + 0.35), y0 - d['bd'] * 0.15, z0))
        pts = np.array(pts)
        L = len(pts)
        mod = lambda s01, phi, L=L: 1 + 1.2 * np.exp(-((((s01 * (L - 1)) % 1.0) - 0.5) / 0.12) ** 2)
        out.append(tube_mesh(pts, TM, 0.11, ds=0.004, sides=6, mod=mod) + (C.nerve,))
    return out


def brachial_plexus():
    m = GM
    out = []
    for s in SIDES:
        roots = []
        for n in ('C5', 'C6', 'C7', 'T1'):
            cc = LM.canal_centre(n)
            d = LM.vertebra_dims(n)
            roots.append(np.array((s * (d['crx'] + 1.2), cc[1] - 0.6, cc[2] - 0.6)))
        sup, mid, inf = (np.array((s * 6.0, -0.8, 148.0)), np.array((s * 6.4, -0.6, 146.6)), np.array((s * 6.6, -0.2, 145.0)))
        for rt, tr in zip(roots, (sup, sup, mid, inf)):
            out.append(T(m, [rt, (rt + tr) / 2, tr], 0.26, 0.3, C.nerve, 8))
        cords = {'lat': np.array((s * 11.5, -0.9, 144.6)), 'post': np.array((s * 11.8, 0.6, 144.0)),
                 'med': np.array((s * 11.6, 0.0, 143.0))}
        for tr in (sup, mid, inf):
            for key in ('lat', 'post', 'med'):
                if (key == 'lat' and tr is inf) or (key == 'med' and tr is sup):
                    continue
                out.append(T(m, [tr, (tr + cords[key]) / 2 + np.array([0, 0, 0.3]), cords[key]], 0.22, 0.24, C.nerve, 7))
        ends = {'median': ((-2.8, 0.2, 0.8), ('lat', 'med')), 'ulnar': ((-3.1, 0.6, 0.8), ('med',)),
                'radial': ((-2.5, 1.4, 0.8), ('post',)), 'musculo': ((-2.4, -0.6, 1.5), ('lat',))}
        for nm, (pa, src) in ends.items():
            e = from_arm(s, pa)
            for c in src:
                out.append(T(m, [cords[c], cords[c] * 0.5 + e * 0.5, e], 0.24, 0.24, C.nerve, 8))
    return out


def lumbosacral():
    m = TM
    out = []
    for s in SIDES:
        fem_e = from_leg(s, (0.3, -5.7, 1.0))
        sci_e = from_leg(s, (1.4, 6.2, 0.0))
        lum = []
        for n in ('L2', 'L3', 'L4'):
            cc = LM.canal_centre(n)
            lum.append(np.array((s * 3.4, cc[1] - 1.0, cc[2] - 1.6)))
        j = np.array((s * 5.4, -1.4, 98.0))
        for r in lum:
            out.append(T(m, [r, (r + j) / 2, j], 0.22, 0.26, C.nerve, 7))
        out.append(T(m, [j, (s * 6.6, -2.8, 94.5), (s * 7.8, -4.8, 91.6), fem_e], 0.3, 0.3, C.nerve, 8))     # femoral
        out.append(T(m, [j + np.array([-s * 1.0, 0.8, 0]), (s * 4.4, -1.0, 92.0), (s * 4.8, -3.4, 88.6), (s * 5.2, -4.6, 86.8)],
                     0.18, 0.15, C.nerve, 6))                                                                  # obturator
        sj = np.array((s * 5.6, 1.6, 91.6))
        srcs = [np.array((s * 2.4, LM.SPINE['L4'][0] + 1.0, 99.4)), np.array((s * 2.6, LM.SPINE['L5'][0] + 1.2, 96.2))]
        for (y, z) in LM.SACRUM[:3]:
            srcs.append(np.array((s * 1.6, y - 1.4, z - 0.8)))
        for r in srcs:
            out.append(T(m, [r, (r + sj) / 2 + np.array([0, -0.4, 0]), sj], 0.26, 0.32, C.nerve, 7))
        out.append(T(m, [sj, (s * 7.0, 3.0, 91.6), sci_e], 0.55, 0.55, C.nerve, 10))                        # sciatic
    return out


def autonomic():
    m = TM
    out = []
    for s in SIDES:
        top = from_head((s * 2.4, 0.6, -8.4))
        if s < 0:
            ph = [(-2.4, 0.6, 155.0), (-3.4, -1.4, 146.0), (-3.6, -2.8, 136.0), (-4.2, -3.4, 128.0), (-4.6, -3.2, 121.5)]
            vg = [top, (-2.8, -0.2, 151.0), (-3.2, -0.6, 141.0), (-2.2, 1.4, 130.0), (-0.8, 1.8, 120.0), (1.0, -1.6, 113.2)]
        else:
            ph = [(2.4, 0.6, 155.0), (3.4, -1.2, 146.0), (3.6, -2.6, 138.0), (6.8, -4.4, 127.0), (7.0, -4.6, 119.6)]
            vg = [top, (2.8, -0.2, 151.0), (2.8, -1.8, 140.0), (3.4, -0.4, 135.4), (2.0, 1.2, 128.0), (1.9, 0.4, 118.0),
                  (2.6, -2.0, 113.0)]
            out.append(T(m, [(3.3, -0.6, 136.0), (3.0, 0.4, 134.4), (1.4, -0.6, 136.0), (0.9, -1.6, 144.0), (0.8, -2.0, 149.0)],
                         0.1, 0.09, C.nerve, 6))                                                              # recurrent laryngeal
        out.append(T(m, ph, 0.13, 0.11, C.nerve, 6))
        out.append(T(m, vg, 0.18, 0.15, C.nerve, 7))
    return out


# =================================================================== registry
def parts():
    P = [Part('Torso_Arteries_Thorax', GM, tubes=arteries_thorax, target=19000, cat='vessel', base=(0.72, 0.1, 0.09),
              info='Crosse et aorte thoracique, tronc brachio-céphalique, carotides, subclavières, vertébrales, thoraciques internes'),
         Part('Torso_Arteries_Abdomen', TM, tubes=arteries_abdomen, target=19000, cat='vessel', base=(0.72, 0.1, 0.09),
              info='Aorte abdominale, tronc cœliaque, mésentériques, rénales, gonadiques, iliaques'),
         Part('Torso_Veins_Thorax', GM, tubes=veins_thorax, target=19000, cat='vessel', base=(0.2, 0.25, 0.55),
              info='Veine cave supérieure, troncs brachio-céphaliques, jugulaires internes, subclavières, azygos'),
         Part('Torso_Veins_Abdomen', TM, tubes=veins_abdomen, target=19000, cat='vessel', base=(0.2, 0.25, 0.55),
              info='Veine cave inférieure, veines hépatiques, rénales, système porte, veines iliaques'),
         Part('Torso_SpinalCord', TM, tubes=spinal_cord, target=19000, cat='nerve', base=(0.93, 0.88, 0.78),
              info='Moelle épinière (renflements, cône terminal), queue de cheval, filum terminal'),
         Part('Torso_SpinalNerves', TM, tubes=spinal_roots, target=19000, cat='nerve', base=(0.96, 0.88, 0.55),
              info='Racines des nerfs spinaux avec ganglions spinaux, chaînes sympathiques'),
         Part('Torso_BrachialPlexus', GM, tubes=brachial_plexus, target=19000, cat='nerve', base=(0.96, 0.88, 0.55),
              info='Plexus brachial (racines, troncs, faisceaux) vers les nerfs du bras'),
         Part('Torso_Nerves_Lumbosacral', TM, tubes=lumbosacral, target=19000, cat='nerve', base=(0.96, 0.88, 0.55),
              info='Plexus lombaire et sacré : nerfs fémoraux, obturateurs, sciatiques'),
         Part('Torso_Nerves_Autonomic', TM, tubes=autonomic, target=19000, cat='nerve', base=(0.96, 0.88, 0.55),
              info='Nerfs phréniques et vagues (pneumogastriques), nerf laryngé récurrent')]
    for s, t, side in ((1, 'L', 'gauche'), (-1, 'R', 'droit')):
        P.append(Part(f'Torso_Intercostals_{t}', TM, tubes=lambda s=s: intercostals(s), target=19000, cat='vessel',
                      base=(0.7, 0.2, 0.2), info=f'Pédicules intercostaux {side}s (veine, artère, nerf sous chaque côte)'))
    return P
