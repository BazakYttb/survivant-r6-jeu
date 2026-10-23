"""Showcase renders -> ../apercus/*.png
usage: python render_final.py [shot ...] [--samples 48] [--scale 1.0]
A shot may pose the jointed rig with a frame of an animation (clip key, time in s)."""
import sys, os, fnmatch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Matrix
import blend_lib as B

OUT = os.path.join(B.HERE, '..', 'apercus')

SKELETON = {'bone', 'tooth', 'cartilage', 'disc', 'ligament'}
OUTFIT = ('skin', 'gear')

SHOTS = {
    # name: (anatomy filter(name, meta) -> bool, view, elev, azim, outfit, res, persp, (view transform, exposure)[, pose])
    # outfit: None = anatomy only, 1.0 = full survivor outfit, < 1 = see-through skin and clothes (no hat, no backpack)
    # pose: (clip key, time) of anim.py, else the rest pose
    'survivant_troisquarts': (lambda n, m: False, 'threeq', 8, 30, 1.0, (1100, 1400), False, ('Standard', -1.2)),
    'survivant_face': (lambda n, m: False, 'front', 4, None, 1.0, (1100, 1400), False, ('Standard', -1.2)),
    'survivant_dos': (lambda n, m: False, 'back', 8, None, 1.0, (1100, 1400), False, ('Standard', -1.2)),
    'radiographie_face': (lambda n, m: True, 'front', 6, None, 0.25, (1100, 1500), False, ('Standard', -1.0)),
    'radiographie_troisquarts': (lambda n, m: True, 'threeq', 12, 30, 0.25, (1100, 1500), False, ('Standard', -1.0)),
    'corps_troisquarts': (lambda n, m: True, 'threeq', 12, 30, None, (1100, 1500), False, None),
    'corps_dos': (lambda n, m: True, 'back', 6, None, None, (1100, 1500), False, None),
    'squelette_face': (lambda n, m: m['cat'] in SKELETON, 'front', 6, None, None, (1100, 1500), False, None),
    'organes_thorax_abdomen': (lambda n, m: m['region'] == 'Torso' and m['cat'] not in SKELETON | {'nerve'}
                               and not n.startswith('Torso_Rib'), 'threeq', 10, 25, None, (1200, 1200), False, None),
    'tete_cerveau': (lambda n, m: m['region'] == 'Head' and n != 'Head_Skull_Calvaria', 'threeq', 28, 35, None,
                     (1200, 1200), False, None),
    'tete_crane': (lambda n, m: m['region'] == 'Head', 'threeq', 10, 30, None, (1200, 1200), False, None),
    'main_gauche': (lambda n, m: m['region'] == 'LeftLowerArm' and m['cat'] in SKELETON | {'vessel', 'nerve'},
                    'front', 4, None, None, (900, 1300), False, None),
    'genou_pied': (lambda n, m: m['region'] in ('LeftUpperLeg', 'LeftLowerLeg'), 'threeq', 8, 40, None, (900, 1400),
                   False, None),
    # jointed rig: elbows and knees bent by an animation frame
    'survivant_course': (lambda n, m: False, 'threeq', 8, 32, 1.0, (1100, 1400), False, ('Standard', -1.2), ('run', 0.0)),
    'radiographie_course': (lambda n, m: True, 'threeq', 8, 32, 0.25, (1100, 1400), False, ('Standard', -1.0),
                            ('run', 0.0)),
    'survivant_accroupi': (lambda n, m: False, 'threeq', 10, 38, 1.0, (1100, 1100), False, ('Standard', -1.2),
                           ('crouchwalk', 0.25)),
}


def pose_objects(objs, man, clip, t):
    import anim as A
    from anim_preview import part_matrix
    W = A.CLIP[clip].world(t)
    for ob in objs:
        part = man[ob.name]['region']
        ob.matrix_world = Matrix(part_matrix(W[part], part).tolist())
    bpy.context.view_layer.update()


def main():
    a = sys.argv[1:]
    samples = int(a[a.index('--samples') + 1]) if '--samples' in a else 48
    scale = float(a[a.index('--scale') + 1]) if '--scale' in a else 1.0
    shots = [s for s in a if s in SHOTS] or list(SHOTS)
    os.makedirs(OUT, exist_ok=True)
    man = B.manifest()
    for shot in shots:
        flt, view, elev, azim, outfit, res, persp, look = SHOTS[shot][:8]
        pose = SHOTS[shot][8] if len(SHOTS[shot]) > 8 else None
        B.reset()
        B._MAT.clear()
        names = [n for n in B.part_names() if n in man and man[n]['cat'] not in OUTFIT and flt(n, man[n])]
        if outfit is not None:
            names += [n for n in B.part_names(['Survivor_*'])
                      if n in man and (outfit >= 0.999 or man[n]['cat'] == 'skin')]
        if not names:
            continue
        objs = [B.load_part(n, man, skin_alpha=outfit if outfit is not None else 1.0) for n in names]
        if pose:
            pose_objects(objs, man, *pose)
        vt, ex = look or ('AgX', 0.0)
        B.setup_render((int(res[0] * scale), int(res[1] * scale)), samples, bg=(0.035, 0.038, 0.045), view=vt, exposure=ex)
        B.camera(objs, view, elev=elev, azim=azim, ortho=not persp, margin=1.08)
        B.render(os.path.abspath(os.path.join(OUT, shot + '.png')))
        print('rendered', shot, len(objs))


if __name__ == '__main__':
    main()
