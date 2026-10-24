"""Créature en peau, corps continu, raccords invisibles : fusion SDF du corps (et de chaque main, de la mâchoire),
décimation du groupe entier PUIS découpe en pièces du rig (os le plus proche, triangles recoupés le long de la
courbe d'égale distance entre deux os) : les pièces voisines partagent exactement les mêmes arêtes ; les normales
du corps continu sont gardées (normales personnalisées), l'ombrage ne montre donc aucune couture au repos.
Manchons rentrés sous la peau pour combler le vide quand une articulation plie (un par jointure, porté par l'enfant).
Sorties : HD_<groupe> (cuisson) et MON_<Pièce>_<n> (jeu).

usage : python construire.py -- sortie.blend"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mon_skel import rig_spec, FINGERS
import mon_gen as G
import mon_flesh as FL
import mon_blend as MB
import mon_build as BLD
import mon_cut as CUT

BUDGET = {'Head': 15000, 'Jaw': 5000, 'Neck': 5000, 'UpperChest': 14000, 'Chest': 12000, 'Abdomen': 8000,
          'Pelvis': 11000, 'Thigh': 7000, 'Shin': 6000, 'Foot': 7000, 'UpperArm': 6000, 'Forearm': 5500,
          'Hand': 5000}
MAX_PIECE = 19000          # triangles par maillage (limite Roblox 20 000, marge)
MAX_SKIN = 15500           # peau propre d'une pièce (hors manchon, griffes, crocs)


def budget(name):
    return BUDGET.get(name.split('_')[0], 1100)


def group_piece(name, members, voxel, fillet, close, blur=70, smooth_pos=3):
    g = G.Piece(name)
    for m in members:
        p = G.PIECES[m]
        g.fuse += p.fuse
        g.fuse_meshes += p.fuse_meshes
    g.voxel, g.fillet, g.close, g.blur_col, g.smooth_pos = voxel, fillet, close, blur, smooth_pos
    return g


def free_parts(piece, tmpcol):
    bys = BLD.prepare_free(piece.free)
    arr = BLD._arrays_from_bys(piece.name, bys, tmpcol) if bys else []
    return arr + [BLD._np_mesh(it) for it in piece.free_meshes]


def vertex_normals(V, T):
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, T[:, k], n)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def open_border(T):
    E = np.sort(np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
    Eu, cnt = np.unique(E, axis=0, return_counts=True)
    return np.unique(Eu[cnt == 1])


def decimate_keep_border(arr, target, tmpcol):
    """Décime la peau d'une pièce sans toucher à son bord (arêtes partagées avec les voisines : sommets protégés par
    un groupe de sommets de poids 0) ; normales du corps continu sur le bord, recalculées à l'intérieur."""
    from scipy.spatial import cKDTree
    V, T, A = arr
    border = open_border(T)
    ob = BLD._arrays_object('_decb', (V, T, A), tmpcol)
    vg = ob.vertex_groups.new(name='libre')
    inner = np.setdiff1d(np.arange(len(V)), border)
    vg.add(inner.tolist(), 1.0, 'REPLACE')
    if len(border):
        vg.add(border.tolist(), 0.0, 'REPLACE')
    mod = ob.modifiers.new('dec', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.use_collapse_triangulate = True
    mod.vertex_group = 'libre'
    mod.vertex_group_factor = 1000.0
    ratio = target / len(T)
    for _ in range(4):
        mod.ratio = min(1.0, ratio)
        me = MB.evaluated_mesh(ob, '_decb_out')
        n = MB.tri_count(me)
        if n <= target:
            break
        bpy.data.meshes.remove(me)
        ratio *= 0.98 * target / n
    Vd, Td, Ad = MB.mesh_arrays(me)
    bpy.data.meshes.remove(me)
    me_src = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me_src)
    N = vertex_normals(Vd, Td)
    d, idx = cKDTree(V).query(Vd)
    bd = open_border(Td)
    keep = bd[d[bd] < 1e-5]
    N[keep] = A['Normal'][idx[keep]]
    Ad = dict(Ad)
    Ad['Normal'] = N.astype(np.float32)
    moved = int((d[bd] >= 1e-5).sum())
    return (Vd, Td, Ad), moved


