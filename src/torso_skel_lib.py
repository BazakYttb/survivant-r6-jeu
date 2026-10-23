"""Generic helpers for torso_skel.py (swept profiles, thick surface patches, local frames,
girdle warp, paint volumes).  All shapes in cm (torso coordinates)."""
import numpy as np
from scipy.spatial import cKDTree
import sdf as S
from sdf import ellipsoid, round_cone, capsule, sphere, ecyl, box, plate, halfspace, rot_xyz, frame
from sweep import catmull, resample, tangents, arclen
from maps import TorsoMap
import colors as C


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _ellip(q1, q2, q3, a1, a2, a3):
    """Approximate signed distance to an axis aligned ellipsoid (radii a1..a3) in local coords."""
    k0 = np.sqrt((q1 / a1) ** 2 + (q2 / a2) ** 2 + (q3 / a3) ** 2)
    k1 = np.sqrt((q1 / a1 ** 2) ** 2 + (q2 / a2 ** 2) ** 2 + (q3 / a3 ** 2) ** 2)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def _prof(v, s01):
    """v: scalar | callable(s01) | list of (s, value) knots."""
    if callable(v):
        return np.asarray(v(s01), float) * np.ones_like(s01)
    if np.ndim(v) == 0:
        return np.full_like(s01, float(v))
    k = np.asarray(v, float)
    return np.interp(s01, k[:, 0], k[:, 1])


# --------------------------------------------------------------------------- swept profile
class Swept:
    """Elliptic cross-section swept along a Catmull-Rom spline through pts (cm).
    rn: half size along N (normal hint direction), rb: along B = T x N.
    asym: rn grows by (1 + asym*b/rb) (thicker on +B side).
    offn/offb: section centre offset (cm) along N/B.  cap0/cap1: end cap lengths."""

    def __init__(self, pts, rn, rb, nhint, ds=0.06, asym=0.0, offn=0.0, offb=0.0, cap0=0.25, cap1=0.25,
                 nsub=20, dense=None):
        if dense is None:
            dense = catmull(np.asarray(pts, float), nsub)
        P = resample(dense, ds=ds)
        s = arclen(P)
        self.L = s[-1]
        s01 = s / max(s[-1], 1e-9)
        T = tangents(P)
        if callable(nhint):
            N = np.asarray(nhint(P, T, s01), float)
        else:
            N = np.broadcast_to(np.asarray(nhint, float), P.shape).copy()
        N = N - T * (N * T).sum(1, keepdims=True)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        B = np.cross(T, N)
        self.P, self.T, self.N, self.B, self.s01 = P, T, N, B, s01
        self.rn, self.rb = _prof(rn, s01), _prof(rb, s01)
        self.asym = _prof(asym, s01)
        self.offn, self.offb = _prof(offn, s01), _prof(offb, s01)
        self.cap0, self.cap1 = cap0, cap1
        self.ds = ds

    def point(self, s):
        return np.array([np.interp(s, self.s01, self.P[:, k]) for k in range(3)])

    def frame_at(self, s):
        i = int(np.clip(np.searchsorted(self.s01, s), 0, len(self.s01) - 1))
        return self.P[i], self.T[i], self.N[i], self.B[i]

    def sdf(self, chunk=40):
        P, T, N, B = self.P, self.T, self.N, self.B
        m = len(P)
        last = m - 1
        rmax_all = (np.maximum(self.rn * (1 + np.abs(self.asym)), self.rb) + np.abs(self.offn) + np.abs(self.offb))
        nodes = []
        for i0 in range(0, m - 1, chunk):
            i1 = min(m - 1, i0 + chunk + 2)
            idx = np.arange(i0, i1 + 1)
            tree = cKDTree(P[idx])
            rmax = float(rmax_all[idx].max()) + max(self.cap0 if i0 == 0 else 0, self.cap1 if i1 == last else 0)
            lo = P[idx].min(0) - rmax - 0.05
            hi = P[idx].max(0) + rmax + 0.05

            def f(p, l, h, idx=idx, tree=tree, rmax=rmax, i0=i0, i1=i1):
                ub = S.FAR + rmax + self.ds * 2
                d, j = tree.query(p, distance_upper_bound=ub)
                out = np.full(len(p), ub)
                ok = np.isfinite(d)
                if not ok.any():
                    return out
                jj = idx[j[ok]]
                q = p[ok] - P[jj]
                t = (q * T[jj]).sum(1)
                nn = (q * N[jj]).sum(1) - self.offn[jj]
                bb = (q * B[jj]).sum(1) - self.offb[jj]
                a2 = self.rb[jj]
                a1 = self.rn[jj] * (1 + self.asym[jj] * np.clip(bb / a2, -1, 1))
                tb = np.zeros_like(t)
                g0 = (jj == 0) & (t < 0)
                g1 = (jj == last) & (t > 0)
                tb[g0] = t[g0]; tb[g1] = t[g1]
                a3 = np.where(tb < 0, self.cap0, self.cap1)
                dd = _ellip(nn, bb, tb, a1, a2, a3)
                # chunk-internal ends: flat cut (neighbour chunk covers beyond)
                c0 = (jj == i0) & (i0 != 0) & (t < 0)
                c1 = (jj == i1) & (i1 != last) & (t > 0)
                cc = c0 | c1
                if cc.any():
                    dd[cc] = np.maximum(dd[cc], np.abs(t[cc]))
                out[ok] = dd
                return out
            nodes.append(S.SDF(f, lo, hi))
        return S.union(*nodes)


