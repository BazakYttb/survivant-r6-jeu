"""Decimated GLB + part metadata for the web viewer -> ../viewer/"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import blend_lib as B

OUT = os.path.join(B.HERE, '..', 'viewer')
ratio = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
os.makedirs(OUT, exist_ok=True)
B.reset()
man = B.manifest()
objs = [B.load_part(n, man) for n in B.part_names() if n in man]
for ob in objs:
    nf = len(ob.data.polygons)
    if nf > 900 and man[ob.name]['cat'] not in ('skin', 'gear'):      # the survivor outfit stays full detail
        m = ob.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = max(ratio, 700 / nf)
dg = bpy.context.evaluated_depsgraph_get()
print('viewer triangles', sum(len(o.evaluated_get(dg).data.polygons) for o in objs))
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'anatomie.glb'), export_format='GLB', use_selection=True,
                          export_apply=True, export_vertex_color='ACTIVE', export_normals=True,
                          export_materials='NONE', export_yup=True)
meta = {n: dict(cat=v['cat'], region=v['region'], info=v.get('info', ''), tris=v['tris']) for n, v in man.items()}
json.dump(meta, open(os.path.join(OUT, 'parts.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('glb MB', round(os.path.getsize(os.path.join(OUT, 'anatomie.glb')) / 1e6, 2))
