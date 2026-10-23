"""Animated Blender scene: survivor + anatomy parented to the jointed R6 armature, one action per animation.

usage: python export_blend_rig.py [--no-anatomy] [--out ../dist/Survivant_R6_Anime.blend]

Bones are named like the 10 body parts of the jointed rig (HumanoidRootPart, Torso, Head,
Right/Left UpperArm, LowerArm, UpperLeg, LowerLeg) with their heads on the Roblox Motor6D pivots
(shoulders, elbows, hips, knees: rig_spec.py), so a pose in Blender is the same joint motion as in
Roblox. Each clip of anim.py is an action (30 fps) kept on its own NLA track.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bpy
from mathutils import Matrix
import blend_lib as B
import anim as A
import rig_spec as RS
from anim_preview import REGION_PART, CONV, CONV_INV


def _bones():
    """name -> (parent, head, tail) in Blender coordinates: head on the part's Motor6D pivot, tail on the
    next joint down the limb (or the hand / sole / top of the head)."""
    piv = {p1: RS.to_blender(piv_) for _, (p0, p1, piv_, _) in RS.JOINT_DEFS.items()}
    tails = {'Torso': piv['Head'], 'Head': RS.to_blender((0, 2.1, 0))}
    for upper, lower, _ in RS.LIMBS.values():
        tails[upper] = piv[lower]
        c = np.asarray(RS.CENTER[lower], float)
        tails[lower] = RS.to_blender(c - (0, RS.SIZE[lower][1] / 2, 0))        # wrist end / sole
    out = {'HumanoidRootPart': (None, RS.to_blender((0, 0, 0)), RS.to_blender((0, 0, 0.6)))}
    for p in RS.PARTS:
        out[p] = (RS.PARENT[p], piv[p], tails[p])
    return out


BONES = _bones()
FPS = 30


def main():
    a = sys.argv[1:]
    out = a[a.index('--out') + 1] if '--out' in a else os.path.join(B.HERE, '..', 'dist', 'Survivant_R6_Anime.blend')
    anatomy = '--no-anatomy' not in a
    B.reset()
    B._MAT.clear()
    sc = bpy.context.scene
    sc.render.fps = FPS
    man = B.manifest()
    col_out = bpy.data.collections.new('Survivant'); sc.collection.children.link(col_out)
    col_an = bpy.data.collections.new('Anatomie'); sc.collection.children.link(col_an)
    objs = []
    for n in B.part_names():
        if n not in man:
            continue
        outfit = man[n]['cat'] in ('skin', 'gear')
        if not outfit and not anatomy:
            continue
        ob = B.load_part(n, man, col_out if outfit else col_an)
        objs.append((ob, REGION_PART[man[n]['region']]))

    # armature
    arm_data = bpy.data.armatures.new('Rig_R6_Articule')
    arm = bpy.data.objects.new('Rig_R6_Articule', arm_data)
    sc.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for name, (parent, head, tail) in BONES.items():
        b = arm_data.edit_bones.new(name)
        b.head, b.tail = tuple(head), tuple(tail)
        b.roll = 0.0
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
        eb[name] = b
    bpy.ops.object.mode_set(mode='OBJECT')
    rest = {name: np.array(arm_data.bones[name].matrix_local) for name in BONES}

    # parent every mesh to its bone, keeping its world transform
    bpy.context.view_layer.update()
    for ob, part in objs:
        mw = ob.matrix_world.copy()
        ob.parent = arm
        ob.parent_type = 'BONE'
        ob.parent_bone = part
        bpy.context.view_layer.update()
        ob.matrix_world = mw

    # actions (30 fps samples, linear between them like Roblox)
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    arm.animation_data_create()
    for clip in A.CLIPS:
        act = bpy.data.actions.new(clip.name)
        act.use_fake_user = True
        arm.animation_data.action = act
        n = int(round(clip.length * FPS))
        for fi in range(n + 1):
            t = min(fi / FPS, clip.length)
            if clip.loop and fi == n:
                t = 0.0
            W = clip.world(t)
            pose_arm = {'HumanoidRootPart': rest['HumanoidRootPart']}
            for name in RS.PARTS:
                D = CONV @ W[name] @ A.inv4(A.REST[name]) @ CONV_INV          # world motion of the part
                pose_arm[name] = D @ rest[name]
            for name, (parent, _, _) in BONES.items():
                if parent is None:
                    basis = np.eye(4)
                else:
                    local_rest = np.linalg.inv(rest[parent]) @ rest[name]
                    basis = np.linalg.inv(local_rest) @ np.linalg.inv(pose_arm[parent]) @ pose_arm[name]
                pb = arm.pose.bones[name]
                pb.matrix_basis = Matrix(basis.tolist())
                pb.keyframe_insert('location', frame=fi + 1, group=name)
                pb.keyframe_insert('rotation_quaternion', frame=fi + 1, group=name)
        track = arm.animation_data.nla_tracks.new()
        track.name = clip.label
        track.strips.new(clip.name, 1, act)
        track.mute = True
        arm.animation_data.action = None
    # the walk is the active action when the file opens
    walk = bpy.data.actions.get('Survivant_Marche')
    arm.animation_data.action = walk
    sc.frame_start, sc.frame_end = 1, int(round(A.CLIP['walk'].length * FPS)) + 1
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # light + camera for a quick look
    B.setup_render((1280, 1280), 32, bg=(0.05, 0.055, 0.06), view='Standard', exposure=-1.4)
    bpy.ops.object.light_add(type='SUN', location=(4, -6, 9))
    bpy.context.active_object.data.energy = 3.0
    bpy.ops.object.camera_add(location=(9, -13, 5.5))
    cam = bpy.context.active_object
    cam.rotation_euler = (math.radians(78), 0, math.radians(35))
    sc.camera = cam
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
    print('saved', out, len(objs), 'objects', len(A.CLIPS), 'actions')


if __name__ == '__main__':
    main()