# --------------------------------------------------------------------------- thick surface patch
class Patch:
    """Thick surface from a parametric patch S(u,v) (u,v in [0,1]); thickness t(u,v) (half, cm),
    optional per-sample centre offset along the normal off(u,v). Edges are rounded."""

    def __init__(self, fn, thick, nu=60, nv=60, off=None, flip=False):
        u = np.linspace(0, 1, nu); v = np.linspace(0, 1, nv)
        U, V = np.meshgrid(u, v, indexing='ij')
        P = fn(U.ravel(), V.ravel()).reshape(nu, nv, 3)
        Pu = np.gradient(P, axis=0); Pv = np.gradient(P, axis=1)
        Nm = np.cross(Pu, Pv)
        Nm /= np.maximum(np.linalg.norm(Nm, axis=2, keepdims=True), 1e-12)
        if flip:
            Nm = -Nm
        t = thick(U, V) * np.ones_like(U)
        if off is not None:
            P = P + Nm * (off(U, V) * np.ones_like(U))[..., None]
        # local spacing
        du = np.linalg.norm(Pu, axis=2); dv = np.linalg.norm(Pv, axis=2)
        self.eps = 0.8 * np.maximum(du, dv)
        self.P, self.N, self.t, self.U, self.V = P, Nm, t, U, V
        self.nu, self.nv = nu, nv

    def point(self, u, v):
        iu = int(round(u * (self.nu - 1))); iv = int(round(v * (self.nv - 1)))
        return self.P[iu, iv], self.N[iu, iv]

    def sdf(self, blk=16):
        nodes = []
        for a in range(0, self.nu - 1, blk):
            for b in range(0, self.nv - 1, blk):
                a1 = min(self.nu, a + blk + 2); b1 = min(self.nv, b + blk + 2)
                P = self.P[a:a1, b:b1].reshape(-1, 3)
                N = self.N[a:a1, b:b1].reshape(-1, 3)
                t = self.t[a:a1, b:b1].ravel()
                e = self.eps[a:a1, b:b1].ravel()
                tree = cKDTree(P)
                rmax = float(t.max() + e.max())
                lo = P.min(0) - rmax; hi = P.max(0) + rmax

                def f(p, l, h, P=P, N=N, t=t, e=e, tree=tree, rmax=rmax):
                    ub = S.FAR + rmax
                    d, j = tree.query(p, distance_upper_bound=ub)
                    out = np.full(len(p), ub)
                    ok = np.isfinite(d)
                    if not ok.any():
                        return out
                    jj = j[ok]
                    q = p[ok] - P[jj]
                    dn = (q * N[jj]).sum(1)
                    tg = np.sqrt(np.maximum((q * q).sum(1) - dn * dn, 0))
                    tg = np.maximum(tg - e[jj], 0)
                    out[ok] = np.sqrt(tg * tg + dn * dn) - t[jj]
                    return out
                nodes.append(S.SDF(f, lo, hi))
        return S.union(*nodes)


