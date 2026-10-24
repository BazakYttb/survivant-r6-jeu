"""Construction Blender des pièces : brins -> Curves -> Geometry Nodes (bandes / tubes / fusion SDF) -> maillages
finaux MON_<Pièce>_<n> (au plus MAX_TRIS triangles chacun) avec les attributs Col, Mat et Tangent."""
import math
import time
import numpy as np
import bpy
from mon_common import simplify, to_blender, srgb_to_lin, unit
import mon_blend as MB
from mon_gen import norm_strand, K_TENDON

MAX_TRIS = 19500
FLAT_BUCKET = 0.6


def sides_for(r):
    if r < 0.010:
        return 3
    if r < 0.020:
        return 4
    if r < 0.036:
        return 5
    if r < 0.062:
        return 6
    if r < 0.10:
        return 7
    return 8


def prepare_free(strands, tol_rel=0.16, max_seg=0.3):
    """Simplifie les brins libres et les range par (côtés, aplatissement)."""
    bys = {}
    for st in strands:
        P, R, C, kind, nrm, flat = norm_strand(st)
        idx = simplify(P, R, tol_rel, 0.0025, max_seg)
        C = np.asarray(C, float)
        Cs = C[idx] if C.ndim == 2 else C
        nr = None if nrm is None else np.asarray(nrm, float)[idx] if np.ndim(nrm) == 2 else nrm
        fb = 1.0 if flat > 0.85 else FLAT_BUCKET
        sides = sides_for(float(np.max(R)))
        if fb < 1.0:
            sides = max(sides, 5)
        bys.setdefault((sides, fb), []).append((P[idx], R[idx], Cs, kind, nr, fb))
    return bys


def _arrays_from_bys(name, bys, tmpcol):
    out = []
    for (sides, fb), lst in sorted(bys.items()):
        tag = '%s_%d_%d' % (name, sides, int(fb * 100))
        src = MB.curves_object(tag + '_src', lst, tmpcol)
        ng = MB.gn_tubes(src, sides, tag + '_gn', flat=fb)
        host = MB.host_with_tree(tag + '_host', ng, tmpcol)
        me = MB.evaluated_mesh(host)
        out.append(MB.mesh_arrays(me))
        bpy.data.meshes.remove(me)
        bpy.data.objects.remove(host)
        bpy.data.node_groups.remove(ng)
        cv = src.data
        bpy.data.objects.remove(src)
        bpy.data.hair_curves.remove(cv)
    return out


def _np_mesh(item):
    """(V Roblox, F, C sRGB[, kind[, tangent Roblox]]) -> (V Blender, T, attributs)."""
    V, F, C = item[0], item[1], item[2]
    kind = item[3] if len(item) > 3 else K_TENDON
    tang = item[4] if len(item) > 4 else None
    n = len(V)
    Vb = to_blender(V).astype(np.float32)
    F = np.asarray(F, np.int64)
    if F.shape[1] == 4:
        F = np.vstack([F[:, [0, 1, 2]], F[:, [0, 2, 3]]])
    Cl = srgb_to_lin(np.broadcast_to(np.asarray(C, float), (n, 3)))
    A = {'Col': np.hstack([Cl, np.ones((n, 1))]).astype(np.float32),
         'Mat': np.broadcast_to(np.asarray(kind, float), (n,)).astype(np.float32).copy(),
         'Tangent': (np.zeros((n, 3)) if tang is None else to_blender(np.broadcast_to(np.asarray(tang, float), (n, 3)))).astype(np.float32)}
    return Vb, F.astype(np.int32), A


def _source_mesh(name, items, tmpcol):
    arrs = [_np_mesh(it) for it in items]
    V = np.vstack([a[0] for a in arrs])
    off = np.cumsum([0] + [len(a[0]) for a in arrs])
    T = np.vstack([a[1] + off[i] for i, a in enumerate(arrs)])
    A = {k: np.concatenate([a[2][k] for a in arrs]) for k in arrs[0][2]}
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V)); me.vertices.foreach_set('co', V.ravel())
    me.loops.add(len(T) * 3); me.loops.foreach_set('vertex_index', T.ravel())
    me.polygons.add(len(T)); me.polygons.foreach_set('loop_start', (np.arange(len(T)) * 3).astype(np.int32))
    me.update(calc_edges=True)
    MB.set_attrs(me, A)
    ob = bpy.data.objects.new(name, me)
    tmpcol.objects.link(ob)
    return ob


