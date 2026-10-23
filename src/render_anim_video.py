"""Animation showreel of the survivor (Blender Cycles + ffmpeg) -> ../apercus/animations_survivant.mp4

usage: python render_anim_video.py [--res 1280x720] [--samples 8] [--fps 30] [--out ../apercus/animations_survivant.mp4]
       [--only 2,5] (render some segments only, numbered from 1) [--keep] (keep the PNG frames)
       [--patch] (with --only and frames kept from a full run: re-render those segments in place, then encode)

Every segment plays clips of anim.py on a checker floor that scrolls at the clip's speed (the speed the
character moves at in Roblox for playback rate 1): planted boots must stay still on the checker. The climb
runs on a ladder whose rungs move down at the climbing speed (hands and boots stay on them), the sitting
pose on a seat, and the tool overlay (right arm only) over the walk with a torch in the hand.
The last segment shows the radiography mode (see-through skin and clothes, anatomy visible).
"""
import sys, os, math, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view
import blend_lib as B
import anim as A
from anim_preview import REGION_PART, part_matrix, lights, camera

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
STAND = dict(azim=38, elev=9, target=(0, 0, 2.35), dist=16.5, shift=2.3)
LOW = dict(azim=48, elev=13, target=(0, -0.4, 1.05), dist=15.5, shift=0.9)

SEGMENTS = [
    dict(title='Repos', sub='respiration, regard qui balaie, coudes souples', items=[('idle', 3.2)], cam=STAND),
    dict(title='Marche', sub='6 studs/s : bottes plantées, genoux et coudes qui plient', items=[('walk', 2.8)], cam=STAND),
    dict(title='Course', sub='16 studs/s : phase de vol, genoux hauts, bras pliés', items=[('run', 2.24)], cam=STAND),
    dict(title='Accroupi', sub='genoux fléchis, regard aux aguets', items=[('crouch', 1.8)], cam=STAND),
    dict(title='Marche accroupie', sub='2,6 studs/s : appuis larges, pas silencieux', items=[('crouchwalk', 3.0)], cam=STAND),
    dict(title="S'allonger", sub='transition debout vers allongé (touche X)', items=[('idle', 0.3), ('liedown', 0.95), ('prone', 1.3)],
         cam=dict(STAND, target=(0, -0.3, 2.2), dist=18.0, shift=1.4)),
    dict(title='Ramper', sub='1 stud/s : appui sur les coudes, jambes en grenouille', items=[('crawl', 3.5)], cam=LOW),
    dict(title='Se relever', sub='transition allongé vers debout', items=[('prone', 0.4), ('getup', 1.15), ('idle', 0.6)],
         cam=dict(STAND, target=(0, -0.3, 2.2), dist=18.0, shift=1.4)),
    dict(title='Saut, chute, atterrissage', sub='', items=[('idle', 0.3), ('jump', 0.5), ('fall', 0.9), ('land', 0.42), ('idle', 0.5)],
         cam=dict(STAND, target=(0, 0, 3.8), dist=22.0), air=2.0),
    dict(title='Grimper', sub='5 studs/s : mains et bottes restent sur les barreaux', items=[('climb', 2.7)],
         cam=dict(STAND, azim=52, elev=9, target=(0, 0, 3.1), dist=20.5, shift=2.0), props=('ladder',)),
    dict(title='Assis', sub='sur un siège (Seat) : mains sur les genoux', items=[('sit', 2.4)],
         cam=dict(STAND, azim=40), props=('seat',)),
    dict(title='Outil en main', sub='bras droit seul, superposé à la marche', items=[('walk', 2.8)], cam=STAND,
         overlay='tool', props=('torch',)),
    dict(title='Radiographie (touche R)', sub="peau et vêtements translucides : l'anatomie suit chaque mouvement",
         items=[('walk', 2.8)], cam=dict(STAND, azim=30), xray=True),
]


def _mat(name, rgb, rough=0.7, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*B.srgb_to_lin(rgb), 1)
    bs.inputs['Roughness'].default_value = rough
    if emit:
        bs.inputs['Emission Color'].default_value = (*B.srgb_to_lin(emit[0]), 1)
        bs.inputs['Emission Strength'].default_value = emit[1]
    return m


