"""Signed distance field toolkit (numpy).

Every shape is an SDF node evaluated on (N,3) point arrays.  Nodes carry an
axis-aligned bounding box so that far-away primitives can be skipped while
evaluating a block of the grid (their value is replaced by a lower bound,
which keeps the sign and the near-surface values exact).
"""
import numpy as np

FAR = 2.0  # cm: band outside which exact values are not needed (set per part)


def set_far(v):
    global FAR
    FAR = float(v)


def _norm(v):
    return np.sqrt(np.einsum('ij,ij->i', v, v))


def _box_gap(alo, ahi, blo, bhi):
    d = np.maximum(0.0, np.maximum(alo - bhi, blo - ahi))
    return float(np.sqrt((d * d).sum()))


class SDF:
    def __init__(self, f, lo, hi, kids=(), pad=0.0):
        self.f = f
        self.lo = np.asarray(lo, float)
        self.hi = np.asarray(hi, float)
        self.kids = kids
        self.pad = pad

    def maxpath(self):
        return self.pad + max([k.maxpath() for k in self.kids], default=0.0)

    def ev(self, p, blo=None, bhi=None):
        if blo is not None:
            g = _box_gap(blo, bhi, self.lo, self.hi)
            if g > FAR:
                return np.full(len(p), g, dtype=p.dtype)
        return self.f(p, blo, bhi)

    def __call__(self, p):
        return self.ev(p)

    # operators -------------------------------------------------------
    def __or__(self, o):
        return union(self, o)

    def __sub__(self, o):
        return subtract(self, o)

    def __and__(self, o):
        return intersect(self, o)

    def offset(self, r):
        a = self
        return SDF(lambda p, l, h: a.ev(p, l, h) - r, a.lo - max(r, 0), a.hi + max(r, 0), (a,), abs(r))

    def translate(self, t):
        t = np.asarray(t, float)
        a = self
        return SDF(lambda p, l, h: a.ev(p - t, None if l is None else l - t, None if h is None else h - t),
                   a.lo + t, a.hi + t, (a,))


# ----------------------------------------------------------------------
# rotation helpers (R rows = local axes expressed in world)

def frame(z, xhint=(1, 0, 0)):
    z = np.asarray(z, float); z = z / np.linalg.norm(z)
    x = np.asarray(xhint, float)
    x = x - z * np.dot(x, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0, 1, 0.]) - z * z[1]
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z])


def rot_xyz(rx=0, ry=0, rz=0):
    """Rotation matrix (degrees), applied X then Y then Z; returns R rows=local axes."""
    rx, ry, rz = np.radians([rx, ry, rz])
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    M = Rz @ Ry @ Rx          # world = M @ local
    return M.T                # rows = local axes in world


def _local(p, c, R):
    q = p - c
    return q if R is None else q @ R.T


def _rbox(c, ext, R):
    c = np.asarray(c, float)
    if R is None:
        return c - ext, c + ext
    e = np.abs(np.asarray(R).T) @ np.asarray(ext, float)
    return c - e, c + e


# ----------------------------------------------------------------------
# primitives

def sphere(c, r):
    c = np.asarray(c, float)
    return SDF(lambda p, l, h: _norm(p - c) - r, c - r, c + r)


def ellipsoid(c, r, R=None):
    c = np.asarray(c, float); r = np.asarray(r, float)
    r2 = r * r

    def f(p, l, h):
        q = _local(p, c, R)
        k0 = _norm(q / r)
        k1 = _norm(q / r2)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
    lo, hi = _rbox(c, r, R)
    return SDF(f, lo, hi)


def round_cone(a, b, r1, r2):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    if a2 <= 1e-9:  # degenerate: one sphere contains the other
        return sphere(a, r1) if r1 >= r2 else sphere(b, r2)
    il2 = 1.0 / l2

    def f(p, l, h):
        pa = p - a
        y = pa @ ba
        z = y - l2
        w = pa * l2 - np.outer(y, ba)
        x2 = np.einsum('ij,ij->i', w, w)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
        d1 = np.sqrt(x2 + z2) * il2 - r2
        d2 = np.sqrt(x2 + y2) * il2 - r1
        out = np.where(np.sign(y) * a2 * y2 < k, d2, d3)
        out = np.where(np.sign(z) * a2 * z2 > k, d1, out)
        return out
    lo = np.minimum(a - r1, b - r2); hi = np.maximum(a + r1, b + r2)
    return SDF(f, lo, hi)


