"""Livrables Roblox depuis la scène texturée : Monstre.blend (propre), Monstre.glb (textures intégrées), Monstre.fbx
(textures intégrées), Monstre_couleurs_sommets.glb (repli sans textures), rig.json.

usage : python exporter.py -- scene_texturee.blend dossier_monstre"""
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mon_common import to_blender, from_blender
from mon_skel import *
import mon_blend as MB
import mon_rig as RIG
import mon_scene2 as SC2

MARKERS = {'REF_A': (0.0, 5.0, 0.0), 'REF_B': (0.0, 7.0, 0.0), 'REF_C': (1.5, 5.0, 0.0), 'REF_D': (0.0, 5.0, -1.0)}
MARKER_SIZE = 0.05


def glow_pos():
    return HEAD_C + (FH * 0.42 - UH * 0.36) * SCALE * 0.98


def cube(name, center_roblox, size, col, color=(1, 0, 1)):
    me = bpy.data.meshes.new(name)
    h = size / 2
    c = to_blender(np.asarray(center_roblox, float))
    v = [(c[0] + x, c[1] + y, c[2] + z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.update()
    ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    ca.data.foreach_set('color', np.tile([*color, 1], 8).astype(np.float32))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    src, root = args[0], args[1]
    exp = os.path.join(root, 'export')
    bld = os.path.join(root, 'blender')
    os.makedirs(exp, exist_ok=True)
    os.makedirs(bld, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=src)
    # retirer la version HD (cuisson seulement) et les restes
    hd = bpy.data.collections.get('HD_Cuisson')
    if hd is not None:
        for o in list(hd.objects):
            me = o.data
            bpy.data.objects.remove(o)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(hd)
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    meshes = sorted([o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('MON_')], key=lambda o: o.name)
    for o in meshes:
        assert MB.tri_count(o.data) <= 19500, o.name
    # marqueurs
    mcol = MB.collection('MON_Marqueurs')
    marks = [cube(n, p, MARKER_SIZE, mcol) for n, p in MARKERS.items()]
    marks.append(cube('GLOW_MOUTH', glow_pos(), MARKER_SIZE, mcol, (1.0, 0.45, 0.1)))
    # images : empaquetées dans le .blend
    for img in bpy.data.images:
        if img.name.startswith('T_') and not img.packed_file:
            img.pack()
    # rig.json
    R = rig_spec()
    per_piece = {}
    for o in meshes:
        per_piece.setdefault(o['piece'], []).append(o.name)
    tris = {o.name: MB.tri_count(o.data) for o in meshes}
    rig = {
        'unites': 'studs (1 unité Blender = 1 stud)',
        'repere': 'Roblox : Y vers le haut, le monstre regarde vers -Z, sa droite est +X ; Blender (x, y, z) = Roblox (X, -Z, Y)',
        'hauteur_studs': None,
        'racine': {'nom': 'HumanoidRootPart', 'pivot': [round(float(x), 5) for x in J['Pelvis']]},
        'pieces': {name: {'parent': par, 'pivot': [round(float(x), 5) for x in piv], 'articulation': jn,
                          'maillages': per_piece.get(name, []),
                          'triangles': int(sum(tris[m] for m in per_piece.get(name, [])))}
                   for name, (par, piv, jn) in R.items()},
        'marqueurs': {n: [float(x) for x in p] for n, p in MARKERS.items()},
        'marqueur_taille': MARKER_SIZE,
        'lueur_gueule': [round(float(x), 5) for x in glow_pos()],
        'tete': {'centre': [round(float(x), 5) for x in HEAD_C], 'avant': [round(float(x), 5) for x in FH],
                 'haut': [round(float(x), 5) for x in UH], 'charniere_machoire': [round(float(x), 5) for x in JAW_HINGE],
                 'ouverture_machoire_deg': round(math.degrees(JAW_OPEN), 2)},
    }
    lo = np.array([1e9] * 3); hi = -lo
    for o in meshes:
        V = np.zeros(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get('co', V)
        V = from_blender(V.reshape(-1, 3))
        lo = np.minimum(lo, V.min(0)); hi = np.maximum(hi, V.max(0))
    rig['boite_englobante'] = {'min': [round(float(x), 3) for x in lo], 'max': [round(float(x), 3) for x in hi]}
    rig['hauteur_studs'] = round(float(hi[1] - max(lo[1], 0.0)), 3)
    rig['total_triangles'] = int(sum(tris.values()))
    with open(os.path.join(exp, 'rig.json'), 'w', encoding='utf-8') as fh:
        json.dump(rig, fh, ensure_ascii=False, indent=1)
    # le .blend : rig d'empties (maillages parentés, pose de repos) pour poser le monstre dans Blender, et une scène de
    # rendu prête (brume claire, lueur de la gueule parentée à la tête, caméra trois quarts) ; rien de cela n'est exporté
    emp = RIG.build_rig(meshes)
    g, gl = SC2.glow(glow_pos())
    bpy.context.view_layer.update()
    for o in (g, gl):
        mw = o.matrix_world.copy()
        o.parent = emp['Head']
        o.matrix_parent_inverse = emp['Head'].matrix_world.inverted()
        o.matrix_world = mw
    SC2.scene_mist()
    cam = MB.add_camera('Camera_TroisQuarts', np.array([-9.02, 2.0, -11.11]), np.array([0.3, 5.4, 0.0]), lens=38)
    scn = MB.setup_cycles(samples=96, res=(1024, 1536))
    scn.camera = cam
    scn.view_settings.look = 'AgX - Medium High Contrast'
    skin_mats = [m for m in bpy.data.materials if m.name.startswith('MAT_')]
    for m in skin_mats:                                   # diffusion sous la peau : rendu Blender seulement
        b = m.node_tree.nodes.get('Principled BSDF')
        b.inputs['Subsurface Weight'].default_value = 0.16
        b.inputs['Subsurface Radius'].default_value = (1.0, 0.38, 0.22)
        b.inputs['Subsurface Scale'].default_value = 0.02
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(bld, 'Monstre.blend'), compress=True)
    for m in skin_mats:
        m.node_tree.nodes.get('Principled BSDF').inputs['Subsurface Weight'].default_value = 0.0
    # export : maillages à plat (sans parents) + marqueurs
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    sel = meshes + marks
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in sel:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    t0 = time.time()
    bpy.ops.export_scene.gltf(filepath=os.path.join(exp, 'Monstre.glb'), export_format='GLB', use_selection=True,
                              export_apply=True, export_vertex_color='NONE', export_normals=True, export_texcoords=True,
                              export_materials='EXPORT', export_image_format='AUTO', export_yup=True)
    print('GLB %.1f Mo (%.1f s)' % (os.path.getsize(os.path.join(exp, 'Monstre.glb')) / 1e6, time.time() - t0))
    t0 = time.time()
    bpy.ops.export_scene.fbx(filepath=os.path.join(exp, 'Monstre.fbx'), use_selection=True, object_types={'MESH'},
                             global_scale=1.0, apply_unit_scale=False, apply_scale_options='FBX_SCALE_NONE',
                             axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True, mesh_smooth_type='OFF',
                             colors_type='NONE', add_leaf_bones=False, bake_anim=False, path_mode='COPY',
                             embed_textures=True, use_custom_props=False)
    print('FBX %.1f Mo (%.1f s)' % (os.path.getsize(os.path.join(exp, 'Monstre.fbx')) / 1e6, time.time() - t0))
    # repli sans textures : couleurs de sommets cuites depuis les textures
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 4
    bk = sc.render.bake
    bk.use_selected_to_active = False
    bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
    bk.target = 'VERTEX_COLORS'
    for o in meshes:
        ca = o.data.color_attributes.get('ColTex') or o.data.color_attributes.new('ColTex', 'FLOAT_COLOR', 'POINT')
        o.data.color_attributes.active_color = ca
        for x in bpy.context.selected_objects:
            x.select_set(False)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.bake(type='DIFFUSE', target='VERTEX_COLORS')
    vc = bpy.data.materials.new('MON_CouleursSommets')
    nt = vc.node_tree
    a = nt.nodes.new('ShaderNodeVertexColor'); a.layer_name = 'ColTex'
    nt.links.new(a.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    nt.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.45
    for o in meshes:
        o.data.materials.clear()
        o.data.materials.append(vc)
    for x in bpy.context.selected_objects:
        x.select_set(False)
    for o in sel:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(exp, 'Monstre_couleurs_sommets.glb'), export_format='GLB',
                              use_selection=True, export_apply=True, export_vertex_color='ACTIVE', export_normals=True,
                              export_materials='EXPORT', export_yup=True)
    print('GLB couleurs de sommets %.1f Mo' % (os.path.getsize(os.path.join(exp, 'Monstre_couleurs_sommets.glb')) / 1e6))
    print('%d maillages, %d triangles, max %d ; hauteur %.2f studs' % (len(meshes), rig['total_triangles'],
                                                                       max(tris.values()), rig['hauteur_studs']))


main()
