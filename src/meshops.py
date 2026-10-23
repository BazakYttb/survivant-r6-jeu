"""Mesh post-processing: cleanup, smoothing, decimation, normals, cavity."""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components


def adjacency(nv, f):
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    A = sp.coo_matrix((np.ones(len(i)), (i, j)), shape=(nv, nv)).tocsr()
    A.data[:] = 1.0
    return A


def remove_small_components(v, f, min_faces=60, keep_ratio=0.0):
    if len(f) == 0:
        return v, f
    A = adjacency(len(v), f)
    n, lab = connected_components(A, directed=False)
    if n == 1:
        return v, f
    flab = lab[f[:, 0]]
    counts = np.bincount(flab, minlength=n)
    keep = counts >= max(min_faces, keep_ratio * counts.max())
    fk = f[keep[flab]]
    return compact(v, fk)


def compact(v, f):
    used = np.unique(f)
    remap = -np.ones(len(v), int); remap[used] = np.arange(len(used))
    return v[used], remap[f]


def taubin(v, f, iters=6, lam=0.5, mu=-0.53):
    A = adjacency(len(v), f)
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1
    W = sp.diags(1.0 / deg) @ A
    v = v.copy()
    for _ in range(iters):
        v = v + lam * (W @ v - v)
        v = v + mu * (W @ v - v)
    return v


def decimate(v, f, target):
    if len(f) <= target:
        return v, f
    import pyfqmr
    s = pyfqmr.Simplify()
    s.setMesh(v.astype(np.float64), f.astype(np.int32))
    s.simplify_mesh(target_count=int(target), aggressiveness=6, preserve_border=True, verbose=False)
    v2, f2, _ = s.getMesh()
    return np.asarray(v2), np.asarray(f2)


def face_normals(v, f):
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    return n


def vertex_normals(v, f):
    fn = face_normals(v, f)  # area weighted
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    l = np.linalg.norm(vn, axis=1, keepdims=True); l[l == 0] = 1
    return vn / l


def cavity(v, f, n, smooth=2):
    """Positive in concave areas, negative on convex ridges (unitless ~[-1,1])."""
    A = adjacency(len(v), f)
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1
    W = sp.diags(1.0 / deg) @ A
    lap = W @ v - v
    e = np.linalg.norm(v[f[:, 0]] - v[f[:, 1]], axis=1).mean()
    c = (lap * n).sum(1) / max(e, 1e-9)
    for _ in range(smooth):
        c = 0.5 * c + 0.5 * (W @ c)
    return np.clip(c * 1.6, -1, 1)


def signed_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0


def orient_outward(v, f):
    """Flip every closed component whose signed volume is negative."""
    if len(f) == 0:
        return f
    A = adjacency(len(v), f)
    n, lab = connected_components(A, directed=False)
    flab = lab[f[:, 0]]
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    vol = np.bincount(flab, weights=np.einsum('ij,ij->i', a, np.cross(b, c)), minlength=n)
    flip = vol[flab] < 0
    f = f.copy()
    f[flip] = f[flip][:, ::-1]
    return f


def finalize(v, f, target, smooth_iters=6, min_faces=60):
    v, f = remove_small_components(v, f, min_faces=min_faces)
    if smooth_iters:
        v = taubin(v, f, smooth_iters)
    v, f = decimate(v, f, target)
    v, f = remove_small_components(v, f, min_faces=8)
    # drop degenerate faces
    good = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    f = f[good]
    v, f = compact(v, f)
    return v, orient_outward(v, f)


def merge(meshes):
    vs, fs, cs = [], [], []
    off = 0
    for m in meshes:
        v, f, c = m
        vs.append(v); fs.append(f + off); cs.append(c); off += len(v)
    return np.concatenate(vs), np.concatenate(fs), np.concatenate(cs)


def split_long_edges(v, f, lmax):
    """Split every edge longer than lmax at its midpoint; triangles are re-split conformingly (1->2, 1->3, 1->4)."""
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    ue, inv = np.unique(e, axis=0, return_inverse=True)
    inv = inv.ravel()
    L = np.linalg.norm(v[ue[:, 0]] - v[ue[:, 1]], axis=1)
    mark = L > lmax
    if not mark.any():
        return v, f
    mid = -np.ones(len(ue), np.int64)
    mid[mark] = len(v) + np.arange(mark.sum())
    v = np.concatenate([v, 0.5 * (v[ue[mark, 0]] + v[ue[mark, 1]])])
    nf = len(f)
    m01, m12, m20 = mid[inv[:nf]], mid[inv[nf:2 * nf]], mid[inv[2 * nf:]]
    a, b, c = f[:, 0], f[:, 1], f[:, 2]
    k = (m01 >= 0).astype(int) + (m12 >= 0) + (m20 >= 0)
    out = [f[k == 0]]
    # one split edge
    for mm, (p, q, r) in ((m01, (a, b, c)), (m12, (b, c, a)), (m20, (c, a, b))):
        s = (k == 1) & (mm >= 0)
        out += [np.stack([p[s], mm[s], r[s]], 1), np.stack([mm[s], q[s], r[s]], 1)]
    # two split edges: the unsplit edge is (u, w); the shared corner t sits between both split edges
    for ma, mb, (t, u, w) in ((m01, m12, (b, c, a)), (m12, m20, (c, a, b)), (m20, m01, (a, b, c))):
        s = (k == 2) & (ma >= 0) & (mb >= 0)
        # ma is on edge (w,t), mb on edge (t,u)
        out += [np.stack([ma[s], t[s], mb[s]], 1), np.stack([w[s], ma[s], mb[s]], 1), np.stack([w[s], mb[s], u[s]], 1)]
    s = k == 3
    out += [np.stack([a[s], m01[s], m20[s]], 1), np.stack([m01[s], b[s], m12[s]], 1),
            np.stack([m20[s], m12[s], c[s]], 1), np.stack([m01[s], m12[s], m20[s]], 1)]
    return v, np.concatenate(out).astype(f.dtype)


