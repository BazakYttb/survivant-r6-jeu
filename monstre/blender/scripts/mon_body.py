"""Corps du monstre : génération des brins et maillages de chaque pièce du rig (repère Roblox, studs)."""
import math
import zlib
import numpy as np
from mon_common import *
from mon_skel import *
import mon_gen as G
from mon_gen import P, ST, K_TENDON, K_SKULL, K_TOOTH, K_GUM, K_CLAW, K_SLIME, K_CORE

SEED = 1666
DENSITY = 1.0          # multiplicateur global du nombre de tendons


def RNG(name, k=0):
    return np.random.default_rng((zlib.crc32(name.encode()) + 7919 * k + SEED) % (2 ** 32))


def nd(n):
    return max(1, int(round(n * DENSITY)))


def ring_point(A, B, u, prof, th, fwd=(0.0, 0.0, -1.0), aspect=(1.0, 1.0), k=1.0):
    T, F, X = seg_frame(A, B, fwd)
    c = A + (B - A) * u
    r = prof(np.array([u]), np.array([th]))[0] * k
    d = aspect[0] * math.cos(th) * X + aspect[1] * math.sin(th) * F
    return c + r * d, unit(d)


def drips_on(piece, A, B, prof, rng, n, length=(0.4, 1.6), r0=(0.018, 0.045), u_range=(0.1, 0.95),
             th_pref=None, fwd=(0.0, 0.0, -1.0), aspect=(1.0, 1.0), skip=None, k=0.96, end_y=None):
    """n filaments qui pendent depuis la surface du segment A -> B."""
    for _ in range(n):
        u = rng.uniform(*u_range)
        th = rng.uniform(0, TAU) if th_pref is None else th_pref(rng)
        p0, d = ring_point(A, B, u, prof, th, fwd, aspect, k)
        G.drip(piece, p0, d, rng, rng.uniform(*length), rng.uniform(*r0), skip=skip)


def core_tendons(piece, A, B, prof, rng, n, rad, rf=(0.0, 0.4), ext=(0.1, 0.1), fwd=(0.0, 0.0, -1.0), twist=(-0.2, 0.2)):
    """Cœur sombre fusionné (grille SDF) : quelques gros tendons près de l'axe."""
    G.bundle(piece, A, B, n, prof, rng, rad=rad, rf=rf, ext=ext, twist=twist, partial=0.0, fwd=fwd,
             base=TAR_DEEP, free=False, bulge=0.5, end_converge=0.2, kind=K_CORE)


# ----------------------------------------------------------------------------------------------------------------
# jambes et pieds


def build_legs():
    for side, s in (('R', 1.0), ('L', -1.0)):
        rng = RNG('leg' + side)
        hip, knee, ankle = J['Hip_' + side], J['Knee_' + side], J['Ankle_' + side]
        thigh, shin, foot = P('Thigh_' + side), P('Shin_' + side), P('Foot_' + side)
        top = hip + np.array([-s * 0.05, 0.32, 0.0])
        Tt, Ft, Xt = seg_frame(top, knee)

        def rth(u, th):
            quad = 0.1 * np.exp(-((u - 0.3) / 0.25) ** 2) * np.maximum(0, np.sin(th))
            ham = 0.06 * np.exp(-((u - 0.4) / 0.3) ** 2) * np.maximum(0, -np.sin(th))
            return 0.68 - 0.26 * u + quad + ham
        bend_t = lambda u: np.outer(np.sin(math.pi * u) * 0.07, Ft)
        core_tendons(thigh, top, knee, rth, rng, 6, (0.2, 0.27), rf=(0.0, 0.45))
        G.rope_bundle(thigh, top, knee, rth, rng, n_ropes=nd(6), per_rope=(3, 4), rope_rf=(0.7, 0.88),
                      rope_r=(0.26, 0.34), tps=(0.35, 0.9), ext=(0.14, 0.12), bend=bend_t, rope_twist=(0.1, 0.35))
        G.bundle(thigh, top, knee, nd(9), rth, rng, rad=(0.04, 0.09), rf=(0.9, 1.02), twist=(0.1, 0.45),
                 ext=(0.12, 0.1), bend=bend_t, free=True)
        G.arcs(thigh, top, knee, nd(4), rth, rng, rad=(0.02, 0.035), free=True)
        G.wraps(thigh, top, knee, nd(6), rth, rng, rad=(0.009, 0.018), fuse_min=9)
        # genou : condyles noueux cachés sous des bandes de tendons qui enveloppent l'articulation (pièce du tibia)
        Tk, Fk, Xk = seg_frame(hip, knee)
        G.knob(shin, knee + Fk * 0.2 + Tk * 0.03, (Xk, Fk, Tk), (0.22, 0.15, 0.24), rng, noise=0.3)
        for sx in (-1, 1):
            G.knob(shin, knee + Xk * sx * 0.2 - Fk * 0.02, (Xk, Fk, Tk), (0.16, 0.2, 0.22), rng, noise=0.3)
        Ts, Fs, Xs = seg_frame(knee, ankle)

        def rsh(u, th):
            calf = 0.15 * np.exp(-((u - 0.25) / 0.18) ** 2) * np.maximum(0, -np.sin(th)) ** 1.3
            return 0.4 - 0.17 * u + calf
        core_tendons(shin, knee, ankle, rsh, rng, 4, (0.13, 0.18), rf=(0.0, 0.4))
        G.rope_bundle(shin, knee, ankle, rsh, rng, n_ropes=nd(5), per_rope=(3, 4), rope_rf=(0.62, 0.8),
                      rope_r=(0.3, 0.4), tps=(0.55, 1.1), ext=(0.12, 0.1), separate=0.25, rope_twist=(0.25, 0.6))
        G.bundle(shin, knee, ankle, nd(5), rsh, rng, rad=(0.02, 0.05), rf=(0.88, 1.03), twist=(0.2, 0.7),
                 ext=(0.1, 0.08), free=True)
        G.arcs(shin, knee, ankle, nd(2), rsh, rng, rad=(0.018, 0.03), free=True)
        G.wraps(shin, knee, ankle, nd(6), rsh, rng, rad=(0.008, 0.016), fuse_min=9, turns=(1.0, 2.6))
        for k in range(5):                      # bandes qui enveloppent le genou
            a0 = rng.uniform(0, TAU)
            n = 24
            ang = a0 + np.linspace(0, rng.uniform(2.2, 4.0), n) * rng.choice([-1, 1])
            hgt = np.linspace(-0.14, 0.14, n) * rng.choice([-1, 1]) + rng.uniform(-0.05, 0.05)
            rr = 0.4 + 0.04 * np.sin(np.linspace(0, math.pi, n))
            pts = knee[None] + np.outer(hgt, Tk) + rr[:, None] * (np.cos(ang)[:, None] * Xk + np.sin(ang)[:, None] * Fk)
            rad = rng.uniform(0.024, 0.04) * (0.35 + 0.65 * np.sin(np.linspace(0, math.pi, n)))
            nrm = np.cos(ang)[:, None] * Xk + np.sin(ang)[:, None] * Fk
            shin.free.append(ST(pts, rad, tendon_color(rng, 1.0), K_TENDON, nrm, 0.5))
        drips_on(thigh, top, knee, rth, rng, nd(10), length=(0.4, 2.2), r0=(0.016, 0.035), u_range=(0.25, 0.95),
                 skip=('Thigh_' + side, 'Pelvis'))
        drips_on(shin, knee, ankle, rsh, rng, nd(4), length=(0.3, 0.9), r0=(0.012, 0.026), u_range=(0.05, 0.6),
                 skip=('Thigh_' + side, 'Shin_' + side))
        build_foot(side, s, foot, ankle, rng)