def capsule(a, b, r):
    return round_cone(a, b, r, r)


def tube(points, radii, k=0.0):
    """Chain of round cones (smooth tube with variable radius)."""
    pts = [np.asarray(p, float) for p in points]
    rs = list(radii) if np.ndim(radii) else [radii] * len(pts)
    segs = [round_cone(pts[i], pts[i + 1], rs[i], rs[i + 1]) for i in range(len(pts) - 1)]
    return smooth_union_all(segs, k) if k > 0 else union(*segs)


def box(c, half, R=None, rnd=0.0):
    c = np.asarray(c, float); half = np.asarray(half, float)

    def f(p, l, h):
        q = np.abs(_local(p, c, R)) - (half - rnd)
        out = _norm(np.maximum(q, 0)) + np.minimum(q.max(1), 0)
        return out - rnd
    lo, hi = _rbox(c, half, R)
    return SDF(f, lo, hi)


def ecyl(c, rx, ry, hz, R=None, rnd=0.0):
    """Elliptic cylinder along local z (half height hz), rounded edges."""
    c = np.asarray(c, float)
    m = min(rx, ry)

    def f(p, l, h):
        q = _local(p, c, R)
        e = np.sqrt((q[:, 0] / rx) ** 2 + (q[:, 1] / ry) ** 2)
        dxy = (e - 1.0) * m + rnd
        dz = np.abs(q[:, 2]) - hz + rnd
        w = np.stack([dxy, dz], 1)
        return np.minimum(np.maximum(dxy, dz), 0) + _norm2(np.maximum(w, 0)) - rnd
    lo, hi = _rbox(c, (rx, ry, hz), R)
    return SDF(f, lo, hi)


def _norm2(w):
    return np.sqrt((w * w).sum(1))


def torus(c, Rr, r, R=None, sx=1.0):
    """Torus in local xy plane (major radius Rr, tube r). sx stretches x."""
    c = np.asarray(c, float)

    def f(p, l, h):
        q = _local(p, c, R)
        rad = np.sqrt((q[:, 0] / sx) ** 2 + q[:, 1] ** 2)
        return np.sqrt((rad - Rr) ** 2 + q[:, 2] ** 2) - r
    e = Rr * max(sx, 1) + r
    lo, hi = _rbox(c, (e, e, r), R)
    return SDF(f, lo, hi)


def capped_torus(c, Rr, r, half_angle, R=None):
    """Arc of torus in local xy plane, symmetric about +y, opening angle 2*half_angle (deg)."""
    c = np.asarray(c, float)
    s, co = np.sin(np.radians(half_angle)), np.cos(np.radians(half_angle))

    def f(p, l, h):
        q = _local(p, c, R)
        x = np.abs(q[:, 0]); y = q[:, 1]
        k = np.where(co * x > s * y, x * s + y * co, np.sqrt(x * x + y * y))
        return np.sqrt(np.maximum(x * x + y * y + q[:, 2] ** 2 + Rr * Rr - 2 * Rr * k, 0)) - r
    e = Rr + r
    lo, hi = _rbox(c, (e, e, r), R)
    return SDF(f, lo, hi)


def halfspace(o, n):
    o = np.asarray(o, float); n = np.asarray(n, float); n = n / np.linalg.norm(n)
    return SDF(lambda p, l, h: (p - o) @ n, np.full(3, -1e4), np.full(3, 1e4))


