"""Générateurs de brins (numpy) : faisceaux torsadés, arcs décollés, fibres enroulées, filaments qui gouttent,
nœuds articulaires, griffes, crocs. Un brin = (P (N,3) repère Roblox, R (N,) rayons, C couleur sRGB)."""
import math
import numpy as np
from mon_common import (TAU, unit, smoothstep, rot, catmull, resample, frames, seg_frame, Noise1D, snoise,
                        tendon_color, TAR, TAR_DEEP, BROWN, OXBLOOD, BLUE, BONE, GUM, CLAW, CLAW_TIP, arclen)


# types de matière (attribut Mat) : la matière procédurale et la cuisson s'en servent
K_TENDON, K_SKULL, K_TOOTH, K_GUM, K_CLAW, K_SLIME, K_CORE = 0, 1, 2, 3, 4, 5, 6


def ST(P, R, C, kind=K_TENDON, nrm=None, flat=1.0):
    """Brin : points (N,3), rayons (N,), couleur sRGB (3,) ou (N,3), type, normale d'aplatissement (N,3), aplatissement."""
    return (np.asarray(P, float), np.asarray(R, float), np.asarray(C, float), kind, nrm, float(flat))


def norm_strand(st):
    """Complète un brin donné en tuple court (P, R, C[, kind[, nrm[, flat]]])."""
    if len(st) == 6:
        return st
    st = tuple(st) + (K_TENDON, None, 1.0)[len(st) - 3:]
    return st


def flat_pick(rng, prob, lo=0.48, hi=0.7):
    return rng.uniform(lo, hi) if rng.random() < prob else 1.0


class Piece:
    """Géométrie d'une pièce du rig : brins fusionnés (cœur), brins libres, maillages fusionnés et libres."""

    def __init__(self, name):
        self.name = name
        self.fuse = []          # brins fusionnés par la grille SDF
        self.fuse_meshes = []   # (V, F, C) maillages fermés fusionnés
        self.free = []          # brins libres (tubes)
        self.free_meshes = []   # (V, F, C) maillages libres (griffes, crocs, crâne…)
        self.cut_meshes = []    # (V, F) volumes soustraits du cœur (gueule)
        self.voxel = 0.012
        self.fillet = 3


PIECES = {}


def P(name):
    if name not in PIECES:
        PIECES[name] = Piece(name)
    return PIECES[name]


def loguni(rng, a, b, size=None):
    return np.exp(rng.uniform(math.log(a), math.log(b), size))


# ----------------------------------------------------------------------------------------------------------------
# capsules d'obstacles (pour que les filaments qui pendent glissent sur les membres au lieu de les traverser)

OBSTACLES = []      # (nom, A, B, r)


def add_obstacle(name, A, B, r):
    OBSTACLES.append((name, np.asarray(A, float), np.asarray(B, float), float(r)))


def push_out(Pp, margin=0.02, skip=None):
    """Repousse les points à l'extérieur des capsules (sauf celles dont le nom commence par un des préfixes skip)."""
    Pp = Pp.copy()
    for name, A, B, r in OBSTACLES:
        if skip and any(name.startswith(k) for k in skip):
            continue
        AB = B - A
        L2 = AB @ AB
        t = np.clip(((Pp - A) @ AB) / L2, 0, 1)
        Q = A + t[:, None] * AB
        d = Pp - Q
        dist = np.linalg.norm(d, axis=1)
        inside = dist < r + margin
        if inside.any():
            dn = d[inside] / np.maximum(dist[inside], 1e-6)[:, None]
            Pp[inside] = Q[inside] + dn * (r + margin)
    return Pp


# ----------------------------------------------------------------------------------------------------------------
# faisceaux


