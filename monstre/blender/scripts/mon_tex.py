"""Textures réalistes faites dans Blender : matière procédurale (fibres orientées le long des tendons, pores,
mucus, creux brun-rouge, zones plus ou moins mouillées), dépliage UV (Smart UV Project), cuisson Cycles en images
(couleur, rugosité, normale) puis matière finale à images, exportable en glTF/FBX (SurfaceAppearance dans Roblox).

Types (attribut Mat) : 0 tendon, 1 crâne, 2 dent, 3 gencive, 4 griffe, 5 mucus, 6 coeur sombre."""
import math
import os
import time
import numpy as np
import bpy

S_PERP = 22.0          # fréquence des fibres en travers (par stud)
S_PAR = 1.3            # fréquence le long des fibres


class NB:
    """Petit constructeur de graphe de nœuds de shader."""

    def __init__(self, nt):
        self.nt = nt
        self.N = nt.nodes
        self.L = nt.links

    def node(self, typ, **inputs):
        n = self.N.new(typ)
        for k, v in inputs.items():
            if k.startswith('_'):
                setattr(n, k[1:], v)
            else:
                self.set_in(n, k, v)
        return n

    def set_in(self, n, k, v):
        sock = n.inputs[k] if not isinstance(k, int) else n.inputs[k]
        if hasattr(v, 'is_output') or isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, clamp=False):
        n = self.N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        self.set_in(n, 0, a)
        if b is not None:
            self.set_in(n, 1, b)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.N.new('ShaderNodeVectorMath'); n.operation = op
        self.set_in(n, 0, a)
        if b is not None:
            self.set_in(n, 1, b)
        if scale is not None:
            self.set_in(n, 'Scale', scale)
        out = n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']
        return out

    def maprange(self, v, a, b, c=0.0, d=1.0, smooth=False, clamp=True):
        n = self.N.new('ShaderNodeMapRange')
        if smooth:
            n.interpolation_type = 'SMOOTHSTEP'
        n.clamp = clamp
        self.set_in(n, 'Value', v)
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c; n.inputs['To Max'].default_value = d
        return n.outputs['Result']

    def mix(self, fac, a, b, dtype='RGBA'):
        n = self.N.new('ShaderNodeMix'); n.data_type = dtype
        self.set_in(n, 'Factor', fac)
        if dtype == 'RGBA':
            self.set_in(n, 'A', a); self.set_in(n, 'B', b)
            return n.outputs['Result']
        ia = [i for i in n.inputs if i.name == 'A' and i.enabled][0]
        ib = [i for i in n.inputs if i.name == 'B' and i.enabled][0]
        self.set_in(n, ia.identifier if False else n.inputs.find(ia.identifier) if False else 0, fac)
        if hasattr(a, 'is_output') or isinstance(a, bpy.types.NodeSocket):
            self.L.new(a, ia)
        else:
            ia.default_value = a
        if hasattr(b, 'is_output') or isinstance(b, bpy.types.NodeSocket):
            self.L.new(b, ib)
        else:
            ib.default_value = b
        out = [o for o in n.outputs if o.name == 'Result' and o.enabled][0]
        return out

    def rgbmul(self, a, b):
        n = self.N.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = 'MULTIPLY'
        n.inputs['Factor'].default_value = 1.0
        self.set_in(n, 'A', a); self.set_in(n, 'B', b)
        return n.outputs['Result']

    def gray(self, v):
        n = self.N.new('ShaderNodeCombineColor')
        for i in range(3):
            self.set_in(n, i, v)
        return n.outputs['Color']


def _mask(nb, kind, k):
    """1 pour le type k, 0 ailleurs (transition douce sur une unité)."""
    d = nb.math('ABSOLUTE', nb.math('SUBTRACT', kind, float(k)))
    return nb.math('SUBTRACT', 1.0, nb.math('MINIMUM', d, 1.0))