def build_foot(side, s, foot, ankle, rng):
    """Le pied se défait en racines : les tendons du bas du tibia s'écartent en éventail concave (comme la base
    d'un tronc, partie haute fusionnée en SDF), touchent le sol puis rampent en se ramifiant."""
    ground = 0.0
    foot.voxel = 0.018
    foot.fillet = 4
    axis = np.array([ankle[0], 0.0, ankle[2]])
    top_h = ankle[1] + 0.5
    for k in range(3):                      # petit cœur sombre dans la cheville
        a = TAU * k / 3 + rng.uniform(-0.4, 0.4)
        off = 0.04 * np.array([math.cos(a), 0, math.sin(a)])
        path = resample(np.array([axis + off + [0, top_h, 0], axis + off * 2 + [0, ankle[1] * 0.6, 0],
                                  axis + off * 3 + [0, 0.18, 0]]), 0.04)
        t = np.linspace(0, 1, len(path))
        foot.fuse.append((path, rng.uniform(0.06, 0.075) * (1 + 0.5 * t), TAR_DEEP * rng.uniform(0.8, 1.2)))
    n_roots = nd(18)
    for k in range(n_roots):
        back = k >= int(n_roots * 0.78)
        a = rng.uniform(2.3, 3.95) if back else rng.uniform(-1.4, 1.4) + s * 0.3
        a0 = a + rng.uniform(-0.5, 0.5) - 0.6 * rng.choice([-1, 1])        # angle de départ (torsion de l'éventail)
        rho0 = rng.uniform(0.03, 0.11)
        rho1 = rng.uniform(0.32, 0.8) * (0.8 if back else 1.0)
        h0 = top_h - rng.uniform(0.0, 0.35)
        n1 = 18
        t1 = np.linspace(0, 1, n1)
        ang = a0 + (a - a0) * smoothstep(t1)
        rho = rho0 + (rho1 - rho0) * t1 ** 2.6
        hh = h0 * (1 - t1) ** 1.15
        dirs = np.stack([s * np.sin(ang), np.zeros(n1), -np.cos(ang)], 1)
        p1 = axis[None] + dirs * rho[:, None]
        p1[:, 1] = hh
        d = dirs[-1]
        side_v = np.array([d[2], 0.0, -d[0]])
        length = rng.uniform(0.9, 2.6) * (0.55 if back else 1.0)
        n2 = 28
        t2 = np.linspace(0, 1, n2)[1:]
        wav = rng.uniform(0.1, 0.45) * snoise(rng, t2, 2, 0.5, 1.4)
        p2 = p1[-1][None] + d[None] * (length * t2 ** 1.05)[:, None] + side_v[None] * (wav * length * 0.3 * t2)[:, None]
        r0 = rng.uniform(0.065, 0.11)
        r_fl = r0 * (1 + 0.25 * t1)
        r_gr = r0 * 1.2 * (1 - 0.93 * t2 ** 0.8) + 0.004
        pts = np.vstack([p1, p2])
        r = np.concatenate([r_fl, r_gr])
        t = np.concatenate([t1 * 0.3, 0.3 + 0.7 * t2])
        arch = np.zeros(len(t))
        if rng.random() < 0.4:
            c = rng.uniform(0.5, 0.8)
            arch = rng.uniform(0.04, 0.13) * np.clip(1 - ((t - c) / 0.13) ** 2, 0, 1) ** 1.5
        pts[:, 1] = np.maximum(pts[:, 1], r * 0.75 + ground) + arch
        if rng.random() < 0.3:                                # bout recourbé vers le haut
            tip = t > 0.86
            pts[tip, 1] += 0.2 * ((t[tip] - 0.86) / 0.14) ** 2 * rng.uniform(0.3, 1.0)
        col = tendon_color(rng, 0.9)
        cut = n1 + 2
        foot.fuse.append((pts[:cut], r[:cut], col))
        radial = pts - np.array([ankle[0], 0.0, ankle[2]])
        radial[:, 1] = 0.0
        radial = unit(radial + 1e-9)
        w_up = smoothstep((t - 0.25) / 0.15)[:, None]
        nrm = unit(radial * (1 - w_up) + np.array([0.0, 1.0, 0.0]) * w_up)
        foot.free.append(ST(pts[cut - 3:], r[cut - 3:] * 1.15, col, K_TENDON, nrm[cut - 3:], 0.62))
        for _ in range(int(rng.integers(1, 4))):              # radicelles
            i0 = int(n1 + (len(t) - n1) * rng.uniform(0.2, 0.75))
            q = pts[i0]
            bd = unit(d + side_v * rng.uniform(-1.5, 1.5))
            m = 14
            tt = np.linspace(0, 1, m)
            L2 = rng.uniform(0.2, 0.7)
            pp = q[None] + bd[None] * (L2 * tt)[:, None] + side_v[None] * (0.1 * L2 * snoise(rng, tt, 2, 0.5, 1.5))[:, None]
            r2 = r[i0] * 0.6 * (1 - 0.9 * tt) + 0.003
            pp[:, 1] = np.maximum(r2 * 0.8 + ground, q[1] * (1 - smoothstep(tt / 0.4)))
            foot.free.append((pp, r2, tendon_color(rng, 0.85)))
    # fibres fines qui s'enroulent autour de l'éventail
    for k in range(nd(6)):
        a0 = rng.uniform(0, TAU)
        n = 30
        tt = np.linspace(0, 1, n)
        ang = a0 + tt * rng.uniform(2, 5) * rng.choice([-1, 1])
        y = (ankle[1] + 0.45) * (1 - tt) ** 1.15 + 0.05
        rr = 0.13 + 0.3 * tt ** 2.6
        pts = np.stack([ankle[0] + rr * np.cos(ang), y, ankle[2] + rr * np.sin(ang)], 1)
        rad = rng.uniform(0.01, 0.018) * (0.4 + 0.6 * np.sin(math.pi * tt))
        foot.free.append((pts, rad, tendon_color(rng, 0.9)))


# ----------------------------------------------------------------------------------------------------------------
# obstacles pour les filaments qui pendent


def setup_obstacles():
    G.OBSTACLES.clear()
    for side in ('R', 'L'):
        G.add_obstacle('Thigh_' + side, J['Hip_' + side] + np.array([0, 0.2, 0]), J['Knee_' + side], 0.56)
        G.add_obstacle('Shin_' + side, J['Knee_' + side], J['Ankle_' + side], 0.34)
        G.add_obstacle('Arm_' + side, J['Shoulder_' + side], J['Elbow_' + side], 0.44)
        G.add_obstacle('Fore_' + side, J['Elbow_' + side], J['Wrist_' + side], 0.33)
    G.add_obstacle('Pelvis', J['Pelvis'] + np.array([0, -0.55, 0.0]), J['Pelvis'] + np.array([0, 0.45, 0.02]), 1.0)


# ----------------------------------------------------------------------------------------------------------------
# torse


def ellip_prof(w0, w1, wmid=None, umid=0.5, bulge=None):
    """Profil d'enveloppe (demi-largeur) le long d'un segment du torse."""
    def f(u, th):
        u = np.asarray(u, float)
        r = w0 + (w1 - w0) * u
        if wmid is not None:
            r = r + (wmid - (w0 + (w1 - w0) * umid)) * np.exp(-((u - umid) / 0.35) ** 2)
        if bulge is not None:
            r = r + bulge(u, th)
        return r
    return f


def lattice(piece, A, B, prof, rng, n, aspect, rad=(0.028, 0.06), turns=(0.25, 0.55), rf=(0.9, 1.02), ext=(0.12, 0.12),
            fwd=(0.0, 0.0, -1.0), free=True):
    """Treillis ajouré : deux familles de tendons en spirale de sens opposés (losanges, on voit au travers)."""
    for sgn in (1, -1):
        G.bundle(piece, A, B, n, prof, rng, aspect=aspect, rad=rad, rf=rf, twist=(sgn * turns[0], sgn * turns[1]),
                 ext=ext, partial=0.15, fwd=fwd, free=free, wobble=0.1)


def spine_curve():
    pts = np.array([J['Pelvis'] + [0, -0.15, 0.5], J['Pelvis'] + [0, 0.35, 0.56], J['SpineLow'] + [0, 0, 0.56],
                    J['SpineMid'] + [0, 0, 0.66], J['SpineHigh'] + [0, 0.12, 0.66], J['NeckBase'] + [0, 0.12, 0.46],
                    J['HeadJoint'] + [0, 0.02, 0.3]])
    return resample(catmull(pts, 12), 0.02)


def owner_of_spine_point(q):
    """Pièce qui porte un point de la colonne (selon la hauteur le long du dos)."""
    y = q[1]
    if q[2] < J['NeckBase'][2] + 0.5 and y > J['NeckBase'][1] - 0.25:
        return 'Neck'
    if y < J['SpineLow'][1]:
        return 'Pelvis'
    if y < J['SpineMid'][1]:
        return 'Abdomen'
    if y < J['SpineHigh'][1]:
        return 'Chest'
    return 'UpperChest'


