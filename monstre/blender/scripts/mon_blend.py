"""Aides Blender (bpy 5.2) : objets, courbes, maillages, matières, caméra, rendu."""
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
from mon_common import to_blender, srgb_to_lin


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(ob, col=None):
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


_PROFILES = {}


def profile_object(sides):
    """Profil circulaire unitaire à `sides` côtés (objet courbe utilisé comme biseau)."""
    if sides in _PROFILES and _PROFILES[sides].name in bpy.data.objects:
        return _PROFILES[sides]
    cu = bpy.data.curves.new('PROFIL_%d' % sides, 'CURVE')
    cu.dimensions = '2D'
    sp = cu.splines.new('POLY')
    sp.points.add(sides - 1)
    for i in range(sides):
        a = 2 * math.pi * i / sides + math.pi / sides
        sp.points[i].co = (math.cos(a), math.sin(a), 0, 1)
    sp.use_cyclic_u = True
    ob = bpy.data.objects.new('PROFIL_%d' % sides, cu)
    col = collection('_profils')
    col.objects.link(ob)
    col.hide_render = True
    col.hide_viewport = True
    _PROFILES[sides] = ob
    return ob


def curve_object(name, strands, sides, col=None, caps=True):
    """Objet courbe : une spline POLY par brin (points (N,3) Roblox, rayons (N,)), biseau à `sides` côtés."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.twist_mode = 'MINIMUM'
    cu.use_fill_caps = caps
    if sides in (4, 6, 8, 10):
        cu.bevel_mode = 'ROUND'
        cu.bevel_depth = 1.0
        cu.bevel_resolution = (sides - 4) // 2
    else:
        cu.bevel_mode = 'OBJECT'
        cu.bevel_object = profile_object(sides)
    for P, R in strands:
        Pb = to_blender(P)
        sp = cu.splines.new('POLY')
        sp.points.add(len(Pb) - 1)
        co = np.hstack([Pb, np.ones((len(Pb), 1))]).astype(np.float32).ravel()
        sp.points.foreach_set('co', co)
        sp.points.foreach_set('radius', np.asarray(R, np.float32))
    ob = bpy.data.objects.new(name, cu)
    link(ob, col)
    return ob


def evaluated_mesh(ob, name=None):
    """Maillage évalué (modificateurs appliqués) d'un objet, comme nouveau bloc de données."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.materials.clear()
    if name:
        me.name = name
    return me


