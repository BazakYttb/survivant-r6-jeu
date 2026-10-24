"""Rendus finaux de la créature texturée : python rendus.py -- scene.blend dossier [vues] [largeur] [spp]
vues : trois_quarts, trois_quarts_sombre, face, profil, dos, tete, tete_sombre, tete_sans_lueur (contrôle : gueule sans
la lumière orange), main, pliage (séparées par des virgules)."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mon_common import *
from mon_skel import *
import mon_blend as MB
import mon_scene2 as SC2
import mon_rig as RIG

args = sys.argv[sys.argv.index('--') + 1:]
blend, folder = args[0], args[1]
views = args[2].split(',') if len(args) > 2 else ['trois_quarts']
width = int(args[3]) if len(args) > 3 else 1024
spp = int(args[4]) if len(args) > 4 else 128
os.makedirs(folder, exist_ok=True)

CAMS = {
    'trois_quarts': dict(az=-40, d=14.5, h=2.0, ty=5.4, lens=38, tx=0.3, pose='hero', scene='mist'),
    'trois_quarts_sombre': dict(az=-38, d=14.0, h=2.4, ty=5.5, lens=38, tx=0.3, pose='hero', scene='interior'),
    'face': dict(az=0, d=17, h=4.5, ty=5.5, lens=40, tx=0, pose='', scene='mist'),
    'profil': dict(az=90, d=17, h=4.5, ty=5.5, lens=40, tx=0, tz=-0.5, pose='', scene='mist'),
    'dos': dict(az=180, d=17, h=5.5, ty=5.6, lens=40, tx=0, pose='', scene='mist'),
    'tete': dict(az=-35, d=4.6, h=8.9, ty=9.6, lens=50, tx=0, tz=-2.2, pose='', scene='mist'),
    'tete_sombre': dict(az=-30, d=4.4, h=8.6, ty=9.5, lens=50, tx=0, tz=-2.2, pose='', scene='interior'),
    'tete_sans_lueur': dict(az=-35, d=4.6, h=8.9, ty=9.6, lens=50, tx=0, tz=-2.2, pose='', scene='mist', lueur=False),
    'main': dict(az=74, d=4.1, h=3.75, ty=3.45, lens=50, tx=2.5, tz=-0.8, pose='', scene='mist'),
    'pliage': dict(az=-40, d=15.0, h=3.0, ty=5.4, lens=38, tx=0.3, pose='pliage', scene='mist'),
}


def setup(view):
    bpy.ops.wm.open_mainfile(filepath=blend)
    hd = bpy.data.collections.get('HD_Cuisson')
    if hd is not None:
        hd.hide_render = True
    for m in bpy.data.materials:
        if m.name.startswith('MAT_'):
            b = m.node_tree.nodes.get('Principled BSDF')
            b.inputs["Subsurface Weight"].default_value = 0.16
            b.inputs['Subsurface Radius'].default_value = (1.0, 0.38, 0.22)
            b.inputs["Subsurface Scale"].default_value = 0.02
    v = CAMS[view]
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('MON_')]
    emp = RIG.build_rig(meshes)
    gpos = HEAD_C + (FH * 0.42 - UH * 0.36) * SCALE * 0.98
    head_emp = emp['Head']
    if v.get('lueur', True):
        g, gl = SC2.glow(gpos)
        bpy.context.view_layer.update()
        for o in (g, gl):
            mw = o.matrix_world.copy()
            o.parent = head_emp
            o.matrix_parent_inverse = head_emp.matrix_world.inverted()
            o.matrix_world = mw
    bpy.context.view_layer.update()
    if v['pose'] == 'hero':
        RIG.pose(emp, RIG.HERO_PEAU)
    elif v['pose'] == 'pliage':
        RIG.pose(emp, RIG.PLIAGE)
    if v['scene'] == 'mist':
        SC2.scene_mist()
    else:
        SC2.scene_interior()
    az = math.radians(v['az'])
    tgt = np.array([v['tx'], v['ty'], v.get('tz', 0.0)])
    eye = tgt * np.array([1, 0, 1]) + np.array([math.sin(az) * v['d'], v['h'], -math.cos(az) * v['d']])
    cam = MB.add_camera('Camera_' + view, eye, tgt, lens=v['lens'])
    scn = MB.setup_cycles(samples=spp, res=(width, int(width * 1.5)))
    scn.camera = cam
    scn.view_settings.look = 'AgX - Medium High Contrast'
    return scn


for view in views:
    setup(view)
    MB.render(os.path.join(folder, view + '.png'))
    print('rendu', view, flush=True)