def _poly2d(q, V):
    """Signed distance of 2D points q (N,2) to polygon V (M,2)."""
    N = len(q)
    d = ((q - V[0]) ** 2).sum(1)
    s = np.ones(N)
    M = len(V)
    for i in range(M):
        j = i - 1
        e = V[j] - V[i]
        w = q - V[i]
        t = np.clip((w @ e) / (e @ e), 0, 1)
        b = w - np.outer(t, e)
        d = np.minimum(d, (b * b).sum(1))
        c1 = q[:, 1] >= V[i, 1]
        c2 = q[:, 1] < V[j, 1]
        c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def plate(origin, R, poly, thick, rnd=0.2, bend=(0.0, 0.0), thick_fn=None):
    """2D polygon (local x,y) extruded along local z with half-thickness `thick`.
    bend=(cx, cy) curves the plate: z offset = cx*x^2 + cy*y^2."""
    origin = np.asarray(origin, float); V = np.asarray(poly, float)
    cx, cy = bend

    def f(p, l, h):
        q = _local(p, origin, R)
        d2 = _poly2d(q[:, :2], V) + rnd
        z = q[:, 2] - (cx * q[:, 0] ** 2 + cy * q[:, 1] ** 2)
        t = thick if thick_fn is None else thick_fn(q[:, 0], q[:, 1])
        dz = np.abs(z) - t + rnd
        w = np.stack([d2, dz], 1)
        return np.minimum(np.maximum(d2, dz), 0) + _norm2(np.maximum(w, 0)) - rnd
    ext_xy = np.abs(V).max(0)
    ez = thick * 3 + abs(cx) * ext_xy[0] ** 2 + abs(cy) * ext_xy[1] ** 2
    lo, hi = _rbox(origin, (ext_xy[0], ext_xy[1], ez), R)
    return SDF(f, lo, hi)


# ----------------------------------------------------------------------
# boolean operators

def union(*ss):
    ss = [s for s in ss if s is not None]
    if len(ss) == 1:
        return ss[0]

    def f(p, l, h):
        d = ss[0].ev(p, l, h)
        for s in ss[1:]:
            d = np.minimum(d, s.ev(p, l, h))
        return d
    lo = np.min([s.lo for s in ss], 0); hi = np.max([s.hi for s in ss], 0)
    return SDF(f, lo, hi, ss)


def _smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smooth_union(a, b, k):
    def f(p, l, h):
        return _smin(a.ev(p, l, h), b.ev(p, l, h), k)
    return SDF(f, np.minimum(a.lo, b.lo) - k, np.maximum(a.hi, b.hi) + k, (a, b), k)


def smooth_union_all(ss, k):
    ss = [s for s in ss if s is not None]

    def f(p, l, h):
        d = ss[0].ev(p, l, h)
        for s in ss[1:]:
            d = _smin(d, s.ev(p, l, h), k)
        return d
    lo = np.min([s.lo for s in ss], 0) - k; hi = np.max([s.hi for s in ss], 0) + k
    return SDF(f, lo, hi, tuple(ss), k)


def subtract(a, *bs):
    def f(p, l, h):
        d = a.ev(p, l, h)
        for b in bs:
            d = np.maximum(d, -b.ev(p, l, h))
        return d
    return SDF(f, a.lo, a.hi, (a,) + bs)


def smooth_subtract(a, b, k):
    def f(p, l, h):
        da = a.ev(p, l, h); db = b.ev(p, l, h)
        hh = np.clip(0.5 - 0.5 * (db + da) / k, 0, 1)
        return da * (1 - hh) + (-db) * hh + k * hh * (1 - hh)
    return SDF(f, a.lo, a.hi, (a, b), k)


def intersect(a, *bs):
    def f(p, l, h):
        d = a.ev(p, l, h)
        for b in bs:
            d = np.maximum(d, b.ev(p, l, h))
        return d
    lo = a.lo.copy(); hi = a.hi.copy()
    for b in bs:
        lo = np.maximum(lo, b.lo); hi = np.minimum(hi, b.hi)
    return SDF(f, lo, hi, (a,) + bs)


