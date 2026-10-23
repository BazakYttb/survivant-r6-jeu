"""Blender helpers: import built parts, materials, preview renders, export."""
import os, json, fnmatch, math
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, '..', 'build')
PARTS = os.path.join(BUILD, 'parts')


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def manifest():
    return json.load(open(os.path.join(BUILD, 'manifest.json')))


def part_names(patterns=None):
    names = sorted(n[:-4] for n in os.listdir(PARTS) if n.endswith('.npz'))
    if patterns:
        names = [n for n in names if any(fnmatch.fnmatch(n, p) for p in patterns)]
    return names


_MAT = {}


def vc_material(gloss=0.45, name='VC'):
    key = (name, gloss)
    if key in _MAT:
        return _MAT[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Col'
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 1 - gloss
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.35
    _MAT[key] = m
    return m


def skin_material(alpha=1.0):
    """Roblox-like plastic for the R6 skin (colours come from the vertex colours); alpha < 1 = see-through."""
    key = ('SKIN', round(alpha, 3))
    if key in _MAT:
        return _MAT[key]
    m = bpy.data.materials.new(f'Skin_{alpha:.2f}')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Col'
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.55
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.3
    bsdf.inputs['Alpha'].default_value = alpha
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    _MAT[key] = m
    return m


GLOSS = {'bone': 0.25, 'tooth': 0.55, 'cartilage': 0.6, 'organ': 0.62, 'brain': 0.5, 'eye': 0.85,
         'vessel': 0.6, 'nerve': 0.45, 'muscle': 0.5, 'ligament': 0.5, 'gland': 0.55, 'disc': 0.5}


def load_part(name, man=None, collection=None, skin_alpha=1.0):
    d = np.load(os.path.join(PARTS, name + '.npz'))
    v, f, c = d['v'], d['f'], d['c']
    cn = d['cn'] if 'cn' in d else None
    # drop degenerate and duplicate faces up front (Mesh.validate would, and per-corner normals must stay aligned)
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    _, first = np.unique(np.sort(f, axis=1), axis=0, return_index=True)
    uniq = np.zeros(len(f), bool); uniq[first] = True
    keep &= uniq
    f = f[keep]
    if cn is not None:
        cn = cn[keep]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(v))
    me.vertices.foreach_set('co', v.ravel())
    me.loops.add(len(f) * 3)
    me.loops.foreach_set('vertex_index', f.ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set('loop_start', np.arange(0, len(f) * 3, 3))
    me.polygons.foreach_set('loop_total', np.full(len(f), 3))
    me.update(calc_edges=True)
    me.validate()
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    try:
        me.set_sharp_from_angle(angle=math.radians(52))
    except Exception as e:
        print('sharp failed', e)
    if cn is not None and len(cn) * 3 == len(me.loops):    # analytic parts carry exact per-corner normals
        me.normals_split_custom_set(cn.reshape(-1, 3).astype(float))
    ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    rgba = np.ones((len(v), 4), np.float32)
    rgba[:, :3] = srgb_to_lin(c)
    ca.data.foreach_set('color', rgba.ravel())
    me.color_attributes.active_color = ca
    ob = bpy.data.objects.new(name, me)
    cat = (man or {}).get(name, {}).get('cat', 'bone')
    if cat == 'skin':
        me.materials.append(skin_material(skin_alpha))
        ob.visible_shadow = skin_alpha >= 0.999
    else:
        me.materials.append(vc_material(GLOSS.get(cat, 0.4), 'VC_' + cat))
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def setup_render(res=(900, 1200), samples=24, bg=(0.06, 0.065, 0.075), view='AgX', exposure=0.0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = view
        sc.view_settings.look = 'AgX - Medium High Contrast' if view == 'AgX' else 'None'
        sc.view_settings.exposure = exposure
    except Exception:
        pass
    w = bpy.data.worlds.new('W'); sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes.get('Background')
    bgn.inputs['Color'].default_value = (*bg, 1)
    bgn.inputs['Strength'].default_value = 1.0
    sc.render.threads_mode = 'AUTO'


def add_lights(center, size):
    c = Vector(center)
    def area(loc, energy, sz, color=(1, 1, 1)):
        bpy.ops.object.light_add(type='AREA', location=c + Vector(loc) * size)
        L = bpy.context.active_object
        L.data.energy = energy * size * size
        L.data.size = sz * size
        L.data.color = color
        d = c - L.location
        L.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    area((-1.2, -2.0, 1.4), 420, 1.2, (1.0, 0.97, 0.92))
    area((1.8, -1.0, 0.6), 150, 1.0, (0.85, 0.9, 1.0))
    area((0.5, 2.2, 1.6), 300, 0.8, (1.0, 1.0, 1.0))


def camera(objs, view='front', margin=1.12, ortho=True, elev=8, azim=None):
    mn = np.array([1e9] * 3); mx = -mn
    for o in objs:   # vertex based (bound_box can be stale for freshly created meshes), in world space (posed parts)
        co = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get('co', co)
        M = np.array(o.matrix_world)
        co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        if len(co):
            mn = np.minimum(mn, co.min(0)); mx = np.maximum(mx, co.max(0))
    c = (mn + mx) / 2; ext = mx - mn
    az = {'front': 0, 'back': 180, 'left': 90, 'right': -90, 'threeq': 35}.get(view, 0) if azim is None else azim
    if view == 'top':
        d = Vector((0, 0.0001, 1)); el = 90
    if view == 'bottom':
        d = Vector((0, 0.0001, -1))
    a = math.radians(az); e = math.radians(elev)
    if view not in ('top', 'bottom'):
        d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    R = float(np.linalg.norm(ext))
    bpy.ops.object.camera_add(location=Vector(c) + d * R * 3)
    cam = bpy.context.active_object
    cam.rotation_euler = (Vector(c) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()          # refresh matrix_world before projecting the extents
    sc = bpy.context.scene
    sc.camera = cam
    rx, ry = sc.render.resolution_x, sc.render.resolution_y
    # projected extent
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0)); up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    pts = [Vector((x, y, z)) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    w_ = max(abs((p - Vector(c)).dot(right)) for p in pts) * 2
    h_ = max(abs((p - Vector(c)).dot(up)) for p in pts) * 2
    if ortho:
        cam.data.type = 'ORTHO'
        # Blender applies ortho_scale to the larger image dimension
        cam.data.ortho_scale = (max(w_, h_ * rx / ry) if rx >= ry else max(h_, w_ * ry / rx)) * margin
    else:
        cam.data.lens = 85
    cam.data.clip_end = R * 10
    add_lights(c, R)
    return cam


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