def procedural_material(name='MON_Procedural', ao_distance=0.35):
    """Matière procédurale réaliste (sert à la cuisson et peut servir au rendu)."""
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nb = NB(nt)
    b = nt.nodes['Principled BSDF']
    tc = nb.node('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    at_t = nb.node('ShaderNodeAttribute', _attribute_name='Tangent')
    at_k = nb.node('ShaderNodeAttribute', _attribute_name='Mat')
    at_c = nb.node('ShaderNodeAttribute', _attribute_name='Col')
    t = nb.vmath('NORMALIZE', at_t.outputs['Vector'])
    kind = at_k.outputs['Fac']
    base = at_c.outputs['Color']
    # coordonnées anisotropes : fines en travers des fibres, étirées le long
    dot = nb.vmath('DOT_PRODUCT', p, t)
    pt = nb.vmath('SCALE', t, scale=dot)
    pperp = nb.vmath('SUBTRACT', p, pt)
    q = nb.vmath('ADD', nb.vmath('SCALE', pperp, scale=S_PERP), nb.vmath('SCALE', pt, scale=S_PAR))
    # fibres : bords de cellules de Voronoï étirées -> sillons entre fibres
    vor = nb.node('ShaderNodeTexVoronoi', _feature='DISTANCE_TO_EDGE', Vector=q, Scale=1.0, Randomness=0.75)
    fib = nb.maprange(vor.outputs['Distance'], 0.0, 0.3, smooth=True)
    vor2 = nb.node('ShaderNodeTexVoronoi', _feature='DISTANCE_TO_EDGE', Vector=nb.vmath('SCALE', q, scale=2.3), Scale=1.0)
    fib2 = nb.maprange(vor2.outputs['Distance'], 0.0, 0.32, smooth=True)
    fibers = nb.math('ADD', nb.math('MULTIPLY', fib, 0.7), nb.math('MULTIPLY', fib2, 0.3))
    fvar = nb.node('ShaderNodeTexNoise', Vector=nb.vmath('SCALE', q, scale=0.18), Scale=1.0, Detail=2.0).outputs['Fac']
    # bosses, pores, plaques de mucus
    lump = nb.node('ShaderNodeTexNoise', Vector=p, Scale=8.0, Detail=2.0, Roughness=0.45).outputs['Fac']
    lump_f = nb.node('ShaderNodeTexNoise', Vector=p, Scale=30.0, Detail=1.0).outputs['Fac']
    por = nb.node('ShaderNodeTexVoronoi', Vector=p, Scale=70.0, Randomness=1.0)
    pores = nb.maprange(por.outputs['Distance'], 0.0, 0.18, 1.0, 0.0, smooth=True)
    slime_n = nb.node('ShaderNodeTexNoise', Vector=p, Scale=2.6, Detail=3.0).outputs['Fac']
    slime = nb.maprange(slime_n, 0.52, 0.64, smooth=True)
    # occlusion (creux) : brun-rouge très sombre
    ao = nb.node('ShaderNodeAmbientOcclusion', Distance=ao_distance, _samples=12)
    aof = nb.maprange(ao.outputs['AO'], 0.15, 0.95, smooth=True)
    masks = {k: _mask(nb, kind, k) for k in range(7)}
    # ---- hauteur (relief) par type
    h_tendon = nb.math('ADD', nb.math('MULTIPLY', fibers, 0.75),
                       nb.math('ADD', nb.math('MULTIPLY', lump, 0.3), nb.math('MULTIPLY', pores, -0.008)))
    h_skull = nb.math('ADD', nb.math('MULTIPLY', fibers, 0.05), nb.math('MULTIPLY', lump, 0.05))
    h_tooth = nb.math('MULTIPLY', lump_f, 0.06)
    h_gum = nb.math('ADD', nb.math('MULTIPLY', lump_f, 0.25), nb.math('MULTIPLY', lump, 0.3))
    h_claw = nb.math('ADD', nb.math('MULTIPLY', fibers, 0.25), nb.math('MULTIPLY', lump_f, 0.05))
    h_slime = nb.math('MULTIPLY', lump, 0.08)
    h_core = nb.math('ADD', nb.math('MULTIPLY', lump, 0.45), nb.math('MULTIPLY', fibers, 0.25))
    hs = [h_tendon, h_skull, h_tooth, h_gum, h_claw, h_slime, h_core]
    height = nb.math('MULTIPLY', hs[0], masks[0])
    for k in range(1, 7):
        height = nb.math('ADD', height, nb.math('MULTIPLY', hs[k], masks[k]))
    bump = nb.node('ShaderNodeBump', Strength=0.38, Distance=0.009, Height=height)
    # ---- couleur par type
    crev = (0.0065, 0.0026, 0.0022, 1.0)
    shade_t = nb.math('ADD', 0.55, nb.math('ADD', nb.math('MULTIPLY', fibers, 0.55), nb.math('MULTIPLY', fvar, 0.3)))
    c_tendon = nb.rgbmul(base, nb.gray(shade_t))
    redtint = nb.maprange(nb.node('ShaderNodeTexNoise', Vector=p, Scale=1.6, Detail=2.0).outputs['Fac'], 0.5, 0.75)
    c_tendon = nb.mix(nb.math('MULTIPLY', redtint, 0.3), c_tendon, nb.rgbmul(c_tendon, (1.7, 0.8, 0.7, 1.0)))
    c_skull = nb.rgbmul(base, nb.gray(nb.math('ADD', 0.75, nb.math('MULTIPLY', lump, 0.45))))
    stain = nb.maprange(nb.node('ShaderNodeTexNoise', Vector=p, Scale=22.0, Detail=3.0).outputs['Fac'], 0.35, 0.7)
    c_tooth = nb.mix(stain, nb.rgbmul(base, (0.42, 0.36, 0.25, 1.0)), base)
    c_gum = nb.rgbmul(base, nb.gray(nb.math('ADD', 0.55, nb.math('MULTIPLY', lump_f, 0.8))))
    c_claw = nb.rgbmul(base, nb.gray(nb.math('ADD', 0.7, nb.math('MULTIPLY', fibers, 0.45))))
    c_slime = nb.rgbmul(base, (0.8, 0.78, 0.78, 1.0))
    c_core = nb.rgbmul(base, nb.gray(nb.math('ADD', 0.6, nb.math('MULTIPLY', lump, 0.5))))
    cs = [c_tendon, c_skull, c_tooth, c_gum, c_claw, c_slime, c_core]
    col = cs[0]
    for k in range(1, 7):
        col = nb.mix(masks[k], col, cs[k])
    col = nb.mix(aof, crev, col)                         # creux sombres et rougeâtres
    # ---- rugosité par type
    r_tendon = nb.math('ADD', 0.26, nb.math('ADD', nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, fibers), 0.12),
                                          nb.math('ADD', nb.math('MULTIPLY', lump, 0.08), nb.math('MULTIPLY', slime, -0.18))))
    r_skull = nb.math('ADD', 0.1, nb.math('MULTIPLY', lump, 0.08))
    rs = [r_tendon, r_skull, 0.36, 0.17, nb.math('ADD', 0.28, nb.math('MULTIPLY', fibers, 0.12)), 0.05,
          nb.math('ADD', 0.3, nb.math('MULTIPLY', lump, 0.15))]
    rough = nb.math('MULTIPLY', rs[0], masks[0])
    for k in range(1, 7):
        rough = nb.math('ADD', rough, nb.math('MULTIPLY', rs[k], masks[k]))
    rough = nb.math('ADD', rough, nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, aof), 0.15))
    nb.L.new(col, b.inputs['Base Color'])
    nb.L.new(nb.math('MAXIMUM', rough, 0.04, clamp=True), b.inputs['Roughness'])
    nb.L.new(bump.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = 0.5
    return mat


# ----------------------------------------------------------------------------------------------------------------
# UV, cuisson, matière finale


def tex_size(ob, density=170.0, efficiency=0.5, smin=256, smax=1024):
    me = ob.data
    V = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', V); V = V.reshape(-1, 3)
    me.calc_loop_triangles()
    T = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', T); T = T.reshape(-1, 3)
    area = 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1).sum()
    texels = area * density ** 2 / efficiency
    size = 2 ** int(round(math.log2(max(math.sqrt(texels), 1))))
    return int(min(max(size, smin), smax)), float(area)


