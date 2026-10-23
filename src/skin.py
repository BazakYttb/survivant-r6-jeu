"""Classic R6 'noob' skin: bevelled R6 blocks (exact R6 sizes), the classic rounded head and its smile face.
Shapes are defined directly in studs (Blender coords: X = character's left, Y = back, Z = up)."""
import numpy as np
import sdf as S
from sdf import box, ecyl, intersect, halfspace
from parts import Part

# classic R6 'noob' body colours (Roblox BrickColors)
YELLOW = (245 / 255, 205 / 255, 48 / 255)     # Bright yellow  - head & arms
BLUE = (13 / 255, 105 / 255, 172 / 255)       # Bright blue    - torso
GREEN = (164 / 255, 189 / 255, 71 / 255)      # Br. yellowish green - legs
FACE = (0.07, 0.07, 0.07)

HEAD_C = np.array((0.0, 0.0, 4.5))
HEAD_R = 0.63          # radius of the classic head (~1.26 stud wide, like a SpecialMesh Head at scale 1.25)
HEAD_HZ = 0.63
HEAD_RND = 0.25
BEVEL = 0.08


class StudMap:
    """Identity mapping: the shapes are written directly in studs."""
    spc = 1.0

    def __init__(self, region):
        self.region = region

    def fwd(self, p):
        return np.atleast_2d(np.asarray(p, float))

    def inv(self, q):
        return np.atleast_2d(np.asarray(q, float))


def leg(s):
    """R6 leg block; its top edges stay sharp so that no groove opens under the pelvis at the crotch."""
    return intersect(box((s * 0.5, 0, 1 + BEVEL), (0.5, 0.5, 1 + BEVEL), rnd=BEVEL), halfspace((0, 0, 2), (0, 0, 1)))


def head():
    return ecyl(HEAD_C, HEAD_R, HEAD_R, HEAD_HZ, rnd=HEAD_RND)


EYES = [(0.145, 4.625), (-0.145, 4.625)]          # (x, z) on the front of the head
EYE_R = (0.047, 0.105)
SMILE = [(-0.255, 4.405), (-0.17, 4.325), (-0.07, 4.282), (0.04, 4.282), (0.15, 4.318), (0.255, 4.41)]
SMILE_W = 0.024


def _face_region(p):
    x, z = p[:, 0], p[:, 2]
    d = np.full(len(p), 1e9)
    for ex, ez in EYES:
        e = np.sqrt(((x - ex) / EYE_R[0]) ** 2 + ((z - ez) / EYE_R[1]) ** 2)
        d = np.minimum(d, (e - 1) * min(EYE_R))
    q = np.stack([x, z], 1)
    pts = np.array(SMILE)
    for a, b in zip(pts[:-1], pts[1:]):
        ba = b - a
        t = np.clip(((q - a) @ ba) / (ba @ ba), 0, 1)
        r = q - a - np.outer(t, ba)
        d = np.minimum(d, np.sqrt((r * r).sum(1)) - SMILE_W)
    return d


def face():
    hd = head()

    def layer(p, l, h):                                  # thin decal layer on the head surface
        return np.abs(hd.ev(p) - 0.0035) - 0.0045

    shell = S.SDF(layer, HEAD_C - 0.7, HEAD_C + 0.7)
    region = S.SDF(lambda p, l, h: _face_region(p), (-0.31, -0.66, 4.24), (0.31, -0.54, 4.76))
    return intersect(shell, region, halfspace((0, -0.35, 0), (0, 1, 0)))


# ----------------------------------------------------------------------
# analytic meshes (clean topology + exact normals, like a real R6 part)

def _weld(v, f, tol=1e-6):
    key = np.round(v / tol).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return v[idx], inv.ravel()[f]


