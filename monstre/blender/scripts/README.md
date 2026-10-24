# Scripts Blender du monstre (bpy 5.2)

Tout est fait dans Blender 5.2 utilisé comme module Python (`bpy`), en mode sans interface, rendus Cycles CPU.
Environnement (hors du dépôt) : `uv venv -p 3.13 venv` puis `uv pip install --python venv/bin/python "bpy==5.2.*" numpy scipy pillow`.

Chaîne complète, à lancer depuis ce dossier (temps mesurés sur 4 cœurs, 15 Go de mémoire) :

```bash
PY=chemin/vers/venv/bin/python
$PY construire.py -- creature.blend                                    # anatomie -> corps continu -> 37 pièces (~4 min)
$PY cuire_textures.py -- creature.blend creature_tex.blend textures/   # UV + cuisson couleur/rugosité/normale (~8 min)
$PY rendus.py -- creature_tex.blend rendus/ trois_quarts,trois_quarts_sombre,face,profil,dos,tete,main,pliage 1024 96
$PY exporter.py -- creature_tex.blend ../..                            # monstre/blender/Monstre.blend, monstre/export/*
$PY verifier_export.py -- ../..                                        # réimporte GLB/FBX et contrôle noms, triangles, marqueurs
```

(`cuire_textures.py` lit la variable d'environnement `BSPP`, échantillons de la cuisson de couleur : 16 pour les livrables.)

| Fichier | Rôle |
|---|---|
| `mon_common.py` | maths (courbes, repères, bruit), couleurs, conversion de repère Roblox <-> Blender |
| `mon_skel.py` | squelette (pivots `J`, repère de tête `FH`/`UH`, mains), `rig_spec()` : 37 pièces |
| `mon_flesh.py` | anatomie de la créature : surfaces balayées à profil anatomique (tronc, membres, pieds), capsules et ellipsoïdes (côtes, rebord costal, sternum, colonne, omoplates, clavicules, bassin, articulations, tendons), tête et mâchoire, griffes et crocs |
| `mon_body.py` | crâne paramétrique (`head_radius`, gueule, mâchoire) ; contient aussi la première version « tendons noirs » |
| `mon_gen.py` | générateurs de brins (capsules, griffes, crocs, ellipsoïdes) |
| `mon_blend.py` | aides Blender : objets Curves, arbre Geometry Nodes de fusion SDF (congés, fermeture, lissage, report des attributs), décimation |
| `mon_build.py` | assemblage des maillages (numpy <-> Blender), décimation |
| `mon_cut.py` | découpe du corps continu en pièces (os le plus proche) et manchons rentrés sous la peau |
| `mon_tex.py` | dépliage UV (Smart UV Project), images, matière finale à textures |
| `mon_skin.py` | peau procédurale (marbrures, rougeurs, ecchymoses, veines, crasse, terre sur les pieds, griffures, rides, plis, grain) et cuisson « sélection vers actif » |
| `mon_rig.py` | rig d'empties dans Blender, poses (présentation, test de pliage) |
| `mon_scene.py`, `mon_scene2.py` | scènes de rendu : brume claire, intérieur sombre en bois, lueur de la gueule |
| `construire.py`, `cuire_textures.py`, `rendus.py`, `exporter.py`, `verifier_export.py` | les étapes ci-dessus |

Construction (`construire.py`) : les formes anatomiques de tout le corps sont fusionnées en une seule peau (grille SDF,
congés, fermeture, lissage des positions), de même pour chaque main et pour la mâchoire. Cette peau continue sert à la
cuisson (`HD_*`). Pour le jeu, elle est décimée d'un bloc, puis découpée en pièces le long des courbes d'égale distance
entre deux os (triangles recoupés) : deux pièces voisines partagent exactement les mêmes sommets de bord et les mêmes
normales (normales personnalisées), donc aucun raccord ne se voit au repos. Une pièce trop dense est redécimée seule,
bord verrouillé. Chaque jointure a un manchon porté par la pièce enfant : la peau de la parente près de la frontière,
rentrée de 0,012 stud sous la surface, qui bouche le vide quand l'articulation plie.