def bundle(piece, A, B, n, prof, rng, aspect=(1.0, 1.0), twist=(-0.35, 0.35), rad=(0.03, 0.10), rf=(0.6, 1.0),
           ext=(0.12, 0.12), partial=0.25, ds=0.045, fwd=(0.0, 0.0, -1.0), bend=None, base=None, free=False,
           theta=None, bulge=0.25, end_converge=0.55, wobble=0.16, flat_prob=0.6, kind=K_TENDON):
    """n tendons torsadés autour de A -> B. prof(u, th) = rayon de l'enveloppe ; rf = profondeur (fraction).
    Les bouts dépassent de ext (recouvrement aux articulations) et convergent vers l'axe (cachés dans le voisin)."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    L = float(np.linalg.norm(B - A))
    ths = (np.arange(n) + rng.uniform(0.15, 0.85, n)) / n * TAU
    rng.shuffle(ths)
    out = []
    twist = (min(twist), max(twist))
    tw_dom = rng.uniform(*twist)                 # torsion dominante (corde), petites variations par tendon
    tw_amp = 0.35 * (twist[1] - twist[0])
    for k in range(n):
        th0 = ths[k] if theta is None else theta(k, rng)
        tw = tw_dom + rng.uniform(-tw_amp, tw_amp) * 0.5
        r_f = rng.uniform(*rf)
        tr = loguni(rng, *rad)
        e0 = ext[0] / L * rng.uniform(0.6, 1.0)
        e1 = ext[1] / L * rng.uniform(0.6, 1.0)
        tapered = rng.random() < partial
        if tapered:
            s0 = rng.uniform(-e0, 0.7)
            s1 = min(1 + e1, s0 + rng.uniform(0.25, 0.95))
        else:
            s0, s1 = -e0, 1 + e1
        m = max(6, int((s1 - s0) * L / ds) + 1)
        s = np.linspace(s0, s1, m)
        u = np.clip(s, 0.0, 1.0)
        nz = Noise1D(rng, 3, 0.3, 1.2)
        th = th0 + TAU * tw * s + wobble * nz(s)
        rr = prof(u, th) * r_f * (1 + 0.07 * snoise(rng, s, 3, 1, 4))
        # aux articulations les bouts plongent vers l'axe
        conv = np.ones_like(s)
        if e0 > 0:
            conv *= 1 - end_converge * smoothstep(-s / max(e0, 1e-6))
        if e1 > 0:
            conv *= 1 - end_converge * smoothstep((s - 1) / max(e1, 1e-6))
        rr = rr * conv
        if tapered:            # tendon partiel : naît et meurt sous les autres
            dive = smoothstep((s - s0) / 0.12) * smoothstep((s1 - s) / 0.15)
            rr = rr * (0.55 + 0.45 * dive)
        rdir = aspect[0] * np.cos(th)[:, None] * X[None] + aspect[1] * np.sin(th)[:, None] * F[None]
        Pp = A[None] + np.outer(s * L, T) + rr[:, None] * rdir
        if bend is not None:
            Pp = Pp + bend(u)
        radius = tr * (0.82 + 0.18 * snoise(rng, s, 3, 2, 8))
        if bulge and rng.random() < bulge:       # renflement local (nœud de fibres)
            c = rng.uniform(0.1, 0.9)
            radius = radius * (1 + rng.uniform(0.3, 0.8) * np.exp(-((s - c) / rng.uniform(0.04, 0.1)) ** 2))
        if tapered:
            radius = radius * (0.25 + 0.75 * smoothstep((s - s0) / 0.1) * smoothstep((s1 - s) / 0.14))
        endt = np.ones_like(s)
        endt *= 0.45 + 0.55 * smoothstep((s - s0) / max(0.6 * e0, 0.02))
        endt *= 0.45 + 0.55 * smoothstep((s1 - s) / max(0.6 * e1, 0.02))
        radius = radius * endt
        depth = (r_f - rf[0]) / max(rf[1] - rf[0], 1e-6)
        col = tendon_color(rng, 0.45 + 0.55 * depth, base)
        fl = flat_pick(rng, flat_prob) if free else 1.0
        st = ST(Pp, np.maximum(radius, 0.006) / (fl ** 0.5), col, kind, unit(rdir), fl)
        (piece.free if free else piece.fuse).append(st)
        out.append(st)
    return out


def arcs(piece, A, B, n, prof, rng, rad=(0.022, 0.045), height=(0.08, 0.3), span=(0.18, 0.45), u_range=(0.05, 0.95),
         th_range=(0.0, TAU), fwd=(0.0, 0.0, -1.0), aspect=(1.0, 1.0), free=False, base=None, twist=(-0.4, 0.4)):
    """Tendons qui se décollent du faisceau en arc puis y rentrent (on voit au travers)."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    L = float(np.linalg.norm(B - A))
    for _ in range(n):
        sp = rng.uniform(*span)
        u0 = rng.uniform(u_range[0], max(u_range[0], u_range[1] - sp))
        u1 = u0 + sp
        th0 = rng.uniform(*th_range)
        tw = rng.uniform(*twist) * sp
        h = rng.uniform(*height)
        m = max(10, int(sp * L / 0.035))
        t = np.linspace(0, 1, m)
        u = u0 + (u1 - u0) * t
        th = th0 + TAU * tw * t
        lift = h * np.sin(math.pi * t) ** 0.8
        rr = prof(u, th) * 0.92 + lift
        rdir = aspect[0] * np.cos(th)[:, None] * X[None] + aspect[1] * np.sin(th)[:, None] * F[None]
        Pp = A[None] + np.outer(u * L, T) + rr[:, None] * rdir
        r0 = loguni(rng, *rad)
        radius = r0 * (0.75 + 0.25 * np.sin(math.pi * t)) * (0.9 + 0.1 * snoise(rng, t, 2, 2, 6))
        col = tendon_color(rng, 1.0, base)
        fl = flat_pick(rng, 0.5) if free else 1.0
        (piece.free if free else piece.fuse).append(ST(Pp, radius / fl ** 0.5, col, K_TENDON, unit(rdir), fl))


