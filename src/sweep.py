"""Tube sweeps along splines (vessels, nerves, ribs, intestines...)."""
import numpy as np


def catmull(points, n=16, closed=False):
    """Centripetal Catmull-Rom through points -> dense polyline."""
    P = np.asarray(points, float)
    if len(P) < 2:
        return P
    if closed:
        P = np.vstack([P[-1], P, P[0], P[1]])
    else:
        P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-6) ** 0.5
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-6) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-6) ** 0.5
        ts = np.linspace(t1, t2, n, endpoint=False)[:, None]
        A1 = (t1 - ts) / (t1 - t0) * p0 + (ts - t0) / (t1 - t0) * p1
        A2 = (t2 - ts) / (t2 - t1) * p1 + (ts - t1) / (t2 - t1) * p2
        A3 = (t3 - ts) / (t3 - t2) * p2 + (ts - t2) / (t3 - t2) * p3
        B1 = (t2 - ts) / (t2 - t0) * A1 + (ts - t0) / (t2 - t0) * A2
        B2 = (t3 - ts) / (t3 - t1) * A2 + (ts - t1) / (t3 - t1) * A3
        C = (t2 - ts) / (t2 - t1) * B1 + (ts - t1) / (t2 - t1) * B2
        out.append(C)
    out.append(P[-2][None])
    return np.vstack(out)


def arclen(path):
    d = np.linalg.norm(np.diff(path, axis=0), axis=1)
    return np.concatenate([[0], np.cumsum(d)])


def resample(path, ds=None, n=None):
    s = arclen(path)
    L = s[-1]
    if n is None:
        n = max(2, int(np.ceil(L / ds)) + 1)
    t = np.linspace(0, L, n)
    return np.stack([np.interp(t, s, path[:, k]) for k in range(3)], 1)


def tangents(path):
    T = np.gradient(path, axis=0)
    return T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)


def rmf(path, T, n0=None):
    """Rotation minimising frames (double reflection)."""
    N = np.zeros_like(path)
    if n0 is None:
        a = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
        n0 = np.cross(T[0], a)
    n0 = n0 - T[0] * (n0 @ T[0]); N[0] = n0 / np.linalg.norm(n0)
    for i in range(len(path) - 1):
        v1 = path[i + 1] - path[i]
        c1 = v1 @ v1
        if c1 < 1e-18:
            N[i + 1] = N[i]; continue
        rL = N[i] - (2 / c1) * (v1 @ N[i]) * v1
        tL = T[i] - (2 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        Ni = rL - (2 / c2) * (v2 @ rL) * v2 if c2 > 1e-18 else rL
        Ni -= T[i + 1] * (Ni @ T[i + 1])
        N[i + 1] = Ni / np.linalg.norm(Ni)
    B = np.cross(T, N)
    return N, B


def sweep(path, rn, rb=None, sides=12, mod=None, caps=True, normal_hint=None, cap_rings=3):
    """Sweep an ellipse (radii rn along N, rb along B) along path.
    rn, rb: scalar or array (len(path)).  mod(s01, phi) -> radial factor.
    normal_hint: (len,3) preferred N directions (projected), else RMF.
    Returns verts, faces, params(s01, phi)."""
    path = np.asarray(path, float)
    m = len(path)
    rn = np.broadcast_to(np.asarray(rn, float), (m,)).copy()
    rb = rn.copy() if rb is None else np.broadcast_to(np.asarray(rb, float), (m,)).copy()
    T = tangents(path)
    if normal_hint is not None:
        N = normal_hint - T * (normal_hint * T).sum(1, keepdims=True)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        B = np.cross(T, N)
    else:
        N, B = rmf(path, T)
    phi = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    s01 = arclen(path); s01 = s01 / max(s01[-1], 1e-12)
    cph, sph = np.cos(phi), np.sin(phi)
    fac = np.ones((m, sides)) if mod is None else np.broadcast_to(mod(s01[:, None], phi[None, :]), (m, sides))
    V = (path[:, None, :] + (rn[:, None] * cph[None] * fac)[..., None] * N[:, None, :]
         + (rb[:, None] * sph[None] * fac)[..., None] * B[:, None, :])
    verts = [V.reshape(-1, 3)]
    params = [np.stack([np.repeat(s01, sides), np.tile(phi, m)], 1)]
    faces = []
    idx = np.arange(m * sides).reshape(m, sides)
    a = idx[:-1]; b = np.roll(idx[:-1], -1, axis=1); c = idx[1:]; d = np.roll(idx[1:], -1, axis=1)
    faces.append(np.stack([a, c, b], -1).reshape(-1, 3))
    faces.append(np.stack([b, c, d], -1).reshape(-1, 3))
    nv = m * sides
    if caps:
        for end in (0, 1):
            i = 0 if end == 0 else m - 1
            sgn = -1 if end == 0 else 1
            ring_prev = idx[i]
            for k in range(1, cap_rings + 1):
                ang = k / (cap_rings + 1) * np.pi / 2
                sc = np.cos(ang); off = np.sin(ang)
                r_off = 0.5 * (rn[i] + rb[i]) * off * 0.9
                ring = (path[i] + sgn * T[i] * r_off
                        + (rn[i] * cph * sc * fac[i])[:, None] * N[i] + (rb[i] * sph * sc * fac[i])[:, None] * B[i])
                ids = nv + np.arange(sides); nv += sides
                verts.append(ring)
                params.append(np.stack([np.full(sides, float(end)), phi], 1))
                pa, pb = ring_prev, np.roll(ring_prev, -1)
                ca, cb = ids, np.roll(ids, -1)
                if end == 1:
                    faces.append(np.stack([pa, ca, pb], 1)); faces.append(np.stack([pb, ca, cb], 1))
                else:
                    faces.append(np.stack([pa, pb, ca], 1)); faces.append(np.stack([pb, cb, ca], 1))
                ring_prev = ids
            tip = path[i] + sgn * T[i] * 0.5 * (rn[i] + rb[i]) * 0.9
            verts.append(tip[None]); params.append(np.array([[float(end), 0.0]]))
            t = nv; nv += 1
            pa, pb = ring_prev, np.roll(ring_prev, -1)
            if end == 1:
                faces.append(np.stack([pa, np.full(sides, t), pb], 1))
            else:
                faces.append(np.stack([pa, pb, np.full(sides, t)], 1))
    return np.vstack(verts), np.vstack(faces).astype(np.int64), np.vstack(params)


def tube_mesh(points_cm, mapping, r_cm, ds=0.004, sides=10, n=16, r_end_cm=None, mod=None,
              rb_cm=None, normal_fn=None, caps=True, rprofile=None):
    """Spline through cm points, mapped to studs, swept with radius in studs."""
    dense = catmull(points_cm, n=n)
    ps = mapping.fwd(dense)
    ps = resample(ps, ds=ds)
    m = len(ps)
    t = np.linspace(0, 1, m)
    if rprofile is not None:
        r = rprofile(t) * mapping.spc
    else:
        r1 = r_cm if r_end_cm is None else r_end_cm
        r = (r_cm + (r1 - r_cm) * t) * mapping.spc
    if rb_cm is None:
        rb = None
    elif callable(rb_cm):
        rb = np.asarray(rb_cm(t), float) * mapping.spc
    else:
        rb = np.broadcast_to(np.asarray(rb_cm, float), (m,)) * mapping.spc
    hint = None if normal_fn is None else normal_fn(ps)
    return sweep(ps, r, rb, sides=sides, mod=mod, caps=caps, normal_hint=hint)