def smooth_intersect(a, b, k):
    def f(p, l, h):
        da = a.ev(p, l, h); db = b.ev(p, l, h)
        hh = np.clip(0.5 - 0.5 * (db - da) / k, 0, 1)
        return db * (1 - hh) + da * hh + k * hh * (1 - hh)
    return SDF(f, np.maximum(a.lo, b.lo), np.minimum(a.hi, b.hi), (a, b), k)


def shell(a, t):
    """Hollow shell of thickness t inside the surface of a."""
    def f(p, l, h):
        d = a.ev(p, l, h)
        return np.maximum(d, -(d + t))
    return SDF(f, a.lo, a.hi, (a,))


def displace(a, fn, amp):
    """d += fn(p) where |fn| <= amp; fn evaluated only near the surface."""
    def f(p, l, h):
        d = a.ev(p, l, h)
        m = np.abs(d) < amp + FAR * 0.5
        if m.any():
            d = d.copy()
            d[m] += fn(p[m])
        return d
    return SDF(f, a.lo - amp, a.hi + amp, (a,), amp)


def warp(a, fn, lo=None, hi=None):
    """Evaluate a at fn(p) (domain deformation)."""
    def f(p, l, h):
        return a.ev(fn(p), None, None)
    return SDF(f, a.lo if lo is None else lo, a.hi if hi is None else hi, (a,))


def mirror_x(a):
    """Union of a and its mirror across x=0."""
    def f(p, l, h):
        q = p.copy(); q[:, 0] = -q[:, 0]
        return np.minimum(a.ev(p, l, h), a.ev(q, None if l is None else np.array([-h[0], l[1], l[2]]),
                                             None if h is None else np.array([-l[0], h[1], h[2]])))
    lo = np.minimum(a.lo, [-a.hi[0], a.lo[1], a.lo[2]]); hi = np.maximum(a.hi, [-a.lo[0], a.hi[1], a.hi[2]])
    return SDF(f, lo, hi, (a,))


def flip_x(a):
    def f(p, l, h):
        q = p.copy(); q[:, 0] = -q[:, 0]
        return a.ev(q, None if l is None else np.array([-h[0], l[1], l[2]]),
                    None if h is None else np.array([-l[0], h[1], h[2]]))
    return SDF(f, [-a.hi[0], a.lo[1], a.lo[2]], [-a.lo[0], a.hi[1], a.hi[2]], (a,))


def transformed(a, c, R=None, s=1.0):
    """Place shape a (defined in its own local frame) at c with rotation R and uniform scale s."""
    c = np.asarray(c, float)

    def f(p, l, h):
        q = _local(p, c, R) / s
        return a.ev(q) * s
    ext = np.maximum(np.abs(a.lo), np.abs(a.hi)) * s
    lo, hi = _rbox(c, ext, R)
    return SDF(f, lo, hi, (a,))


# ----------------------------------------------------------------------
# noise

_rs = np.random.RandomState(1337)
_PERM = np.concatenate([_rs.permutation(256)] * 2).astype(np.int64)
_GRAD = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1]], float)


def perlin(p, seed=0):
    p = p + np.array([17.13, 31.71, 47.37]) * seed
    pi = np.floor(p).astype(np.int64)
    pf = p - pi
    pi &= 255
    u = pf * pf * pf * (pf * (pf * 6 - 15) + 10)
    X, Y, Z = pi[:, 0], pi[:, 1], pi[:, 2]
    x, y, z = pf[:, 0], pf[:, 1], pf[:, 2]
    P = _PERM

    def g(ix, iy, iz, fx, fy, fz):
        hh = P[P[P[ix] + iy] + iz] % 12
        gr = _GRAD[hh]
        return gr[:, 0] * fx + gr[:, 1] * fy + gr[:, 2] * fz
    X1, Y1, Z1 = (X + 1) & 255, (Y + 1) & 255, (Z + 1) & 255
    n000 = g(X, Y, Z, x, y, z); n100 = g(X1, Y, Z, x - 1, y, z)
    n010 = g(X, Y1, Z, x, y - 1, z); n110 = g(X1, Y1, Z, x - 1, y - 1, z)
    n001 = g(X, Y, Z1, x, y, z - 1); n101 = g(X1, Y, Z1, x - 1, y, z - 1)
    n011 = g(X, Y1, Z1, x, y - 1, z - 1); n111 = g(X1, Y1, Z1, x - 1, y - 1, z - 1)
    ux, uy, uz = u[:, 0], u[:, 1], u[:, 2]
    nx00 = n000 + ux * (n100 - n000); nx10 = n010 + ux * (n110 - n010)
    nx01 = n001 + ux * (n101 - n001); nx11 = n011 + ux * (n111 - n011)
    nxy0 = nx00 + uy * (nx10 - nx00); nxy1 = nx01 + uy * (nx11 - nx01)
    return nxy0 + uz * (nxy1 - nxy0)