def rounded_box(lo, hi, r, sharp_top=False, k=6, n_flat=2):
    """Closed box with edges rounded by radius r (top edges kept sharp if sharp_top).
    Returns verts (N,3), faces (M,3) wound outward, per-corner normals (M,3,3)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    r_lo = np.full(3, float(r)); r_hi = np.full(3, float(r))
    if sharp_top:
        r_hi[2] = 0.0
    ilo, ihi = lo + r_lo, hi - r_hi
    th = np.linspace(0, np.pi / 4, k + 1)

    def samples(a):
        s = list(ilo[a] - r_lo[a] * np.tan(th[::-1])) if r_lo[a] > 0 else [lo[a]]
        s += list(np.linspace(ilo[a], ihi[a], n_flat + 2)[1:-1])
        s += list(ihi[a] + r_hi[a] * np.tan(th)) if r_hi[a] > 0 else [hi[a]]
        return np.array(s)

    V, F, CN = [], [], []
    off = 0
    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3
        for side, sign in ((lo, -1), (hi, 1)):
            sb, sc = samples(b), samples(c)
            B_, C_ = np.meshgrid(sb, sc, indexing='ij')
            P = np.zeros(B_.shape + (3,))
            P[..., a] = side[a]; P[..., b] = B_; P[..., c] = C_
            P = P.reshape(-1, 3)
            Cc = np.clip(P, ilo, ihi)
            D = P - Cc
            L = np.linalg.norm(D, axis=1)
            nrm = np.zeros_like(P); nrm[:, a] = sign
            rad = (r_lo if sign < 0 else r_hi)[a]
            if rad > 0:                                     # rounded side: q on the rounding, normal along D
                m = L > 1e-12
                Q = P.copy()
                Q[m] = Cc[m] + r * D[m] / L[m, None]
                nrm[m] = D[m] / L[m, None]
            else:                                           # sharp side: flat face, outline with rounded corners
                Dn = np.abs(D).max(1)
                sc_ = np.where(L > 1e-12, Dn / np.maximum(L, 1e-12), 1.0)
                Q = Cc + D * sc_[:, None]
            nb, nc = len(sb), len(sc)
            I = np.arange(nb * nc).reshape(nb, nc)
            q0, q1, q2, q3 = I[:-1, :-1].ravel(), I[1:, :-1].ravel(), I[1:, 1:].ravel(), I[:-1, 1:].ravel()
            tri = np.concatenate([np.stack([q0, q1, q2], 1), np.stack([q0, q2, q3], 1)])
            if sign < 0:
                tri = tri[:, ::-1]
            V.append(Q); F.append(tri + off); CN.append(nrm[tri]); off += len(Q)
    v, f = _weld(np.concatenate(V), np.concatenate(F))
    cn = np.concatenate(CN)
    good = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    return v, f[good], cn[good]


def revolved_head(c=HEAD_C, R=HEAD_R, hz=HEAD_HZ, rr=HEAD_RND, nseg=72, k=12):
    """Classic R6 head: vertical cylinder with rounded top and bottom edges (surface of revolution)."""
    prof = []                                                      # (rho, z, n_rho, n_z) bottom pole -> top pole
    for t in np.linspace(0, R - rr, 5)[:-1]:
        prof.append((t, -hz, 0.0, -1.0))
    for ph in np.linspace(-np.pi / 2, 0, k + 1)[:-1]:
        prof.append((R - rr + rr * np.cos(ph), -hz + rr + rr * np.sin(ph), np.cos(ph), np.sin(ph)))
    for z in np.linspace(-hz + rr, hz - rr, 5)[:-1]:
        prof.append((R, z, 1.0, 0.0))
    for ph in np.linspace(0, np.pi / 2, k + 1)[:-1]:
        prof.append((R - rr + rr * np.cos(ph), hz - rr + rr * np.sin(ph), np.cos(ph), np.sin(ph)))
    for t in np.linspace(R - rr, 0, 5):
        prof.append((t, hz, 0.0, 1.0))
    prof = np.array(prof)
    ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    ca, sa = np.cos(ang), np.sin(ang)
    V, N = [], []
    ring = []
    for rho, z, nr, nz in prof:
        if rho < 1e-9:
            ring.append([len(V)] * nseg)
            V.append((c[0], c[1], c[2] + z)); N.append((0, 0, nz))
        else:
            ring.append(list(range(len(V), len(V) + nseg)))
            V += list(zip(c[0] + rho * ca, c[1] + rho * sa, np.full(nseg, c[2] + z)))
            N += list(zip(nr * ca, nr * sa, np.full(nseg, nz)))
    V, N = np.array(V, float), np.array(N, float)
    F = []
    for i in range(len(prof) - 1):
        r0, r1 = ring[i], ring[i + 1]
        for j in range(nseg):
            a, b, cc, d = r0[j], r0[(j + 1) % nseg], r1[(j + 1) % nseg], r1[j]
            F.append((a, b, cc)); F.append((a, cc, d))
    F = np.array(F)
    good = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    F = F[good]
    return V, F, N[F]


def flat(rgb):
    """Plain colour, no baked shading: Roblox lights the skin itself, like a real R6 part."""
    rgb = np.asarray(rgb, float)
    return lambda ctx: np.tile(rgb, (len(ctx['ps']), 1))


def analytic(fn, rgb):
    """Part.mesh callback: (verts, faces, colours, per-corner normals)."""
    def build():
        v, f, cn = fn()
        return v, f, np.tile(np.asarray(rgb, float), (len(v), 1)), cn
    return build


def parts():
    P = [Part('Skin_Head', StudMap('Head'), mesh=analytic(revolved_head, YELLOW), cat='skin', base=YELLOW,
              info='Peau R6 : tête classique (jaune)'),
         Part('Skin_Face', StudMap('Head'), sdf=face, color=flat(FACE), target=3000, h=0.0016, far=0.05, cat='skin',
              base=FACE, smooth=1, min_faces=20, info='Peau R6 : visage classique (yeux et sourire)'),
         Part('Skin_Torso', StudMap('Torso'), mesh=analytic(lambda: rounded_box((-1, -0.5, 2), (1, 0.5, 4), BEVEL), BLUE),
              cat='skin', base=BLUE, info='Peau R6 : torse (bleu)')]
    for s, reg in ((1, 'LeftArm'), (-1, 'RightArm')):
        P.append(Part(f'Skin_{reg}', StudMap(reg), cat='skin', base=YELLOW,
                      mesh=analytic(lambda s=s: rounded_box((s * 1.5 - 0.5, -0.5, 2), (s * 1.5 + 0.5, 0.5, 4), BEVEL), YELLOW),
                      info=f'Peau R6 : bras {"gauche" if s > 0 else "droit"} (jaune)'))
    for s, reg in ((1, 'LeftLeg'), (-1, 'RightLeg')):
        P.append(Part(f'Skin_{reg}', StudMap(reg), cat='skin', base=GREEN,
                      mesh=analytic(lambda s=s: rounded_box((s * 0.5 - 0.5, -0.5, 0), (s * 0.5 + 0.5, 0.5, 2), BEVEL,
                                                            sharp_top=True), GREEN),
                      info=f'Peau R6 : jambe {"gauche" if s > 0 else "droite"} (vert)'))
    return P


# soft containment of the anatomy inside the skin, applied to the finished meshes (stud space):
# region -> [(axis, sign, limit, softness)]; sign +1 keeps coordinates above the limit, -1 below.
CONTAIN = {
    'LeftLeg': [(2, 1, 0.006, 0.01)], 'RightLeg': [(2, 1, 0.006, 0.01)],          # toes and soles above the floor
    'LeftArm': [(2, 1, 2.006, 0.008)], 'RightArm': [(2, 1, 2.006, 0.008)],        # finger tips inside the arm block
    'Torso': [(1, 1, -0.492, 0.01)],                                               # nothing through the belly
}


def contain(v, region):
    """Monotonic soft clamp (softplus) per axis: identity far from the limit, so neighbouring parts stay consistent."""
    v = np.array(v, float)
    for ax, sg, lim, w in CONTAIN.get(region, ()):
        x = sg * v[:, ax]
        v[:, ax] = sg * (sg * lim + w * np.logaddexp(0, (x - sg * lim) / w))
    return v


def contain_reach(v, region):
    """Largest displacement contain() would apply to these vertices."""
    return float(np.abs(contain(v, region) - v).max()) if len(v) else 0.0
