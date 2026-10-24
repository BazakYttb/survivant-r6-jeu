"""Textures de la créature : dépliage UV de chaque maillage de jeu, puis cuisson Cycles depuis la peau continue haute
définition (couleur, rugosité, normale) et matière finale à textures.

usage : python cuire_textures.py -- creature.blend creature_tex.blend dossier_textures [préfixes de pièces]
(variable d'environnement BSPP : échantillons de la cuisson de couleur, 12 par défaut, 16 pour les livrables)"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import mon_skin as SK
args = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=args[0])
los = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('MON_')]
if len(args) > 3:
    los = [o for o in los if any(o.name.startswith('MON_' + k) for k in args[3].split(','))]
hds = {}
for o in bpy.data.objects:
    if o.name.startswith('HD_'):
        for pc in (o['pieces'].split(',') if 'pieces' in o else [o['piece']]):
            hds[pc] = o
SK.texture_from_hd(los, hds, args[2], samples=int(os.environ.get('BSPP', '12')))
bpy.ops.wm.save_as_mainfile(filepath=args[1], compress=True)