def wraps(piece, A, B, n, prof, rng, rad=(0.012, 0.026), turns=(0.8, 2.4), cover=(0.3, 1.0), lift=(1.0, 1.08),
          fwd=(0.0, 0.0, -1.0), aspect=(1.0, 1.0), fuse_min=0.02, base=None):
    """Fibres fines qui s'enroulent en spirale par-dessus le faisceau (croisées)."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    L = float(np.linalg.norm(B - A))
    for _ in range(n):
        cv = rng.uniform(*cover)
        u0 = rng.uniform(0, 1 - cv)
        u1 = u0 + cv
        tn = rng.uniform(*turns) * rng.choice([-1, 1]) * cv
        th0 = rng.uniform(0, TAU)
        m = max(10, int(cv * L / 0.03 + abs(tn) * 24))
        t = np.linspace(0, 1, m)
        u = u0 + (u1 - u0) * t
        th = th0 + TAU * tn * t
        rr = prof(u, th) * rng.uniform(*lift)
        rdir = aspect[0] * np.cos(th)[:, None] * X[None] + aspect[1] * np.sin(th)[:, None] * F[None]
        Pp = A[None] + np.outer(u * L, T) + rr[:, None] * rdir
        r0 = loguni(rng, *rad)
        radius = r0 * (0.35 + 0.65 * smoothstep(t / 0.12) * smoothstep((1 - t) / 0.12))
        col = tendon_color(rng, 0.9, base)
        fl = flat_pick(rng, 0.7, 0.45, 0.65)
        (piece.fuse if r0 >= fuse_min else piece.free).append(ST(Pp, radius / fl ** 0.5, col, K_TENDON, unit(rdir), fl))


def drip(piece, P0, out, rng, length, r0, drop=None, base=None, sway=0.1, push=True, skip=None, bead=0.3):
    """Filament visqueux : part un peu vers l'extérieur, tombe, s'affine, perle parfois, finit en goutte."""
    P0 = np.asarray(P0, float)
    out = np.asarray(out, float) * np.array([1.0, 0.25, 1.0])
    out = unit(out) if np.linalg.norm(out) > 1e-6 else np.array([0.0, 0.0, -1.0])
    down = np.array([0.0, -1.0, 0.0])
    m = max(10, int(length / 0.04))
    t = np.linspace(0.0, 1.0, m)
    side = np.cross(out, down)
    side = unit(side) if np.linalg.norm(side) > 1e-3 else np.array([1.0, 0, 0])
    ob = rng.uniform(0.08, 0.2) * length
    Pp = (P0[None] + out[None] * (ob * np.sin(0.5 * math.pi * np.minimum(t * 2.5, 1.0)))[:, None]
          + down[None] * (length * t ** 1.25)[:, None]
          + side[None] * (sway * length * snoise(rng, t, 2, 0.4, 1.3) * t)[:, None])
    Pp[:, 1] = np.maximum(Pp[:, 1], 0.03)
    if push and OBSTACLES:
        Pp = push_out(Pp, 0.015, skip)
    radius = r0 * (1 - t) ** 0.9 * (1 + 0.15 * snoise(rng, t, 2, 2, 6)) + 0.0035
    if bead and rng.random() < bead:
        c = rng.uniform(0.35, 0.8)
        radius = radius + r0 * rng.uniform(0.4, 0.9) * np.exp(-((t - c) / 0.025) ** 2)
    radius[:2] = np.maximum(radius[:2], r0 * 1.15)
    if drop is None:
        drop = rng.random() < 0.45
    if drop:
        rd = max(0.012, r0 * rng.uniform(0.5, 0.85))
        k = 8
        tail = np.linspace(0, 1, k + 1)[1:]
        Pd = Pp[-1][None] + down[None] * (rd * 3.4 * tail)[:, None]
        Rd = rd * np.sin(math.pi * np.clip(tail ** 0.8 * 1.04, 0, 1)) ** 0.9 + 0.0015
        Rd[0] = max(Rd[0], radius[-1])
        Pp = np.vstack([Pp, Pd])
        radius = np.concatenate([radius, Rd])
    col = tendon_color(rng, 0.85, base)
    piece.free.append(ST(Pp, radius, col, K_SLIME))
    return Pp


# ----------------------------------------------------------------------------------------------------------------
# maillages simples (numpy)


def ellipsoid(c, axes, radii, nu=12, nv=8, noise=0.0, rng=None):
    c = np.asarray(c, float)
    u = np.linspace(0.0, TAU, nu, endpoint=False)
    w = np.linspace(0.0, math.pi, nv + 1)[1:-1]
    U, W = np.meshgrid(u, w, indexing='ij')
    d = np.stack([np.sin(W) * np.cos(U), np.sin(W) * np.sin(U), np.cos(W)], -1).reshape(-1, 3)
    d = np.vstack([d, [[0, 0, 1.0]], [[0, 0, -1.0]]])
    sc = np.ones(len(d))
    if noise and rng is not None:
        ph = rng.uniform(0, TAU, 3)
        sc = 1 + noise * (np.sin(3 * d[:, 0] + ph[0]) * np.sin(3 * d[:, 1] + ph[1]) * np.sin(3 * d[:, 2] + ph[2]))
    A = np.stack([np.asarray(x, float) * r for x, r in zip(axes, radii)])
    v = c + (d * sc[:, None]) @ A
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
    e = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    if np.einsum('ij,ij->i', e, v[f[:, 0]] - c).sum() < 0:
        f = f[:, ::-1].copy()
    return v, f


def knob(piece, c, axes, radii, rng, color=None, fuse=True, nu=14, nv=10, noise=0.12, kind=K_TENDON):
    v, f = ellipsoid(c, axes, radii, nu, nv, noise, rng)
    col = tendon_color(rng, 1.0) if color is None else color
    tang = np.broadcast_to(unit(np.asarray(axes[2], float)), (len(v), 3)).copy()
    (piece.fuse_meshes if fuse else piece.free_meshes).append((v, f, np.broadcast_to(col, (len(v), 3)).copy(), kind, tang))


def rope_bundle(piece, A, B, prof, rng, n_ropes=4, per_rope=(3, 5), rope_rf=(0.5, 0.78), rope_r=(0.28, 0.45),
                rope_twist=(-0.3, 0.3), tps=(0.5, 1.6), strand_rad=(0.32, 0.5), ext=(0.12, 0.12), ds=0.04,
                fwd=(0.0, 0.0, -1.0), bend=None, aspect=(1.0, 1.0), base=None, free=True, partial=0.25,
                separate=0.3, sep_h=(0.08, 0.25), end_converge=0.55, theta0=None):
    """Cordes de tendons : n_ropes cordes enroulées autour de l'axe A -> B, chacune faite de 3 à 5 tendons tressés.
    Certaines cordes se décollent du membre sur une partie (trous), d'autres naissent ou meurent en chemin."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    L = float(np.linalg.norm(B - A))
    ths = (np.arange(n_ropes) + rng.uniform(0.2, 0.8, n_ropes)) / n_ropes * TAU
    if theta0 is not None:
        ths = ths + theta0
    rope_twist = (min(rope_twist), max(rope_twist))
    for i in range(n_ropes):
        th0 = ths[i]
        tw = rng.uniform(*rope_twist)
        rf = rng.uniform(*rope_rf)
        rr_rel = rng.uniform(*rope_r)
        e0 = ext[0] / L * rng.uniform(0.7, 1.0)
        e1 = ext[1] / L * rng.uniform(0.7, 1.0)
        tapered = rng.random() < partial
        if tapered:
            if rng.random() < 0.5:
                s0, s1 = -e0, rng.uniform(0.45, 0.9)
            else:
                s0, s1 = rng.uniform(0.1, 0.55), 1 + e1
        else:
            s0, s1 = -e0, 1 + e1
        m = max(8, int((s1 - s0) * L / ds) + 1)
        s = np.linspace(s0, s1, m)
        u = np.clip(s, 0, 1)
        th = th0 + TAU * tw * s + 0.25 * snoise(rng, s, 3, 0.4, 1.4)
        env = prof(u, th)
        conv = np.ones_like(s)
        if e0 > 0:
            conv *= 1 - end_converge * smoothstep(-s / max(e0, 1e-6))
        if e1 > 0:
            conv *= 1 - end_converge * smoothstep((s - 1) / max(e1, 1e-6))
        lift = np.zeros_like(s)
        if rng.random() < separate:          # la corde se décolle du membre (on voit au travers)
            c = rng.uniform(0.2, 0.8)
            w = rng.uniform(0.12, 0.25)
            lift = rng.uniform(*sep_h) * np.clip(1 - ((s - c) / w) ** 2, 0, 1) ** 1.5
        rad_c = env * rf * conv + lift
        center = (A[None] + np.outer(s * L, T)
                  + rad_c[:, None] * (aspect[0] * np.cos(th)[:, None] * X[None] + aspect[1] * np.sin(th)[:, None] * F[None]))
        if bend is not None:
            center = center + bend(u)
        Rr = env * rr_rel * (0.85 + 0.15 * snoise(rng, s, 2, 1, 4)) * (0.5 + 0.5 * conv)
        if tapered:
            k = smoothstep((s - s0) / 0.15) * smoothstep((s1 - s) / 0.18)
            Rr = Rr * (0.3 + 0.7 * k)
        Tc, Nc, Bc = frames(center)
        ns = int(rng.integers(per_rope[0], per_rope[1] + 1))
        sgn = rng.choice([-1, 1])
        rate = rng.uniform(*tps) * sgn
        phase0 = rng.uniform(0, TAU)
        arc_s = s * L
        for j in range(ns):
            ph = phase0 + TAU * j / ns + rng.uniform(-0.25, 0.25)
            ang = ph + TAU * rate * arc_s + 0.2 * snoise(rng, s, 2, 0.5, 2)
            off = Rr * rng.uniform(0.45, 0.72)
            Pp = center + off[:, None] * (np.cos(ang)[:, None] * Nc + np.sin(ang)[:, None] * Bc)
            r = Rr * rng.uniform(*strand_rad) * (0.85 + 0.15 * snoise(rng, s, 3, 2, 7))
            endt = (0.4 + 0.6 * smoothstep((s - s0) / max(0.7 * e0, 0.03))) * \
                   (0.4 + 0.6 * smoothstep((s1 - s) / max(0.7 * e1, 0.03)))
            r = r * endt
            col = tendon_color(rng, 0.65 + 0.35 * rf, base)
            (piece.free if free else piece.fuse).append(ST(Pp, np.maximum(r, 0.006), col))