def coons(c0, c1, d0, d1):
    """Coons patch from 4 boundary callables: c0(u) bottom (v=0), c1(u) top (v=1), d0(v) left (u=0),
    d1(v) right (u=1); each maps (N,) -> (N,3)."""
    P00 = c0(np.array([0.0]))[0]; P10 = c0(np.array([1.0]))[0]
    P01 = c1(np.array([0.0]))[0]; P11 = c1(np.array([1.0]))[0]

    def fn(u, v):
        u = np.asarray(u, float); v = np.asarray(v, float)
        uu = u[:, None]; vv = v[:, None]
        return ((1 - vv) * c0(u) + vv * c1(u) + (1 - uu) * d0(v) + uu * d1(v)
                - ((1 - uu) * (1 - vv) * P00 + uu * (1 - vv) * P10 + (1 - uu) * vv * P01 + uu * vv * P11))
    return fn


def curve(pts, nsub=30):
    """Arc-length parametrised Catmull-Rom curve through pts -> callable(u in [0,1]) -> (N,3)."""
    d = catmull(np.asarray(pts, float), nsub)
    s = arclen(d); s = s / s[-1]

    def c(u):
        u = np.clip(np.asarray(u, float), 0, 1)
        return np.stack([np.interp(u, s, d[:, k]) for k in range(3)], 1)
    return c


# --------------------------------------------------------------------------- local frames
class Fr:
    """Local frame: c origin (world cm), R rows = local axes in world."""

    def __init__(self, c, R):
        self.c = np.asarray(c, float)
        self.R = np.asarray(R, float)

    def w(self, p):
        return self.c + np.asarray(p, float) @ self.R

    def v(self, d):
        return np.asarray(d, float) @ self.R

    def loc(self, p):
        return (np.asarray(p, float) - self.c) @ self.R.T

    def rot(self, Rl=None):
        return self.R if Rl is None else np.asarray(Rl, float) @ self.R

    def E(self, c, r, rx=0, ry=0, rz=0, Rl=None):
        if Rl is None and (rx or ry or rz):
            Rl = rot_xyz(rx, ry, rz)
        return ellipsoid(self.w(c), r, self.rot(Rl))

    def Eax(self, a, b, r1, r2, xhint=(1, 0, 0), ext=0.0):
        """Ellipsoid spanning segment a-b (local), radii r1 (x), r2 (y) across."""
        a = np.asarray(a, float); b = np.asarray(b, float)
        d = b - a; L = np.linalg.norm(d)
        Rl = frame(d, xhint)
        return ellipsoid(self.w((a + b) / 2), (r1, r2, L / 2 + ext), self.rot(Rl))

    def sph(self, c, r):
        return sphere(self.w(c), r)

    def cap(self, a, b, r):
        return capsule(self.w(a), self.w(b), r)

    def rc(self, a, b, r1, r2):
        return round_cone(self.w(a), self.w(b), r1, r2)

    def ecyl(self, c, rx, ry, hz, Rl=None, rnd=0.0):
        return ecyl(self.w(c), rx, ry, hz, self.rot(Rl), rnd)

    def box(self, c, half, Rl=None, rnd=0.0):
        return box(self.w(c), half, self.rot(Rl), rnd)

    def plate(self, origin, Rl, poly, thick, rnd=0.15, bend=(0, 0), thick_fn=None):
        return plate(self.w(origin), self.rot(Rl), poly, thick, rnd, bend, thick_fn)

    def hs(self, o, n):
        return halfspace(self.w(o), self.v(n))


def custom(f_local, fr, lo_l, hi_l):
    """Custom SDF defined in local frame coords: f_local(q (N,3)) -> d.  Local bbox lo_l/hi_l."""
    corners = np.array([[x, y, z] for x in (lo_l[0], hi_l[0]) for y in (lo_l[1], hi_l[1]) for z in (lo_l[2], hi_l[2])])
    wc = fr.w(corners)

    def f(p, l, h):
        return f_local(fr.loc(p))
    return S.SDF(f, wc.min(0), wc.max(0))