def unwrap(ob, margin=0.003):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def _new_image(name, size, noncolor):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    return img


def bake_object(ob, proc_mat, size, samples=16, margin=6):
    """Cuisson couleur / rugosité / normale (espace tangent) dans trois images."""
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    bk = sc.render.bake
    bk.margin = margin
    bk.margin_type = 'EXTEND'
    bk.use_clear = True
    bk.target = 'IMAGE_TEXTURES'
    bk.normal_space = 'TANGENT'
    m = proc_mat.copy()
    m.name = 'bake_' + ob.name
    ob.data.materials.clear()
    ob.data.materials.append(m)
    tex = m.node_tree.nodes.new('ShaderNodeTexImage')
    m.node_tree.nodes.active = tex
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    base = ob.name.replace('MON_', 'T_')
    imgs = {}
    for typ, suffix, noncolor, spp in (('DIFFUSE', 'Couleur', False, samples), ('ROUGHNESS', 'Rugosite', True, 1),
                                        ('NORMAL', 'Normale', True, 1)):
        img = _new_image('%s_%s' % (base, suffix), size, noncolor)
        tex.image = img
        sc.cycles.samples = spp
        if typ == 'DIFFUSE':
            bk.use_pass_direct = False
            bk.use_pass_indirect = False
            bk.use_pass_color = True
        bpy.ops.object.bake(type=typ, margin=margin, use_clear=True, target='IMAGE_TEXTURES')
        imgs[suffix] = img
    ob.data.materials.clear()
    bpy.data.materials.remove(m)
    return imgs