def mesh_object(name, V, F, col=None, colors=None, smooth=True, roblox=True):
    """Objet maillage depuis numpy (V en repère Roblox si roblox=True), couleurs sRGB par sommet (N,3)."""
    me = bpy.data.meshes.new(name)
    Vb = to_blender(V) if roblox else np.asarray(V, float)
    F = np.asarray(F, np.int64)
    me.vertices.add(len(Vb))
    me.vertices.foreach_set('co', Vb.astype(np.float32).ravel())
    nl = F.shape[1]
    me.loops.add(len(F) * nl)
    me.loops.foreach_set('vertex_index', F.astype(np.int32).ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set('loop_start', (np.arange(len(F)) * nl).astype(np.int32))
    me.update(calc_edges=True)
    me.validate()
    if smooth:
        me.shade_smooth()
    if colors is not None:
        set_point_colors(me, colors)
    ob = bpy.data.objects.new(name, me)
    link(ob, col)
    return ob


def set_point_colors(me, colors_srgb, name='Col'):
    ca = me.color_attributes.get(name)
    if ca is None:
        ca = me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    c = srgb_to_lin(np.asarray(colors_srgb, float))
    rgba = np.hstack([c, np.ones((len(c), 1))]).astype(np.float32)
    ca.data.foreach_set('color', rgba.ravel())
    me.color_attributes.active_color = ca
    me.color_attributes.render_color_index = me.color_attributes.find(name)
    return ca


def tri_count(me):
    n = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_total', n)
    return int((n - 2).sum())


def look_at(cam, eye_roblox, target_roblox, roll=0.0):
    eye = Vector(to_blender(eye_roblox))
    tgt = Vector(to_blender(target_roblox))
    d = tgt - eye
    q = d.to_track_quat('-Z', 'Y')
    cam.location = eye
    cam.rotation_euler = q.to_euler()
    if roll:
        cam.rotation_euler.rotate_axis('Z', roll)


def add_camera(name, eye, target, lens=50, sensor=36, col=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_start = 0.05
    cd.clip_end = 500
    cam = bpy.data.objects.new(name, cd)
    link(cam, col)
    look_at(cam, eye, target)
    return cam


def setup_cycles(samples=64, res=(1024, 1536), denoise=True, threads=0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = denoise
    sc.cycles.max_bounces = 6
    sc.cycles.glossy_bounces = 3
    sc.cycles.diffuse_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 4
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 0.5
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    if threads:
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = threads
    sc.view_settings.view_transform = 'AgX'
    return sc


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ----------------------------------------------------------------------------------------------------------------
# Curves (courbes de cheveux) + Geometry Nodes : tubes, fusion SDF


def curves_object(name, strands, col=None):
    """Objet Curves : strands = [(P, R, C, kind, nrm, flat)] en repère Roblox. Attributs : radius, Col (linéaire),
    Mat (type de matière) et nrm (normale d'aplatissement, repère Blender)."""
    cv = bpy.data.hair_curves.new(name)
    sizes = [len(st[0]) for st in strands]
    cv.add_curves(sizes)
    P = np.vstack([to_blender(st[0]) for st in strands]).astype(np.float32)
    R = np.concatenate([np.asarray(st[1], float) for st in strands]).astype(np.float32)
    C, K, Nn = [], [], []
    for st in strands:
        n = len(st[0])
        c = np.asarray(st[2], float)
        C.append(np.broadcast_to(c, (n, 3)) if c.ndim == 1 else c)
        K.append(np.full(n, float(st[3])))
        nr = st[4]
        Nn.append(np.zeros((n, 3)) if nr is None else to_blender(np.broadcast_to(np.asarray(nr, float), (n, 3))))
    C = srgb_to_lin(np.vstack(C))
    C = np.hstack([C, np.ones((len(C), 1))]).astype(np.float32)
    cv.position_data.foreach_set('vector', P.ravel())
    ra = cv.attributes.get('radius') or cv.attributes.new('radius', 'FLOAT', 'POINT')
    ra.data.foreach_set('value', R)
    cv.attributes.new('Col', 'FLOAT_COLOR', 'POINT').data.foreach_set('color', C.ravel())
    cv.attributes.new('Mat', 'FLOAT', 'POINT').data.foreach_set('value', np.concatenate(K).astype(np.float32))
    cv.attributes.new('nrm', 'FLOAT_VECTOR', 'POINT').data.foreach_set('vector', np.vstack(Nn).astype(np.float32).ravel())
    ob = bpy.data.objects.new(name, cv)
    link(ob, col)
    return ob


def _gn_tree(name):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = ng.nodes.new('NodeGroupInput')
    go = ng.nodes.new('NodeGroupOutput')
    return ng, gi, go


def _named(N, name, dtype):
    na = N.new('GeometryNodeInputNamedAttribute')
    na.data_type = dtype
    na.inputs['Name'].default_value = name
    return na


def _store(N, L, geo_socket, name, dtype, value_socket, domain='POINT'):
    st = N.new('GeometryNodeStoreNamedAttribute')
    st.data_type = dtype
    st.domain = domain
    st.inputs['Name'].default_value = name
    L.new(geo_socket, st.inputs['Geometry'])
    L.new(value_socket, st.inputs['Value'])
    return st.outputs['Geometry']


def _curve_to_tubes(N, L, curve_socket, sides, flat=1.0):
    """Courbes -> tubes (attributs Tangent et rad conservés) ; profil écrasé suivant la normale si flat < 1."""
    poly = N.new('GeometryNodeCurveSplineType'); poly.spline_type = 'POLY'
    L.new(curve_socket, poly.inputs['Curve'])
    g = poly.outputs['Curve']
    if flat < 0.999:
        scn = N.new('GeometryNodeSetCurveNormal'); scn.inputs['Mode'].default_value = 'Free'
        L.new(g, scn.inputs['Curve'])
        L.new(_named(N, 'nrm', 'FLOAT_VECTOR').outputs['Attribute'], scn.inputs['Normal'])
        g = scn.outputs['Curve']
    tan = N.new('GeometryNodeInputTangent')
    g = _store(N, L, g, 'Tangent', 'FLOAT_VECTOR', tan.outputs['Tangent'])
    radn = N.new('GeometryNodeInputRadius')
    g = _store(N, L, g, 'rad', 'FLOAT', radn.outputs['Radius'])
    circ = N.new('GeometryNodeCurvePrimitiveCircle'); circ.inputs['Resolution'].default_value = sides
    prof = circ.outputs['Curve']
    if flat < 0.999:
        tg = N.new('GeometryNodeTransform'); tg.inputs['Scale'].default_value = (flat, 1.0, 1.0)
        L.new(prof, tg.inputs['Geometry']); prof = tg.outputs['Geometry']
    c2m = N.new('GeometryNodeCurveToMesh'); c2m.inputs['Fill Caps'].default_value = True
    L.new(g, c2m.inputs['Curve'])
    L.new(prof, c2m.inputs['Profile Curve'])
    L.new(radn.outputs['Radius'], c2m.inputs['Scale'])
    return c2m.outputs['Mesh']


def _lumps(N, L, mesh_socket, amp=0.16, freq=7.0):
    """Bosses organiques : déplacement le long de la normale, proportionnel au rayon local du tendon."""
    pos = N.new('GeometryNodeInputPosition')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = freq; nz.inputs['Detail'].default_value = 2.0
    L.new(pos.outputs['Position'], nz.inputs['Vector'])
    sub = N.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = 0.5
    L.new(nz.outputs['Fac'], sub.inputs[0])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 2.0 * amp
    L.new(sub.outputs['Value'], mul.inputs[0])
    mul2 = N.new('ShaderNodeMath'); mul2.operation = 'MULTIPLY'
    L.new(mul.outputs['Value'], mul2.inputs[0])
    L.new(_named(N, 'rad', 'FLOAT').outputs['Attribute'], mul2.inputs[1])
    nrm = N.new('GeometryNodeInputNormal')
    vs = N.new('ShaderNodeVectorMath'); vs.operation = 'SCALE'
    L.new(nrm.outputs['Normal'], vs.inputs[0]); L.new(mul2.outputs['Value'], vs.inputs['Scale'])
    sp = N.new('GeometryNodeSetPosition')
    L.new(mesh_socket, sp.inputs['Geometry']); L.new(vs.outputs['Vector'], sp.inputs['Offset'])
    return sp.outputs['Geometry']


def gn_tubes(src_curves, sides, name, flat=1.0, lumps=0.16):
    """Arbre GN : courbes -> tubes (bandes aplaties si flat < 1), bosses organiques, lissé."""
    ng, gi, go = _gn_tree(name)
    N, L = ng.nodes, ng.links
    oi = N.new('GeometryNodeObjectInfo'); oi.transform_space = 'ORIGINAL'
    oi.inputs['Object'].default_value = src_curves
    m = _curve_to_tubes(N, L, oi.outputs['Geometry'], sides, flat)
    if lumps:
        m = _lumps(N, L, m, lumps)
    ss = N.new('GeometryNodeSetShadeSmooth')
    L.new(m, ss.inputs['Geometry'])
    L.new(ss.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def gn_fuse(name, src_curves=None, src_mesh=None, cut_mesh=None, voxel=0.012, fillet=3, offset=0.0,
            sides=24, smooth=0, blur_col=0, close=0.0, smooth_pos=0):
    """Arbre GN de fusion : tubes + maillages fermés -> grille SDF -> congés (SDF Grid Fillet) -> (soustraction)
    -> maillage ; Col, Mat et Tangent sont repris de la source la plus proche."""
    ng, gi, go = _gn_tree(name)
    N, L = ng.nodes, ng.links
    join = N.new('GeometryNodeJoinGeometry')
    if src_curves is not None:
        oi = N.new('GeometryNodeObjectInfo'); oi.transform_space = 'ORIGINAL'
        oi.inputs['Object'].default_value = src_curves
        L.new(_curve_to_tubes(N, L, oi.outputs['Geometry'], sides), join.inputs['Geometry'])
    if src_mesh is not None:
        om = N.new('GeometryNodeObjectInfo'); om.transform_space = 'ORIGINAL'
        om.inputs['Object'].default_value = src_mesh
        L.new(om.outputs['Geometry'], join.inputs['Geometry'])
    sdf = N.new('GeometryNodeMeshToSDFGrid')
    sdf.inputs['Voxel Size'].default_value = voxel
    sdf.inputs['Band Width'].default_value = 3 + max(fillet, 0) + 2 * int(math.ceil(close / voxel))
    L.new(join.outputs['Geometry'], sdf.inputs['Mesh'])
    g = sdf.outputs['SDF Grid']
    if close > 0:                     # fermeture : dilatation, puis (congés) érosion -> peau tendue sur les os
        of1 = N.new('GeometryNodeSDFGridOffset'); of1.inputs['Distance'].default_value = close
        L.new(g, of1.inputs['Grid']); g = of1.outputs['Grid']
    if fillet > 0:
        fl = N.new('GeometryNodeSDFGridFillet'); fl.inputs['Iterations'].default_value = fillet
        L.new(g, fl.inputs['Grid']); g = fl.outputs['Grid']
    if smooth > 0:
        sm = N.new('GeometryNodeSDFGridLaplacian'); sm.inputs['Iterations'].default_value = smooth
        L.new(g, sm.inputs['Grid']); g = sm.outputs['Grid']
    if close > 0:
        of2 = N.new('GeometryNodeSDFGridOffset'); of2.inputs['Distance'].default_value = -close
        L.new(g, of2.inputs['Grid']); g = of2.outputs['Grid']
    if offset:
        of = N.new('GeometryNodeSDFGridOffset'); of.inputs['Distance'].default_value = offset
        L.new(g, of.inputs['Grid']); g = of.outputs['Grid']
    if cut_mesh is not None:
        oc = N.new('GeometryNodeObjectInfo'); oc.transform_space = 'ORIGINAL'
        oc.inputs['Object'].default_value = cut_mesh
        sdf2 = N.new('GeometryNodeMeshToSDFGrid')
        sdf2.inputs['Voxel Size'].default_value = voxel
        sdf2.inputs['Band Width'].default_value = 3
        L.new(oc.outputs['Geometry'], sdf2.inputs['Mesh'])
        bo = N.new('GeometryNodeSDFGridBoolean'); bo.operation = 'DIFFERENCE'
        L.new(g, bo.inputs['Grid 1']); L.new(sdf2.outputs['SDF Grid'], bo.inputs['Grid 2'])
        g = bo.outputs['Grid']
    g2m = N.new('GeometryNodeGridToMesh')
    g2m.inputs['Threshold'].default_value = 0.0
    g2m.inputs['Adaptivity'].default_value = 0.0
    L.new(g, g2m.inputs['Grid'])
    m = g2m.outputs['Mesh']
    if smooth_pos > 0:                # lissage des positions : efface les facettes de la grille sur les petites formes
        blp = N.new('GeometryNodeBlurAttribute'); blp.data_type = 'FLOAT_VECTOR'
        blp.inputs['Iterations'].default_value = smooth_pos
        L.new(N.new('GeometryNodeInputPosition').outputs['Position'], blp.inputs['Value'])
        spn = N.new('GeometryNodeSetPosition')
        L.new(m, spn.inputs['Geometry']); L.new(blp.outputs['Value'], spn.inputs['Position'])
        m = spn.outputs['Geometry']
    for aname, dtype in (('Col', 'FLOAT_COLOR'), ('Mat', 'FLOAT'), ('Tangent', 'FLOAT_VECTOR')):
        sn = N.new('GeometryNodeSampleNearestSurface'); sn.data_type = dtype
        L.new(join.outputs['Geometry'], sn.inputs['Mesh'])
        L.new(_named(N, aname, dtype).outputs['Attribute'], sn.inputs['Value'])
        m = _store(N, L, m, aname, dtype, sn.outputs['Value'])
    if blur_col:
        bl = N.new('GeometryNodeBlurAttribute'); bl.data_type = 'FLOAT_COLOR'
        bl.inputs['Iterations'].default_value = blur_col
        L.new(_named(N, 'Col', 'FLOAT_COLOR').outputs['Attribute'], bl.inputs['Value'])
        m = _store(N, L, m, 'Col', 'FLOAT_COLOR', bl.outputs['Value'])
    ss = N.new('GeometryNodeSetShadeSmooth')
    L.new(m, ss.inputs['Geometry'])
    L.new(ss.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def host_with_tree(name, ng, col=None):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    link(ob, col)
    mod = ob.modifiers.new('GN', 'NODES')
    mod.node_group = ng
    return ob


def bake_mesh(ob, name=None, target_tris=None):
    """Évalue un objet (modificateurs) en maillage ; décimation jusqu'à target_tris si demandé."""
    me = evaluated_mesh(ob, name)
    if target_tris is not None and tri_count(me) > target_tris:
        tmp = bpy.data.objects.new('_dec_tmp', me)
        link(tmp)
        ratio = target_tris / tri_count(me)
        for _ in range(3):
            mod = tmp.modifiers.new('dec', 'DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = min(1.0, ratio)
            mod.use_collapse_triangulate = True
            me2 = evaluated_mesh(tmp, name)
            tmp.modifiers.remove(mod)
            n = tri_count(me2)
            if n <= target_tris or ratio < 0.02:
                break
            bpy.data.meshes.remove(me2)
            ratio *= 0.97 * target_tris / n
        bpy.data.objects.remove(tmp)
        bpy.data.meshes.remove(me)
        me = me2
    return me


ATTRS = (('Col', 'FLOAT_COLOR', 4), ('Mat', 'FLOAT', 1), ('Tangent', 'FLOAT_VECTOR', 3))


def mesh_arrays(me):
    """Sommets (Blender), triangles, attributs par sommet {Col (RGBA linéaire), Mat, Tangent}."""
    me.calc_loop_triangles()
    nv = len(me.vertices)
    V = np.zeros(nv * 3, np.float32); me.vertices.foreach_get('co', V)
    T = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', T)
    A = {}
    for name, dtype, k in ATTRS:
        a = me.attributes.get(name)
        if a is None:
            continue
        key = {'FLOAT_COLOR': 'color', 'FLOAT': 'value', 'FLOAT_VECTOR': 'vector'}[dtype]
        arr = np.zeros(len(a.data) * k, np.float32)
        a.data.foreach_get(key, arr)
        arr = arr.reshape(-1, k) if k > 1 else arr
        if a.domain == 'CORNER':
            vi = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
            out = np.zeros((nv, k) if k > 1 else nv, np.float32)
            out[vi] = arr
            arr = out
        A[name] = arr
    return V.reshape(-1, 3), T.reshape(-1, 3), A


def set_attrs(me, A):
    for name, dtype, k in ATTRS:
        if name not in A:
            continue
        key = {'FLOAT_COLOR': 'color', 'FLOAT': 'value', 'FLOAT_VECTOR': 'vector'}[dtype]
        a = me.attributes.get(name) or me.attributes.new(name, dtype, 'POINT')
        a.data.foreach_set(key, np.asarray(A[name], np.float32).ravel())
    if 'Col' in A:
        ca = me.color_attributes.get('Col')
        me.color_attributes.active_color = ca
        me.color_attributes.render_color_index = me.color_attributes.find('Col')
