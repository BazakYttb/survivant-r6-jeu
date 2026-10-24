"""Rig rigide dans Blender : un empty par pièce au pivot de son articulation (hiérarchie de rig_spec), maillages
MON_<Pièce>_<n> parentés à leur pièce. Une pose = rotations (degrés, axes du monde Blender au repos) par pièce."""
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix, Euler
from mon_common import to_blender
from mon_skel import rig_spec
import mon_blend as MB


def build_rig(mesh_objs, col_name='MON_Rig'):
    col = MB.collection(col_name)
    R = rig_spec()
    root = bpy.data.objects.new('RIG_HumanoidRootPart', None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.3
    col.objects.link(root)
    emp = {'HumanoidRootPart': root}
    for name, (parent, piv, joint) in R.items():
        e = bpy.data.objects.new('RIG_' + name, None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = 0.06
        e['joint'] = joint
        e['parent_piece'] = parent
        col.objects.link(e)
        emp[name] = e
    bpy.context.view_layer.update()
    for name, (parent, piv, joint) in R.items():
        e = emp[name]
        e.location = Vector(to_blender(piv))
    bpy.context.view_layer.update()
    for name, (parent, piv, joint) in R.items():
        e = emp[name]
        p = emp[parent]
        mw = e.matrix_world.copy()
        e.parent = p
        e.matrix_parent_inverse = p.matrix_world.inverted()
        e.matrix_world = mw
    bpy.context.view_layer.update()
    for ob in mesh_objs:
        if 'piece' not in ob:
            continue
        p = emp[ob['piece']]
        mw = ob.matrix_world.copy()
        ob.parent = p
        ob.matrix_parent_inverse = p.matrix_world.inverted()
        ob.matrix_world = mw
    bpy.context.view_layer.update()
    return emp


def pose(emp, rotations):
    """rotations : {pièce: (rx, ry, rz)} en degrés autour des axes du monde Blender (X droite du monstre,
    Y devant lui, Z haut), appliquées au pivot de l'articulation."""
    for name, e in emp.items():
        e.rotation_mode = 'XYZ'
        e.rotation_euler = (0, 0, 0)
    for name, rot in rotations.items():
        emp[name].rotation_euler = Euler(tuple(math.radians(a) for a in rot), 'XYZ')
    bpy.context.view_layer.update()


def rest(emp):
    pose(emp, {})


# pose de présentation proche de la référence : tête tournée vers sa droite et penchée, bras droit tendu vers
# l'avant-droite, bras gauche qui pend, jambe droite un peu en avant, genou fléchi
HERO = {
    'Neck': (-4, -4, -24),
    'Head': (-4, -10, -24),
    'Jaw': (5, 0, 0),
    'UpperChest': (0, 0, -5),
    'Chest': (3, 2, -3),
    'UpperArm_R': (2, -6, 2),
    'Forearm_R': (6, -4, 0),
    'Hand_R': (0, 0, 8),
    'UpperArm_L': (-2, 14, -4),
    'Forearm_L': (12, 4, 35),
    'Hand_L': (10, 0, 40),
    'Thigh_R': (8, 0, 0),
    'Shin_R': (-12, 0, 0),
    'Foot_R': (4, 0, 0),
    'Thigh_L': (-5, 0, 0),
    'Shin_L': (2, 0, 0),
    'Foot_L': (3, 0, 0),
}


# pose de présentation de la créature en peau : la posture de repos (déjà voûtée, tête basse comme sur la référence),
# mâchoire un peu plus ouverte ; aucune autre pièce ne tourne, donc aucune jointure du rig rigide ne s'ouvre
HERO_PEAU = {
    'Jaw': (3, 0, 0),
}


# test de pliage : articulations fléchies franchement (contrôle des manchons et des raccords)
PLIAGE = {
    'Thigh_R': (30, 0, 0), 'Shin_R': (-45, 0, 0), 'Foot_R': (15, 0, 0),
    'Thigh_L': (-15, 0, 4), 'Shin_L': (-25, 0, 0),
    'UpperArm_R': (35, -15, 0), 'Forearm_R': (55, 0, 0), 'Hand_R': (20, 0, 0),
    'UpperArm_L': (-20, 20, 0), 'Forearm_L': (40, 0, 0),
    'Index1_R': (0, 0, 0), 'Neck': (12, 0, 15), 'Head': (10, 0, 10), 'Jaw': (14, 0, 0),
    'Abdomen': (8, 0, 5), 'Chest': (6, 0, 0),
}
