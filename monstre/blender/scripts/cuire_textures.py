"""Textures de la créature : dépliage UV de chaque maillage de jeu, puis cuisson Cycles depuis la peau continue haute
définition (couleur, rugosité, normale) et matière finale à textures.

usage : python cuire_textures.py -- creature.blend creature_tex.blend dossier_textures [préfixes de pièces]
Variables d'environnement : BSPP (échantillons de la cuisson de couleur, 12 par défaut, 16 pour les livrables),
TDENS (pixels par stud, 300 par défaut), PEAU_REELLE (dossier des vraies textures de peau ; par défaut
../textures_reelles à côté de ce script ; « aucune » pour la peau procédurale seule), SANG (« non » par défaut : pas
de sang ; « oui » seulement pour des rendus hors jeu : la modération de Roblox refuse les textures tachées de sang)."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import mon_skin as SK
import mon_sang as SANG
args = sys.argv[sys.argv.index('--') + 1:]
real = os.environ.get('PEAU_REELLE', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'textures_reelles'))
real = None if real == 'aucune' else os.path.abspath(real)
if real and not os.path.exists(os.path.join(real, 'peau_couleur_1.png')):
    sys.exit('textures réelles introuvables dans %s (PEAU_REELLE=aucune pour s\'en passer)' % real)
bpy.ops.wm.open_mainfile(filepath=args[0])
los = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('MON_')]
if len(args) > 3:
    los = [o for o in los if any(o.name.startswith('MON_' + k) for k in args[3].split(','))]
hds = {}
for o in bpy.data.objects:
    if o.name.startswith('HD_'):
        for pc in (o['pieces'].split(',') if 'pieces' in o else [o['piece']]):
            hds[pc] = o
print('textures réelles :', real)
blood = os.environ.get('SANG', 'non') == 'oui'
if blood:                      # sang : attributs Sang / SangFrais sur chaque maillage HD (gueule, mains, coulures...)
    t0 = time.time()
    for o in sorted(set(hds.values()), key=lambda o: o.name):
        part = SANG.apply_to_object(o, o.name.replace('HD_', ''))
        print('  sang sur %-12s %.1f %% de la surface (%.1f s)' % (o.name, 100 * part, time.time() - t0), flush=True)
SK.texture_from_hd(los, hds, args[2], samples=int(os.environ.get('BSPP', '12')),
                   density=float(os.environ.get('TDENS', '300')), real_dir=real, blood=blood)
bpy.ops.wm.save_as_mainfile(filepath=args[1], compress=True)
