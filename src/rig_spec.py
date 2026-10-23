"""Single source of truth for the jointed R6 rig ("R6 articulé"): 10 body parts, elbows and knees.

The look stays R6 (2x2x1 torso, 2x1x1 head, 1-stud-wide limbs, same silhouette at rest), but each arm
and leg is split in two at the elbow / knee so animations can bend them. Everything that needs the rig
(anim.py, make_lua.py -> Roblox scripts, Blender and web exports) reads it from here.

Roblox rig space (HumanoidRootPart frame): X = character's right, Y = up, Z = back (faces -Z).
HumanoidRootPart centre = origin, ground at Y = -3 (Humanoid RigType R15, HipHeight 2).
Blender / build space: X = character's left, Y = back, Z = up, ground at Z = 0:
    blender = (-x, z, y + 3)        roblox = (-X, Z - 3, Y)

Joint pivots
  shoulders : on the humeral head centre (anatomy), (+-1.2, 0.66, 0)
  elbows    : on the trochlea axis, (+-1.5, 0, 0)            -> split plane Blender Z = 3.0
  hips      : R6 hip line (+-0.5, -1, 0) (the jeans' rounded hip turns around it)
  knees     : femoral condyle axis, (+-0.5, -1.95, 0)        -> split plane Blender Z = 1.05
Limb joints use identity rotations in C0/C1 (like R15); RootJoint and Neck keep the R6 ones so scripts
written for R6 heads / torsos keep working.
Angles: elbow flexion = rotation about +X (hand moves forward); knee flexion = about -X (foot moves back).
"""
import numpy as np

GROUND = -3.0
HIP_HEIGHT = 2.0
ELBOW_Z_BLENDER = 3.0
KNEE_Z_BLENDER = 1.05

R_ROOT = (-1, 0, 0, 0, 0, 1, 0, 1, 0)
IDENT = (1, 0, 0, 0, 1, 0, 0, 0, 1)

# body parts in pose-hierarchy order (a part always comes after its parent)
PARTS = ('Torso', 'Head',
         'RightUpperArm', 'RightLowerArm', 'LeftUpperArm', 'LeftLowerArm',
         'RightUpperLeg', 'RightLowerLeg', 'LeftUpperLeg', 'LeftLowerLeg')
PARENT = {'Torso': 'HumanoidRootPart', 'Head': 'Torso',
          'RightUpperArm': 'Torso', 'RightLowerArm': 'RightUpperArm',
          'LeftUpperArm': 'Torso', 'LeftLowerArm': 'LeftUpperArm',
          'RightUpperLeg': 'Torso', 'RightLowerLeg': 'RightUpperLeg',
          'LeftUpperLeg': 'Torso', 'LeftLowerLeg': 'LeftUpperLeg'}

# rest centre and size of every part (Roblox rig space)
CENTER = {'HumanoidRootPart': (0, 0, 0), 'Torso': (0, 0, 0), 'Head': (0, 1.5, 0),
          'RightUpperArm': (1.5, 0.5, 0), 'RightLowerArm': (1.5, -0.5, 0),
          'LeftUpperArm': (-1.5, 0.5, 0), 'LeftLowerArm': (-1.5, -0.5, 0),
          'RightUpperLeg': (0.5, -1.475, 0), 'RightLowerLeg': (0.5, -2.475, 0),
          'LeftUpperLeg': (-0.5, -1.475, 0), 'LeftLowerLeg': (-0.5, -2.475, 0)}
SIZE = {'HumanoidRootPart': (2, 2, 1), 'Torso': (2, 2, 1), 'Head': (2, 1, 1),
        'RightUpperArm': (1, 1, 1), 'RightLowerArm': (1, 1, 1), 'LeftUpperArm': (1, 1, 1), 'LeftLowerArm': (1, 1, 1),
        'RightUpperLeg': (1, 0.95, 1), 'RightLowerLeg': (1, 1.05, 1),
        'LeftUpperLeg': (1, 0.95, 1), 'LeftLowerLeg': (1, 1.05, 1)}

# Motor6D: name -> (part0, part1, pivot in rig space at rest, rotation of C0 and C1)
JOINT_DEFS = {
    'RootJoint': ('HumanoidRootPart', 'Torso', (0, 0, 0), R_ROOT),
    'Neck': ('Torso', 'Head', (0, 1, 0), R_ROOT),
    'RightShoulder': ('Torso', 'RightUpperArm', (1.2, 0.66, 0), IDENT),
    'RightElbow': ('RightUpperArm', 'RightLowerArm', (1.5, 0, 0), IDENT),
    'LeftShoulder': ('Torso', 'LeftUpperArm', (-1.2, 0.66, 0), IDENT),
    'LeftElbow': ('LeftUpperArm', 'LeftLowerArm', (-1.5, 0, 0), IDENT),
    'RightHip': ('Torso', 'RightUpperLeg', (0.5, -1, 0), IDENT),
    'RightKnee': ('RightUpperLeg', 'RightLowerLeg', (0.5, -1.95, 0), IDENT),
    'LeftHip': ('Torso', 'LeftUpperLeg', (-0.5, -1, 0), IDENT),
    'LeftKnee': ('LeftUpperLeg', 'LeftLowerLeg', (-0.5, -1.95, 0), IDENT),
}
JOINT_OF = {p1: name for name, (p0, p1, _, _) in JOINT_DEFS.items()}       # part1 -> joint name