def build_spine():
    """Vertèbres saillantes et épines dorsales tout le long du dos voûté."""
    rng = RNG('spine')
    sp = spine_curve()
    s_len = arclen(sp)
    T, N, B = frames(sp)
    k = 0
    s_at = 0.05
    while s_at < s_len[-1] - 0.25:
        i = int(np.searchsorted(s_len, s_at))
        q = sp[i]
        t = T[i]
        back = unit(np.array([0.0, 0.25, 1.0]) - t * (np.array([0.0, 0.25, 1.0]) @ t))
        owner = P(owner_of_spine_point(q))
        size = 0.09 + 0.04 * math.sin(math.pi * s_at / s_len[-1])
        side = unit(np.cross(t, back))
        G.knob(owner, q, (side, t, back), np.array([size * 1.25, size, size * 0.95]) * rng.uniform(0.85, 1.15), rng,
               fuse=True, noise=0.15)
        for sx in (-1, 1):            # apophyses transverses
            G.knob(owner, q + side * sx * size * 1.3 - back * 0.03, (side, t, back),
                   np.array([size * 0.7, size * 0.45, size * 0.5]), rng, fuse=True, noise=0.2)
        hump = math.exp(-((s_at / s_len[-1] - 0.68) / 0.2) ** 2)
        if rng.random() < 0.55 + 0.4 * hump:
            L = rng.uniform(0.1, 0.22) + 0.3 * hump * rng.uniform(0.5, 1.0)
            d = unit(back + t * rng.uniform(0.0, 0.6) + side * rng.uniform(-0.25, 0.25))
            G.spike(owner, q + back * size * 0.6, d, rng, L, 0.03 + 0.035 * hump, curl=rng.uniform(-0.6, 0.2))
        s_at += rng.uniform(0.15, 0.22)
        k += 1
    # gros tendons de part et d'autre de la colonne (érecteurs)
    for name in ('Pelvis', 'Abdomen', 'Chest', 'UpperChest'):
        pass


def build_pelvis():
    rng = RNG('pelvis')
    pel = P('Pelvis')
    pel.voxel = 0.028
    A = J['Pelvis'] + np.array([0, -0.62, 0.02])
    B = J['SpineLow']
    asp = (1.0, 0.62)
    prof = ellip_prof(0.9, 0.95, wmid=1.02, umid=0.62)
    # bassin osseux sombre (fusionné) : ailes iliaques, sacrum, arc pubien
    Tp, Fp, Xp = seg_frame(A, B)
    for sx in (-1, 1):
        c = J['Pelvis'] + np.array([sx * 0.55, 0.1, 0.12])
        ax1 = unit(np.array([sx * 0.8, 0.5, 0.0]))
        G.knob(pel, c, (ax1, unit(np.cross(ax1, [0, 0, 1.0])), np.array([0, 0, 1.0])), (0.36, 0.28, 0.22), rng,
               color=TAR_DEEP, noise=0.15, kind=K_CORE)
    G.knob(pel, J['Pelvis'] + np.array([0, 0.0, 0.42]), (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])),
           (0.3, 0.42, 0.16), rng, color=TAR_DEEP, kind=K_CORE)
    G.knob(pel, J['Pelvis'] + np.array([0, -0.38, -0.22]), (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])),
           (0.38, 0.2, 0.18), rng, color=TAR_DEEP, kind=K_CORE)
    core_tendons(pel, A + np.array([0, 0.25, 0]), B, lambda u, th: 0.55 + 0 * u, rng, 6, (0.2, 0.28), rf=(0.0, 0.75))
    # tendons du bassin : cordes et treillis
    G.rope_bundle(pel, A, B, prof, rng, n_ropes=nd(6), per_rope=(3, 4), rope_rf=(0.6, 0.85), rope_r=(0.18, 0.28),
                  tps=(0.4, 1.0), aspect=asp, ext=(0.05, 0.14), rope_twist=(-0.15, 0.15))
    lattice(pel, A, B, prof, rng, nd(5), asp, rad=(0.028, 0.055), turns=(0.15, 0.35))
    # ceinture de tendons sur la crête iliaque
    for k in range(nd(7)):
        y = J['Pelvis'][1] + rng.uniform(0.15, 0.45)
        a0 = rng.uniform(0, TAU)
        span = rng.uniform(1.5, 3.5)
        n = 40
        t = np.linspace(0, 1, n)
        ang = a0 + span * t
        rr = 1.02 + 0.04 * snoise(rng, t, 2, 1, 3)
        pts = np.stack([rr * np.cos(ang), y + 0.12 * snoise(rng, t, 2, 0.5, 2) - 0.1 * np.sin(ang) ** 2,
                        J['Pelvis'][2] + 0.6 * rr * np.sin(ang)], 1)
        rad = rng.uniform(0.03, 0.06) * (0.4 + 0.6 * np.sin(math.pi * t) ** 0.5)
        nrm = np.stack([np.cos(ang), np.zeros(n), 0.6 * np.sin(ang)], 1)
        pel.free.append(ST(pts, rad, tendon_color(rng, 1.0), K_TENDON, nrm, 0.5))
    # attaches des hanches et de l'aine (débordent dans les cuisses)
    for side, s in (('R', 1.0), ('L', -1.0)):
        hip = J['Hip_' + side]
        crest = J['Pelvis'] + np.array([s * 0.85, 0.38, 0.05])
        G.bundle(pel, crest, hip + np.array([s * 0.08, -0.25, 0]), nd(7), lambda u, th: 0.17 + 0.1 * u, rng,
                 rad=(0.03, 0.07), ext=(0.05, 0.08), twist=(-0.3, 0.3), free=True)
        groin = J['Pelvis'] + np.array([s * 0.15, -0.45, -0.25])
        G.bundle(pel, groin, hip + np.array([-s * 0.2, -0.5, -0.05]), nd(4), lambda u, th: 0.1 + 0.08 * u, rng,
                 rad=(0.03, 0.06), ext=(0.05, 0.05), free=True)
    # jupe de filaments qui pendent du bassin
    for k in range(nd(60)):
        th = rng.uniform(0, TAU)
        y = J['Pelvis'][1] + rng.uniform(-0.55, 0.3)
        r = 0.98 if y > J['Pelvis'][1] - 0.2 else 0.8
        p0 = np.array([r * math.cos(th), y, J['Pelvis'][2] + 0.6 * r * math.sin(th)])
        out = np.array([math.cos(th), 0, math.sin(th)])
        L = rng.uniform(1.0, 4.6) if rng.random() < 0.65 else rng.uniform(0.3, 1.0)
        G.drip(pel, p0, out, rng, L, rng.uniform(0.018, 0.05), skip=('Pelvis',))


