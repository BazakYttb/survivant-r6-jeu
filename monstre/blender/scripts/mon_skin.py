"""Peau réaliste faite dans Blender : matière procédurale sur la version HD (marbrures, rougeurs aux
articulations, veines, crasse dans les plis, griffures, grain de peau, rides), puis cuisson Cycles « sélection
vers actif » (HD -> maillage jeu) en trois images : couleur, rugosité, normale (espace tangent).

Types (attribut Mat) : 0 peau, 1 peau du crâne, 2 dent, 3 gencive, 4 ongle/griffe."""
import math
import os
import time
import numpy as np
import bpy
from mon_tex import NB, _mask, unwrap, tex_size, _new_image, final_material, save_images


def skin_material(name='MON_Peau_HD', ao_distance=0.18):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nb = NB(nt)
    b = nt.nodes['Principled BSDF']
    p = nb.node('ShaderNodeTexCoord').outputs['Object']
    at_c = nb.node('ShaderNodeAttribute', _attribute_name='Col')
    at_k = nb.node('ShaderNodeAttribute', _attribute_name='Mat')
    at_t = nb.node('ShaderNodeAttribute', _attribute_name='Tangent')
    base = at_c.outputs['Color']
    kind = at_k.outputs['Fac']
    t = nb.vmath('NORMALIZE', at_t.outputs['Vector'])
    masks = {k: _mask(nb, kind, k) for k in range(5)}
    # rougeur des articulations, déduite de la teinte régionale (r - g)
    sep = nb.node('ShaderNodeSeparateColor', Color=base)
    redm = nb.maprange(nb.math('SUBTRACT', sep.outputs['Red'], sep.outputs['Green']), 0.1, 0.22, smooth=True)
    # marbrures et variations
    m1 = nb.node('ShaderNodeTexNoise', Vector=p, Scale=2.2, Detail=5.0, Roughness=0.6).outputs['Fac']
    m2 = nb.node('ShaderNodeTexNoise', Vector=p, Scale=7.0, Detail=3.0).outputs['Fac']
    m3 = nb.node('ShaderNodeTexNoise', Vector=p, Scale=0.9, Detail=2.0).outputs['Fac']
    col = nb.mix(nb.maprange(m1, 0.3, 0.7), nb.rgbmul(base, (0.8, 0.83, 0.93, 1)), nb.rgbmul(base, (1.1, 0.97, 0.86, 1)))
    spots = nb.maprange(nb.node('ShaderNodeTexVoronoi', Vector=p, Scale=18.0, Randomness=1.0).outputs['Distance'], 0.0, 0.2, 1.0, 0.0, smooth=True)
    col = nb.mix(nb.math('MULTIPLY', spots, nb.math('MULTIPLY', nb.maprange(m2, 0.55, 0.75), 0.35)), col, nb.rgbmul(col, (0.85, 0.72, 0.66, 1)))
    col = nb.mix(nb.math('MULTIPLY', nb.maprange(m3, 0.5, 0.72), 0.6), col, nb.rgbmul(col, (1.14, 0.84, 0.8, 1)))
    col = nb.mix(nb.math('MULTIPLY', redm, 0.9), col, nb.rgbmul(col, (1.05, 0.66, 0.62, 1)))
    # ecchymoses violacées à bord jaunâtre, rares
    bz = nb.node('ShaderNodeTexNoise', Vector=p, Scale=1.7, Detail=3.0, Roughness=0.55).outputs['Fac']
    bm = nb.maprange(bz, 0.66, 0.74, smooth=True)
    col = nb.mix(nb.math('MULTIPLY', bm, 0.5), col, nb.rgbmul(col, (0.8, 0.64, 0.8, 1)))
    halo = nb.math('MULTIPLY', nb.maprange(bz, 0.6, 0.67, smooth=True), nb.math('SUBTRACT', 1.0, bm))
    col = nb.mix(nb.math('MULTIPLY', halo, 0.3), col, nb.rgbmul(col, (1.04, 1.0, 0.72, 1)))
    # veines bleutées : lignes sinueuses le long des membres (bruit en crête dans des coordonnées étirées), rares
    pv = nb.vmath('ADD', nb.vmath('SCALE', t, scale=nb.math('MULTIPLY', nb.vmath('DOT_PRODUCT', p, t), 0.9)),
                  nb.vmath('SCALE', nb.vmath('SUBTRACT', p, nb.vmath('SCALE', t, scale=nb.vmath('DOT_PRODUCT', p, t))), scale=4.5))
    vn = nb.node('ShaderNodeTexNoise', Vector=pv, Scale=1.0, Detail=3.0, Roughness=0.5).outputs['Fac']
    ridge = nb.math('ABSOLUTE', nb.math('SUBTRACT', vn, 0.5))
    vmask = nb.maprange(nb.node('ShaderNodeTexNoise', Vector=p, Scale=1.3, Detail=2.0).outputs['Fac'], 0.44, 0.58, smooth=True)
    vein = nb.math('MULTIPLY', nb.maprange(ridge, 0.0, 0.032, 1.0, 0.0, smooth=True), vmask)
    col = nb.mix(nb.math('MULTIPLY', vein, 0.5), col, nb.rgbmul(col, (0.55, 0.63, 0.9, 1)))
    # griffures rouge sombre (bandes ondulées très fines, par endroits)
    wv = nb.node('ShaderNodeTexWave', Vector=p, Scale=1.6, Distortion=6.0, _wave_type='BANDS', _bands_direction='DIAGONAL')
    wv.inputs['Detail'].default_value = 3.0
    scr_mask = nb.maprange(nb.node('ShaderNodeTexNoise', Vector=p, Scale=1.4, Detail=2.0).outputs['Fac'], 0.6, 0.7, smooth=True)
    scr = nb.math('MULTIPLY', nb.maprange(wv.outputs['Fac'], 0.96, 1.0, smooth=True), scr_mask)
    col = nb.mix(nb.math('MULTIPLY', scr, 0.85), col, (0.28, 0.04, 0.03, 1))
    # crasse dans les plis (occlusion)
    ao = nb.node('ShaderNodeAmbientOcclusion', Distance=ao_distance, _samples=12, _only_local=True)
    aof = nb.maprange(ao.outputs['AO'], 0.2, 0.95, smooth=True)
    col = nb.mix(aof, nb.rgbmul(col, (0.3, 0.2, 0.17, 1)), col)
    # crasse et taches brunâtres par endroits
    grime = nb.maprange(nb.node('ShaderNodeTexNoise', Vector=p, Scale=3.5, Detail=6.0, Roughness=0.7).outputs['Fac'], 0.55, 0.75, smooth=True)
    col = nb.mix(nb.math('MULTIPLY', grime, 0.4), col, nb.rgbmul(col, (0.62, 0.52, 0.42, 1)))
    # terre et crasse sur les pieds et le bas des jambes (selon la hauteur), par plaques
    z = nb.node('ShaderNodeSeparateXYZ', Vector=p).outputs['Z']
    dn = nb.node('ShaderNodeTexNoise', Vector=p, Scale=4.0, Detail=6.0, Roughness=0.65).outputs['Fac']
    dirt = nb.math('MULTIPLY', nb.maprange(z, 0.25, 2.8, 1.0, 0.0, smooth=True), nb.maprange(dn, 0.28, 0.62))
    col = nb.mix(nb.math('MULTIPLY', dirt, 0.85), col, nb.rgbmul(col, (0.42, 0.34, 0.27, 1)))
    # dents, gencives, ongles
    stain = nb.maprange(nb.node('ShaderNodeTexNoise', Vector=p, Scale=24.0, Detail=3.0).outputs['Fac'], 0.35, 0.7)
    c_tooth = nb.mix(stain, nb.rgbmul(base, (0.45, 0.38, 0.27, 1)), base)
    c_tooth = nb.mix(aof, nb.rgbmul(c_tooth, (0.35, 0.25, 0.15, 1)), c_tooth)
    c_gum = nb.rgbmul(base, nb.gray(nb.math('ADD', 0.5, nb.math('MULTIPLY', m2, 0.9))))
    stri = nb.node('ShaderNodeTexNoise', Vector=nb.vmath('ADD', nb.vmath('SCALE', nb.vmath('SUBTRACT', p,
                   nb.vmath('SCALE', t, scale=nb.vmath('DOT_PRODUCT', p, t))), scale=60.0), nb.vmath('SCALE', t, scale=3.0)),
                   Scale=1.0, Detail=2.0).outputs['Fac']
    c_nail = nb.rgbmul(base, nb.gray(nb.math('ADD', 0.7, nb.math('MULTIPLY', stri, 0.6))))
    col = nb.mix(masks[2], col, c_tooth)
    col = nb.mix(masks[3], col, c_gum)
    col = nb.mix(masks[4], col, c_nail)
    # rugosité
    r_skin = nb.math('ADD', 0.42, nb.math('ADD', nb.math('MULTIPLY', m2, 0.16), nb.math('MULTIPLY', grime, 0.12)))
    r_skin = nb.math('ADD', r_skin, nb.math('MULTIPLY', dirt, 0.2))
    r_skin = nb.math('ADD', r_skin, nb.math('MULTIPLY', masks[1], -0.08))
    rough = nb.math('ADD', nb.math('MULTIPLY', r_skin, nb.math('ADD', masks[0], masks[1])),
                    nb.math('ADD', nb.math('MULTIPLY', masks[2], 0.32),
                            nb.math('ADD', nb.math('MULTIPLY', masks[3], 0.16), nb.math('MULTIPLY', masks[4], 0.3))))
    # relief : grain de peau, rides le long des membres (plus marquées aux articulations), veines, griffures
    grain = nb.node('ShaderNodeTexVoronoi', Vector=p, Scale=40.0, Randomness=1.0)
    g = nb.maprange(grain.outputs['Distance'], 0.0, 0.55, 0.0, 1.0, smooth=True)
    q = nb.vmath('ADD', nb.vmath('SCALE', t, scale=nb.math('MULTIPLY', nb.vmath('DOT_PRODUCT', p, t), 24.0)),
                 nb.vmath('SCALE', nb.vmath('SUBTRACT', p, nb.vmath('SCALE', t, scale=nb.vmath('DOT_PRODUCT', p, t))), scale=2.0))
    wr = nb.node('ShaderNodeTexNoise', Vector=q, Scale=1.0, Detail=3.0, Roughness=0.6).outputs['Fac']
    wrin = nb.math('MULTIPLY', nb.maprange(wr, 0.42, 0.6, smooth=True), nb.math('ADD', 0.35, nb.math('MULTIPLY', redm, 1.5)))
    bumps = nb.node('ShaderNodeTexNoise', Vector=p, Scale=10.0, Detail=3.0).outputs['Fac']
    # gros plis de peau aux articulations (anneaux autour du membre)
    q2 = nb.vmath('ADD', nb.vmath('SCALE', t, scale=nb.math('MULTIPLY', nb.vmath('DOT_PRODUCT', p, t), 15.0)),
                  nb.vmath('SCALE', nb.vmath('SUBTRACT', p, nb.vmath('SCALE', t, scale=nb.vmath('DOT_PRODUCT', p, t))), scale=1.5))
    fo = nb.node('ShaderNodeTexNoise', Vector=q2, Scale=1.0, Detail=2.0, Roughness=0.5).outputs['Fac']
    folds = nb.math('MULTIPLY', nb.maprange(fo, 0.45, 0.6, smooth=True), redm)
    bumps = nb.math('ADD', bumps, nb.math('MULTIPLY', folds, -1.6))
    h_skin = nb.math('ADD', nb.math('MULTIPLY', g, 0.06),
                     nb.math('ADD', nb.math('MULTIPLY', wrin, -0.35),
                             nb.math('ADD', nb.math('MULTIPLY', vein, 0.25),
                                     nb.math('ADD', nb.math('MULTIPLY', scr, -0.4), nb.math('MULTIPLY', bumps, 0.13)))))
    h = nb.math('ADD', nb.math('MULTIPLY', h_skin, nb.math('ADD', masks[0], nb.math('MULTIPLY', masks[1], 0.6))),
                nb.math('ADD', nb.math('MULTIPLY', masks[3], nb.math('MULTIPLY', m2, 0.4)),
                        nb.math('MULTIPLY', masks[4], nb.math('MULTIPLY', stri, 0.3))))
    bump = nb.node('ShaderNodeBump', Strength=0.45, Distance=0.006, Height=h)
    nb.L.new(col, b.inputs['Base Color'])
    nb.L.new(nb.math('MAXIMUM', rough, 0.05, clamp=True), b.inputs['Roughness'])
    nb.L.new(bump.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = 0.45
    return mat


def bake_from_hd(lo, hd, size, samples=12, margin=8, extrusion=0.035, max_ray=0.1):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = extrusion
    bk.max_ray_distance = max_ray
    bk.margin = margin
    bk.margin_type = 'EXTEND'
    bk.use_clear = True
    bk.target = 'IMAGE_TEXTURES'
    bk.normal_space = 'TANGENT'
    m = bpy.data.materials.new('bake_' + lo.name)
    lo.data.materials.clear()
    lo.data.materials.append(m)
    tex = m.node_tree.nodes.new('ShaderNodeTexImage')
    m.node_tree.nodes.active = tex
    for o in bpy.context.selected_objects:
        o.select_set(False)
    hd.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    base = lo.name.replace('MON_', 'T_')
    imgs = {}
    for typ, suffix, noncolor, spp in (('DIFFUSE', 'Couleur', False, samples), ('ROUGHNESS', 'Rugosite', True, 1),
                                        ('NORMAL', 'Normale', True, 4)):
        img = _new_image('%s_%s' % (base, suffix), size, noncolor)
        tex.image = img
        sc.cycles.samples = spp
        if typ == 'DIFFUSE':
            bk.use_pass_direct = False
            bk.use_pass_indirect = False
            bk.use_pass_color = True
        bpy.ops.object.bake(type=typ, margin=margin, use_clear=True, target='IMAGE_TEXTURES',
                            use_selected_to_active=True, cage_extrusion=extrusion, max_ray_distance=max_ray)
        imgs[suffix] = img
    lo.data.materials.clear()
    bpy.data.materials.remove(m)
    return imgs


def texture_from_hd(los, hds, folder, samples=12, density=200.0, coat=0.0, log=True):
    """los : maillages jeu ; hds : {pièce: objet HD}. Les maillages jeu sont invisibles aux rayons pendant la cuisson
    (l'occlusion ne voit que la version HD)."""
    skin = bpy.data.materials.get('MON_Peau_HD') or skin_material()
    for h in hds.values():
        h.data.materials.clear()
        h.data.materials.append(skin)
    vis = {}
    for o in los:
        vis[o.name] = (o.visible_camera, o.visible_diffuse, o.visible_glossy, o.visible_shadow)
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_shadow = False
        o.visible_transmission = o.visible_volume_scatter = False
    t_all = time.time()
    for lo in los:
        t0 = time.time()
        size, area = tex_size(lo, density=density)
        unwrap(lo)
        imgs = bake_from_hd(lo, hds[lo['piece']], size, samples)
        save_images(imgs, folder)
        final_material(lo, imgs, coat)
        if log:
            print('  %-22s %4d px  %6.2f studs²  %.1f s' % (lo.name, size, area, time.time() - t0), flush=True)
    for o in los:
        c, d, g, s = vis[o.name]
        o.visible_camera, o.visible_diffuse, o.visible_glossy, o.visible_shadow = c, d, g, s
        o.visible_transmission = o.visible_volume_scatter = True
    if log:
        print('textures : %d maillages en %.1f s' % (len(los), time.time() - t_all))
