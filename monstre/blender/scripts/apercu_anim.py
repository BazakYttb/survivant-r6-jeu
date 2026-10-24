"""Planches d'aperçu des animations du monstre dans Blender (rig d'empties, Cycles basse définition).
usage : python apercu_anim.py -- scene.blend sortie.png clé1,clé2@t1;t2,clé3@t1;t2@azimut,... [images_par_clip] [largeur] [vue]
Les clés viennent de mon_clips.CLIPS et mon_morts.CLIPS (si présent) ; une victime en boîtes (rig du survivant, aux
couleurs de sa tenue) est posée pour les clips de mise à mort. « @azimut » (degrés) change l'angle de vue d'une ligne."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mathutils import Quaternion, Vector
from PIL import Image, ImageDraw, ImageFont
from mon_common import to_blender, src_survivant
import mon_blend as MB
import mon_rig as RIG
import mon_scene2 as SC2
import mon_anim as A
import mon_clips as C
try:
    import mon_morts as MORTS
except ImportError:
    MORTS = None

args = sys.argv[sys.argv.index('--') + 1:]
blend, out, keys = args[0], args[1], args[2].split(',')
nfr = int(args[3]) if len(args) > 3 else 6
width = int(args[4]) if len(args) > 4 else 300
view = args[5] if len(args) > 5 else 'trois_quarts'
VIEWS = {'trois_quarts': dict(az=-40, d=16.5, h=3.0, ty=5.0, tx=0.0, tz=-1.0, lens=35),
         'profil': dict(az=90, d=17, h=4.0, ty=5.0, tx=0, tz=-1.5, lens=35),
         'face': dict(az=0, d=17, h=4.0, ty=5.0, tx=0, tz=-1.0, lens=35)}
PB = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)      # Roblox -> Blender


def bl_quat(R):
    q = A.quat(PB @ R @ PB.T)
    return Quaternion((q[3], q[0], q[1], q[2]))


def setup():
    bpy.ops.wm.open_mainfile(filepath=blend)
    hd = bpy.data.collections.get('HD_Cuisson')
    if hd is not None:
        hd.hide_render = True
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('MON_')]
    emp = RIG.build_rig(meshes)
    for e in emp.values():
        e.rotation_mode = 'QUATERNION'
    # lueur de la gueule attachée à la tête
    g, gl = SC2.glow(A.HEAD_C + (A.FH * 0.42 - A.UH * 0.36) * A.SCALE * 0.98)
    bpy.context.view_layer.update()
    for o in (g, gl):
        mw = o.matrix_world.copy(); o.parent = emp['Head']
        o.matrix_parent_inverse = emp['Head'].matrix_world.inverted(); o.matrix_world = mw
    SC2.scene_mist(fog=False)
    scn = MB.setup_cycles(samples=12, res=(width, int(width * 1.5)))
    scn.camera = camera(None)
    scn.cycles.max_bounces = 3
    victim = make_victim()
    return emp, victim


CAMS = {}


def camera(az_deg):
    """Caméra de la vue choisie, à un autre azimut si az_deg est donné (une par azimut)."""
    if az_deg not in CAMS:
        v = VIEWS[view]
        az = math.radians(v['az'] if az_deg is None else az_deg)
        tgt = np.array([v['tx'], v['ty'], v['tz']])
        eye = tgt * np.array([1, 0, 1]) + np.array([math.sin(az) * v['d'], v['h'], -math.cos(az) * v['d']])
        CAMS[az_deg] = MB.add_camera('cam_%s' % az_deg, eye, tgt, lens=v['lens'])
    return CAMS[az_deg]


def police(taille):
    for nom in ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf', 'segoeui.ttf', 'Helvetica.ttc'):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            pass
    return ImageFont.load_default(size=taille)                  # (sans accents)


def make_victim():
    """Victime en boîtes (proportions du survivant R6 articulé), parentées à un empty par pièce."""
    sys.path.insert(0, src_survivant())
    import rig_spec as RS
    col = MB.collection('Victime')
    teintes = {'veste': (0.098, 0.122, 0.034), 'peau': (0.55, 0.305, 0.188), 'jean': (0.045, 0.069, 0.155)}
    mats = {}
    for nom, c in teintes.items():
        mats[nom] = bpy.data.materials.new('Victime_' + nom)
        mats[nom].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*c, 1)
    boxes = {}
    for p in RS.PARTS:
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        ob = bpy.context.active_object
        for c in ob.users_collection:
            c.objects.unlink(ob)
        col.objects.link(ob)
        ob.name = 'V_' + p
        sx, sy, sz = RS.SIZE[p]
        ob.scale = (sx * 0.96, sz * 0.96, sy * 0.96)
        ob.data.materials.append(mats['jean' if 'Leg' in p else 'peau' if p == 'Head' or 'LowerArm' in p else 'veste'])
        ob.rotation_mode = 'QUATERNION'
        ob.hide_render = True
        boxes[p] = ob
    return boxes


def pose_victim(boxes, W_anchor_model, world):
    """world : matrices du survivant (repère de son HRP, rig_spec) ; W_anchor_model : repère modèle du monstre."""
    sys.path.insert(0, src_survivant())
    import rig_spec as RS
    for p, ob in boxes.items():
        if world is None:
            ob.hide_render = True
            continue
        ob.hide_render = False
        Wp = W_anchor_model @ world[p]                     # world[p] : repère centré de la pièce -> repère du HRP
        R = Wp[:3, :3]; t = Wp[:3, 3]
        ob.location = Vector(to_blender(t))
        ob.rotation_quaternion = bl_quat(R)


def apply(emp, P):
    for n, e in emp.items():
        if n == 'HumanoidRootPart':
            continue
        R, t = P.get_rt(n)
        e.rotation_quaternion = bl_quat(R)
        e.location = Vector(to_blender(A.PIV[n] + t))
    bpy.context.view_layer.update()


emp, victim = setup()
clips = dict(C.CLIPS)
if MORTS is not None:
    clips.update(MORTS.CLIPS)
tiles = []
tmp = os.path.join(os.path.dirname(os.path.abspath(out)), '_apercu_tmp.png')
fonte = police(max(11, width // 25))
for spec in keys:
    k, _, ts = spec.partition('@')                       # « clé », « clé@t1;t2;... » (instants), « ...@azimut »
    ts, _, az = ts.partition('@')
    bpy.context.scene.camera = camera(float(az) if az else None)
    clip = clips[k]
    row = []
    if ts:
        times = [float(x) for x in ts.split(';')]
    else:
        times = [clip.length * i / (nfr - (0 if clip.loop else 1)) for i in range(nfr)]
    for t in times:
        P = clip.fn(t)
        apply(emp, P)
        if MORTS is not None and k in MORTS.CLIPS:
            W = A.fk(P)
            pose_victim(victim, W['VictimeAncre'] @ A.T4(A.PIV['VictimeAncre']) @ A.M4(A.Ry(180)), MORTS.victim_world(k, t))
        else:
            pose_victim(victim, None, None)
        MB.render(tmp)
        im = Image.open(tmp).convert('RGB')
        ImageDraw.Draw(im).text((6, 5), '%s  %.2f s' % (clip.label or k, t), fill=(20, 20, 20), font=fonte)
        row.append(im)
        print(k, '%.2f s' % t, flush=True)
    tiles.append(row)
w, h = tiles[0][0].size
ncol = max(len(r) for r in tiles)
sheet = Image.new('RGB', (w * ncol, h * len(tiles)), (255, 255, 255))
for r, row in enumerate(tiles):
    for c, im in enumerate(row):
        sheet.paste(im, (c * w, r * h))
sheet.save(out, quality=88)
print('planche', out)