def build_abdomen():
    rng = RNG('abdomen')
    ab = P('Abdomen')
    ab.voxel = 0.028
    A, B = J['SpineLow'], J['SpineMid']
    asp = (1.0, 0.74)
    prof = ellip_prof(1.0, 1.15, wmid=0.94, umid=0.42)
    # colonne sombre à l'arrière seulement : on voit au travers sur les côtés et devant
    back = A + np.array([0, 0, 0.22])
    core_tendons(ab, back, B + np.array([0, 0, 0.22]), lambda u, th: 0.42 + 0 * u, rng, 6, (0.16, 0.24), rf=(0.0, 0.85),
                 ext=(0.15, 0.15))
    lattice(ab, A, B, prof, rng, nd(7), asp, rad=(0.03, 0.065), turns=(0.25, 0.5), ext=(0.15, 0.15))
    G.rope_bundle(ab, A, B, prof, rng, n_ropes=nd(4), per_rope=(3, 4), rope_rf=(0.75, 0.92), rope_r=(0.16, 0.24),
                  aspect=asp, ext=(0.15, 0.15), separate=0.5, sep_h=(0.06, 0.16), rope_twist=(-0.1, 0.1))
    G.arcs(ab, A, B, nd(4), prof, rng, aspect=asp, rad=(0.025, 0.04), free=True, height=(0.06, 0.2))
    G.wraps(ab, A, B, nd(6), prof, rng, aspect=asp, rad=(0.01, 0.02), fuse_min=9)
    # muscles du dos (érecteurs) le long de la colonne
    for sx in (-1, 1):
        G.bundle(ab, A + np.array([sx * 0.2, -0.1, 0.4]), B + np.array([sx * 0.22, 0.1, 0.46]), nd(4),
                 lambda u, th: 0.1 + 0 * u, rng, rad=(0.04, 0.07), ext=(0.1, 0.1), free=True, twist=(-0.15, 0.15))
    T_, F_, X_ = seg_frame(A, B)
    for k in range(nd(7)):
        u = rng.uniform(0.05, 0.95)
        c = A + (B - A) * u
        a0 = rng.uniform(0, TAU)
        n = 40
        t = np.linspace(0, 1, n)
        ang = a0 + rng.uniform(2.0, 4.5) * t * rng.choice([-1, 1])
        w = prof(np.array([u]), np.array([0.0]))[0] * rng.uniform(1.0, 1.08)
        pts = (c[None] + (w * np.cos(ang))[:, None] * X_[None] + (w * asp[1] * np.sin(ang))[:, None] * F_[None]
               + np.outer(0.08 * snoise(rng, t, 2, 0.5, 2), T_))
        rad = rng.uniform(0.032, 0.058) * (0.3 + 0.7 * np.sin(math.pi * t) ** 0.5)
        nrm = np.cos(ang)[:, None] * X_[None] + asp[1] * np.sin(ang)[:, None] * F_[None]
        ab.free.append(ST(pts, rad, tendon_color(rng, 1.0), K_TENDON, nrm, 0.5))
    G.fuzz(ab, A, B, prof, rng, nd(14), aspect=asp, length=(0.08, 0.25))
    drips_on(ab, A, B, prof, rng, nd(13), length=(0.4, 2.4), r0=(0.016, 0.038), aspect=asp, k=0.95, skip=('Pelvis',),
             th_pref=lambda r: r.uniform(0.2, math.pi - 0.2))


def build_chest():
    rng = RNG('chest')
    ch = P('Chest')
    ch.voxel = 0.03
    A, B = J['SpineMid'], J['SpineHigh']
    T, F, X = seg_frame(A, B)
    asp = (1.0, 0.68)
    prof = ellip_prof(1.12, 1.36, wmid=1.34, umid=0.6)
    # masse sombre intérieure (poumons, coeur)
    for sx in (-1, 1):
        G.knob(ch, A + (B - A) * 0.55 + np.array([sx * 0.5, 0, 0.05]), (np.array([1.0, 0, 0]), T, -F), (0.6, 0.7, 0.58),
               rng, color=TAR_DEEP, noise=0.1, kind=K_CORE)
    G.knob(ch, A + (B - A) * 0.45 + np.array([0.08, 0, -0.18]), (np.array([1.0, 0, 0]), T, -F), (0.25, 0.3, 0.22), rng,
           color=OXBLOOD * 0.6, kind=K_CORE)
    core_tendons(ch, A + np.array([0, 0, 0.3]), B + np.array([0, 0, 0.3]), lambda u, th: 0.15 + 0 * u, rng, 3, (0.1, 0.13),
                 rf=(0.0, 0.6), ext=(0.15, 0.15))
    # côtes irrégulières (tresses), certaines cassées ou fourchues
    n_ribs = 7
    for i in range(n_ribs):
        u = 0.02 + 0.92 * (i + rng.uniform(-0.25, 0.25)) / (n_ribs - 1)
        c0 = A + (B - A) * u
        wa = prof(np.array([min(u, 1.0)]), np.array([0.0]))[0] * rng.uniform(0.9, 1.0)
        wb = wa * 0.66 * rng.uniform(0.93, 1.05)
        for side_s in (1.0, -1.0):
            xw = np.array([side_s, 0.0, 0.0])
            broken = rng.random() < 0.28
            phi_end = rng.uniform(0.2, 0.9) if broken else rng.uniform(1.2, 1.42)
            phis = np.linspace(-1.42, phi_end, 30)
            drop = -0.32 * (phis + 1.42) / 2.84 - 0.05 * np.sin(phis * 2)
            pts = (c0[None] + (wa * np.cos(phis))[:, None] * xw[None] + (wb * np.sin(phis))[:, None] * F[None]
                   + drop[:, None] * T[None])
            pts = pts + 0.025 * np.stack([snoise(rng, phis, 2, 0.3, 1.0), snoise(rng, phis, 2, 0.3, 1.0),
                                          snoise(rng, phis, 2, 0.3, 1.0)], 1)
            taper = (lambda t: 0.4 + 0.6 * (1 - t) ** 0.6) if broken else (lambda t: 1.0 - 0.35 * t)
            G.braid(ch, pts, rng, strands=int(rng.integers(2, 4)), rb=0.045, turns_per_stud=1.3,
                    tube_r=rng.uniform(0.038, 0.054), taper=taper)
            if not broken and rng.random() < 0.25:            # côte fourchue vers l'avant
                k0 = int(len(pts) * 0.6)
                fork = pts[k0:] + np.outer(np.linspace(0, 1, len(pts) - k0) ** 1.5, -T * 0.16)
                G.braid(ch, fork, rng, strands=2, rb=0.02, tube_r=0.02, taper=lambda t: 1.0 - 0.6 * t)
    # sternum
    st = np.array([A + F * 0.55 + T * -0.1, A + (B - A) * 0.5 + F * 0.62, B + F * 0.58 + T * 0.05])
    st = resample(catmull(st, 10), 0.04)
    G.braid(ch, st, rng, strands=3, rb=0.05, turns_per_stud=1.2, tube_r=0.04)
    # tendons extérieurs clairsemés (obliques, dentelés)
    lattice(ch, A, B, prof, rng, nd(3), asp, rad=(0.022, 0.045), turns=(0.15, 0.4), rf=(1.02, 1.1), ext=(0.1, 0.15))
    G.arcs(ch, A, B, nd(4), prof, rng, aspect=asp, rad=(0.025, 0.04), free=True, height=(0.06, 0.18))
    for sx in (-1, 1):            # muscles du dos
        G.bundle(ch, A + np.array([sx * 0.22, -0.1, 0.5]), B + np.array([sx * 0.25, 0.1, 0.55]), nd(4),
                 lambda u, th: 0.12 + 0 * u, rng, rad=(0.045, 0.08), ext=(0.12, 0.12), free=True, twist=(-0.1, 0.1))
    G.fuzz(ch, A, B, prof, rng, nd(22), aspect=asp, length=(0.08, 0.3))
    drips_on(ch, A, B, prof, rng, nd(18), length=(0.4, 2.8), r0=(0.016, 0.036), aspect=asp, k=1.0,
             u_range=(0.0, 0.6), th_pref=lambda r: r.uniform(0.1, math.pi - 0.1))


