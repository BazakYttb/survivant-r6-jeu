"""Render animation frames of the survivor (Blender, Cycles) to check the clips.

usage: python anim_preview.py OUT.png clip[,clip...] [--frames 8] [--azim 70] [--elev 10] [--res 360x420]
       [--anatomy] [--boxes] [--video DIR --fps 30]
--boxes: coloured blocks of the jointed rig instead of the built meshes (quick motion checks).
Contact sheet: one row per clip, `--frames` evenly spaced frames per row.
--video DIR: also writes every frame of the first clip as PNG files in DIR (for a video).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mathutils import Matrix, Vector
import blend_lib as B
import anim as A
import rig_spec as RS

REGION_PART = {r: r for r in RS.REGIONS}         # anatomy / outfit regions are the body part names
CONV = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 3], [0, 0, 0, 1]], float)       # Roblox rig -> Blender
CONV_INV = np.linalg.inv(CONV)


def part_matrix(W, part):
    return CONV @ W @ A.inv4(A.REST[part]) @ CONV_INV


BOX_COLORS = {'Torso': (0.28, 0.31, 0.19), 'Head': (0.83, 0.61, 0.47), 'UpperArm': (0.28, 0.31, 0.19),
              'LowerArm': (0.80, 0.58, 0.44), 'UpperLeg': (0.16, 0.21, 0.31), 'LowerLeg': (0.38, 0.25, 0.16)}


def box_objects():
    """One coloured block per body part (rest pose in world coordinates)."""
    objs = {}
    for part in RS.PARTS:
        sx, sy, sz = RS.SIZE[part]
        cx, cy, cz = RS.CENTER[part]
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-cx, cz, cy + 3.0))
        ob = bpy.context.active_object
        ob.scale = (sx * 0.985, sz * 0.985, sy * 0.985)
        bpy.ops.object.transform_apply(location=True, scale=True, rotation=True)
        bev = ob.modifiers.new('bev', 'BEVEL'); bev.width = 0.06; bev.segments = 3
        key = next(k for k in BOX_COLORS if part.endswith(k))
        m = bpy.data.materials.new(part); m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = (*B.srgb_to_lin(BOX_COLORS[key]), 1); bs.inputs['Roughness'].default_value = 0.6
        ob.data.materials.append(m)
        objs[part] = (ob, part)
    return objs


def setup(anatomy=False, skin_alpha=1.0, boxes=False):
    B.reset()
    B._MAT.clear()
    objs = {}
    if boxes:
        objs = box_objects()
    else:
        man = B.manifest()
        names = [n for n in B.part_names() if n in man and (n.startswith('Survivor_') or anatomy)]
        for n in names:
            ob = B.load_part(n, man, skin_alpha=skin_alpha)
            objs[n] = (ob, REGION_PART[man[n]['region']])
    # ground
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    g = bpy.context.active_object
    m = bpy.data.materials.new('Ground'); m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (0.20, 0.21, 0.20, 1); bs.inputs['Roughness'].default_value = 0.9
    g.data.materials.append(m)
    return objs, g


def pose(objs, W):
    for n, (ob, part) in objs.items():
        ob.matrix_world = Matrix(part_matrix(W[part], part).tolist())


def camera(azim, elev, dist=17.0, target=(0, 0, 2.4), lens=60):
    a, e = math.radians(azim), math.radians(elev)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    loc = Vector(target) + d * dist
    if 'PrevCam' in bpy.data.objects:
        cam = bpy.data.objects['PrevCam']
    else:
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.active_object
        cam.name = 'PrevCam'
    cam.location = loc
    cam.rotation_euler = (Vector(target) - loc).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    bpy.context.scene.camera = cam
    return cam


def lights():
    for loc, en, col in (((-6, -9, 10), 2600, (1, 0.97, 0.92)), ((8, -4, 5), 900, (0.85, 0.9, 1.0)),
                         ((2, 9, 8), 1500, (1, 1, 1))):
        bpy.ops.object.light_add(type='AREA', location=loc)
        L = bpy.context.active_object
        L.data.energy = en; L.data.size = 6; L.data.color = col
        L.rotation_euler = (Vector((0, 0, 2.4)) - L.location).to_track_quat('-Z', 'Y').to_euler()


def main():
    a = sys.argv[1:]
    out, clips = a[0], a[1].split(',')
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    nf = int(opt('--frames', '8'))
    azim, elev = float(opt('--azim', '70')), float(opt('--elev', '10'))
    res = tuple(int(x) for x in opt('--res', '360x420').split('x'))
    video = opt('--video', None)
    objs, ground = setup('--anatomy' in a, float(opt('--skin-alpha', '1.0')), '--boxes' in a)
    B.setup_render(res, int(opt('--samples', '10')), bg=(0.05, 0.055, 0.06), view='Standard',
                   exposure=float(opt('--exposure', '-1.5')))
    lights()
    sc = bpy.context.scene
    tmp = os.path.join(os.path.dirname(os.path.abspath(out)), '_frames')
    os.makedirs(tmp, exist_ok=True)
    rows = []
    for ck in clips:
        clip = A.CLIP[ck]
        target = (0, -0.3, 0.9) if clip.ground == 'body' else (0, 0, 2.4)
        camera(azim, elev, dist=float(opt('--dist', '15' if clip.ground == 'body' else '17')), target=target)
        row = []
        ts = np.linspace(0, clip.length, nf, endpoint=not clip.loop)
        for i, t in enumerate(ts):
            pose(objs, clip.world(t))
            path = os.path.join(tmp, f'{ck}_{i:03d}.png')
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            row.append(path)
        rows.append(row)
        if video and ck == clips[0]:
            fps = int(opt('--fps', '30'))
            os.makedirs(video, exist_ok=True)
            n = int(round(clip.length * fps))
            for i in range(n):
                pose(objs, clip.world(i / fps))
                sc.render.filepath = os.path.join(video, f'{ck}_{i:04d}.png')
                bpy.ops.render.render(write_still=True)
    from PIL import Image
    W, H = res
    sheet = Image.new('RGB', (W * nf, H * len(rows)))
    for r, row in enumerate(rows):
        for i, p in enumerate(row):
            sheet.paste(Image.open(p).convert('RGB'), (i * W, r * H))
    sheet.save(out)
    print('sheet', out)


if __name__ == '__main__':
    main()