def braid(piece, center, rng, strands=3, rb=0.035, turns_per_stud=2.0, tube_r=0.028, base=None, taper=None,
          free=True, jitter=0.15):
    """Tresse de quelques tendons autour d'une ligne centrale (côtes, doigts, clavicules, racines)."""
    C = np.asarray(center, float)
    T, N, B = frames(C)
    s = arclen(C)
    t = s / max(s[-1], 1e-9)
    scale = np.ones(len(C)) if taper is None else taper(t)
    ph0 = rng.uniform(0, TAU)
    sgn = rng.choice([-1, 1])
    for j in range(strands):
        ph = ph0 + TAU * j / strands + rng.uniform(-0.3, 0.3)
        a = ph + sgn * TAU * turns_per_stud * s + 0.3 * snoise(rng, t, 2, 0.5, 2)
        off = rb * scale * (1 + jitter * snoise(rng, t, 2, 2, 6))
        Pp = C + off[:, None] * (np.cos(a)[:, None] * N + np.sin(a)[:, None] * B)
        r = tube_r * rng.uniform(0.8, 1.2) * scale * (0.85 + 0.15 * snoise(rng, t, 3, 3, 9))
        col = tendon_color(rng, 0.9, base)
        (piece.free if free else piece.fuse).append(ST(Pp, np.maximum(r, 0.005), col))