def build_upperchest():
    rng = RNG('upperchest')
    uc = P('UpperChest')
    uc.voxel = 0.03
    A, B = J['SpineHigh'], J['NeckBase']
    T, F, X = seg_frame(A, B)
    nb = J['NeckBase']
    # bosse du haut du dos : masse sombre fusionnée (omoplates, trapèzes)
    G.knob(uc, A + (B - A) * 0.45 + np.array([0, 0.14, 0.4]), (np.array([1.0, 0, 0]), T, -F), (1.25, 0.72, 0.62), rng,
           color=TAR_DEEP, noise=0.12, kind=K_CORE)
    for sx in (-1, 1):
        sc_c = A + np.array([sx * 0.78, 0.2, 0.72])
        G.knob(uc, sc_c, (unit(np.array([sx, 0.3, 0.4])), unit(np.array([0, 1.0, -0.3])), unit(np.array([sx * -0.3, 0, 1.0]))),
               (0.42, 0.36, 0.1), rng, color=TAR, noise=0.2)          # omoplates
    core_tendons(uc, A, B, lambda u, th: 0.6 - 0.2 * u, rng, 6, (0.2, 0.28), rf=(0.0, 0.7), ext=(0.2, 0.1))
    prof = ellip_prof(1.45, 0.66, wmid=1.3, umid=0.4)
    G.rope_bundle(uc, A + np.array([0, -0.1, 0]), B, prof, rng, n_ropes=nd(6), per_rope=(3, 4), rope_rf=(0.6, 0.85),
                  rope_r=(0.17, 0.26), aspect=(1.0, 0.75), ext=(0.25, 0.12), rope_twist=(-0.1, 0.1))
    # tendons du dos voûté : du cou vers le bas du dos (passent sur la bosse)
    for k in range(nd(16)):
        sx = rng.uniform(-1, 1)
        p0 = nb + np.array([sx * 0.25, rng.uniform(-0.05, 0.15), rng.uniform(0.0, 0.25)])
        p1 = A + (B - A) * 0.55 + np.array([sx * 0.75, 0.25, 0.75])
        p2 = J['SpineMid'] + np.array([sx * rng.uniform(0.3, 0.75), rng.uniform(0.2, 0.6), 0.62])
        path = resample(catmull(np.array([p0, p1, p2]), 12), 0.04)
        t = np.linspace(0, 1, len(path))
        r = rng.uniform(0.03, 0.07) * (0.5 + 0.5 * np.sin(math.pi * np.clip(t * 1.1, 0, 1)) ** 0.5)
        uc.free.append((path, r, tendon_color(rng, 1.0)))
    for side, s in (('R', 1.0), ('L', -1.0)):
        sh = J['Shoulder_' + side]
        acro = sh + np.array([-s * 0.12, 0.2, 0.05])
        # trapèze : du cou à l'épaule, en arc
        for k in range(nd(10)):
            p0 = nb + np.array([s * rng.uniform(0.05, 0.3), rng.uniform(-0.15, 0.1), rng.uniform(-0.05, 0.35)])
            p2 = acro + np.array([rng.uniform(-0.1, 0.1), rng.uniform(-0.12, 0.08), rng.uniform(-0.15, 0.2)])
            p1 = (p0 + p2) / 2 + np.array([0, rng.uniform(0.18, 0.38), rng.uniform(0.0, 0.2)])
            path = resample(catmull(np.array([p0 - (p1 - p0) * 0.15, p0, p1, p2, p2 + (p2 - p1) * 0.2]), 10), 0.04)
            t = np.linspace(0, 1, len(path))
            r = rng.uniform(0.04, 0.085) * (0.55 + 0.45 * np.sin(math.pi * t))
            uc.free.append((path, r, tendon_color(rng, 1.0)))
        # clavicule
        cl = resample(catmull(np.array([A + F * 0.55 + T * 0.35 + np.array([s * 0.1, 0, 0]),
                                        A + F * 0.6 + T * 0.45 + np.array([s * 0.7, 0, 0]),
                                        acro + np.array([0, -0.05, -0.1])]), 10), 0.04)
        G.braid(uc, cl, rng, strands=3, rb=0.04, turns_per_stud=1.4, tube_r=0.033)
        # pectoraux : du sternum vers l'épaule
        for k in range(nd(6)):
            p0 = J['SpineMid'] + F * 0.6 + T * rng.uniform(0.1, 0.8) + np.array([s * rng.uniform(0.0, 0.15), 0, 0])
            p2 = sh + np.array([-s * 0.15, rng.uniform(-0.35, -0.05), -0.12])
            p1 = (p0 + p2) / 2 + F * 0.18
            path = resample(catmull(np.array([p0, p1, p2]), 10), 0.04)
            t = np.linspace(0, 1, len(path))
            r = rng.uniform(0.035, 0.065) * (0.5 + 0.5 * np.sin(math.pi * t) ** 0.6)
            uc.free.append((path, r, tendon_color(rng, 1.0)))
        # pointe de l'épaule (acromion) hérissée de fibres
        G.knob(uc, acro, (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])), (0.2, 0.15, 0.2), rng,
               noise=0.2)
        for k in range(nd(9)):
            d = unit(np.array([s * rng.uniform(0.2, 1.0), rng.uniform(0.6, 1.2), rng.uniform(-0.5, 0.6)]))
            base_p = acro + np.array([rng.uniform(-0.15, 0.15), rng.uniform(0.0, 0.1), rng.uniform(-0.15, 0.15)])
            L = rng.uniform(0.15, 0.45)
            n = 10
            t = np.linspace(0, 1, n)
            path = base_p[None] + np.outer(t * L, d) + np.outer((t ** 2) * L * 0.25, np.array([s, -0.3, 0]))
            r = rng.uniform(0.012, 0.028) * (1 - t) ** 0.9 + 0.002
            uc.free.append((path, r, tendon_color(rng, 0.9)))
    G.fuzz(uc, A, B, prof, rng, nd(45), aspect=(1.0, 0.75), length=(0.1, 0.4), th_range=(-0.3, math.pi * 2))
    drips_on(uc, A, B, prof, rng, nd(6), length=(0.3, 1.2), r0=(0.014, 0.03), aspect=(1.0, 0.75),
             th_pref=lambda r: r.uniform(0.3, math.pi - 0.3))


def build_neck():
    rng = RNG('neck')
    nk = P('Neck')
    nk.voxel = 0.025
    A = J['NeckBase'] + np.array([0, -0.1, 0.12])
    B = J['HeadJoint'] + FH * 0.12
    prof = lambda u, th: 0.46 - 0.08 * u + 0 * th
    core_tendons(nk, A, B, prof, rng, 4, (0.15, 0.2), rf=(0.0, 0.5), ext=(0.15, 0.15))
    G.rope_bundle(nk, A, B, prof, rng, n_ropes=nd(4), per_rope=(3, 4), rope_rf=(0.55, 0.8), rope_r=(0.3, 0.42),
                  ext=(0.2, 0.18), tps=(0.5, 1.2), rope_twist=(0.2, 0.45), fwd=(0, 1.0, 0))
    G.bundle(nk, A, B, nd(6), prof, rng, rad=(0.03, 0.06), rf=(0.9, 1.03), twist=(0.2, 0.6), ext=(0.15, 0.15),
             free=True, fwd=(0, 1.0, 0))
    G.wraps(nk, A, B, nd(5), prof, rng, rad=(0.01, 0.02), fuse_min=9, fwd=(0, 1.0, 0))
    drips_on(nk, A, B, prof, rng, nd(4), length=(0.3, 1.2), r0=(0.014, 0.03), fwd=(0, 1.0, 0),
             th_pref=lambda r: r.uniform(math.pi * 0.9, math.pi * 1.6))


# ----------------------------------------------------------------------------------------------------------------
# bras, mains, doigts


def build_arms():
    for side, s in (('R', 1.0), ('L', -1.0)):
        rng = RNG('arm' + side)
        sh, el, wr = J['Shoulder_' + side], J['Elbow_' + side], J['Wrist_' + side]
        up, fo = P('UpperArm_' + side), P('Forearm_' + side)
        top = sh + np.array([-s * 0.08, 0.22, 0.0])
        Tu, Fu, Xu = seg_frame(top, el)

        def rua(u, th):
            delt = 0.26 * np.exp(-((u - 0.08) / 0.2) ** 2) * (0.75 + 0.25 * np.cos(th - (0 if s > 0 else math.pi)))
            return 0.46 - 0.1 * u + delt
        core_tendons(up, top, el, rua, rng, 5, (0.16, 0.22), rf=(0.0, 0.42))
        G.rope_bundle(up, top, el, rua, rng, n_ropes=nd(5), per_rope=(3, 4), rope_rf=(0.68, 0.86), rope_r=(0.26, 0.36),
                      tps=(0.4, 1.0), ext=(0.18, 0.12), rope_twist=(-0.35, -0.1))
        G.bundle(up, top, el, nd(6), rua, rng, rad=(0.025, 0.06), rf=(0.88, 1.03), twist=(-0.5, -0.1), ext=(0.15, 0.1),
                 free=True)
        G.arcs(up, top, el, nd(3), rua, rng, rad=(0.02, 0.034), free=True)
        G.wraps(up, top, el, nd(6), rua, rng, rad=(0.009, 0.018), fuse_min=9)
        for k in range(nd(6)):              # fibres hérissées sur le deltoïde
            d = unit(np.array([s * rng.uniform(0.3, 1.0), rng.uniform(0.3, 1.0), rng.uniform(-0.5, 0.5)]))
            p0 = top + Tu * rng.uniform(0.05, 0.4) + d * 0.3
            L = rng.uniform(0.12, 0.35)
            t = np.linspace(0, 1, 9)
            path = p0[None] + np.outer(t * L, d) + np.outer(t ** 2 * L * 0.3, -Tu)
            up.free.append((path, rng.uniform(0.01, 0.022) * (1 - t) ** 0.9 + 0.002, tendon_color(rng, 0.9)))
        Tf, Ff, Xf = seg_frame(el, wr)

        def rfa(u, th):
            return 0.44 - 0.23 * u + 0.08 * np.exp(-((u - 0.15) / 0.14) ** 2)
        # coude osseux (olécrane) : appartient à l'avant-bras
        back_dir = unit(-Fu * 0.8 - Tu * 0.2)
        G.knob(fo, el + back_dir * 0.18, (Xu, Fu, Tu), (0.2, 0.17, 0.22), rng, noise=0.3)
        core_tendons(fo, el, wr, rfa, rng, 4, (0.12, 0.17), rf=(0.0, 0.4))
        G.rope_bundle(fo, el, wr, rfa, rng, n_ropes=nd(4), per_rope=(3, 4), rope_rf=(0.62, 0.82), rope_r=(0.3, 0.4),
                      tps=(0.5, 1.2), ext=(0.12, 0.1), rope_twist=(0.15, 0.45), separate=0.35)
        G.bundle(fo, el, wr, nd(6), rfa, rng, rad=(0.02, 0.05), rf=(0.88, 1.03), twist=(0.1, 0.5), ext=(0.1, 0.08),
                 free=True)
        G.arcs(fo, el, wr, nd(3), rfa, rng, rad=(0.018, 0.03), free=True)
        G.wraps(fo, el, wr, nd(6), rfa, rng, rad=(0.008, 0.016), fuse_min=9, turns=(1.0, 2.6))
        G.fuzz(up, top, el, rua, rng, nd(30), u_range=(0.0, 0.6), length=(0.1, 0.38))
        G.fuzz(fo, el, wr, rfa, rng, nd(16), u_range=(0.0, 0.8), length=(0.08, 0.25))
        drips_on(up, top, el, rua, rng, nd(12), length=(0.4, 2.6), r0=(0.014, 0.032), u_range=(0.2, 0.95),
                 skip=('Arm_' + side, 'Fore_' + side))
        drips_on(fo, el, wr, rfa, rng, nd(24), length=(0.6, 3.8), r0=(0.012, 0.032), u_range=(0.05, 0.95),
                 skip=('Arm_' + side, 'Fore_' + side), th_pref=lambda r: r.uniform(0, TAU))
        build_hand(side, s, rng)