def _box(name, center, size, mat, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
    if bevel:
        bv = ob.modifiers.new('bev', 'BEVEL'); bv.width = bevel; bv.segments = 2
    ob.data.materials.append(mat)
    return ob


def _cyl(name, center, radius, depth, axis, mat, verts=24):
    rot = {'X': (0, math.pi / 2, 0), 'Y': (math.pi / 2, 0, 0), 'Z': (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=center, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


def _join(name, obs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    ob = bpy.context.active_object
    ob.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)     # vertices in world coordinates
    return ob


def make_props():
    """Ladder (rungs where the climb puts hands and boots), seat (under the sitting thighs) and a torch (held by
    the tool overlay, at the R15 grip of the right hand), in Blender coordinates; all hidden until a segment
    asks for them."""
    wood = _mat('PropWood', (0.42, 0.30, 0.19), 0.8)
    metal = _mat('PropMetal', (0.36, 0.37, 0.38), 0.45)
    props = {}
    # ladder: rails outside the hands, rungs CLIMB_RUNG apart; rung k sits where the climb grabs it
    yb = A.CLIMB_Z                                        # rig z = Blender y
    z0 = A.CLIMB_HAND_Y + 0.15 + 3.0                     # rung under the hands at clip time 0
    parts = [_box('Rail', (sx * 1.32, yb, 3.0), (0.13, 0.16, 12.0), wood) for sx in (-1, 1)]
    parts += [_cyl('Rung', (0, yb, z0 + k * A.CLIMB_RUNG), 0.075, 2.64, 'X', metal, 16) for k in range(-7, 4)]
    props['ladder'] = _join('Ladder', parts)
    # seat: top under the thighs of the sitting pose
    W = A.CLIP['sit'].world(0.0)
    low = min(A.lowest(W[A.UPPER_LEG[s]], A.UPPER_LEG[s]) for s in A.SIDES) + 3.0
    zc = np.mean([W[A.UPPER_LEG[s]][2, 3] for s in A.SIDES])
    seat = [_box('SeatTop', (0, zc + 0.15, low - 0.15), (2.4, 2.0, 0.3), wood)]
    seat += [_box('SeatLeg', (sx * 1.0, zc + 0.15 + sy * 0.8, (low - 0.3) / 2), (0.22, 0.22, low - 0.3), wood)
             for sx in (-1, 1) for sy in (-1, 1)]
    props['seat'] = _join('Seat', seat)
    # torch: handle along the grip axis (rest pose: forward from the right fist), cloth wrap and flame on top
    hx, hy, hz = A.RS.to_blender(A.RS.HAND['center'])
    handle = _cyl('TorchHandle', (hx, hy - 0.15, hz), 0.09, 1.5, 'Y', wood, 16)
    wrap = _cyl('TorchWrap', (hx, hy - 0.95, hz), 0.15, 0.32, 'Y', _mat('PropCloth', (0.55, 0.50, 0.40), 0.9), 16)
    flame = _cyl('TorchFlame', (hx, hy - 1.25, hz), 0.12, 0.34, 'Y',
                 _mat('PropFlame', (1.0, 0.62, 0.2), 0.5, emit=((1.0, 0.55, 0.15), 6.0)), 16)
    props['torch'] = _join('Torch', [handle, wrap, flame])
    for ob in props.values():
        ob.hide_render = True
    return props


def floor_material():
    m = bpy.data.materials.new('Floor')
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Roughness'].default_value = 0.85
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    ck = nt.nodes.new('ShaderNodeTexChecker')
    ck.inputs['Scale'].default_value = 0.5                    # 2-stud squares
    ck.inputs['Color1'].default_value = (0.075, 0.08, 0.078, 1)
    ck.inputs['Color2'].default_value = (0.11, 0.115, 0.112, 1)
    mp.inputs['Location'].default_value = (0.0, 0.0, 0.25)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], ck.inputs['Vector'])
    nt.links.new(ck.outputs['Color'], bs.inputs['Base Color'])
    return m, mp


def setup(res, samples):
    B.reset()
    B._MAT.clear()
    man = B.manifest()
    objs = {}
    for n in B.part_names():
        if n not in man:
            continue
        ob = B.load_part(n, man)
        objs[n] = (ob, REGION_PART[man[n]['region']], man[n]['cat'])
    xray_mat = B.skin_material(0.25)
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
    floor = bpy.context.active_object
    fm, mapping = floor_material()
    floor.data.materials.append(fm)
    B.setup_render(res, samples, bg=(0.05, 0.055, 0.06), view='Standard', exposure=-1.45)
    sc = bpy.context.scene
    # no persistent data: with it, Cycles sometimes drops a mesh's colour attribute for every later frame
    # (the beanie turned black mid-segment); a full scene sync per frame is a few tenths of a second
    sc.render.use_persistent_data = False
    sc.cycles.max_bounces = 3
    lights()
    return objs, xray_mat, mapping, floor, make_props()


def beanie_probe(hat):
    """A point on the front of the beanie (hat mesh coordinates) whose rendered colour must stay red."""
    v = np.array([vt.co[:] for vt in hat.data.vertices])
    zmax = v[:, 2].max()
    band = v[(v[:, 2] > zmax - 0.5) & (v[:, 2] < zmax - 0.3)]
    return Vector(band[np.argmin(band[:, 1])]) + Vector((0, -0.02, 0))


def beanie_ok(path, hat, probe):
    """False when the beanie rendered black (lost vertex colours); True when it is fine or not visible."""
    from PIL import Image
    sc = bpy.context.scene
    x, y, depth = world_to_camera_view(sc, sc.camera, hat.matrix_world @ probe)
    W, H = sc.render.resolution_x, sc.render.resolution_y
    if hat.hide_render or depth <= 0 or not (0.02 < x < 0.98 and 0.02 < y < 0.98):
        return True
    im = np.asarray(Image.open(path).convert('RGB')).astype(float)
    px, py = int(x * W), int((1 - y) * H)
    patch = im[max(0, py - 2):py + 3, max(0, px - 2):px + 3]
    return patch.sum(-1).mean() > 60


def set_mode(objs, xray, xray_mat, opaque_mat):
    for n, (ob, part, cat) in objs.items():
        if cat == 'gear':
            ob.hide_render = xray
        elif cat == 'skin':
            ob.data.materials[0] = xray_mat if xray else opaque_mat[n]
        else:
            ob.hide_render = not xray


def timeline(seg, fps):
    """Per frame: (clip key, time in clip, ground offset, height offset)."""
    out, ground = [], 0.0
    total = sum(d for _, d in seg['items'])
    n = int(round(total * fps))
    starts = np.cumsum([0.0] + [d for _, d in seg['items']])
    for i in range(n):
        t = i / fps
        k = min(int(np.searchsorted(starts, t, side='right')) - 1, len(seg['items']) - 1)
        key, dur = seg['items'][k]
        clip = A.CLIP[key]
        tc = t - starts[k]
        tc = tc % clip.length if clip.loop else min(tc, clip.length)
        h = 0.0
        if seg.get('air'):
            u = tc / clip.length
            if key == 'jump':
                h = seg['air'] * (1 - (1 - u) ** 2)
            elif key == 'fall':
                h = seg['air'] * (1 - min(1.0, (t - starts[k]) / dur) ** 2)
        out.append((key, tc, ground, h))
        ground += (clip.speed or 0.0) / fps
    return out


def overlay(path, seg, index, count, fade):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(path).convert('RGB')
    W, H = im.size
    s = W / 1280
    d = ImageDraw.Draw(im, 'RGBA')
    ft = ImageFont.truetype(FONT_B, int(38 * s))
    fs = ImageFont.truetype(FONT, int(20 * s))
    fn = ImageFont.truetype(FONT, int(17 * s))
    x, y = int(36 * s), int(30 * s)
    tw = d.textlength(seg['title'], font=ft)
    sw = d.textlength(seg['sub'], font=fs) if seg['sub'] else 0
    box_w = max(tw, sw) + 40 * s
    box_h = (96 if seg['sub'] else 62) * s
    d.rounded_rectangle((x - 18 * s, y - 14 * s, x - 18 * s + box_w, y - 14 * s + box_h), radius=int(12 * s),
                        fill=(10, 12, 14, 165))
    d.text((x, y), seg['title'], font=ft, fill=(240, 236, 226, 255))
    if seg['sub']:
        d.text((x, y + 50 * s), seg['sub'], font=fs, fill=(200, 205, 196, 255))
    foot = f'Survivant R6 articulé · animations Roblox (KeyframeSequence) · {index}/{count}'
    fw = d.textlength(foot, font=fn)
    d.text((W - fw - 28 * s, H - 36 * s), foot, font=fn, fill=(190, 192, 186, 200))
    if fade < 1.0:
        im = Image.blend(Image.new('RGB', im.size, (0, 0, 0)), im, max(0.0, fade))
    im.save(path)


def main():
    a = sys.argv[1:]
    opt = lambda k, dflt: a[a.index(k) + 1] if k in a else dflt
    res = tuple(int(v) for v in opt('--res', '1280x720').split('x'))
    fps = int(opt('--fps', '30'))
    out = os.path.abspath(opt('--out', os.path.join(B.HERE, '..', 'apercus', 'animations_survivant.mp4')))
    only = [int(v) for v in opt('--only', '').split(',') if v]
    frames_dir = os.path.join(os.path.dirname(out), '_video_frames')
    patch = '--patch' in a
    if not patch:
        shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir, exist_ok=True)
    starts = np.cumsum([0] + [int(round(sum(d for _, d in s['items']) * fps)) for s in SEGMENTS])
    objs, xray_mat, mapping, floor, props = setup(res, int(opt('--samples', '8')))
    opaque_mat = {n: ob.data.materials[0] for n, (ob, part, cat) in objs.items() if cat == 'skin'}
    sc = bpy.context.scene
    hat = objs['Survivor_Hat'][0]
    probe = beanie_probe(hat)
    fi = 0
    segs = [(i + 1, s) for i, s in enumerate(SEGMENTS) if not only or i + 1 in only]
    for index, seg in segs:
        if patch:
            fi = int(starts[index - 1])          # same frame numbers as in the full run
        set_mode(objs, bool(seg.get('xray')), xray_mat, opaque_mat)
        for k, ob in props.items():
            ob.hide_render = k not in seg.get('props', ())
        floor.hide_render = 'ladder' in seg.get('props', ())
        cam = dict(seg['cam'])
        shift = cam.pop('shift', 0.0)        # aim left of the character so it sits right of the captions
        az = math.radians(cam['azim'])
        cam['target'] = (cam['target'][0] - shift * math.cos(az), cam['target'][1] - shift * math.sin(az), cam['target'][2])
        camera(**cam, lens=55)
        tl = timeline(seg, fps)
        nfade = 6
        for i, (key, tc, ground, h) in enumerate(tl):
            W = A.CLIP[key].world(tc)
            if seg.get('overlay'):
                # partial clip (right arm only), as Roblox blends it: its joint motion relative to the torso
                # rides on the walking torso
                ov = A.CLIP[seg['overlay']]
                Wo = ov.world(tc % ov.length)
                rel = W['Torso'] @ A.inv4(Wo['Torso'])
                W = dict(W, **{p: rel @ Wo[p] for p in ov.parts})
            lift = Matrix.Translation((0, 0, h))
            for n, (ob, part, cat) in objs.items():
                ob.matrix_world = lift @ Matrix(part_matrix(W[part], part).tolist())
            props['torch'].matrix_world = lift @ Matrix(part_matrix(W['RightLowerArm'], 'RightLowerArm').tolist())
            props['ladder'].location.z = -((A.CLIMB_V * tc) % A.CLIMB_RUNG) if key == 'climb' else 0.0
            mapping.inputs['Location'].default_value = (0.0, -ground, 0.25)
            path = os.path.join(frames_dir, f'{fi:05d}.png')
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            for retry in range(2):
                if beanie_ok(path, hat, probe):
                    break
                print('frame', fi, 'beanie rendered black, rendering again', flush=True)
                bpy.ops.render.render(write_still=True)
            fade = min(1.0, (i + 1) / nfade, (len(tl) - i) / nfade)
            overlay(path, seg, index, len(SEGMENTS), fade)
            fi += 1
        print('segment', index, seg['title'], len(tl), 'frames', flush=True)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(frames_dir, '%05d.png'),
           '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    if '--keep' not in a:
        shutil.rmtree(frames_dir, ignore_errors=True)
    print('video', out, fi, 'frames', round(fi / fps, 1), 's')


if __name__ == '__main__':
    main()
