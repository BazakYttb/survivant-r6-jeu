"""Exporte une version allégée du maillage du monstre (par pièce, repère Roblox du modèle) pour les aperçus rapides.
usage : python dump_proxy.py -- scene.blend sortie.npz [ratio]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mon_common import from_blender

args = sys.argv[sys.argv.index('--') + 1:]
blend, out = args[0], args[1]
ratio = float(args[2]) if len(args) > 2 else 0.12
bpy.ops.wm.open_mainfile(filepath=blend)
data = {}
for ob in bpy.data.objects:
    if ob.type != 'MESH' or not ob.name.startswith('MON_') or 'piece' not in ob:
        continue
    if any(c.name == 'HD_Cuisson' for c in ob.users_collection):
        continue
    m = ob.modifiers.new('dec', 'DECIMATE')
    m.ratio = ratio
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    V = np.array([ob.matrix_world @ v.co for v in me.vertices], float)
    T = np.array([t.vertices[:] for t in me.loop_triangles], int)
    ev.to_mesh_clear()
    ob.modifiers.remove(m)
    p = ob['piece']
    V = from_blender(V)
    if p in data:
        V0, T0 = data[p]
        data[p] = (np.concatenate([V0, V]), np.concatenate([T0, T + len(V0)]))
    else:
        data[p] = (V, T)
np.savez_compressed(out, **{('V_' + k): v[0] for k, v in data.items()}, **{('T_' + k): v[1] for k, v in data.items()})
print('pieces', len(data), 'tris', sum(len(v[1]) for v in data.values()))
