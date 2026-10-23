"""Assemble every built part in Blender and export for Roblox Studio.

usage: python export.py [--light 0.45] [--no-glb]
Outputs (../dist):
  Anatomie_R6_Ultra.fbx / .glb    every part at full resolution
  Anatomie_R6_Leger.fbx / .glb    decimated copy (ratio --light) for lighter games; the survivor's outfit is kept
                                  at full resolution
(the animated Blender scene is written by export_blend_rig.py)
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
import blend_lib as B

DIST = os.path.join(B.HERE, '..', 'dist')

# alignment markers: Blender studs -> expected Roblox rig space (relative to R6 Torso centre)
MARKERS = {'REF_A': (0, 0, 3), 'REF_B': (0, 0, 5.2), 'REF_C': (1.5, 0, 3), 'REF_D': (0, -0.6, 3)}
MARKER_SIZE = 0.05


def add_markers(col):
    obs = []
    for name, loc in MARKERS.items():
        me = bpy.data.meshes.new(name)
        h = MARKER_SIZE / 2
        v = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        me.from_pydata([(a + loc[0], b + loc[1], c + loc[2]) for a, b, c in v], [], f)
        me.update()
        ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
        ca.data.foreach_set('color', np.tile([1, 0, 1, 1], len(v)).astype(np.float32))
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        obs.append(ob)
    return obs


def export(path_base, objs, glb=True):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path_base + '.fbx', use_selection=True, object_types={'MESH'},
                             global_scale=1.0, apply_unit_scale=False, apply_scale_options='FBX_SCALE_NONE',
                             axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True, mesh_smooth_type='OFF',
                             colors_type='SRGB', prioritize_active_color=True, add_leaf_bones=False,
                             bake_anim=False, path_mode='AUTO', use_custom_props=False)
    if glb:
        bpy.ops.export_scene.gltf(filepath=path_base + '.glb', export_format='GLB', use_selection=True,
                                  export_apply=True, export_vertex_color='ACTIVE', export_normals=True,
                                  export_materials='EXPORT', export_yup=True)
    for ext in ('.fbx', '.glb'):
        p = path_base + ext
        if os.path.exists(p):
            print(f'  {os.path.basename(p)}: {os.path.getsize(p) / 1e6:.1f} MB')


def main():
    args = sys.argv[1:]
    ratio = float(args[args.index('--light') + 1]) if '--light' in args else 0.45
    glb = '--no-glb' not in args
    os.makedirs(DIST, exist_ok=True)
    B.reset()
    man = B.manifest()
    names = [n for n in B.part_names() if n in man]
    col = bpy.data.collections.new('Anatomie'); bpy.context.scene.collection.children.link(col)
    objs = []
    tot = 0
    for n in names:
        ob = B.load_part(n, man, col)
        objs.append(ob)
        tot += len(ob.data.polygons)
        assert len(ob.data.polygons) <= 20000, n
    mcol = bpy.data.collections.new('Markers'); bpy.context.scene.collection.children.link(mcol)
    marks = add_markers(mcol)
    print(f'{len(objs)} parts, {tot} triangles')
    export(os.path.join(DIST, 'Anatomie_R6_Ultra'), objs + marks, glb)

    # light version: decimate every part (keeps vertex colours), small parts are kept as they are;
    # the R6 skin is already light and its analytic normals must stay exact
    for ob in objs:
        nf = len(ob.data.polygons)
        if nf > 1500 and man.get(ob.name, {}).get('cat') not in ('skin', 'gear'):
            m = ob.modifiers.new('dec', 'DECIMATE')
            m.decimate_type = 'COLLAPSE'
            m.ratio = max(ratio, 1200 / nf)
            m.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    lt = sum(len(o.evaluated_get(dg).data.polygons) for o in objs)
    print(f'light: {lt} triangles')
    export(os.path.join(DIST, 'Anatomie_R6_Leger'), objs + marks, glb)
    for ob in objs:
        for m in list(ob.modifiers):
            ob.modifiers.remove(m)

    json.dump(dict(parts=len(objs), triangles=tot, triangles_light=lt,
                   markers={k: list(v) for k, v in MARKERS.items()}),
              open(os.path.join(DIST, 'export_info.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