# invisible hand for tools (R15 tool grip): welded to the lower arm, RightGripAttachment at the palm
HAND = {'name': 'RightHand', 'part0': 'RightLowerArm', 'center': (1.5, -0.95, 0), 'size': (0.3, 0.1, 0.3),
        'grip_attachment': 'RightGripAttachment', 'grip_rotation': (1, 0, 0, 0, 0, 1, 0, -1, 0)}

# anatomy / outfit regions = body part names; old R6 limb -> (upper, lower) and the split plane (Blender Z)
LIMBS = {'RightArm': ('RightUpperArm', 'RightLowerArm', ELBOW_Z_BLENDER),
         'LeftArm': ('LeftUpperArm', 'LeftLowerArm', ELBOW_Z_BLENDER),
         'RightLeg': ('RightUpperLeg', 'RightLowerLeg', KNEE_Z_BLENDER),
         'LeftLeg': ('LeftUpperLeg', 'LeftLowerLeg', KNEE_Z_BLENDER)}
REGIONS = ('Head', 'Torso') + PARTS[2:]

LABELS_FR = {'Torso': 'Torse', 'Head': 'Tête', 'RightUpperArm': 'Bras droit (haut)', 'RightLowerArm': 'Avant-bras droit',
             'LeftUpperArm': 'Bras gauche (haut)', 'LeftLowerArm': 'Avant-bras gauche',
             'RightUpperLeg': 'Cuisse droite', 'RightLowerLeg': 'Jambe droite (bas)',
             'LeftUpperLeg': 'Cuisse gauche', 'LeftLowerLeg': 'Jambe gauche (bas)'}


def m4(R=None, p=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = np.asarray(R, float).reshape(3, 3)
    if p is not None:
        M[:3, 3] = p
    return M


def cframe(p, r):
    """Roblox CFrame.new(x, y, z, R00..R22) as a 4x4 matrix."""
    return m4(r, p)


def c0c1(name):
    """(C0, C1) of a joint as 4x4 matrices: C0 in part0 space, C1 in part1 space."""
    p0, p1, piv, r = JOINT_DEFS[name]
    piv = np.asarray(piv, float)
    return (cframe(piv - np.asarray(CENTER[p0], float), r), cframe(piv - np.asarray(CENTER[p1], float), r))


def rest(name):
    return m4(p=CENTER[name])


def to_blender(p):
    p = np.asarray(p, float)
    return np.stack([-p[..., 0], p[..., 2], p[..., 1] + 3.0], -1)


def to_roblox(q):
    q = np.asarray(q, float)
    return np.stack([-q[..., 0], q[..., 2] - 3.0, q[..., 1]], -1)


def region_of_name(name):
    """Body part a mesh welds to, from its name (anatomy 'LeftUpperArm_Humerus', outfit 'Survivor_LeftUpperArm')."""
    if name.startswith('Survivor_'):
        rest_ = name[len('Survivor_'):]
        return {'Hat': 'Head', 'Face': 'Head', 'Backpack': 'Torso'}.get(rest_, rest_)
    return name.split('_', 1)[0]


def lua_table():
    """RIG constants for the Roblox scripts (generated into the Lua templates by make_lua.py)."""
    def num(v):
        v = float(v)
        return ('%.4f' % v).rstrip('0').rstrip('.') if v != int(v) else str(int(v))

    def vec(t):
        return '{' + ', '.join(num(x) for x in t) + '}'
    lines = ['local RIG = {', '\trigType = "R15",', f'\thipHeight = {num(HIP_HEIGHT)},', '\tparts = {']
    for n in ('HumanoidRootPart',) + PARTS:
        parent = PARENT.get(n)
        lines.append(f'\t\t{{ name = "{n}", center = {vec(CENTER[n])}, size = {vec(SIZE[n])}'
                     + (f', parent = "{parent}"' if parent else '') + ' },')
    lines.append('\t},')
    lines.append('\tjoints = {')
    for j, (p0, p1, piv, r) in JOINT_DEFS.items():
        C0, C1 = c0c1(j)
        lines.append(f'\t\t{{ name = "{j}", part0 = "{p0}", part1 = "{p1}", pivot = {vec(piv)}, '
                     f'c0 = {vec(list(C0[:3, 3]) + list(np.asarray(r).ravel()))}, '
                     f'c1 = {vec(list(C1[:3, 3]) + list(np.asarray(r).ravel()))} }},')
    lines.append('\t},')
    lines.append('\tposeOrder = {' + ', '.join(f'"{p}"' for p in PARTS) + '},')
    lines.append(f'\thand = {{ name = "{HAND["name"]}", part0 = "{HAND["part0"]}", center = {vec(HAND["center"])}, '
                 f'size = {vec(HAND["size"])}, attachment = "{HAND["grip_attachment"]}", '
                 f'rotation = {vec(HAND["grip_rotation"])} }},')
    lines.append('\tlabels = {' + ', '.join(f'{p} = "{LABELS_FR[p]}"' for p in PARTS) + '},')
    lines.append('}')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(lua_table())
    for j in JOINT_DEFS:
        C0, C1 = c0c1(j)
        print(j, C0[:3, 3], C1[:3, 3])
