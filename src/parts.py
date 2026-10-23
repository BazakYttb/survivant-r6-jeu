"""Part description + mesh building."""
import numpy as np
import sdf as S
import meshops as M
from maps import stud_bbox


class Part:
    def __init__(self, name, mapping, sdf=None, tubes=None, color=None, target=8000, h=None, far=1.5,
                 cat='bone', base=(0.89, 0.85, 0.75), smooth=4, min_faces=60, ao_scale=None, info='', mesh=None,
                 refine=None, region=None, clip=None):
        self.name = name
        self.mapping = mapping
        self.sdf = sdf
        self.tubes = tubes
        self.color = color
        self.target = target
        self.h = h
        self.far = far
        self.cat = cat
        self.base = base
        self.smooth = smooth
        self.min_faces = min_faces
        self.ao_scale = ao_scale
        self.info = info
        self.mesh = mesh          # optional callable -> (verts, faces, colours, per-corner normals): analytic meshes
        self.refine = refine      # e.g. 0.55: decimate to 55 % of target, then split long edges back up to target
        self.region = region or mapping.region     # body part the mesh welds to (rig_spec.REGIONS)
        self.clip = clip          # ('above' | 'below', z): keep one side of the plane z (Blender) and cap the cut


def stud_shape(node_studs, mp):
    """Use a shape defined directly in stud space (Blender coords) inside a cm-space tree of mapping mp.
    Handy to make sockets that exactly match a bone of another region (e.g. acetabulum vs femoral head)."""
    from maps import stud_bbox
    lo_s, hi_s = node_studs.lo, node_studs.hi
    g = np.stack(np.meshgrid(*[np.linspace(lo_s[i], hi_s[i], 5) for i in range(3)], indexing='ij'), -1).reshape(-1, 3)
    c = mp.inv(g)

    def f(p, l, h):
        return node_studs.ev(mp.fwd(p)) / mp.spc
    return S.SDF(f, c.min(0), c.max(0), (node_studs,))


def grad(node, p, eps=0.03):
    g = np.zeros_like(p)
    for k in range(3):
        e = np.zeros(3); e[k] = eps
        g[:, k] = (node.ev(p + e) - node.ev(p - e)) / (2 * eps)
    l = np.linalg.norm(g, axis=1, keepdims=True); l[l == 0] = 1
    return g / l


def project(points, node, offset=0.0, iters=6):
    """Move cm points onto the iso-surface node = offset."""
    p = np.asarray(points, float).copy()
    for _ in range(iters):
        d = node.ev(p) - offset
        p -= d[:, None] * grad(node, p)
    return p


def sdf_ao(node, mp, v, n, scale):
    occ = np.zeros(len(v))
    for i in range(1, 5):
        dt = scale * i
        q = v + n * dt
        dq = node.ev(mp.inv(q)) * mp.spc
        occ += np.clip(dt - dq, 0, None) / dt * (0.6 ** (i - 1))
    return np.clip(1 - 0.75 * occ, 0, 1)


def build_part(part, verbose=True):
    import time
    t0 = time.time()
    mp = part.mapping
    meshes = []
    if part.sdf is not None:
        node = part.sdf()
        lo_s, hi_s = stud_bbox(mp, node.lo, node.hi)
        dims = hi_s - lo_s
        h = part.h
        if h is None:
            hc = dims.max() / 45
            vc, fc = S.mesh_sdf(node, mp.inv, hc, lo_s, hi_s, mp.spc, far=max(part.far, 3 * hc / mp.spc))
            if len(fc) == 0:
                raise RuntimeError(f'{part.name}: empty at coarse pass')
            area = 0.5 * np.linalg.norm(M.face_normals(vc, fc), axis=1).sum()
            h = np.sqrt(2.2 * area / (4.0 * part.target))
            h = float(np.clip(h, dims.max() / 420, dims.max() / 60))
        far = max(part.far, 3 * h / mp.spc)
        v, f = S.mesh_sdf(node, mp.inv, h, lo_s, hi_s, mp.spc, far=far)
        if len(f) == 0:
            raise RuntimeError(f'{part.name}: empty mesh')
        nraw = len(f)
        S.set_far(1e9)
        if part.refine:
            # uniform vertex density so that painted details do not smear across long flat triangles
            v, f = M.finalize(v, f, int(part.target * part.refine), part.smooth, part.min_faces)
            v, f = M.refine_to(v, f, part.target)
            for _ in range(2):          # put the new vertices back on the surface (small moves only)
                pc = mp.inv(v)
                d = node.ev(pc) * mp.spc
                g = grad(node, pc, eps=0.25 * h / mp.spc)
                v = v - np.clip(d, -0.25 * h * 4, 0.25 * h * 4)[:, None] * g
        else:
            v, f = M.finalize(v, f, part.target, part.smooth, part.min_faces)
        n = M.vertex_normals(v, f)
        ao = sdf_ao(node, mp, v, n, part.ao_scale or max(2.5 * h, dims.max() * 0.02))
        cav = M.cavity(v, f, n)
        ctx = dict(pc=mp.inv(v), ps=v, n=n, ao=ao, cav=cav, node=node, mp=mp)
        col = part.color(ctx) if part.color else np.tile(part.base, (len(v), 1))
        meshes.append((v, f, col))
        info = f'raw {nraw} h {h:.4f}'
    if part.tubes is not None:
        for (v, f, prm, cfn) in part.tubes():
            f = M.orient_outward(v, f)
            n = M.vertex_normals(v, f)
            cav = M.cavity(v, f, n, smooth=1) * 0.5
            ctx = dict(pc=mp.inv(v), ps=v, n=n, ao=np.ones(len(v)), cav=cav, prm=prm, mp=mp)
            col = cfn(ctx)
            meshes.append((v, f, col))
        info = 'tubes'
    v, f, col = M.merge(meshes)
    if part.sdf is None and len(f) > part.target * 1.02:
        # decimate merged tubes, then carry the colours over from the nearest original vertex
        from scipy.spatial import cKDTree
        n0 = len(f)
        v2, f2 = M.decimate(v, f, part.target)
        f2 = M.orient_outward(v2, f2)
        _, idx = cKDTree(v).query(v2)
        v, f, col = v2, f2, col[idx]
        info = f'tubes decimated {n0} -> {len(f)}'
    if verbose:
        print(f'{part.name:40s} {len(f):6d} tris  {info}  {time.time() - t0:5.1f}s', flush=True)
    return v.astype(np.float32), f.astype(np.int32), np.clip(col, 0, 1).astype(np.float32)