def build_hand(side, s, rng):
    h = HAND[side]
    D, Nn, Tt = h['D'], h['N'], h['T']
    wr, kn = h['wrist'], h['knuckles']
    hand = P('Hand_' + side)
    hand.voxel = 0.018
    hand.fillet = 3
    W = unit(np.cross(D, Nn))
    # carpe : noeuds sombres fusionnés et paume aplatie (sombre)
    for k in range(4):
        c = wr + D * rng.uniform(0.02, 0.18) + Tt * rng.uniform(-0.1, 0.1) + Nn * rng.uniform(-0.03, 0.03)
        G.knob(hand, c, (Tt, Nn, D), np.array([0.08, 0.06, 0.07]) * rng.uniform(0.8, 1.2), rng, noise=0.35)
    pc = wr + D * 0.38
    G.knob(hand, pc, (Tt, Nn, D), (0.22, 0.07, 0.3), rng, color=TAR_DEEP, noise=0.3, kind=K_CORE)
    # métacarpes : un faisceau tressé vers chaque doigt
    for name in FINGERS[:4]:
        a = h['fingers'][name]['segs'][0][0]
        start = wr + D * 0.02 + Tt * (a - kn) @ Tt * 0.35
        path = resample(catmull(np.array([start - D * 0.08, start + (a - start) * 0.5 + Nn * -0.03, a + D * 0.04]), 8), 0.035)
        G.braid(hand, path, rng, strands=3, rb=0.042, turns_per_stud=1.5, tube_r=rng.uniform(0.033, 0.042),
                taper=lambda t: 1.0 - 0.15 * t)
    # éminence du pouce
    th1 = h['fingers']['Thumb']['segs'][0][0]
    for k in range(3):
        path = resample(np.array([wr + Tt * 0.05 - D * 0.05, (wr + th1) / 2 + Nn * 0.06 + Tt * 0.04, th1 + D * 0.02]), 0.035)
        path = resample(catmull(path, 6), 0.035)
        hand.free.append((path + rng.uniform(-0.03, 0.03, 3), rng.uniform(0.03, 0.045) * np.ones(len(path)),
                          tendon_color(rng, 1.0)))
    # tendons du dos de la main
    G.bundle(hand, wr - D * 0.12, kn, nd(10), lambda u, th: 0.2 + 0.07 * u, rng, aspect=(1.0, 0.45),
             rad=(0.02, 0.045), rf=(0.92, 1.08), twist=(-0.12, 0.12), ext=(0.05, 0.05), free=True,
             fwd=-Nn)
    for k in range(nd(9)):
        c = wr + D * rng.uniform(0.1, 0.5) + Tt * rng.uniform(-0.15, 0.15) - Nn * 0.05
        G.drip(hand, c, -Nn + D * 0.3, rng, rng.uniform(0.4, 3.0), rng.uniform(0.01, 0.022), push=False)
    # doigts : os sombre, quelques tendons presque parallèles (légère torsion), phalanges noueuses, griffe
    for name in FINGERS:
        f = h['fingers'][name]
        segs = f['segs']
        cax = f['axis']
        nseg = len(segs)
        for j, (a, b, d) in enumerate(segs):
            part = P('%s%d_%s' % (name, j + 1, side))
            r0 = (0.1 if name != 'Thumb' else 0.112) - 0.018 * j
            r1 = r0 - 0.02
            up_f = unit(np.cross(d, cax))                     # dos du doigt (côté opposé à la paume)
            # jointure noueuse : deux bosses latérales et une sur le dos (couvre l'articulation précédente)
            for sx in (-1, 1):
                G.knob(part, a + cax * sx * r0 * 0.45 + up_f * r0 * 0.15, (cax, up_f, d),
                       np.array([r0 * 0.55, r0 * 0.6, r0 * 0.75]), rng, fuse=False, nu=8, nv=6, noise=0.3)
            G.knob(part, a + up_f * r0 * 0.55, (cax, up_f, d), np.array([r0 * 0.6, r0 * 0.45, r0 * 0.8]), rng,
                   fuse=False, nu=8, nv=6, noise=0.3)
            L = float(np.linalg.norm(b - a))
            ext_b = 0.0 if j == nseg - 1 else 0.05
            core = resample(np.array([a - d * 0.03, b + d * ext_b * 0.5]), 0.04)
            tt = np.linspace(0, 1, len(core))
            part.free.append(ST(core, r0 * 0.55 * (1 - 0.3 * tt), TAR_DEEP, K_CORE))
            nt = 4
            for k in range(nt):
                ang0 = TAU * k / nt + rng.uniform(-0.3, 0.3)
                tw = rng.uniform(-0.25, 0.25)
                m = max(8, int(L / 0.035))
                tt = np.linspace(0, 1, m)
                ang = ang0 + TAU * tw * tt
                rr = r0 * (1 - (1 - r1 / r0) * tt) * rng.uniform(0.5, 0.65) * (1 + 0.1 * snoise(rng, tt, 2, 1, 3))
                base_line = a[None] - d[None] * 0.04 + np.outer(tt * (L + 0.04 + ext_b), d)
                pts = base_line + rr[:, None] * (np.cos(ang)[:, None] * cax[None] + np.sin(ang)[:, None] * up_f[None])
                rad = r0 * rng.uniform(0.3, 0.42) * (1 - 0.3 * tt) * (0.85 + 0.15 * snoise(rng, tt, 2, 2, 6))
                rad = rad * (1 + 0.35 * np.exp(-(tt / 0.12) ** 2))
                part.free.append((pts, rad, tendon_color(rng, 0.95)))
            if rng.random() < 0.55:
                c = a + (b - a) * rng.uniform(0.3, 0.8)
                G.drip(part, c - up_f * r0 * 0.6, -up_f + np.array([0, -1.0, 0]), rng,
                       rng.uniform(0.2, 1.2), rng.uniform(0.008, 0.016), push=False)
        last = P('%s%d_%s' % (name, nseg, side))
        a, b, d = segs[-1]
        L = 0.64 if name in ('Middle', 'Ring') else (0.58 if name != 'Thumb' else 0.5)
        G.claw(last, b - d * 0.05, d, cax, rng, length=L * rng.uniform(0.95, 1.1), r0=0.07, curl=1.1)
        G.knob(last, b - d * 0.02, (cax, unit(np.cross(d, cax)), d), (0.072, 0.07, 0.085), rng, fuse=False, nu=10, nv=7,
               noise=0.2)


