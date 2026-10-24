"""Créature réaliste en peau : anatomie émaciée faite de formes simples (os, côtes, colonne, omoplates, muscles
maigres, articulations) fusionnées par grilles SDF dans Blender (peau continue, congés lisses). Repère Roblox.

Chaque pièce du rig reçoit ses formes, avec un recouvrement aux articulations (les formes débordent dans la pièce
voisine). Attributs : Col (teinte régionale de la peau, sRGB), Mat (0 peau, 1 peau du crâne, 2 dent, 3 gencive,
4 ongle/griffe)."""
import math
import zlib
import numpy as np
from mon_common import TAU, unit, rot, catmull, resample, seg_frame, smoothstep, arclen, snoise
from mon_skel import *
import mon_gen as G
from mon_gen import P, ST

K_SKIN, K_HEAD, K_TOOTH, K_GUM, K_NAIL = 0, 1, 2, 3, 4

SKIN = np.array([0.62, 0.55, 0.5])
SKIN_PALE = np.array([0.67, 0.61, 0.57])
SKIN_RED = np.array([0.63, 0.5, 0.46])
SKIN_BONE = np.array([0.69, 0.64, 0.57])
SKIN_DARK = np.array([0.5, 0.44, 0.41])
NAIL = np.array([0.16, 0.13, 0.11])
NAIL_TIP = np.array([0.42, 0.37, 0.30])
TOOTH = np.array([0.66, 0.59, 0.43])
GUMC = np.array([0.36, 0.08, 0.07])
SEED = 4242
EX, EY, EZ = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])


def RNG(name):
    return np.random.default_rng((zlib.crc32(name.encode()) + SEED) % (2 ** 32))


def cap(piece, pts, r, col=SKIN, kind=K_SKIN, ds=0.025, smooth=True):
    """Capsule (os, muscle, tendon) le long de pts ; r scalaire ou une valeur par point de contrôle."""
    pts = np.asarray(pts, float)
    path = catmull(pts, 12) if (len(pts) > 2 and smooth) else pts
    path = resample(path, ds)
    rr = np.atleast_1d(np.asarray(r, float))
    if len(rr) == 1:
        R = np.full(len(path), rr[0])
    else:
        sc = arclen(pts)
        sp = arclen(path)
        R = np.interp(sp / sp[-1], sc / sc[-1], rr)
    piece.fuse.append(ST(path, R, col, kind))


def blob(piece, c, axes, radii, col=SKIN, kind=K_SKIN, nu=28, nv=18):
    v, f = G.ellipsoid(np.asarray(c, float), [unit(a) for a in axes], radii, nu, nv)
    piece.fuse_meshes.append((v, f, np.broadcast_to(np.asarray(col, float), (len(v), 3)).copy(), kind,
                              np.broadcast_to(unit(axes[2]), (len(v), 3)).copy()))


def frame_of(A, B, fwd=(0.0, 0.0, -1.0)):
    T, F, X = seg_frame(A, B, fwd)
    return T, F, X


def gauss(u, c, w):
    return np.exp(-((u - c) / w) ** 2)


def dirw(th, center, power=1.5):
    """Poids angulaire autour de la direction center (radians) : 1 en face, 0 à l'opposé."""
    return np.clip(np.cos(th - center), 0, 1) ** power


