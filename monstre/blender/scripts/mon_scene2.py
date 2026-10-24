"""Scènes de rendu réalistes : brume claire (comme la référence) et intérieur sombre en bois (comme l'image de
l'utilisateur). Lueur orange dans la gueule (là où sera le Neon dans Roblox)."""
import math
import numpy as np
import bpy
from mathutils import Vector
from mon_common import to_blender
import mon_blend as MB
import mon_scene as SC
from mon_tex import NB


def glow(pos_roblox, col=None, strength=2.0, radius=0.06):
    """Petite source orange dans la gueule (objet émissif + lumière ponctuelle), non exportée."""
    col = col or MB.collection('Rendu')
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=tuple(to_blender(pos_roblox)), segments=16, ring_count=8)
    g = bpy.context.active_object
    g.name = 'Rendu_Lueur'
    for c in g.users_collection:
        c.objects.unlink(g)
    col.objects.link(g)
    m = bpy.data.materials.new('Rendu_Lueur')
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Emission Color'].default_value = (1.0, 0.38, 0.08, 1)
    b.inputs['Emission Strength'].default_value = 30.0
    b.inputs['Base Color'].default_value = (1.0, 0.4, 0.1, 1)
    g.data.materials.append(m)
    g.visible_shadow = False
    l = bpy.data.lights.new('Rendu_LueurLampe', 'POINT')
    l.energy = strength * 10
    l.color = (1.0, 0.45, 0.12)
    l.shadow_soft_size = 0.05
    lo = bpy.data.objects.new('Rendu_LueurLampe', l)
    col.objects.link(lo)
    lo.location = tuple(to_blender(pos_roblox))
    bpy.context.view_layer.update()
    return g, lo


def scene_mist(fog=True):
    SC.world_misty(top=(0.86, 0.865, 0.87), bottom=(0.62, 0.6, 0.57), light_top=(0.5, 0.5, 0.52),
                   light_bottom=(0.06, 0.055, 0.05))
    SC.ground_fade()
    SC.sun(energy=3.5, rot=(48, 0, 205), angle=4)
    SC.area('Contre', np.array([6.0, 14.0, 9.0]), np.array([0, 6.0, 0]), energy=2500, size=8)
    if fog:
        SC.haze(density=0.003, ground_density=0.03)


def _wood(nt, nb, scale=(1.0, 1.0, 1.0), dark=0.25, plank_axis='Z', planks=6.0):
    """Bois sombre en planches (bandes + veinage), renvoie (couleur, rugosité, hauteur)."""
    tc = nb.node('ShaderNodeTexCoord')
    mp = nb.node('ShaderNodeMapping', Vector=tc.outputs['Object'])
    mp.inputs['Scale'].default_value = scale
    sep = nb.node('ShaderNodeSeparateXYZ', Vector=mp.outputs['Vector'])
    axis = sep.outputs[plank_axis if plank_axis in ('X', 'Y', 'Z') else 'X']
    # planches : partie fractionnaire de la coordonnée -> joints sombres
    f = nb.math('FRACT', nb.math('MULTIPLY', axis, planks))
    gap = nb.math('MULTIPLY', nb.maprange(f, 0.0, 0.03, 0.0, 1.0, smooth=True), nb.maprange(f, 0.97, 1.0, 1.0, 0.0, smooth=True))
    pid = nb.math('FLOOR', nb.math('MULTIPLY', axis, planks))
    rnd = nb.node('ShaderNodeTexNoise', Vector=nb.node('ShaderNodeCombineXYZ', X=pid, Y=pid, Z=pid).outputs['Vector'],
                  Scale=3.1, Detail=0.0).outputs['Fac']
    grain = nb.node('ShaderNodeTexWave', Vector=mp.outputs['Vector'], Scale=2.0, Distortion=8.0, _wave_type='BANDS',
                    _bands_direction='Z' if plank_axis != 'Z' else 'X')
    grain.inputs['Detail'].default_value = 6.0
    dirt = nb.node('ShaderNodeTexNoise', Vector=mp.outputs['Vector'], Scale=0.8, Detail=6.0).outputs['Fac']
    v = nb.math('ADD', nb.math('MULTIPLY', grain.outputs['Fac'], 0.35), nb.math('MULTIPLY', rnd, 0.5))
    v = nb.math('ADD', v, nb.math('MULTIPLY', dirt, 0.4))
    cr = nb.node('ShaderNodeValToRGB', Fac=v)
    cr.color_ramp.elements[0].color = (0.035 * dark * 4, 0.02 * dark * 4, 0.012 * dark * 4, 1)
    cr.color_ramp.elements[1].color = (0.16 * dark * 4, 0.09 * dark * 4, 0.05 * dark * 4, 1)
    col = nb.mix(gap, (0.01, 0.007, 0.005, 1), cr.outputs['Color'])
    rough = nb.maprange(dirt, 0.3, 0.7, 0.45, 0.8)
    height = nb.math('ADD', nb.math('MULTIPLY', gap, 0.6), nb.math('MULTIPLY', grain.outputs['Fac'], 0.15))
    return col, rough, height