# ----------------------------------------------------------------------------------------------------------------
# tête : crâne lisse allongé sans yeux, fente de gueule, crocs, mâchoire entrouverte

HM = np.stack([FH, XH, UH], 1)          # repère tête -> monde (colonnes F, X, U)
_HS = SCALE * 0.98


def head_radius(d, rng_ph=None):
    """Rayon du crâne dans la direction d (repère tête : colonnes F, X, U), en studs."""
    df, dx, du = d[:, 0], d[:, 1], d[:, 2]
    aF = np.where(df > 0, 1.0, 0.66)
    aU = np.where(du > 0, 0.6, 0.4)
    aX = 0.45 * (1 - 0.34 * np.clip(df, 0, 1) ** 1.5) * (1 + 0.1 * np.clip(du, 0, 1))
    aX = aX * (1 - 0.18 * np.clip(-du, 0, 1) * np.clip(df + 0.3, 0, 1))            # mâchoire supérieure étroite
    r = 1.0 / np.sqrt((df / aF) ** 2 + (dx / aX) ** 2 + (du / aU) ** 2)
    # occiput bombé et crête sagittale vers l'arrière
    r = r * (1 + 0.07 * np.exp(-(((df + 0.55) / 0.35) ** 2 + ((du - 0.35) / 0.4) ** 2)))
    r = r * (1 + 0.045 * np.exp(-((dx / 0.13) ** 2)) * np.clip(du, 0, 1) * np.clip(0.55 - df, 0, 1))
    # arcade (front) sans yeux : léger bourrelet, orbites à peine creusées
    r = r * (1 + 0.045 * np.exp(-((df - 0.6) / 0.07) ** 2) * np.clip(du + 0.1, 0, 1) ** 0.5)
    for sx in (1, -1):
        e = (df - 0.72) ** 2 / 0.014 + (dx - sx * 0.33) ** 2 / 0.012 + (du - 0.16) ** 2 / 0.012
        r = r * (1 - 0.11 * np.exp(-e))
    # fosses temporales et pommettes
    for sx in (1, -1):
        e = (df - 0.18) ** 2 / 0.06 + (dx - sx * 0.82) ** 2 / 0.05 + (du - 0.05) ** 2 / 0.05
        r = r * (1 - 0.1 * np.exp(-e))
        e2 = ((du + 0.1) / 0.08) ** 2 + ((df - 0.45) / 0.28) ** 2 + ((np.abs(dx) - 0.7) / 0.25) ** 2
        r = r * (1 + 0.05 * np.exp(-e2) * (np.sign(dx) == sx))
    # stries longitudinales (fibres moulées sous la peau), surtout devant et dessus
    psi = np.arctan2(dx, du)
    warp = 0.35 * np.sin(3.1 * df + 1.3) + 0.2 * np.sin(5.3 * du - 0.7 * dx)
    stri = np.sin(17 * psi + 2.0 * warp) * 0.7 + 0.3 * np.sin(29 * psi - 1.7 * warp + 1.1)
    r = r * (1 + 0.015 * stri * np.clip(du + 0.4, 0, 1) * (0.4 + 0.6 * np.clip(df + 0.5, 0, 1)))
    # sillons latéraux (tendons moulés sur les flancs du crâne, vers la mâchoire)
    for k, (c_du, c_df) in enumerate(((0.05, -0.1), (-0.12, 0.05), (0.22, -0.25))):
        g = np.exp(-((du - c_du + 0.25 * (df - c_df)) / 0.035) ** 2) * np.clip(np.abs(dx) - 0.45, 0, 1) * 2
        r = r * (1 - 0.018 * g * np.clip(0.6 - df, 0, 1))
    return r * _HS


def sphere_dirs(nlat, nlon):
    """Directions d'une sphère lat/lon : nlat anneaux (sans les pôles) puis pôle haut et pôle bas (repère F, X, U)."""
    lat = np.linspace(0.0, math.pi, nlat + 2)[1:-1]
    lon = np.linspace(0.0, TAU, nlon, endpoint=False)
    LA, LO = np.meshgrid(lat, lon, indexing='ij')
    d = np.stack([np.sin(LA) * np.cos(LO), np.sin(LA) * np.sin(LO), np.cos(LA)], -1).reshape(-1, 3)
    return np.vstack([d, [[0, 0, 1.0]], [[0, 0, -1.0]]])


def sphere_faces(nlat, nlon):
    F = []
    for i in range(nlat - 1):
        for j in range(nlon):
            j2 = (j + 1) % nlon
            a0, a1, b0, b1 = i * nlon + j, i * nlon + j2, (i + 1) * nlon + j, (i + 1) * nlon + j2
            F += [(a0, b0, b1), (a0, b1, a1)]
    top, bot = nlat * nlon, nlat * nlon + 1
    for j in range(nlon):
        j2 = (j + 1) % nlon
        F.append((top, j, j2))
        F.append((bot, (nlat - 1) * nlon + j2, (nlat - 1) * nlon + j))
    return np.array(F, np.int64)


def loguni_(rng, a, b):
    return math.exp(rng.uniform(math.log(a), math.log(b)))


def head_tangents(V):
    """Direction des stries du crâne : de l'avant vers l'arrière, dans le plan tangent."""
    n = unit(V - HEAD_C)
    t = FH[None] - (n @ FH)[:, None] * n
    return unit(t + 1e-9)


def lip_upper(df, dx):
    """Hauteur (du) de la lèvre supérieure : la fente suit le bas de l'avant du crâne en U."""
    return -0.30 + 0.16 * (1 - np.clip(df, 0, 1)) ** 1.2 + 0.05 * (dx / 0.45) ** 2