def refine_to(v, f, target, rounds=6):
    """Add vertices on the longest edges until the mesh has about `target` faces (uniform vertex density
    for vertex colours on decimated meshes)."""
    for _ in range(rounds):
        if len(f) >= target * 0.93:
            break
        e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
        ue = np.unique(e, axis=0)
        L = np.sort(np.linalg.norm(v[ue[:, 0]] - v[ue[:, 1]], axis=1))[::-1]
        nsplit = int((target - len(f)) / 2.6)
        if nsplit < 1:
            break
        lmax = L[min(nsplit, len(L) - 1)]
        v2, f2 = split_long_edges(v, f, lmax)
        if len(f2) > target:
            break
        v, f = v2, f2
    return v, f


def clip_plane(v, f, c, z0, keep='above'):
    """Cut a triangle mesh by the plane Z = z0, keep one side ('above' or 'below') and close every cut loop
    with a fan around its centre (colours interpolated along the cut). Used for vessels, nerves and ligaments
    that cross the elbow or knee: each segment gets its own capped piece."""
    v = np.asarray(v, float)
    f = np.asarray(f, np.int64)
    c = np.asarray(c, float)
    sg = 1.0 if keep == 'above' else -1.0
    d = sg * (v[:, 2] - z0)
    d = np.where(np.abs(d) < 1e-7, 1e-7, d)               # nothing exactly on the plane
    inside = d > 0
    cnt = inside[f].sum(1)
    nv, nc = [v], [c]
    extra_v, extra_c = [], []
    edge_new = {}
    n0 = len(v)

    def cut(a, b):
        key = (a, b) if a < b else (b, a)
        if key not in edge_new:
            t = d[a] / (d[a] - d[b])
            extra_v.append(v[a] + t * (v[b] - v[a]))
            extra_c.append(c[a] + t * (c[b] - c[a]))
            edge_new[key] = n0 + len(extra_v) - 1
        return edge_new[key]
    tris = [f[cnt == 3]]
    cap_next = {}
    for tri in f[(cnt == 1) | (cnt == 2)]:
        ins = inside[tri]
        if ins.sum() == 1:
            k = int(np.argmax(ins))
            a, b, cc = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]
            e1, e2 = cut(a, b), cut(a, cc)
            tris.append(np.array([[a, e1, e2]]))
            cap_next[e2] = e1
        else:
            k = int(np.argmin(ins))
            dd, a, b = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]
            ea, eb = cut(a, dd), cut(b, dd)
            tris.append(np.array([[a, b, eb], [a, eb, ea]]))
            cap_next[ea] = eb
    V = np.vstack([v] + ([np.array(extra_v)] if extra_v else []))
    Cc = np.vstack([c] + ([np.array(extra_c)] if extra_c else []))
    F = np.vstack(tris) if tris else np.zeros((0, 3), np.int64)
    # cap every closed loop with a fan
    caps, cv, ccol = [], [], []
    seen = set()
    for start in list(cap_next):
        if start in seen:
            continue
        loop, cur = [], start
        while cur in cap_next and cur not in seen:
            seen.add(cur)
            loop.append(cur)
            cur = cap_next[cur]
        if cur != start or len(loop) < 3:
            continue
        ci = len(V) + len(cv)
        cv.append(V[loop].mean(0))
        ccol.append(Cc[loop].mean(0))
        for i in range(len(loop)):
            caps.append((ci, loop[i], loop[(i + 1) % len(loop)]))
    if cv:
        V = np.vstack([V, np.array(cv)])
        Cc = np.vstack([Cc, np.array(ccol)])
        capf = np.array(caps, np.int64)
        # the cap must face away from the kept side
        nz = np.cross(V[capf[:, 1]] - V[capf[:, 0]], V[capf[:, 2]] - V[capf[:, 0]])[:, 2]
        if (sg * nz).mean() > 0:
            capf = capf[:, [0, 2, 1]]
        F = np.vstack([F, capf])
    used = np.unique(F)
    remap = -np.ones(len(V), np.int64)
    remap[used] = np.arange(len(used))
    return V[used], remap[F], Cc[used]