def claw(piece, base_p, direction, curl_axis, rng, length=0.5, r0=0.065, curl=1.0, flat=0.75, m=16, sides=8,
         kind_claw=K_CLAW, col=None, tip=None):
    """Griffe : cône courbe, pointu, un peu aplati sur les côtés ; sombre (col, CLAW par défaut) avec la pointe plus
    claire (tip, CLAW_TIP par défaut)."""
    t = np.linspace(0.0, 1.0, m)
    d = unit(direction)
    ca = unit(curl_axis)
    pts = [np.asarray(base_p, float)]
    step = length / (m - 1)
    dirs = [d]
    for k in range(1, m):
        d = rot(ca, curl / (m - 1) * (0.6 + 0.8 * t[k])) @ d
        pts.append(pts[-1] + d * step)
        dirs.append(d)
    Pp = np.array(pts)
    radius = r0 * (1 - t) ** 1.1 + 0.0015
    # section elliptique : aplatie selon l'axe de courbure
    T, N, Bn = frames(Pp)
    a = np.linspace(0, TAU, sides, endpoint=False)
    side_dir = np.array([unit(ca - (ca @ Ti) * Ti) for Ti in T])
    other = np.cross(T, side_dir)
    V = (Pp[:, None, :] + radius[:, None, None] * (flat * np.cos(a)[None, :, None] * side_dir[:, None, :]
                                                  + np.sin(a)[None, :, None] * other[:, None, :])).reshape(-1, 3)
    F = []
    for i in range(m - 1):
        for j in range(sides):
            a0, a1 = i * sides + j, i * sides + (j + 1) % sides
            b0, b1 = a0 + sides, a1 + sides
            F += [(a0, a1, b1), (a0, b1, b0)]
    nv = len(V)
    V = np.vstack([V, Pp[:1]])
    for j in range(sides):
        F.append((nv, (j + 1) % sides, j))
    F = np.array(F, np.int64)
    e = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    cen = np.repeat(Pp, sides, axis=0)
    cen = np.vstack([cen, Pp[:1] - T[:1] * 0.01])
    if np.einsum('ij,ij->i', e, V[F[:, 0]] - cen[F[:, 0]]).sum() < 0:
        F = F[:, ::-1].copy()
    tt = np.concatenate([np.repeat(t, sides), [0.0]])
    k = np.clip((tt - 0.55) / 0.45, 0, 1) ** 1.6
    c0 = CLAW if col is None else np.asarray(col, float)
    c1 = CLAW_TIP if tip is None else np.asarray(tip, float)
    col = c0[None] * rng.uniform(0.8, 1.2) * (1 - k[:, None]) + c1[None] * k[:, None]
    tang = np.vstack([np.repeat(T, sides, axis=0), T[:1]])
    piece.free_meshes.append((V, F, col, kind_claw, tang))
    return Pp