def scene_interior():
    """Pièce sombre : mur et plancher en vieilles planches, lumière chaude latérale, contre-jour froid, poussière."""
    col = MB.collection('Rendu')
    w = bpy.data.worlds.new('Interieur')
    bpy.context.scene.world = w
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.004, 0.004, 0.005, 1)
    # plancher
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    fl = bpy.context.active_object; fl.name = 'Plancher'
    for c in fl.users_collection:
        c.objects.unlink(fl)
    col.objects.link(fl)
    m = bpy.data.materials.new('Plancher')
    nb = NB(m.node_tree)
    c_, r_, h_ = _wood(m.node_tree, nb, scale=(1.0, 1.0, 1.0), dark=0.22, plank_axis='X', planks=2.2)
    b = m.node_tree.nodes['Principled BSDF']
    nb.L.new(c_, b.inputs['Base Color']); nb.L.new(r_, b.inputs['Roughness'])
    bump = nb.node('ShaderNodeBump', Strength=0.4, Distance=0.02, Height=h_)
    nb.L.new(bump.outputs['Normal'], b.inputs['Normal'])
    fl.data.materials.append(m)
    # mur du fond (planches verticales), derrière le monstre
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, -7.0, 10), rotation=(math.radians(90), 0, 0))
    wl = bpy.context.active_object; wl.name = 'Mur'
    for c in wl.users_collection:
        c.objects.unlink(wl)
    col.objects.link(wl)
    m2 = bpy.data.materials.new('Mur')
    nb2 = NB(m2.node_tree)
    c2, r2, h2 = _wood(m2.node_tree, nb2, scale=(1.0, 1.0, 1.0), dark=0.35, plank_axis='X', planks=1.6)
    b2 = m2.node_tree.nodes['Principled BSDF']
    nb2.L.new(c2, b2.inputs['Base Color']); nb2.L.new(r2, b2.inputs['Roughness'])
    bump2 = nb2.node('ShaderNodeBump', Strength=0.5, Distance=0.03, Height=h2)
    nb2.L.new(bump2.outputs['Normal'], b2.inputs['Normal'])
    wl.data.materials.append(m2)
    # lumières : chaude de côté (lampe), froide en contre-jour, petit rebond
    SC.area('Lampe', np.array([-7.0, 9.0, -6.0]), np.array([0, 6.5, -0.5]), energy=4200, size=3.0, color=(1.0, 0.72, 0.45))
    SC.area('Contre', np.array([5.0, 12.0, 8.0]), np.array([0, 6.5, 0]), energy=1500, size=5.0, color=(0.65, 0.75, 1.0))
    SC.area('Rebond', np.array([4.0, 2.0, -9.0]), np.array([0, 4.0, 0]), energy=400, size=10.0, color=(1.0, 0.85, 0.7))
    SC.haze(density=0.006, ground_density=0.012, color=(0.9, 0.8, 0.7))