def fbm(p, octaves=4, lac=2.0, gain=0.5, seed=0):
    out = np.zeros(len(p)); a = 1.0; f = 1.0; norm = 0
    for i in range(octaves):
        out += a * perlin(p * f, seed + i * 7)
        norm += a; a *= gain; f *= lac
    return out / norm


def _hash3(c):
    c = c.astype(np.int64)
    h = (c[:, 0] * 73856093) ^ (c[:, 1] * 19349663) ^ (c[:, 2] * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    out = np.empty((len(c), 3))
    for k, m in enumerate((0x3FF, 0xFFC00, 0x3FF00000)):
        out[:, k] = ((h & m) >> (10 * k)) / 1024.0
    return out


def worley(p, seed=0):
    """Returns (F1, F2) cellular distances (cell size 1)."""
    p = p + 101.7 * seed
    c0 = np.floor(p)
    f1 = np.full(len(p), 9.0); f2 = np.full(len(p), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = c0 + np.array([dx, dy, dz])
                fp = c + _hash3(c + seed * 13)
                d = _norm(p - fp)
                nf1 = np.minimum(f1, d)
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = nf1
    return f1, f2


# ----------------------------------------------------------------------
# meshing

def mesh_sdf(node, to_cm, h, lo_s, hi_s, stud_per_cm, far=None, block=40):
    """Sample node (defined in cm space) on a stud-space grid and run marching cubes.
    to_cm maps stud points (N,3) -> cm points.  Returns verts (studs), faces."""
    from skimage.measure import marching_cubes
    band = 4 * h / stud_per_cm
    set_far(max(far or 0.0, band + node.maxpath()))
    lo = np.floor(np.asarray(lo_s) / h) * h - 2 * h
    hi = np.ceil(np.asarray(hi_s) / h) * h + 2 * h
    n = np.round((hi - lo) / h).astype(int) + 1
    vol = np.empty(n, dtype=np.float32)
    xs = lo[0] + h * np.arange(n[0]); ys = lo[1] + h * np.arange(n[1]); zs = lo[2] + h * np.arange(n[2])
    for i0 in range(0, n[0], block):
        for j0 in range(0, n[1], block):
            for k0 in range(0, n[2], block):
                X, Y, Z = np.meshgrid(xs[i0:i0 + block], ys[j0:j0 + block], zs[k0:k0 + block], indexing='ij')
                ps = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
                pc = to_cm(ps)
                d = node.ev(pc, pc.min(0), pc.max(0))
                vol[i0:i0 + block, j0:j0 + block, k0:k0 + block] = (d * stud_per_cm).reshape(X.shape)
    # make borders "outside" so meshes are closed
    vol[0, :, :] = vol[-1, :, :] = h; vol[:, 0, :] = vol[:, -1, :] = h; vol[:, :, 0] = vol[:, :, -1] = h
    if vol.min() >= 0:
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    v, f, _, _ = marching_cubes(vol, level=0.0, spacing=(h, h, h))
    v += lo
    return v, meshops_orient(v, f)


def meshops_orient(v, f):
    """Make the winding outward (positive signed volume)."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    vol = np.einsum('ij,ij->i', a, np.cross(b, c)).sum()
    return f if vol > 0 else f[:, ::-1].copy()