def fang(piece, base_p, direction, inward, rng, length, r0, sides=5, m=8, color=None):
    """Croc en aiguille, légèrement recourbé vers l'intérieur de la gueule."""
    t = np.linspace(0.0, 1.0, m)
    d = unit(direction)
    Pp = np.asarray(base_p, float)[None] + np.outer(t * length, d) + np.outer((t ** 2) * length * 0.22, unit(inward))
    radius = r0 * (1 - t) ** 1.15 + 0.0012
    base = BONE if color is None else color
    col = np.clip(np.outer(0.55 + 0.6 * t, base * rng.uniform(0.75, 1.1)), 0, 1)
    piece.free.append(ST(Pp, radius, col, K_TOOTH))


def spike(piece, base_p, direction, rng, length, r0, curl=None):
    d = unit(direction)
    ax = np.cross(d, [1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 0, 1.0])
    claw(piece, base_p, d, ax, rng, length=length, r0=r0, curl=rng.uniform(0.2, 0.6) if curl is None else curl,
         flat=0.85, m=10, sides=6)


def fuzz(piece, A, B, prof, rng, n, length=(0.08, 0.35), rad=(0.005, 0.012), u_range=(0.0, 1.0), th_range=(0.0, TAU),
         fwd=(0.0, 0.0, -1.0), aspect=(1.0, 1.0), up=0.6, droop=0.5):
    """Fibres fines hérissées qui sortent de la surface (poils de tendons effilochés, retombant un peu)."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    T, F, X = seg_frame(A, B, fwd)
    for _ in range(n):
        u = rng.uniform(*u_range)
        th = rng.uniform(*th_range)
        dirn = aspect[0] * math.cos(th) * X + aspect[1] * math.sin(th) * F
        p0 = A + (B - A) * u + prof(np.array([u]), np.array([th]))[0] * 0.97 * dirn
        d = unit(unit(dirn) + T * rng.uniform(-0.3, up) + rng.normal(0, 0.25, 3))
        L = rng.uniform(*length)
        m = 7
        t = np.linspace(0, 1, m)
        path = p0[None] + np.outer(t * L, d) + np.outer((t ** 2) * L * droop, np.array([0, -1.0, 0]))
        r = rng.uniform(*rad) * (1 - 0.8 * t) + 0.0015
        piece.free.append((path, r, tendon_color(rng, 0.8)))