def vbody_fn(rx, ry, hz, n=2.0, heart=0.0, waist=0.07, rnd=0.25, kidney=0.0, yoff=0.0):
    """Vertebral-body like elliptic/superelliptic cylinder (local z axis): waist, heart (narrower at the
    front (-y) if >0, narrower at the back if <0), kidney (posterior concavity)."""
    def f(q):
        x, y, z = q[:, 0], q[:, 1] - yoff, q[:, 2]
        zz = np.clip(z / hz, -1, 1)
        s = 1 - waist * (1 - zz * zz)
        rxe = rx * s * (1 + heart * np.clip(y / ry, -1, 1)) if heart else rx * s
        rye = ry * s
        if kidney:
            y = y + kidney * ry * np.clip(1 - (x / rx) ** 2, 0, 1) * (y > 0)
        e = ((np.abs(x) / rxe) ** n + (np.abs(y) / rye) ** n) ** (1.0 / n)
        m = np.minimum(rxe, rye)
        dxy = (e - 1) * m + rnd
        dz = np.abs(z) - hz + rnd
        w = np.stack([dxy, dz], 1)
        return np.minimum(np.maximum(dxy, dz), 0) + np.sqrt((np.maximum(w, 0) ** 2).sum(1)) - rnd
    return f


# --------------------------------------------------------------------------- girdle warp
GM = TorsoMap(girdle=True)
TM = TorsoMap()


def g2n(p):
    """Girdle-map cm -> 'normal-map cm' (same stud position under TorsoMap())."""
    p = np.array(p, float)
    one = p.ndim == 1
    p = np.atleast_2d(p).copy()
    p[:, 0] = GM._fx(p[:, 0]) / TM.sx
    return p[0] if one else p


def n2g(p):
    p = np.array(p, float)
    one = p.ndim == 1
    p = np.atleast_2d(p).copy()
    p[:, 0] = GM._ix(p[:, 0] * TM.sx)
    return p[0] if one else p


def girdle_wrap(nodeN):
    """Shape designed in normal-map cm -> evaluated in girdle-map cm (same stud-space result)."""
    def f(p, l, h):
        q = g2n(p)
        if l is None:
            return nodeN.ev(q)
        return nodeN.ev(q, g2n(l), g2n(h))
    return S.SDF(f, n2g(nodeN.lo), n2g(nodeN.hi), (nodeN,))


# --------------------------------------------------------------------------- colours
def bone_base(p, seed=0, tint=0.0):
    big = S.fbm(p * 0.18, 3, seed=seed)
    fine = S.perlin(p * 2.3, seed + 5)
    col = C.mix(C.BONE, C.BONE_DARK, np.clip(0.35 + 0.9 * big, 0, 1) * 0.45)
    col = C.mix(col, C.BONE_WHITE, np.clip(fine * 0.8, 0, 1) * 0.35)
    speck = np.clip((S.perlin(p * 7.0, seed + 9) - 0.42) * 6, 0, 1)
    col = C.mix(col, C.BONE_DARK * 0.85, speck * 0.35)
    if tint:
        col = C.mix(col, C.C(0.93, 0.88, 0.70), tint)
    return col


CART = C.C(0.80, 0.86, 0.90)


def cart_base(p, seed=0):
    col = C.mix(CART, C.C(0.92, 0.94, 0.95), np.clip(S.fbm(p * 0.8, 2, seed=seed) + 0.4, 0, 1) * 0.5)
    return C.mix(col, C.C(0.74, 0.80, 0.87), np.clip(S.perlin(p * 3.0, seed + 3), 0, 1) * 0.3)


def paint_mask(node, p, w=0.12):
    S.set_far(1e9)
    d = node.ev(p)
    return np.clip(1 - np.maximum(d, 0) / w, 0, 1)


def bone_color(seed=0, paints=(), tint=0.0, xform=None, ao_k=0.5, cav_k=0.55):
    """paints: list of (node, colour (3,) or 'cart', width, strength)."""
    def f(ctx):
        p = ctx['pc'] if xform is None else xform(ctx['pc'])
        col = bone_base(p, seed, tint)
        for node, colr, w, k in paints:
            m = paint_mask(node, p, w) * k
            if isinstance(colr, str):
                cc = cart_base(p, seed)
            else:
                cc = np.broadcast_to(np.asarray(colr, float), col.shape)
            col = C.mix(col, cc, m)
        return C.shade(col, ctx, ao_k, cav_k, 0.12)
    return f
