"""Remplace les 15 actions de Survivant_R6_Anime.blend par les animations corrigées de src/anim.py.

usage, avec Blender :
    blender -b dist/Survivant_R6_Anime.blend --python outils/maj_actions_blend.py -- src dist/Survivant_R6_Anime_corrige.blend
usage, avec bpy installé comme module Python (pip install bpy, Python 3.13 pour Blender 5.x) :
    python outils/maj_actions_blend.py dist/Survivant_R6_Anime.blend src dist/Survivant_R6_Anime_corrige.blend
contrôle d'un fichier (sauts d'une image à l'autre et amplitude des os, action par action) :
    python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime_corrige.blend

Même calcul que src/export_blend_rig.py (images à 30 i/s, poses des os depuis les poses monde des pièces),
appliqué à l'armature Rig_R6_Articule déjà présente : maillages, tenue, anatomie et pistes NLA conservés,
seules les images clés des actions changent.
"""
import sys
import os
import math

VERIFY = '--verifier' in sys.argv
if VERIFY:
    BLEND_IN, SRC, OUT = sys.argv[sys.argv.index('--verifier') + 1], None, None
elif '--' in sys.argv:
    argv = sys.argv[sys.argv.index('--') + 1:]
    BLEND_IN, SRC, OUT = None, argv[0], argv[1]
else:
    BLEND_IN, SRC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

import numpy as np
import bpy
from mathutils import Matrix

FPS = 30
CONV = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 3], [0, 0, 0, 1]], float)       # rig Roblox -> Blender
CONV_INV = np.linalg.inv(CONV)


def clear_action(act):
    """Supprime toutes les courbes d'une action (actions à emplacements de Blender 4.4+ ou ancienne API)."""
    removed = 0
    layers = getattr(act, 'layers', None)
    if layers is not None and len(layers) > 0:
        for layer in layers:
            for strip in layer.strips:
                for cb in getattr(strip, 'channelbags', []):
                    for fc in list(cb.fcurves):
                        cb.fcurves.remove(fc)
                        removed += 1
        return removed
    fcurves = getattr(act, 'fcurves', None)
    if fcurves is not None:
        for fc in list(fcurves):
            fcurves.remove(fc)
            removed += 1
    return removed


def armature():
    arm = bpy.data.objects.get('Rig_R6_Articule')
    if arm is None or arm.type != 'ARMATURE':
        raise SystemExit('armature Rig_R6_Articule introuvable')
    return arm


def update():
    sys.path.insert(0, os.path.abspath(SRC))
    import anim as A
    import rig_spec as RS
    arm = armature()
    bones = ['HumanoidRootPart'] + list(RS.PARTS)
    rest = {name: np.array(arm.data.bones[name].matrix_local) for name in bones}
    parent = {name: (arm.data.bones[name].parent.name if arm.data.bones[name].parent else None) for name in bones}
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass
    if arm.animation_data is None:
        arm.animation_data_create()
    ad = arm.animation_data
    active_before = ad.action.name if ad.action else None
    for clip in A.CLIPS:
        act = bpy.data.actions.get(clip.name)
        if act is None:
            act = bpy.data.actions.new(clip.name)
            act.use_fake_user = True
        n_old = clear_action(act)
        ad.action = act
        n = int(round(clip.length * FPS))
        for fi in range(n + 1):
            t = min(fi / FPS, clip.length)
            if clip.loop and fi == n:
                t = 0.0
            W = clip.world(t)
            pose_arm = {'HumanoidRootPart': rest['HumanoidRootPart']}
            for name in RS.PARTS:
                D = CONV @ W[name] @ A.inv4(A.REST[name]) @ CONV_INV
                pose_arm[name] = D @ rest[name]
            for name in bones:
                p = parent[name]
                if p is None:
                    basis = np.eye(4)
                else:
                    local_rest = np.linalg.inv(rest[p]) @ rest[name]
                    basis = np.linalg.inv(local_rest) @ np.linalg.inv(pose_arm[p]) @ pose_arm[name]
                pb = arm.pose.bones[name]
                pb.matrix_basis = Matrix(basis.tolist())
                pb.keyframe_insert('location', frame=fi + 1, group=name)
                pb.keyframe_insert('rotation_quaternion', frame=fi + 1, group=name)
        print(f'{clip.name}: {n_old} courbes remplacées, {n + 1} images')
    ad.action = bpy.data.actions.get(active_before) if active_before else None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT), compress=True, copy=True)
    print('enregistré :', OUT)


def verify():
    """Par action : plus grand saut de rotation d'un os entre deux images et plus grande rotation par rapport
    au repos (os, image). Une botte retournée (cuisse à ~180°) ou un bras qui tourne sur lui-même se voient ici."""
    arm = armature()
    sc = bpy.context.scene
    ad = arm.animation_data
    names = sorted(a.name for a in bpy.data.actions if a.name.startswith('Survivant_'))
    print(f'{len(names)} actions Survivant_*')
    for name in names:
        act = bpy.data.actions[name]
        ad.action = act
        f0, f1 = (int(round(v)) for v in act.frame_range)
        prev = None
        jump = (0.0, '', 0)
        amp = (0.0, '', 0)
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            cur = {pb.name: pb.matrix_basis.to_quaternion() for pb in arm.pose.bones}
            for b, q in cur.items():
                a = math.degrees(q.angle)
                a = min(a, 360 - a)
                if a > amp[0]:
                    amp = (a, b, f)
                if prev is not None:
                    d = math.degrees(prev[b].rotation_difference(q).angle)
                    d = min(d, 360 - d)
                    if d > jump[0]:
                        jump = (d, b, f)
            prev = cur
        print(f'{name:28s} images {f0}-{f1} ; saut max {jump[0]:5.1f}° ({jump[1]}, image {jump[2]}) ; '
              f'rotation max {amp[0]:5.1f}° ({amp[1]}, image {amp[2]})')


if BLEND_IN:
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(BLEND_IN))
if VERIFY:
    verify()
else:
    update()
