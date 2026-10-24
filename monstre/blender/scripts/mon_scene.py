"""Scène de rendu : matières (goudron mouillé, crocs, gueule), monde clair et brumeux, sol, lumières, caméras."""
import math
import numpy as np
import bpy
from mon_common import to_blender
import mon_blend as MB


def _bsdf(mat):
    nt = mat.node_tree
    return nt, nt.nodes['Principled BSDF']


def tar_material(name='MON_Goudron'):
    """Noir mouillé et brillant : couleur des sommets, rugosité variable, vernis (coat) humide, micro-relief."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    nt, b = _bsdf(mat)
    N, L = nt.nodes, nt.links
    attr = N.new('ShaderNodeAttribute'); attr.attribute_name = 'Col'
    L.new(attr.outputs['Color'], b.inputs['Base Color'])
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 6.0; nz.inputs['Detail'].default_value = 3.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.3; mr.inputs['From Max'].default_value = 0.7
    mr.inputs['To Min'].default_value = 0.12; mr.inputs['To Max'].default_value = 0.32
    L.new(nz.outputs['Fac'], mr.inputs['Value'])
    L.new(mr.outputs['Result'], b.inputs['Roughness'])
    b.inputs['Specular IOR Level'].default_value = 0.55
    b.inputs['Coat Weight'].default_value = 0.65
    b.inputs['Coat Roughness'].default_value = 0.05
    b.inputs['Coat IOR'].default_value = 1.5
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 60.0; nz2.inputs['Detail'].default_value = 2.0
    L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.12; bump.inputs['Distance'].default_value = 0.01
    L.new(nz2.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], b.inputs['Coat Normal'])
    return mat


def glow_material(name='MON_Lueur', strength=18.0):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    nt, b = _bsdf(mat)
    b.inputs['Base Color'].default_value = (1.0, 0.35, 0.06, 1)
    b.inputs['Emission Color'].default_value = (1.0, 0.36, 0.07, 1)
    b.inputs['Emission Strength'].default_value = strength
    return mat


def world_misty(top=(0.80, 0.81, 0.82), bottom=(0.55, 0.53, 0.50), strength=1.0, light_top=(0.55, 0.56, 0.58),
                light_bottom=(0.035, 0.032, 0.03), light_strength=1.0):
    """Monde : fond clair et brumeux vu par la caméra ; éclairage plus sombre en bas (le monstre reste noir,
    avec des reflets venus du ciel)."""
    w = bpy.data.worlds.new('MON_Brume')
    bpy.context.scene.world = w
    nt = w.node_tree
    N, L = nt.nodes, nt.links
    bg = N['Background']
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -0.15; mr.inputs['From Max'].default_value = 0.5
    L.new(sep.outputs['Z'], mr.inputs['Value'])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = (*bottom, 1)
    mix.inputs['B'].default_value = (*top, 1)
    L.new(mr.outputs['Result'], mix.inputs['Factor'])
    mr2 = N.new('ShaderNodeMapRange'); mr2.inputs['From Min'].default_value = -0.05; mr2.inputs['From Max'].default_value = 0.85
    L.new(sep.outputs['Z'], mr2.inputs['Value'])
    mix2 = N.new('ShaderNodeMix'); mix2.data_type = 'RGBA'
    mix2.inputs['A'].default_value = (*light_bottom, 1)
    mix2.inputs['B'].default_value = (*light_top, 1)
    L.new(mr2.outputs['Result'], mix2.inputs['Factor'])
    lp = N.new('ShaderNodeLightPath')
    mix3 = N.new('ShaderNodeMix'); mix3.data_type = 'RGBA'
    L.new(lp.outputs['Is Camera Ray'], mix3.inputs['Factor'])
    L.new(mix2.outputs['Result'], mix3.inputs['A'])
    L.new(mix.outputs['Result'], mix3.inputs['B'])
    L.new(mix3.outputs['Result'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    return w


def ground(size=80.0, col=None):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = 'Sol'
    if col is not None:
        for c in g.users_collection:
            c.objects.unlink(g)
        col.objects.link(g)
    mat = bpy.data.materials.new('Sol')
    nt, b = _bsdf(mat)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.35; nz.inputs['Detail'].default_value = 6.0
    nz.inputs['Roughness'].default_value = 0.65
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    # tache sombre sous les pieds
    vm = N.new('ShaderNodeVectorMath'); vm.operation = 'LENGTH'
    L.new(tc.outputs['Object'], vm.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 1.5; mr.inputs['From Max'].default_value = 6.0
    L.new(vm.outputs['Value'], mr.inputs['Value'])
    mx = N.new('ShaderNodeMath'); mx.operation = 'ADD'
    L.new(mr.outputs['Result'], mx.inputs[0]); L.new(nz.outputs['Fac'], mx.inputs[1])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.55; cr.color_ramp.elements[0].color = (0.05, 0.045, 0.04, 1)
    cr.color_ramp.elements[1].position = 1.25; cr.color_ramp.elements[1].color = (0.45, 0.42, 0.38, 1)
    mapr = N.new('ShaderNodeMapRange'); mapr.inputs['From Min'].default_value = 0.0; mapr.inputs['From Max'].default_value = 1.6
    L.new(mx.outputs['Value'], mapr.inputs['Value'])
    L.new(mapr.outputs['Result'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.85
    g.data.materials.append(mat)
    return g


def sun(name='Soleil', energy=3.0, rot=(50, 0, 140), angle=6, color=(1.0, 0.98, 0.95)):
    l = bpy.data.lights.new(name, 'SUN')
    l.energy = energy
    l.angle = math.radians(angle)
    l.color = color
    o = bpy.data.objects.new(name, l)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = tuple(math.radians(a) for a in rot)
    return o


def assign(objs, mat):
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)


def ground_fade(radius=14.0, col=None):
    """Sol sombre et taché sous le monstre, qui devient transparent au loin (fond brumeux sans horizon)."""
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius, fill_type='NGON', location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = 'Sol'
    if col is not None:
        for c in g.users_collection:
            c.objects.unlink(g)
        col.objects.link(g)
    mat = bpy.data.materials.new('Sol')
    nt, b = _bsdf(mat)
    N, L = nt.nodes, nt.links
    out = N['Material Output']
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.45; nz.inputs['Detail'].default_value = 8.0
    nz.inputs['Roughness'].default_value = 0.7
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 3.0; nz2.inputs['Detail'].default_value = 4.0
    L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    vm = N.new('ShaderNodeVectorMath'); vm.operation = 'LENGTH'
    L.new(tc.outputs['Object'], vm.inputs[0])
    # tache sombre (racines, goudron) autour des pieds, irrégulière
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 1.2; mr.inputs['From Max'].default_value = 5.5
    L.new(vm.outputs['Value'], mr.inputs['Value'])
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'
    L.new(mr.outputs['Result'], add.inputs[0])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.9
    L.new(nz.outputs['Fac'], mul.inputs[0]); L.new(mul.outputs['Value'], add.inputs[1])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.62; cr.color_ramp.elements[0].color = (0.018, 0.016, 0.015, 1)
    cr.color_ramp.elements[1].position = 1.05; cr.color_ramp.elements[1].color = (0.30, 0.28, 0.25, 1)
    sub = N.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = 0.2
    L.new(add.outputs['Value'], sub.inputs[0])
    L.new(sub.outputs['Value'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], b.inputs['Base Color'])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.35; rr.inputs['To Max'].default_value = 0.9
    L.new(nz2.outputs['Fac'], rr.inputs['Value'])
    L.new(rr.outputs['Result'], b.inputs['Roughness'])
    # fondu vers la transparence au loin
    mr2 = N.new('ShaderNodeMapRange'); mr2.inputs['From Min'].default_value = radius * 0.35
    mr2.inputs['From Max'].default_value = radius * 0.95
    L.new(vm.outputs['Value'], mr2.inputs['Value'])
    tr = N.new('ShaderNodeBsdfTransparent')
    mix = N.new('ShaderNodeMixShader')
    L.new(mr2.outputs['Result'], mix.inputs['Fac'])
    L.new(b.outputs['BSDF'], mix.inputs[1])
    L.new(tr.outputs['BSDF'], mix.inputs[2])
    L.new(mix.outputs['Shader'], out.inputs['Surface'])
    g.data.materials.append(mat)
    return g


def haze(size=60.0, density=0.012, ground_density=0.06, ground_h=1.6, color=(0.85, 0.86, 0.88), col=None):
    """Brume volumétrique : légère partout, plus dense au ras du sol."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, size * 0.25 - 0.5))
    c = bpy.context.active_object
    c.name = 'Brume'
    c.scale = (size, size, size * 0.5)
    if col is not None:
        for cc in c.users_collection:
            cc.objects.unlink(c)
        col.objects.link(c)
    mat = bpy.data.materials.new('Brume')
    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        if n.bl_idname != 'ShaderNodeOutputMaterial':
            N.remove(n)
    out = N['Material Output']
    vol = N.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (*color, 1)
    vol.inputs['Anisotropy'].default_value = 0.3
    geo = N.new('ShaderNodeNewGeometry')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(geo.outputs['Position'], sep.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.0; mr.inputs['From Max'].default_value = ground_h
    mr.inputs['To Min'].default_value = ground_density; mr.inputs['To Max'].default_value = density
    mr.interpolation_type = 'SMOOTHSTEP'
    L.new(sep.outputs['Z'], mr.inputs['Value'])
    L.new(mr.outputs['Result'], vol.inputs['Density'])
    L.new(vol.outputs['Volume'], out.inputs['Volume'])
    c.data.materials.append(mat)
    c.visible_shadow = False
    return c


def area(name, loc_roblox, target_roblox, energy=200, size=6.0, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA')
    l.energy = energy
    l.size = size
    l.color = color
    o = bpy.data.objects.new(name, l)
    bpy.context.scene.collection.objects.link(o)
    MB.look_at(o, np.asarray(loc_roblox, float), np.asarray(target_roblox, float))
    return o