def build_head():
    rng = RNG('head')
    head, jaw = P('Head'), P('Jaw')
    # --- coque du crâne (grille lat/lon, pôle en haut) avec la gueule
    nlat, nlon = 56, 112
    dl = sphere_dirs(nlat, nlon)
    r = head_radius(dl)
    vloc = dl * r[:, None]
    # gueule : sous la lèvre supérieure et devant, la coque remonte en palais (voûte sombre)
    lu = lip_upper(dl[:, 0], dl[:, 1])
    mouth = (dl[:, 2] < lu) & (dl[:, 0] > 0.05)
    depth = np.clip((lu - dl[:, 2]) / 0.25, 0, 1)
    soft = smoothstep(np.clip((dl[:, 0] - 0.05) / 0.2, 0, 1))
    k = (depth * soft)[:, None]
    palate = vloc * np.array([0.88, 0.8, 0.25]) + np.array([0.0, 0.0, -0.05 * _HS])
    vloc = np.where(mouth[:, None], vloc * (1 - k) + palate * k, vloc)
    V = HEAD_C + vloc @ HM.T
    gum_k = np.where(mouth, np.clip(depth * 3, 0, 1) * soft, 0.0)
    base_c = TAR[None] * (0.7 + 0.5 * rng.random((len(V), 1)))
    C = base_c * (1 - gum_k[:, None]) + GUM[None] * (0.5 + 0.5 * rng.random((len(V), 1))) * gum_k[:, None]
    F = sphere_faces(nlat, nlon)
    e = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.einsum('ij,ij->i', e, V[F[:, 0]] - HEAD_C).sum() < 0:
        F = F[:, ::-1].copy()
    kinds = np.where(gum_k > 0.5, float(K_GUM), float(K_SKULL))
    head.free_meshes.append((V, F, C, kinds, head_tangents(V)))
    # --- crocs du haut le long de la lèvre (en U), longs devant, minuscules au fond
    n_up = 26
    for kk in range(n_up):
        a = math.radians(-74 + 148 * (kk + rng.uniform(-0.3, 0.3)) / (n_up - 1))
        dfx = np.array([[math.cos(a), math.sin(a) * 0.95, 0.0]])
        dfx[0, 2] = lip_upper(dfx[0, 0] * 0.9, dfx[0, 1] * 0.9) + 0.02
        dd = unit(dfx)
        rr = head_radius(dd)[0] * 0.93
        pl = HEAD_C + (dd[0] * rr) @ HM.T
        front = math.cos(a) ** 2
        L = (0.07 + 0.17 * front * rng.uniform(0.7, 1.25)) * SCALE
        inward = -(FH * math.cos(a) + XH * math.sin(a))
        G.fang(head, pl - UH * 0.01, -UH + FH * 0.12 * math.cos(a), inward, rng, L, 0.016 + 0.01 * front)
    # --- tendons du crâne : naissent sur le dôme, les flancs et l'arrière, se croisent et coulent vers la nuque
    nb = J['NeckBase']
    for kk in range(nd(34)):
        lo0 = rng.uniform(math.radians(70), math.radians(290))
        la0 = rng.uniform(math.radians(15), math.radians(115))
        la1 = rng.uniform(math.radians(115), math.radians(150))
        drift = rng.uniform(-0.6, 0.6)
        pts = []
        nw = 9
        for w in np.linspace(0, 1, nw):
            la = la0 + (la1 - la0) * w ** 1.2
            lo = lo0 + (math.pi + drift * 0.4 - lo0) * w ** 0.9 + drift * math.sin(math.pi * w) * 0.5
            dd = np.array([[math.sin(la) * math.cos(lo), math.sin(la) * math.sin(lo), math.cos(la)]])
            rr = head_radius(dd)[0] * (0.97 if w == 0 else 1.0) + 0.012 + 0.03 * w ** 2
            pts.append(HEAD_C + (dd[0] * rr) @ HM.T)
        tail = nb + np.array([rng.uniform(-0.3, 0.3), rng.uniform(-0.25, 0.05), rng.uniform(0.0, 0.35)])
        pts.append((pts[-1] + tail) / 2 + UH * rng.uniform(0.0, 0.1) + XH * rng.uniform(-0.1, 0.1))
        pts.append(tail)
        path = resample(catmull(np.array(pts), 8), 0.045)
        t = np.linspace(0, 1, len(path))
        r0 = loguni_(rng, 0.014, 0.065)
        rr = r0 * (0.25 + 0.75 * smoothstep(t / 0.3)) * (1 - 0.25 * t) + 0.003
        head.free.append((path, rr, tendon_color(rng, 0.9)))
    # tendons sous la joue (vers le cou), par-dessus la charnière de la mâchoire
    for sx in (-1, 1):
        for kk in range(nd(4)):
            p0 = HEAD_C + (FH * rng.uniform(0.0, 0.35) + XH * sx * 0.33 + UH * rng.uniform(-0.2, 0.05)) * _HS
            p2 = nb + np.array([sx * rng.uniform(0.1, 0.35), rng.uniform(-0.35, -0.1), rng.uniform(-0.2, 0.1)])
            p1 = (p0 + p2) / 2 + XH * sx * 0.12 - UH * 0.1
            path = resample(catmull(np.array([p0, p1, p2]), 10), 0.045)
            t = np.linspace(0, 1, len(path))
            rr = rng.uniform(0.025, 0.05) * (0.35 + 0.65 * smoothstep(t / 0.25)) + 0.003
            head.free.append((path, rr, tendon_color(rng, 0.9)))
    # intérieur sombre de la gorge
    G.knob(head, HEAD_C + FH * 0.1 * SCALE - UH * 0.22 * SCALE, (FH, XH, UH), np.array([0.42, 0.3, 0.16]) * SCALE, rng,
           color=GUM * 0.5, fuse=False, nu=16, nv=10, noise=0.05, kind=K_GUM)
    build_jaw(rng)


JAW_R = rot(XH, -JAW_OPEN)          # rotation d'ouverture (le menton descend)


def jaw_point(t, w, inner=0.0):
    """Point de la mâchoire inférieure : t de -1 (gauche) à 1 (droite) le long du U, w de la lèvre (0) au menton (1).
    Vers l'arrière (|t| -> 1) la mâchoire s'affine et remonte sous la joue (bouts cachés dans le crâne)."""
    a = t * math.radians(86)
    s = _HS
    back = abs(t) ** 3
    fwd = 0.8 * math.cos(a) * (1 - 0.12 * w) - 0.08
    lat = 0.36 * math.sin(a) * (1 - 0.25 * w) * (1 - 0.18 * back)
    depth = (0.2 * math.sin(math.pi * 0.5 * w) + 0.03 * w) * (1 - 0.97 * back)
    up = -0.28 - depth + 0.03 * (1 - abs(t)) + 0.14 * back
    shrink = 1 - inner
    p = HEAD_C + (FH * (fwd * shrink + 0.02) + XH * lat * shrink + UH * (up + inner * 0.22 * (1 - back))) * s
    return JAW_HINGE + JAW_R @ (p - JAW_HINGE)


def build_jaw(rng):
    jaw = P('Jaw')
    nl, nw = 34, 14
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
            F += [(a0, b1, a1), (a0, b0, b1)]                           # extérieur
            F += [(no + a0, no + a1, no + b1), (no + a0, no + b1, no + b0)]   # intérieur (vers la gueule)
    for j in range(nl - 1):                                             # bord de la lèvre
        a0, a1 = j, j + 1
        F += [(a0, a1, no + a1), (a0, no + a1, no + a0)]
    for i in range(nw - 1):                                             # bouts (cachés dans la tête)
        for j in (0, nl - 1):
            a0, b0 = i * nl + j, (i + 1) * nl + j
            if j == 0:
                F += [(a0, no + a0, no + b0), (a0, no + b0, b0)]
            else:
                F += [(a0, no + b0, no + a0), (a0, b0, no + b0)]
    F = np.array(F, np.int64)
    cen = jaw_point(0.0, 0.5, 0.08)
    e = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    outer_f = np.arange(len(F)) % 4 < 2
    C = np.vstack([TAR[None] * (0.7 + 0.5 * rng.random((no, 1))), GUM[None] * (0.45 + 0.5 * rng.random((no, 1)))])
    kinds = np.concatenate([np.full(no, float(K_SKULL)), np.full(no, float(K_GUM))])
    jfh = JAW_R @ FH
    nrm = unit(V - jaw_point(0.0, 0.5, 0.3))
    tang = unit(jfh[None] - (nrm @ jfh)[:, None] * nrm + 1e-9)
    jaw.free_meshes.append((V, F, C, kinds, tang))
    # crocs du bas (vers le haut, recourbés vers l'intérieur)
    n_lo = 22
    up_dir = JAW_R @ UH
    for kk in range(n_lo):
        t = -0.95 + 1.9 * (kk + rng.uniform(-0.3, 0.3)) / (n_lo - 1)
        pl = jaw_point(t, 0.02, 0.06)
        front = 1 - abs(t)
        L = (0.05 + 0.13 * front ** 1.5 * rng.uniform(0.7, 1.3)) * SCALE
        inward = -(jaw_point(t, 0.0) - jaw_point(0.0, 0.0, 0.5))
        G.fang(jaw, pl, up_dir + (JAW_R @ FH) * 0.08, inward, rng, L, 0.014 + 0.008 * front)
    # filaments qui pendent du menton et des joues
    for kk in range(nd(18)):
        t = rng.uniform(-0.85, 0.85)
        w = rng.uniform(0.6, 1.0)
        p0 = jaw_point(t, w, -0.02)
        L = rng.uniform(0.5, 3.2) if kk < 10 else rng.uniform(0.2, 0.6)
        G.drip(jaw, p0, (p0 - JAW_HINGE) * np.array([1, 0, 1]), rng, L, rng.uniform(0.01, 0.024), push=False)
    # tendons masséters : de la joue vers la mâchoire
    for sx in (-1, 1):
        for kk in range(3):
            p0 = jaw_point(sx * rng.uniform(0.75, 0.95), rng.uniform(0.2, 0.7), -0.02)
            p1 = JAW_HINGE + XH * sx * 0.38 * SCALE + rng.uniform(-0.05, 0.05, 3)
            path = resample(np.array([p0, (p0 + p1) / 2 - (JAW_R @ UH) * 0.03, p1]), 0.04)
            jaw.free.append((path, rng.uniform(0.025, 0.04) * np.ones(len(path)), tendon_color(rng, 1.0)))


def glow_position():
    """Position de la lueur de la gueule (marqueur GLOW_MOUTH), entre le palais et la langue, derrière les crocs."""
    return HEAD_C + (FH * 0.42 - UH * 0.36) * SCALE * 0.94


def build_all():
    G.PIECES.clear()
    setup_obstacles()
    build_legs()
    build_pelvis()
    build_abdomen()
    build_chest()
    build_upperchest()
    build_neck()
    build_spine()
    build_arms()
    build_head()