def _fuse_arrays(piece, target, tmpcol):
    fuse = [norm_strand(st) for st in piece.fuse]
    src = MB.curves_object(piece.name + '_fsrc', fuse, tmpcol) if fuse else None
    msrc = _source_mesh(piece.name + '_msrc', piece.fuse_meshes, tmpcol) if piece.fuse_meshes else None
    cut = _source_mesh(piece.name + '_cut', [(m[0], m[1], (0, 0, 0)) for m in piece.cut_meshes], tmpcol) \
        if piece.cut_meshes else None
    ng = MB.gn_fuse(piece.name + '_fuse', src, msrc, cut, voxel=piece.voxel, fillet=piece.fillet,
                    smooth=getattr(piece, 'smooth', 0), offset=getattr(piece, 'offset', 0.0),
                    blur_col=getattr(piece, 'blur_col', 0), close=getattr(piece, 'close', 0.0),
                    smooth_pos=getattr(piece, 'smooth_pos', 0))
    host = MB.host_with_tree(piece.name + '_fhost', ng, tmpcol)
    me = MB.bake_mesh(host, piece.name + '_core', target_tris=target)
    arr = MB.mesh_arrays(me)
    bpy.data.meshes.remove(me)
    bpy.data.objects.remove(host)
    bpy.data.node_groups.remove(ng)
    for o in (src, msrc, cut):
        if o is not None:
            d = o.data
            bpy.data.objects.remove(o)
            if isinstance(d, bpy.types.Curves):
                bpy.data.hair_curves.remove(d)
            else:
                bpy.data.meshes.remove(d)
    return arr


def build_piece(piece, budget, col, tmpcol, core_share=None):
    """Construit les maillages finaux d'une pièce. budget = triangles visés pour toute la pièce."""
    t0 = time.time()
    bys = prepare_free(piece.free)
    parts = []
    free_arr = _arrays_from_bys(piece.name, bys, tmpcol) if bys else []
    mesh_arr = [_np_mesh(it) for it in piece.free_meshes]
    free_tris = sum(len(a[1]) for a in free_arr) + sum(len(a[1]) for a in mesh_arr)
    core_tris = 0
    if piece.fuse or piece.fuse_meshes:
        target = core_share if core_share is not None else max(1200, budget - free_tris)
        core = _fuse_arrays(piece, target, tmpcol)
        parts.append(core)
        core_tris = len(core[1])
    parts += free_arr + mesh_arr
    chunks = _split_parts(parts)
    objs = []
    for i, ch in enumerate(chunks):
        V = np.vstack([c[0] for c in ch])
        off = np.cumsum([0] + [len(c[0]) for c in ch])
        T = np.vstack([c[1] + off[k] for k, c in enumerate(ch)])
        A = {}
        for name, dtype, k in MB.ATTRS:
            vals = []
            for c in ch:
                if name in c[2]:
                    vals.append(c[2][name])
                else:
                    n = len(c[0])
                    vals.append(np.tile([0.01, 0.01, 0.01, 1], (n, 1)) if k == 4 else (np.zeros((n, k)) if k > 1 else np.zeros(n)))
            A[name] = np.concatenate(vals).astype(np.float32)
        name = 'MON_%s_%d' % (piece.name, i + 1)
        ob = _final_object(name, V, T, A, col)
        ob['piece'] = piece.name
        objs.append(ob)
    tot = sum(MB.tri_count(o.data) for o in objs)
    print('  %-12s %6d tris (cœur %5d, libres %5d) en %d maillage(s), %.1f s'
          % (piece.name, tot, core_tris, free_tris, len(objs), time.time() - t0), flush=True)
    return objs


def _islands(T, nv):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    r = np.concatenate([T[:, 0], T[:, 1], T[:, 2]])
    c = np.concatenate([T[:, 1], T[:, 2], T[:, 0]])
    g = coo_matrix((np.ones(len(r), np.int8), (r, c)), shape=(nv, nv))
    return connected_components(g, directed=False)[1]


def _sub(item, tri_idx):
    V, T, A = item
    used = np.unique(T[tri_idx])
    remap = -np.ones(len(V), np.int64); remap[used] = np.arange(len(used))
    return V[used], remap[T[tri_idx]].astype(np.int32), {k: v[used] for k, v in A.items()}