def make_object(name, skin_parts, free, col):
    """Objet final : peau (normales continues imposées) + griffes/crocs (normales calculées)."""
    parts = list(skin_parts) + list(free)
    V, T, A = BLD._merge(parts)
    ob = BLD._arrays_object(name, (V, T, A), col)
    Nn = [sp[2]['Normal'] for sp in skin_parts] + [np.zeros((len(f[0]), 3), np.float32) for f in free]
    Nn = np.vstack(Nn).astype(np.float32)
    ob.data.normals_split_custom_set_from_vertices([tuple(x) for x in Nn])
    return ob


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = args[0] if args else 'Creature.blend'
    t0 = time.time()
    MB.reset()
    FL.build_all()
    names = list(rig_spec().keys())
    hands = {s: ['Hand_' + s] + [n for n in names if n.endswith('_' + s) and any(n.startswith(f) for f in FINGERS)]
             for s in ('R', 'L')}
    body = [n for n in names if n != 'Jaw' and n not in hands['R'] + hands['L']]
    groups = [('CORPS', body, 0.0105, 4, 0.035), ('MAIN_R', hands['R'], 0.007, 3, 0.02),
              ('MAIN_L', hands['L'], 0.007, 3, 0.02), ('MACHOIRE', ['Jaw'], 0.008, 3, 0.0)]
    col_lo = MB.collection('MON_Maillages')
    col_hd = MB.collection('HD_Cuisson')
    tmp = MB.collection('_tmp')
    segs = CUT.piece_segments()
    fparts = {n: free_parts(G.PIECES[n], tmp) for n in names}
    objs = []
    for gname, members, vox, fil, clo in groups:
        t1 = time.time()
        gp = group_piece(gname, members, vox, fil, clo)
        V, T, A = BLD._fuse_arrays(gp, None, tmp)
        hd = BLD._arrays_object('HD_' + gname, BLD._merge([(V, T, A)] + [fp for m in members for fp in fparts[m]]), col_hd)
        hd['pieces'] = ','.join(members)
        target = sum(max(600, budget(m) - sum(len(f[1]) for f in fparts[m])) for m in members)
        Vd, Td, Ad = BLD._decimate_arrays((V, T, A), target, tmp)
        Ad = dict(Ad)
        Ad['Normal'] = vertex_normals(Vd, Td).astype(np.float32)
        print('%-9s SDF %d tris -> jeu %d tris (%.1f s)' % (gname, len(T), len(Td), time.time() - t1), flush=True)
        if len(members) == 1:
            res = {members[0]: ((Vd, Td, Ad), None, None)}
            res_small = res
        else:
            parents = {n: p for n, (p, _, _) in rig_spec().items()}
            res = CUT.split_smooth(Vd, Td, Ad, members, segs, parents=parents)
            res_small = CUT.split_smooth(Vd, Td, Ad, members, segs, sleeve=0.25, parents=parents)
        for name in members:
            if name not in res:
                print('  (pièce vide)', name)
                continue
            own, _, sl_lo = res[name]
            fp = fparts[name]
            n_free = sum(len(f[1]) for f in fp)
            note = ''
            cap_skin = MAX_SKIN - n_free
            if len(own[1]) > cap_skin:                 # trop dense (côtes…) : décimation locale, bord intact
                n0 = len(own[1])
                own, moved = decimate_keep_border(own, cap_skin, tmp)
                note += ' peau %d -> %d (bord déplacé : %d sommets)' % (n0, len(own[1]), moved)
            skin = [own] + ([sl_lo] if sl_lo is not None else [])
            if sum(len(s[1]) for s in skin) + n_free > MAX_PIECE:      # manchon plus court
                sl2 = res_small[name][2]
                skin = [own] + ([sl2] if sl2 is not None else [])
                note += ' manchon court'
                n_sl = len(sl2[1]) if sl2 is not None else 0
                room = MAX_PIECE - n_free - n_sl
                if len(own[1]) > room >= 8000:                         # on fait de la place au manchon
                    own, moved = decimate_keep_border(own, room, tmp)
                    skin = [own] + ([sl2] if sl2 is not None else [])
                    note += ', peau ramenée à %d (bord déplacé : %d)' % (len(own[1]), moved)
            if sum(len(s[1]) for s in skin) + n_free > MAX_PIECE:      # en dernier recours, sans manchon
                skin = [own]
                note += ' SANS manchon'
            if note:
                print('  !', name, note)
            ob = make_object('MON_%s_1' % name, skin, fp, col_lo)
            ob['piece'] = name
            objs.append(ob)
            print('  %-12s jeu %6d tris (peau %d + manchon, griffes/crocs %d)' % (name, MB.tri_count(ob.data), len(own[1]), n_free), flush=True)
    bpy.data.collections.remove(tmp)
    for c in list(bpy.data.collections):
        if c.name.startswith('_profils'):
            bpy.data.collections.remove(c)
    order = {n: i for i, n in enumerate(names)}
    tot = sum(MB.tri_count(o.data) for o in objs)
    mx = max(MB.tri_count(o.data) for o in objs)
    print('JEU %d triangles, %d maillages, max %d ; %.1f s' % (tot, len(objs), mx, time.time() - t0))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)


main()