def final_material(ob, imgs, coat=0.0):
    """Matière finale à images (ce que reçoit Roblox) : couleur, rugosité, normale."""
    m = bpy.data.materials.new('MAT_' + ob.name.replace('MON_', ''))
    nt = m.node_tree
    nb = NB(nt)
    b = nt.nodes['Principled BSDF']
    uv = nb.node('ShaderNodeUVMap', _uv_map='UVMap')
    tc = nb.node('ShaderNodeTexImage', _image=imgs['Couleur'], Vector=uv.outputs['UV'])
    tr = nb.node('ShaderNodeTexImage', _image=imgs['Rugosite'], Vector=uv.outputs['UV'])
    tn = nb.node('ShaderNodeTexImage', _image=imgs['Normale'], Vector=uv.outputs['UV'])
    nm = nb.node('ShaderNodeNormalMap', _uv_map='UVMap', Color=tn.outputs['Color'], Strength=1.0)
    nb.L.new(tc.outputs['Color'], b.inputs['Base Color'])
    nb.L.new(tr.outputs['Color'], b.inputs['Roughness'])
    nb.L.new(nm.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = 0.5
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.05
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


def save_images(imgs, folder, jpeg_color=True):
    os.makedirs(folder, exist_ok=True)
    for suffix, img in imgs.items():
        ext = 'png'
        img.filepath_raw = os.path.join(folder, img.name + '.' + ext)
        img.file_format = 'PNG'
        img.save()


def texture_objects(objs, folder, samples=16, log=True, coat=0.0):
    proc = bpy.data.materials.get('MON_Procedural') or procedural_material()
    t_all = time.time()
    for ob in objs:
        t0 = time.time()
        size, area = tex_size(ob)
        unwrap(ob)
        imgs = bake_object(ob, proc, size, samples)
        save_images(imgs, folder)
        final_material(ob, imgs, coat)
        if log:
            print('  %-22s %4d px  %6.2f studs²  %.1f s' % (ob.name, size, area, time.time() - t0), flush=True)
    if log:
        print('textures : %d maillages en %.1f s' % (len(objs), time.time() - t_all))