def _split_parts(parts):
    """Regroupe les parties en morceaux d'au plus MAX_TRIS triangles ; une partie trop grosse est coupée par îlots."""
    items = []
    for it in parts:
        V, T, A = it
        if len(T) <= MAX_TRIS:
            items.append(it)
            continue
        roots = _islands(T, len(V))
        troot = roots[T[:, 0]]
        order = np.argsort(troot, kind='stable')
        uniq, start = np.unique(troot[order], return_index=True)
        bounds = list(start) + [len(order)]
        cur, cur_n = [], 0
        for k in range(len(uniq)):
            tri_idx = order[bounds[k]:bounds[k + 1]]
            if len(tri_idx) > MAX_TRIS:
                raise RuntimeError('îlot de plus de %d triangles' % MAX_TRIS)
            if cur_n + len(tri_idx) > MAX_TRIS and cur:
                items.append(_sub(it, np.concatenate(cur))); cur, cur_n = [], 0
            cur.append(tri_idx); cur_n += len(tri_idx)
        if cur:
            items.append(_sub(it, np.concatenate(cur)))
    items.sort(key=lambda it: -len(it[1]))
    bins = []
    for it in items:
        for b in bins:
            if b[0] + len(it[1]) <= MAX_TRIS:
                b[1].append(it); b[0] += len(it[1])
                break
        else:
            bins.append([len(it[1]), [it]])
    return [b[1] for b in bins]


def _final_object(name, Vb, T, A, col):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(Vb))
    me.vertices.foreach_set('co', np.asarray(Vb, np.float32).ravel())
    me.loops.add(len(T) * 3)
    me.loops.foreach_set('vertex_index', np.asarray(T, np.int32).ravel())
    me.polygons.add(len(T))
    me.polygons.foreach_set('loop_start', (np.arange(len(T)) * 3).astype(np.int32))
    me.update(calc_edges=True)
    me.validate()
    me.shade_smooth()
    MB.set_attrs(me, A)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def _arrays_object(name, arr, col):
    V, T, A = arr
    return _final_object(name, V, T, A, col)


def _decimate_arrays(arr, target, tmpcol):
    if len(arr[1]) <= target:
        return arr
    ob = _arrays_object('_dec_src', arr, tmpcol)
    me = MB.bake_mesh(ob, '_dec', target_tris=target)
    out = MB.mesh_arrays(me)
    me_src = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me_src)
    bpy.data.meshes.remove(me)
    return out


def _merge(parts):
    V = np.vstack([c[0] for c in parts])
    off = np.cumsum([0] + [len(c[0]) for c in parts])
    T = np.vstack([c[1] + off[k] for k, c in enumerate(parts)])
    A = {}
    for name, dtype, k in MB.ATTRS:
        vals = []
        for c in parts:
            n = len(c[0])
            if name in c[2]:
                vals.append(c[2][name])
            else:
                vals.append(np.tile([0.5, 0.5, 0.5, 1], (n, 1)) if k == 4 else (np.zeros((n, k)) if k > 1 else np.zeros(n)))
        A[name] = np.concatenate(vals).astype(np.float32)
    return V, T, A


def build_piece_hd_ld(piece, budget, col_lo, col_hd, tmpcol):
    """Version haute définition (fusion SDF complète, pour la cuisson) et version jeu décimée (MON_<Pièce>_<n>)."""
    t0 = time.time()
    bys = prepare_free(piece.free)
    free_arr = _arrays_from_bys(piece.name, bys, tmpcol) if bys else []
    mesh_arr = [_np_mesh(it) for it in piece.free_meshes]
    free_parts = free_arr + mesh_arr
    free_tris = sum(len(a[1]) for a in free_parts)
    core = _fuse_arrays(piece, None, tmpcol) if (piece.fuse or piece.fuse_meshes) else None
    hd_parts = ([core] if core is not None else []) + free_parts
    hd = _arrays_object('HD_' + piece.name, _merge(hd_parts), col_hd)
    hd['piece'] = piece.name
    lo_parts = list(free_parts)
    core_lo = 0
    if core is not None:
        target = max(800, budget - free_tris)
        c_lo = _decimate_arrays(core, target, tmpcol)
        lo_parts = [c_lo] + lo_parts
        core_lo = len(c_lo[1])
    chunks = _split_parts(lo_parts)
    objs = []
    for i, ch in enumerate(chunks):
        ob = _arrays_object('MON_%s_%d' % (piece.name, i + 1), _merge(ch), col_lo)
        ob['piece'] = piece.name
        objs.append(ob)
    tot = sum(MB.tri_count(o.data) for o in objs)
    print('  %-12s jeu %6d tris (peau %5d, griffes/crocs %5d) en %d maillage(s) ; HD %7d tris ; %.1f s'
          % (piece.name, tot, core_lo, free_tris, len(objs), MB.tri_count(hd.data), time.time() - t0), flush=True)
    return objs, hd
