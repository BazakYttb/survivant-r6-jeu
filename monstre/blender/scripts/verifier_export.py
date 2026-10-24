"""Contrôle des livrables : réimporte Monstre.glb (et Monstre.fbx) dans une scène vide et vérifie noms, triangles,
textures, marqueurs, normales et hauteur. usage : python verifier_export.py -- dossier_monstre"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy

root = sys.argv[sys.argv.index('--') + 1]
exp = os.path.join(root, 'export')
rig = json.load(open(os.path.join(exp, 'rig.json'), encoding='utf-8'))
MARKERS = rig['marqueurs']


def tri_count(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def world_verts(o):
    V = np.zeros(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get('co', V)
    M = np.array(o.matrix_world)
    return V.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def check(path, kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if kind == 'glb':
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    obs = [o for o in bpy.data.objects if o.type == 'MESH']
    mon = [o for o in obs if o.name.startswith('MON_')]
    errs = []
    tris = {o.name: tri_count(o.data) for o in mon}
    over = [n for n, t in tris.items() if t > 20000]
    if over:
        errs.append('plus de 20 000 triangles : %s' % over)
    pieces = set(rig['pieces'].keys())
    bad = [o.name for o in mon if o.name.rsplit('_', 1)[0][4:] not in pieces]
    if bad:
        errs.append('noms hors rig : %s' % bad)
    missing = [p for p in pieces if not any(o.name.rsplit('_', 1)[0][4:] == p for o in mon)]
    if missing:
        errs.append('pièces sans maillage : %s' % missing)
    # repère : en Blender après import glTF/FBX, Roblox (X, Y, Z) = Blender (x, z, -y)
    for n, p in list(MARKERS.items()) + [('GLOW_MOUTH', rig['lueur_gueule'])]:
        o = bpy.data.objects.get(n)
        if o is None:
            errs.append('marqueur absent : %s' % n)
            continue
        c = world_verts(o).mean(0)
        rb = np.array([c[0], c[2], -c[1]])
        if np.abs(rb - np.array(p)).max() > 1e-3:
            errs.append('marqueur %s à %s au lieu de %s' % (n, rb.round(4), p))
    allv = np.vstack([world_verts(o) for o in mon])
    h = allv[:, 2].max() - max(allv[:, 2].min(), 0.0)
    # normales : vers l'extérieur (moyenne de n . (p - centre de la pièce) > 0)
    inward = []
    for o in mon:
        me = o.data
        me.calc_loop_triangles()
        P = world_verts(o)
        n = np.zeros(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('normal', n)
        c = np.zeros(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('center', c)
        n = n.reshape(-1, 3); c = c.reshape(-1, 3)
        if (np.einsum('ij,ij->i', n, c - P.mean(0)) > 0).mean() < 0.6:
            inward.append(o.name)
    if inward:
        errs.append('normales douteuses : %s' % inward)
    sang = sorted(o.name for o in obs if o.name.startswith('SANG_'))
    if 'couleurs_sommets' not in os.path.basename(path):
        if len(sang) != 7:
            errs.append('gabarits de sang : %d au lieu de 7 (%s)' % (len(sang), sang))
        for n in sang:
            o = bpy.data.objects[n]
            m = o.data.materials[0] if o.data.materials else None
            imgs_m = [nd.image for nd in (m.node_tree.nodes if m and m.node_tree else []) if nd.type == 'TEX_IMAGE' and nd.image]
            if not imgs_m:
                errs.append('gabarit %s sans texture' % n)
            if abs(o.data.polygons[0].normal[2]) < 0.99 and abs(o.data.polygons[0].normal[1]) < 0.99:
                errs.append('gabarit %s pas horizontal' % n)
    imgs = [i for i in bpy.data.images if i.size[0] > 0]
    mats = set(m.name for o in mon for m in o.data.materials if m)
    print('%s : %d maillages MON_, %d triangles (max %d), %d matières, %d images, hauteur %.2f studs, %d gabarits de sang'
          % (os.path.basename(path), len(mon), sum(tris.values()), max(tris.values()), len(mats), len(imgs), h, len(sang)))
    for e in errs:
        print('  ERREUR', e)
    if not errs:
        print('  OK : noms, limite de triangles, marqueurs, normales')
    return errs


e = check(os.path.join(exp, 'Monstre.glb'), 'glb')
if os.path.exists(os.path.join(exp, 'Monstre.fbx')):
    e += check(os.path.join(exp, 'Monstre.fbx'), 'fbx')
if os.path.exists(os.path.join(exp, 'Monstre_couleurs_sommets.glb')):
    e += check(os.path.join(exp, 'Monstre_couleurs_sommets.glb'), 'glb')
print('VERIF', 'OK' if not e else 'ECHEC')