def loft(A, B, prof, u0=-0.1, u1=1.1, own=(0.0, 1.0), inset=0.965, fwd=(0.0, 0.0, -1.0), n_th=56, step=0.02, bend=None,
         end_taper=0.5):
    """Surface fermée balayée le long de A -> B ; prof(u, th) = rayon (th = 0 côté X, pi/2 devant).
    Hors de [own] (débord dans la pièce voisine), la section rentre (inset) et s'amenuise vers le bout."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    L = float(np.linalg.norm(B - A))
    m = max(10, int((u1 - u0) * L / step))
    us = np.linspace(u0, u1, m)
    th = np.linspace(0, TAU, n_th, endpoint=False)
    rings = []
    for u in us:
        uc = float(np.clip(u, 0.0, 1.0))
        c = A + (B - A) * u
        if bend is not None:
            c = c + bend(uc)
        r = prof(np.full(n_th, uc), th)
        k = 1.0
        if u < own[0]:
            e = (own[0] - u) / max(own[0] - u0, 1e-6)
            k = (1.0 - (1.0 - inset) * smoothstep(e * 4)) * (1 - end_taper * smoothstep((e - 0.4) / 0.6))
        elif u > own[1]:
            e = (u - own[1]) / max(u1 - own[1], 1e-6)
            k = (1.0 - (1.0 - inset) * smoothstep(e * 4)) * (1 - end_taper * smoothstep((e - 0.4) / 0.6))
        rings.append(c[None] + (k * r)[:, None] * (np.cos(th)[:, None] * X[None] + np.sin(th)[:, None] * F[None]))
    V = np.vstack(rings)
    F_ = []
    for i in range(m - 1):
        for j in range(n_th):
            j2 = (j + 1) % n_th
            a0, a1, b0, b1 = i * n_th + j, i * n_th + j2, (i + 1) * n_th + j, (i + 1) * n_th + j2
            F_ += [(a0, a1, b1), (a0, b1, b0)]
    c0, c1 = len(V), len(V) + 1
    V = np.vstack([V, rings[0].mean(0), rings[-1].mean(0)])
    for j in range(n_th):
        j2 = (j + 1) % n_th
        F_.append((c0, j2, j))
        F_.append((c1, (m - 1) * n_th + j, (m - 1) * n_th + j2))
    F_ = np.array(F_, np.int64)
    cen = np.vstack([np.repeat([r.mean(0) for r in rings], n_th, axis=0), rings[0].mean(0)[None], rings[-1].mean(0)[None]])
    e = np.cross(V[F_[:, 1]] - V[F_[:, 0]], V[F_[:, 2]] - V[F_[:, 0]])
    if np.einsum('ij,ij->i', e, V[F_[:, 0]] - cen[F_[:, 0]]).sum() < 0:
        F_ = F_[:, ::-1].copy()
    return V, F_, T


def add_loft(piece, A, B, prof, col=SKIN, **kw):
    V, F_, T = loft(A, B, prof, **kw)
    piece.fuse_meshes.append((V, F_, np.tile(col, (len(V), 1)), K_SKIN, np.tile(T, (len(V), 1))))


# ----------------------------------------------------------------------------------------------------------------
# jambes


def setp(pc, voxel=0.011, fillet=6, close=0.05):
    pc.voxel, pc.fillet, pc.close = voxel, fillet, close


def build_legs():
    for side, s in (('R', 1.0), ('L', -1.0)):
        hip, knee, ankle = J['Hip_' + side], J['Knee_' + side], J['Ankle_' + side]
        th, sh, ft = P('Thigh_' + side), P('Shin_' + side), P('Foot_' + side)
        setp(th, 0.011, 3, 0.02); setp(sh, 0.01, 3, 0.02); setp(ft, 0.008, 4, 0.025)
        T, F, X = frame_of(hip, knee)
        out_th = 0.0 if s > 0 else math.pi                  # côté extérieur (X = droite du monstre)
        in_th = math.pi - out_th

        def pth(u, t):
            r = 0.34 - 0.13 * u
            r = r + 0.1 * gauss(u, 0.38, 0.28) * dirw(t, math.pi / 2, 1.4)                     # quadriceps
            r = r + 0.04 * gauss(u, 0.84, 0.08) * dirw(t, math.pi / 2 + (0.6 if s > 0 else -0.6) * -1, 2)   # vaste interne
            r = r + 0.055 * gauss(u, 0.45, 0.3) * dirw(t, -math.pi / 2, 1.5)                   # ischio-jambiers
            r = r + 0.06 * gauss(u, 0.15, 0.2) * dirw(t, in_th, 2)                             # adducteurs
            r = r - 0.02 * gauss(u, 0.55, 0.4) * dirw(t, out_th, 3)                            # bandelette (plat)
            r = r + 0.035 * gauss(u, 0.99, 0.07) * np.abs(np.cos(t)) ** 2                      # condyles
            return r
        add_loft(th, hip + EY * 0.12, knee, pth, u0=-0.12, u1=1.03, own=(0.0, 1.0),
                 bend=lambda u: F * 0.06 * math.sin(math.pi * u))
        blob(th, hip + X * s * 0.16 - T * 0.12, (X, T, F), (0.1, 0.15, 0.12), SKIN_BONE)            # grand trochanter
        T2, F2, X2 = frame_of(knee, ankle)
        out2 = 0.0 if s > 0 else math.pi
        in2 = math.pi - out2

        def psh(u, t):
            r = 0.19 - 0.075 * u
            r = r + 0.11 * gauss(u, 0.24, 0.15) * dirw(t, -math.pi / 2 + (0.35 if s > 0 else -0.35), 1.3)    # mollet
            r = r + 0.03 * gauss(u, 0.45, 0.3) * dirw(t, out2 - 0.3 * s, 2)                    # péroniers
            r = r - 0.022 * dirw(t, math.pi / 2 + 0.5 * (1 if s < 0 else -1), 4) * (1 - u * 0.3)   # face plate du tibia
            r = r + 0.03 * gauss(u, 0.02, 0.06)                                               # plateau tibial
            r = r + 0.022 * gauss(u, 0.99, 0.05) * np.abs(np.cos(t)) ** 3                      # malléoles
            return r
        add_loft(sh, knee, ankle, psh, u0=-0.04, u1=1.02, own=(0.02, 1.0))
        blob(sh, knee + F2 * 0.15 + T2 * 0.05, (X2, T2, F2), (0.1, 0.11, 0.05), SKIN_BONE)        # rotule
        blob(sh, knee + T2 * 0.0 + F2 * 0.01, (X2, T2, F2), (0.24, 0.18, 0.22), SKIN_RED)          # bulbe du genou
        cap(sh, [knee + F2 * 0.17 + T2 * 0.12, knee + F2 * 0.165 + T2 * 0.24, knee + F2 * 0.15 + T2 * 0.33],
            [0.04, 0.036, 0.034], SKIN)                                                         # tendon rotulien
        cap(sh, [knee + T2 * 0.16 + F2 * 0.135, knee + (ankle - knee) * 0.5 + F2 * 0.105, ankle - T2 * 0.18 + F2 * 0.08],
            [0.03, 0.026, 0.022], SKIN_BONE)                                                    # crête tibiale
        build_foot(ft, side, s, ankle)


def build_foot(ft, side, s, ankle):
    fwd = unit(np.array([s * 0.1, 0, -1.0]))
    heel = np.array([ankle[0], 0.16, ankle[2] + 0.2])
    ball = np.array([ankle[0], 0.1, ankle[2]]) + fwd * 0.82 + np.array([s * 0.02, 0, 0])

    def foot_w(u):
        return 0.1 + 0.11 * smoothstep(u / 0.85)                    # étroit à la cheville, s'élargit vers l'avant

    def foot_top(u):
        return 0.06 + 0.38 * (1 - u) ** 2.2                         # cou-de-pied : pente raide puis douce vers les orteils

    def pfoot(u, t):
        w = foot_w(u)
        ct, st = np.cos(t), np.sin(t)
        h = np.where(st > 0, foot_top(u), 0.1 - 0.03 * u)
        return 1.0 / np.sqrt((ct / w) ** 2 + (st / h) ** 2)
    # le pied : de sous la cheville jusqu'aux métatarses (axe presque horizontal) ; repère "devant" = vers le haut
    fa, fb = heel + EY * 0.02 - fwd * 0.05, ball
    f_bend = lambda u: EY * 0.04 * math.sin(math.pi * u)
    add_loft(ft, fa, fb, pfoot, u0=-0.05, u1=1.08, own=(-1, 2), fwd=(0, 1.0, 0), bend=f_bend)
    fT, fF, fX = seg_frame(fa, fb, (0, 1.0, 0))

    def foot_surf(u, off):
        """Point sur le dos du pied : u le long du pied, off décalage latéral (studs)."""
        w = foot_w(u)
        h = foot_top(u)
        x = float(np.clip(off / w, -0.95, 0.95))
        return fa + (fb - fa) * u + f_bend(u) + fX * off + fF * h * math.sqrt(1 - x * x)
    blob(ft, ankle + EY * 0.0, (EX, EY, EZ), (0.15, 0.17, 0.15), SKIN_BONE)                     # cheville (recouvrement)
    cap(ft, [ankle + EY * 0.1, (ankle + heel) / 2 + fwd * 0.08, heel + fwd * 0.15], [0.12, 0.13, 0.12])
    blob(ft, heel, (EX, EY, EZ), (0.12, 0.13, 0.15), SKIN_BONE)                                # talon
    cap(ft, [ankle - EY * 0.2 + EZ * 0.13, heel - EY * 0.01 + EZ * 0.1], [0.05, 0.055])         # tendon d'Achille
    for k in (-1, 1):
        blob(ft, ankle + EX * k * 0.09 - EY * 0.02, (EX, EY, EZ), (0.05, 0.06, 0.05), SKIN_BONE)  # malléoles
    spread = [-0.2, -0.1, 0.0, 0.1, 0.18]
    lengths = [0.34, 0.38, 0.34, 0.3, 0.26]
    for i, off in enumerate(spread):
        o = off * s
        d = unit(fwd + np.array([o * 0.9, 0, 0]))
        base = ball + np.array([o * 1.1, 0.0, 0]) - fwd * 0.12
        blob(ft, base + fwd * 0.06, (EX, EY, EZ), (0.06, 0.055, 0.07), SKIN_BONE)                  # tête du métatarse
        p1 = base + d * lengths[i] * 0.55 + EY * 0.03
        p2 = base + d * lengths[i] - EY * 0.05
        cap(ft, [base, p1, p2], [0.052, 0.045, 0.036])
        blob(ft, p1, (EX, EY, EZ), (0.046, 0.044, 0.05), SKIN_BONE)
        dn = unit(d - EY * 0.9)
        G.claw(ft, p2 - d * 0.01, dn, unit(np.cross(EY, d)), RNG('toe%s%d' % (side, i)),
               length=0.15 + 0.03 * (2 - abs(i - 2)), r0=0.033, curl=0.9, m=10, sides=8, kind_claw=K_NAIL)
    for i in range(4):                                                   # tendons extenseurs, à fleur de peau
        o = spread[i + 1] * s
        sx = 1.0 if fX @ EX > 0 else -1.0
        pts = [foot_surf(u, sx * o * (0.25 + 0.75 * u)) for u in np.linspace(0.12, 0.92, 6)]
        cap(ft, pts, [0.014, 0.014, 0.013, 0.012, 0.012, 0.011], SKIN_BONE)


# ----------------------------------------------------------------------------------------------------------------
# tronc : une suite d'ellipsoïdes le long de la colonne (chair continue), os affleurants (côtes, crêtes, omoplates)


def trunk_axis():
    pts = np.array([J['Pelvis'] + [0, -0.45, 0.06], J['Pelvis'] + [0, 0.1, 0.05], J['SpineLow'] + [0, 0.1, 0.06],
                    J['SpineMid'] + [0, 0.0, 0.08], J['SpineHigh'] + [0, 0.05, 0.12], J['NeckBase'] + [0, -0.05, 0.22]])
    return resample(catmull(pts, 12), 0.01)


TRUNK = [  # (abscisse 0..1 le long du tronc, demi-largeur, demi-profondeur)
    (0.00, 0.42, 0.34), (0.08, 0.56, 0.40), (0.17, 0.6, 0.42), (0.26, 0.54, 0.38), (0.34, 0.5, 0.36),
    (0.42, 0.52, 0.37), (0.50, 0.62, 0.43), (0.60, 0.72, 0.48), (0.70, 0.79, 0.5), (0.78, 0.87, 0.5),
    (0.85, 0.9, 0.47), (0.91, 0.76, 0.42), (0.96, 0.5, 0.34), (1.00, 0.28, 0.24)]


def trunk_frame(u):
    ax = trunk_axis()
    sl = arclen(ax)
    i = int(np.clip(np.searchsorted(sl, u * sl[-1]), 1, len(ax) - 1))
    c = ax[i]
    t = unit(ax[min(i + 1, len(ax) - 1)] - ax[i - 1])
    back = unit(EZ - t * (EZ @ t))
    return c, t, back


def trunk_dims(u):
    us = np.array([d[0] for d in TRUNK])
    return np.interp(u, us, [d[1] for d in TRUNK]), np.interp(u, us, [d[2] for d in TRUNK])


def trunk_owner(c):
    y = c[1]
    if y < J['SpineLow'][1]:
        return 'Pelvis'
    if y < J['SpineMid'][1]:
        return 'Abdomen'
    if y < J['SpineHigh'][1]:
        return 'Chest'
    return 'UpperChest'


TRUNK_REGIONS = None


def trunk_regions():
    """Abscisses (0..1) des limites entre pièces le long du tronc."""
    ax = trunk_axis()
    sl = arclen(ax) / arclen(ax)[-1]
    ys = ax[:, 1]
    cut = lambda y: float(np.interp(y, ys, sl))
    return {'Pelvis': (0.0, cut(J['SpineLow'][1])), 'Abdomen': (cut(J['SpineLow'][1]), cut(J['SpineMid'][1])),
            'Chest': (cut(J['SpineMid'][1]), cut(J['SpineHigh'][1])), 'UpperChest': (cut(J['SpineHigh'][1]), 1.0)}


RIB_ZONE = (0.46, 0.87)


def trunk_section(u, a):
    """Section du tronc à l'abscisse u, angle a (0 = droite du monstre, +pi/2 = dos, -pi/2 = ventre) : coefficients
    (cx, cb) tels que point = centre + cx * side + cb * back. Dos un peu aplati et creux de la colonne, ventre creusé
    sous les côtes (créature affamée), chair un peu rentrée sur la cage thoracique (les côtes ressortent)."""
    w, d = trunk_dims(u)
    a = np.asarray(a, float)
    ca, sa = np.cos(a), np.sin(a)
    dd = d * np.where(sa > 0, 0.92, 1.0)
    groove = 1.0 - 0.05 * np.exp(-((((a - math.pi / 2) + math.pi) % TAU - math.pi) / 0.22) ** 2)
    front = np.clip(-sa, 0, 1)
    hollow = 1.0 - 0.095 * gauss(u, 0.41, 0.075) * front ** 1.3
    ribz = smoothstep((u - RIB_ZONE[0]) / 0.05) * (1 - smoothstep((u - RIB_ZONE[1] + 0.03) / 0.05))
    shrink = 1.0 - 0.016 * ribz * (1 - np.clip(sa, 0, 1) ** 2)
    return w * ca * shrink, dd * sa * groove * hollow * shrink


def trunk_pt(u, a, k=1.0):
    """Point de la surface du tronc (même forme que le loft), k < 1 sous la peau."""
    c, t, back = trunk_frame(u)
    side = unit(np.cross(t, back))
    cx, cb = trunk_section(u, a)
    return c + side * cx * k + back * cb * k


def trunk_loft(u0, u1, own0, own1, nring=72, step=0.02, inset=0.97):
    """Surface fermée balayée le long du tronc entre u0 et u1 ; hors de [own0, own1] la section rentre (inset)."""
    ax = trunk_axis()
    L = arclen(ax)[-1]
    m = max(8, int((u1 - u0) * L / step))
    us = np.linspace(u0, u1, m)
    a = np.linspace(0, TAU, nring, endpoint=False)
    rings = []
    for u in us:
        c, t, back = trunk_frame(u)
        side = unit(np.cross(t, back))
        k = 1.0
        if u < own0:
            k = 1.0 - (1.0 - inset) * smoothstep((own0 - u) / 0.03)
        elif u > own1:
            k = 1.0 - (1.0 - inset) * smoothstep((u - own1) / 0.03)
        cx, cb = trunk_section(u, a)
        ring = c[None] + (k * cx)[:, None] * side[None] + (k * cb)[:, None] * back[None]
        rings.append(ring)
    V = np.vstack(rings)
    F = []
    for i in range(m - 1):
        for j in range(nring):
            j2 = (j + 1) % nring
            a0, a1, b0, b1 = i * nring + j, i * nring + j2, (i + 1) * nring + j, (i + 1) * nring + j2
            F += [(a0, a1, b1), (a0, b1, b0)]
    c0 = len(V)
    c1 = c0 + 1
    V = np.vstack([V, rings[0].mean(0), rings[-1].mean(0)])
    for j in range(nring):
        j2 = (j + 1) % nring
        F.append((c0, j2, j))
        F.append((c1, (m - 1) * nring + j, (m - 1) * nring + j2))
    F = np.array(F, np.int64)
    cen = np.vstack([np.repeat([r.mean(0) for r in rings], nring, axis=0), rings[0].mean(0)[None], rings[-1].mean(0)[None]])
    e = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.einsum('ij,ij->i', e, V[F[:, 0]] - cen[F[:, 0]]).sum() < 0:
        F = F[:, ::-1].copy()
    return V, F


def trunk_surface(u, theta, k=0.97):
    """Point de la surface du tronc : u le long du tronc, theta autour (0 = droite du monstre, +pi/2 = devant,
    -pi/2 = dos) ; k < 1 enfonce le point sous la peau."""
    c, t, back = trunk_frame(u)
    w, d = trunk_dims(u)
    side = unit(np.cross(t, back))
    if side[0] < 0:
        side = -side
    front = -back
    return c + side * w * math.cos(theta) * k + front * d * math.sin(theta) * k


def build_trunk():
    """Chair du tronc : une surface balayée par pièce (débord rentré chez les voisines : pas de surfaces confondues)."""
    reg = trunk_regions()
    for name, (o0, o1) in reg.items():
        u0 = max(0.0, o0 - 0.08)
        u1 = min(1.0, o1 + 0.08)
        V, F = trunk_loft(u0, u1, o0 if o0 > 0 else -1, o1 if o1 < 1 else 2)
        P(name).fuse_meshes.append((V, F, np.tile(SKIN, (len(V), 1)), K_SKIN, np.tile(EY, (len(V), 1))))
        setp(P(name), 0.011, 5, 0.06)


def _rib_path(u_back, phi_end, drop, s, n=26):
    """Côte : part de la colonne (dos) et fait le tour du flanc vers l'avant en descendant ; phi = angle depuis le
    flanc (-pi/2 dos, +pi/2 ventre) ; s = +1 côté droit du monstre."""
    phis = np.linspace(-1.3, phi_end, n)
    e = (phis + 1.3) / (phi_end + 1.3)
    out = []
    ax_len = arclen(trunk_axis())[-1]
    for ph, ee in zip(phis, e):
        u = u_back - drop * ee ** 1.15 / ax_len
        a = -ph if s > 0 else math.pi + ph                 # angle de trunk_section (dos = +pi/2)
        out.append(trunk_pt(u, a, 1.0))
    return np.array(out)


def build_ribs():
    """Côtes qui affleurent sous la peau (de la colonne au sternum), rebord costal, sternum, appendice xiphoïde."""
    n = 10
    ends = {1: [], -1: []}
    rng = RNG('ribs')
    for i in range(n):                                     # de haut en bas
        u_back0 = 0.86 - 0.40 * i / (n - 1)
        phi_end = [1.3, 1.32, 1.34, 1.35, 1.35, 1.33, 1.12, 0.86, 0.58, 0.12][i]
        drop = 0.3 + 0.12 * i / (n - 1)
        r = 0.86 * np.array([0.032, 0.036, 0.038, 0.04, 0.04, 0.04, 0.039, 0.037, 0.034, 0.03])[i]
        for s in (1, -1):
            u_back = u_back0 + rng.uniform(-0.006, 0.006)
            pts = resample(catmull(_rib_path(u_back, phi_end, drop * rng.uniform(0.94, 1.06), s), 6), 0.02)
            m = len(pts)
            rr = np.full(m, r * rng.uniform(0.92, 1.08))
            rr[:4] *= np.linspace(0.7, 1.0, 4)            # contre la colonne : rentrée sous les érecteurs
            k_f = max(5, m // 3)                           # vers l'avant : plus fines (sous la chair)
            rr[-k_f:] *= np.linspace(1.0, 0.62, k_f)
            # chaque morceau va à la pièce du tronc où il se trouve (recouvrement : on coupe en tronçons)
            seg = 10
            for k0 in range(0, m - 1, seg):
                sl = slice(k0, min(m, k0 + seg + 2))
                q = pts[sl]
                P(trunk_owner(q[len(q) // 2])).fuse.append(ST(q, rr[sl], SKIN_BONE, K_SKIN))
            ends[s].append(pts[-1])
    # rebord costal : de l'appendice xiphoïde le long des bouts des côtes 7 à 10
    xu = 0.86 - 0.40 * 5 / 9 - 0.42 / arclen(trunk_axis())[-1]
    xiph = trunk_pt(xu, -math.pi / 2, 1.0)
    for s in (1, -1):
        pts = np.array([xiph] + [ends[s][i] for i in (6, 7, 8, 9)])
        pts = resample(catmull(pts, 10), 0.02)
        rr = np.linspace(0.024, 0.03, len(pts))
        P(trunk_owner(pts[len(pts) // 2])).fuse.append(ST(pts, rr, SKIN_BONE, K_SKIN))
    # sternum : plaque plate (ellipsoïdes aplatis) de la fourchette sternale à l'appendice xiphoïde
    for u in np.linspace(xu + 0.01, 0.9, 9):
        c, t, back = trunk_frame(u)
        side = unit(np.cross(t, back))
        q = trunk_pt(u, -math.pi / 2, 1.0)
        wdt = 0.075 if u > 0.84 else 0.06
        blob(P(trunk_owner(q)), q + back * 0.012, (side, t, -back), (wdt, 0.07, 0.03), SKIN_BONE, nu=18, nv=10)


def spine_pts():
    ax = trunk_axis()
    out = []
    n = len(ax)
    for k in range(0, n, max(1, n // 40)):
        u = k / (n - 1)
        out.append(trunk_pt(u, math.pi / 2, 1.0))
    pts = np.array(out + [J['NeckBase'] + np.array([0, 0.12, 0.32]), J['HeadJoint'] + np.array([0, 0.03, 0.22])])
    return resample(catmull(pts, 6), 0.01)


def owner_y(q):
    y = q[1]
    if y > J['NeckBase'][1] - 0.1 and q[2] < J['NeckBase'][2] + 0.5:
        return 'Neck'
    return trunk_owner(q)


def build_spine():
    """Vertèbres saillantes sous la peau du dos voûté."""
    sp = spine_pts()
    sl = arclen(sp)
    T = np.gradient(sp, axis=0)
    T = T / np.linalg.norm(T, axis=1, keepdims=True)
    s_at = 0.1
    while s_at < sl[-1] - 0.12:
        i = int(np.searchsorted(sl, s_at))
        q, t = sp[i], T[i]
        back = unit(np.array([0, 0.2, 1.0]) - t * (np.array([0, 0.2, 1.0]) @ t))
        side = unit(np.cross(t, back))
        pc = P(owner_y(q))
        hump = math.exp(-((s_at / sl[-1] - 0.72) / 0.22) ** 2)
        size = 0.04 + 0.022 * hump
        blob(pc, q + back * 0.004, (side, t, back), (size * 1.25, size * 0.9, size), SKIN_BONE, nu=16, nv=10)
        s_at += 0.15


def build_pelvis():
    p = P('Pelvis')
    c = J['Pelvis']
    for side, s in (('R', 1.0), ('L', -1.0)):
        crest = [c + [s * 0.18, 0.28, 0.48], c + [s * 0.52, 0.34, 0.22], c + [s * 0.6, 0.2, -0.08],
                 c + [s * 0.46, 0.04, -0.26]]
        cap(p, [q * np.array([0.975, 1, 0.975]) + c * np.array([0.025, 0, 0.025]) for q in crest], [0.045, 0.05, 0.05, 0.045], SKIN_BONE)
        blob(p, c + [s * 0.46, 0.05, -0.26], (EX, EY, EZ), (0.075, 0.07, 0.075), SKIN_BONE)
        blob(p, c + [s * 0.21, -0.26, 0.26], (EX, EY, EZ), (0.22, 0.26, 0.12))
        blob(p, J['Hip_' + side] + [-s * 0.02, 0.1, 0.0], (EX, EY, EZ), (0.21, 0.23, 0.21))
    blob(p, c + [0, 0.02, 0.44], (EX, EY, EZ), (0.15, 0.26, 0.05), SKIN)
    blob(p, c + [0, -0.3, -0.05], (EX, EY, EZ), (0.17, 0.1, 0.12))


def build_abdomen():
    ab = P('Abdomen')
    A, B = J['SpineLow'], J['SpineMid']
    reg = trunk_regions()
    for k in (-1, 1):
        th = -math.pi / 2 + k * 0.28
        pts = [trunk_surface(u, th, 0.9) for u in np.linspace(reg['Abdomen'][0] - 0.03, reg['Abdomen'][1] + 0.03, 5)]
        cap(ab, pts, [0.08, 0.09, 0.09, 0.08, 0.07])


def build_chest():
    ch = P('Chest')
    A, B = J['SpineMid'], J['SpineHigh']
    T, F, X = frame_of(A, B)
    reg = trunk_regions()
    for k in (-1, 1):
        th = -math.pi / 2 + k * 0.26
        pts = [trunk_surface(u, th, 0.9) for u in np.linspace(reg['Chest'][0] - 0.03, reg['Chest'][1] + 0.03, 5)]
        cap(ch, pts, [0.07, 0.08, 0.08, 0.075, 0.07])                                           # érecteurs


def build_upperchest():
    p = P('UpperChest')
    A, B = J['SpineHigh'], J['NeckBase']
    T, F, X = frame_of(A, B)
    for side, s in (('R', 1.0), ('L', -1.0)):
        sh = J['Shoulder_' + side]
        acro = sh + np.array([-s * 0.08, 0.17, 0.06])
        u_cl = 0.9
        th0, th1 = (math.pi / 2 - 0.25, 0.35) if s > 0 else (math.pi / 2 + 0.25, math.pi - 0.35)
        pts = [trunk_surface(u_cl, th, 1.0) for th in np.linspace(th0, th1, 6)] + [acro - EX * s * 0.04]
        cap(p, pts, [0.042, 0.046, 0.046, 0.045, 0.045, 0.048, 0.05], SKIN_BONE)                # clavicule
        blob(p, acro, (EX, EY, EZ), (0.13, 0.09, 0.14), SKIN_BONE)
        cap(p, [B + EX * s * 0.08 + EZ * 0.22 - EY * 0.08, (B + acro) / 2 + EY * 0.15 + EZ * 0.12, acro + EZ * 0.02],
            [0.22, 0.19, 0.12])                                                                  # trapèze
        cap(p, [A + EX * s * 0.45 + EY * 0.05 - EZ * 0.05, sh - EX * s * 0.08 + EY * 0.02], [0.26, 0.21])  # aisselle / grand pectoral
        # omoplate : plaque sur le dos (angle a de la section : dos = +pi/2), bord interne et épine saillants
        a_in = math.pi / 2 - s * 0.42
        a_out = math.pi / 2 - s * 0.95
        c_sc = trunk_pt(0.76, (a_in + a_out) / 2, 1.0)
        n_sc = unit(c_sc - trunk_pt(0.76, (a_in + a_out) / 2, 0.8))
        blob(p, c_sc - n_sc * 0.03, (unit(trunk_pt(0.76, a_out, 1.0) - trunk_pt(0.76, a_in, 1.0)),
                                     unit(trunk_pt(0.82, a_in, 1.0) - trunk_pt(0.7, a_in, 1.0)), n_sc),
             (0.24, 0.3, 0.055), SKIN)
        cap(p, [trunk_pt(u, a_in + s * 0.08 * (u - 0.66) / 0.2, 1.0) for u in (0.66, 0.72, 0.79, 0.85)],
            [0.03, 0.036, 0.036, 0.03], SKIN_BONE)                                                 # bord interne
        cap(p, [trunk_pt(0.81, a_in, 0.995), trunk_pt(0.83, (a_in + a_out) / 2, 0.995), acro + EZ * 0.02],
            [0.022, 0.027, 0.034], SKIN_BONE)                                                      # épine
        blob(p, sh + np.array([-s * 0.02, 0.04, 0]), (EX, EY, EZ), (0.2, 0.2, 0.2))                # épaule


def build_neck():
    p = P('Neck'); setp(p, 0.01, 6, 0.05)
    A = J['NeckBase'] + np.array([0, -0.08, 0.1])
    B = J['HeadJoint'] + FH * 0.1
    T, F, X = frame_of(A, B, fwd=(0, 1.0, 0))
    cap(p, [A - T * 0.2, (A + B) / 2 + F * 0.02, B + T * 0.1], [0.3, 0.23, 0.22])
    for k in (-1, 1):
        cap(p, [J['NeckBase'] + EX * k * 0.13 - EZ * 0.34 - EY * 0.14, (A + B) / 2 + EX * k * 0.15 - F * 0.12,
                J['HeadJoint'] + EX * k * 0.21 + UH * 0.1], [0.065, 0.06, 0.06])
    blob(p, (A + B) / 2 - F * 0.22, (X, T, F), (0.08, 0.1, 0.07), SKIN_BONE)


# ----------------------------------------------------------------------------------------------------------------
# bras, mains, doigts


def build_arms():
    for side, s in (('R', 1.0), ('L', -1.0)):
        sh, el, wr = J['Shoulder_' + side], J['Elbow_' + side], J['Wrist_' + side]
        up, fo = P('UpperArm_' + side), P('Forearm_' + side)
        setp(up, 0.01, 3, 0.02); setp(fo, 0.009, 3, 0.02)
        T, F, X = frame_of(sh, el)
        out_a = 0.0 if s > 0 else math.pi

        def pua(u, t):
            r = 0.17 - 0.04 * u
            r = r + 0.085 * gauss(u, 0.1, 0.16) * (0.55 + 0.45 * dirw(t, out_a, 1.0))           # deltoïde
            r = r + 0.06 * gauss(u, 0.52, 0.24) * dirw(t, math.pi / 2, 1.6)                    # biceps
            r = r + 0.065 * gauss(u, 0.42, 0.3) * dirw(t, -math.pi / 2, 1.6)                   # triceps
            r = r + 0.03 * gauss(u, 0.98, 0.07) * np.abs(np.cos(t)) ** 2                       # épicondyles
            return r
        add_loft(up, sh + EY * 0.1, el, pua, u0=-0.05, u1=1.03, own=(0.0, 1.0))
        T2, F2, X2 = frame_of(el, wr)
        out2 = 0.0 if s > 0 else math.pi

        def pfa(u, t):
            r = 0.15 - 0.07 * u
            r = r + 0.065 * gauss(u, 0.2, 0.2) * (0.6 + 0.4 * dirw(t, math.pi / 2 - 0.4 * s, 1.0))  # fléchisseurs
            r = r + 0.035 * gauss(u, 0.25, 0.22) * dirw(t, out2, 1.5)                          # extenseurs
            r = r * (1 - 0.25 * u * np.abs(np.sin(t)))                                        # poignet aplati
            r = r + 0.025 * gauss(u, 0.99, 0.05) * np.abs(np.cos(t)) ** 3                      # styloïdes
            return r
        add_loft(fo, el, wr, pfa, u0=-0.04, u1=1.02, own=(0.02, 1.0))
        blob(fo, el - F2 * 0.12 + T2 * 0.03, (X2, T2, F2), (0.075, 0.095, 0.075), SKIN_BONE)     # olécrane
        blob(fo, el + T2 * 0.0, (X2, T2, F2), (0.17, 0.13, 0.16), SKIN_RED)                       # bulbe du coude
        L2 = float(np.linalg.norm(wr - el))
        Np = HAND[side]['N']                                                                    # paume
        a_palm = math.atan2(float(Np @ F2), float(Np @ X2))
        for k, off in ((0, 0.25), (1, -0.15), (2, 0.05)):                                       # tendons du poignet
            ang = a_palm + off
            pts = []
            for u in np.linspace(0.5, 1.0, 5):
                rr = pfa(np.array([u]), np.array([ang]))[0]
                pts.append(el + (wr - el) * u + rr * 0.97 * (math.cos(ang) * X2 + math.sin(ang) * F2))
            cap(fo, pts, [0.012, 0.016, 0.017, 0.016, 0.014][:5] if k != 2 else [0.01, 0.013, 0.014, 0.013, 0.012], SKIN)
        cap(fo, [el - F2 * 0.1 + T2 * 0.1, el + (wr - el) * 0.55 - F2 * 0.075, wr - F2 * 0.05 - X2 * s * 0.04],
            [0.03, 0.025, 0.022], SKIN_BONE)                                                     # crête du cubitus
        build_hand(side, s)


def build_hand(side, s):
    h = HAND[side]
    D, Nn, Tt = h['D'], h['N'], h['T']
    wr, kn = h['wrist'], h['knuckles']
    hand = P('Hand_' + side); setp(hand, 0.008, 5, 0.04)
    blob(hand, wr + D * 0.03, (Tt, Nn, D), (0.13, 0.09, 0.12), SKIN_BONE)
    blob(hand, wr + D * 0.36 + Nn * 0.02, (Tt, Nn, D), (0.19, 0.055, 0.27))
    for name in FINGERS[:4]:
        a = h['fingers'][name]['segs'][0][0]
        st = wr + D * 0.1 + Tt * ((a - kn) @ Tt) * 0.5
        cap(hand, [st, (st + a) / 2 - Nn * 0.02, a - D * 0.02], [0.045, 0.04, 0.05], SKIN_BONE)
        cap(hand, [st - Nn * 0.045, a - Nn * 0.065 - D * 0.04], [0.018, 0.016], SKIN_BONE)
        blob(hand, a - D * 0.01 - Nn * 0.02, (Tt, Nn, D), (0.052, 0.048, 0.058), SKIN_RED)
    th1 = h['fingers']['Thumb']['segs'][0][0]
    blob(hand, (wr + th1) / 2 + Nn * 0.05 + Tt * 0.03, (Tt, Nn, D), (0.1, 0.08, 0.15))
    cap(hand, [wr + Tt * 0.06, th1], [0.05, 0.055], SKIN_BONE)
    for name in FINGERS:
        f = h['fingers'][name]
        segs, cax = f['segs'], f['axis']
        for j, (a, b, d) in enumerate(segs):
            part = P('%s%d_%s' % (name, j + 1, side))
            setp(part, 0.007, 5, 0.025)
            r0 = (0.058 if name != 'Thumb' else 0.064) - 0.009 * j
            up_f = unit(np.cross(d, cax))
            L = float(np.linalg.norm(b - a))
            cap(part, [a - d * 0.04, a + d * L * 0.3, a + d * L * 0.65, b + d * (0.03 if j < len(segs) - 1 else 0.0)],
                [r0 * 1.0, r0 * 0.84, r0 * 0.8, r0 * 0.9], SKIN)
            blob(part, a + up_f * r0 * 0.1, (cax, up_f, d), (r0 * 0.98, r0 * 0.9, r0 * 1.0), SKIN_RED, nu=16, nv=10)
            if j == len(segs) - 1:
                blob(part, b - d * 0.02, (cax, up_f, d), (r0 * 0.92, r0 * 0.88, r0 * 1.05), SKIN, nu=16, nv=10)
        last = P('%s%d_%s' % (name, len(segs), side))
        a, b, d = segs[-1]
        Lc = 0.56 if name in ('Middle', 'Ring') else (0.5 if name != 'Thumb' else 0.44)
        G.claw(last, b - d * 0.035, d, cax, RNG('claw' + name + side), length=Lc, r0=0.05, curl=0.75,
               kind_claw=K_NAIL)


# ----------------------------------------------------------------------------------------------------------------
# tête et mâchoire : crâne sans yeux recouvert de peau, gueule fendue, crocs fins

from mon_body import head_radius, lip_upper, sphere_dirs, sphere_faces, jaw_point, HM, _HS, JAW_R, head_tangents


def build_head():
    """Crâne sans yeux recouvert de peau (fusionné), gueule fendue au palais rouge sombre, crocs fins."""
    rng = RNG('head')
    head = P('Head'); head.voxel, head.fillet = 0.008, 4
    nlat, nlon = 90, 150
    dl = sphere_dirs(nlat, nlon)
    r = head_radius(dl)
    vloc = dl * r[:, None]
    lu = lip_upper(dl[:, 0], dl[:, 1])
    mouth = (dl[:, 2] < lu) & (dl[:, 0] > 0.05)
    depth = np.clip((lu - dl[:, 2]) / 0.25, 0, 1)
    soft = smoothstep(np.clip((dl[:, 0] - 0.05) / 0.2, 0, 1))
    k = (depth * soft)[:, None]
    palate = vloc * np.array([0.88, 0.8, 0.25]) + np.array([0.0, 0.0, -0.05 * _HS])
    vloc = np.where(mouth[:, None], vloc * (1 - k) + palate * k, vloc)
    V = HEAD_C + vloc @ HM.T
    gum_k = np.where(mouth, np.clip(depth * 3, 0, 1) * soft, 0.0)
    C = SKIN_PALE[None] * (1 - gum_k[:, None]) + GUMC[None] * gum_k[:, None]
    F = sphere_faces(nlat, nlon)
    e = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.einsum('ij,ij->i', e, V[F[:, 0]] - HEAD_C).sum() < 0:
        F = F[:, ::-1].copy()
    kinds = np.where(gum_k > 0.5, float(K_GUM), float(K_HEAD))
    head.fuse_meshes.append((V, F, C, kinds, head_tangents(V)))
    # nuque et base du crâne (recouvrement avec le cou)
    blob(head, J['HeadJoint'] + FH * 0.05 + UH * 0.06, (XH, FH, UH), (0.22, 0.24, 0.2), SKIN, kind=K_HEAD)
    # crocs du haut, fins, le long de la lèvre en U
    n_up = 26
    for kk in range(n_up):
        a = math.radians(-74 + 148 * (kk + rng.uniform(-0.3, 0.3)) / (n_up - 1))
        dfx = np.array([[math.cos(a), math.sin(a) * 0.95, 0.0]])
        dfx[0, 2] = lip_upper(dfx[0, 0] * 0.9, dfx[0, 1] * 0.9) + 0.02
        dd = unit(dfx)
        rr = head_radius(dd)[0] * 0.93
        pl = HEAD_C + (dd[0] * rr) @ HM.T
        front = math.cos(a) ** 2
        Lf = (0.07 + 0.17 * front * rng.uniform(0.7, 1.25)) * SCALE
        inward = -(FH * math.cos(a) + XH * math.sin(a))
        G.fang(head, pl - UH * 0.01, -UH + FH * 0.12 * math.cos(a), inward, rng, Lf, 0.016 + 0.01 * front)
    # gorge sombre
    G.knob(head, HEAD_C + FH * 0.1 * SCALE - UH * 0.22 * SCALE, (FH, XH, UH), np.array([0.42, 0.3, 0.16]) * SCALE, rng,
           color=GUMC * 0.6, fuse=False, nu=16, nv=10, noise=0.05, kind=K_GUM)
    build_jaw(rng)


def build_jaw(rng):
    jaw = P('Jaw'); jaw.voxel, jaw.fillet = 0.008, 3
    nl, nw = 48, 20
    ts = np.linspace(-1.0, 1.0, nl)
    ws = np.linspace(0.0, 1.0, nw)
    outer = np.array([[jaw_point(t, w) for t in ts] for w in ws])
    inner = np.array([[jaw_point(t, w * 0.85, 0.16) for t in ts] for w in ws])
    V = np.vstack([outer.reshape(-1, 3), inner.reshape(-1, 3)])
    no = nl * nw
    F = []
    for i in range(nw - 1):
        for j in range(nl - 1):
            a0, a1, b0, b1 = i * nl + j, i * nl + j + 1, (i + 1) * nl + j, (i + 1) * nl + j + 1
            F += [(a0, b1, a1), (a0, b0, b1)]
            F += [(no + a0, no + a1, no + b1), (no + a0, no + b1, no + b0)]
    for j in range(nl - 1):
        a0, a1 = j, j + 1
        F += [(a0, a1, no + a1), (a0, no + a1, no + a0)]
    for j in range(nl - 1):                                   # fond (menton) : fermer entre extérieur et intérieur
        a0, a1 = (nw - 1) * nl + j, (nw - 1) * nl + j + 1
        F += [(a0, no + a1, a1), (a0, no + a0, no + a1)]
    for i in range(nw - 1):
        for j in (0, nl - 1):
            a0, b0 = i * nl + j, (i + 1) * nl + j
            if j == 0:
                F += [(a0, no + a0, no + b0), (a0, no + b0, b0)]
            else:
                F += [(a0, no + b0, no + a0), (a0, b0, no + b0)]
    F = np.array(F, np.int64)
    C = np.vstack([np.tile(SKIN_PALE, (no, 1)), np.tile(GUMC, (no, 1))])
    kinds = np.concatenate([np.full(no, float(K_HEAD)), np.full(no, float(K_GUM))])
    jfh = JAW_R @ FH
    nrm = unit(V - jaw_point(0.0, 0.5, 0.3))
    tang = unit(jfh[None] - (nrm @ jfh)[:, None] * nrm + 1e-9)
    jaw.fuse_meshes.append((V, F, C, kinds, tang))
    n_lo = 22
    up_dir = JAW_R @ UH
    for kk in range(n_lo):
        t = -0.95 + 1.9 * (kk + rng.uniform(-0.3, 0.3)) / (n_lo - 1)
        pl = jaw_point(t, 0.02, 0.06)
        front = 1 - abs(t)
        Lf = (0.05 + 0.13 * front ** 1.5 * rng.uniform(0.7, 1.3)) * SCALE
        inward = -(jaw_point(t, 0.0) - jaw_point(0.0, 0.0, 0.5))
        G.fang(jaw, pl, up_dir + (JAW_R @ FH) * 0.08, inward, rng, Lf, 0.014 + 0.008 * front)


def build_all():
    G.PIECES.clear()
    build_legs()
    build_trunk()
    build_ribs()
    build_pelvis()
    build_abdomen()
    build_chest()
    build_upperchest()
    build_neck()
    build_spine()
    build_arms()
    build_head()
