# Scripts Blender du monstre (bpy 5.2)

Tout est fait dans Blender 5.2 utilisé comme module Python (`bpy`), en mode sans interface, rendus Cycles CPU.
Environnement (hors du dépôt) : `uv venv -p 3.13 venv` puis `uv pip install --python venv/bin/python "bpy==5.2.*" numpy scipy pillow`
(ffmpeg en plus pour les sons).

Chaîne complète, à lancer depuis ce dossier (temps mesurés sur 4 cœurs, 15 Go de mémoire) :

```bash
PY=chemin/vers/venv/bin/python
$PY -I textures_reelles.py dossier_du_scan ../textures_reelles         # (une fois) motifs de peau tirés du scan
$PY construire.py -- creature.blend                                    # anatomie -> corps continu -> 37 pièces (~4 min)
$PY cuire_textures.py -- creature.blend creature_tex.blend textures/   # sang, UV + cuisson couleur/rugosité/normale (~12 min)
$PY sang_decals.py sang/                                               # textures des décalques de sang (flaque, éclaboussures...)
$PY rendus.py -- creature_tex.blend rendus/ trois_quarts,trois_quarts_sombre,face,profil,dos,tete,main,pliage 1024 96
$PY exporter.py -- creature_tex.blend ../.. sang/                      # monstre/blender/Monstre.blend, monstre/export/* (+ gabarits SANG_*)
$PY verifier_export.py -- ../..                                        # réimporte GLB/FBX et contrôle noms, triangles, marqueurs, gabarits
$PY exporter_roblox.py                                                 # monstre/roblox : MonstreDonnees.lua, Monstre_Kit.rbxmx, données de test
$PY sons_monstre.py ../../roblox/sons                                  # 19 sons synthétisés (.ogg, ffmpeg)
```

`cuire_textures.py` lit les variables d'environnement `BSPP` (échantillons de la cuisson de couleur : 16 pour les
livrables), `TDENS` (pixels par stud, 300 par défaut), `PEAU_REELLE` (dossier des vraies textures de peau, par défaut
`../textures_reelles` ; `aucune` pour une peau procédurale seule) et `SANG` (`non` : sans sang). Les motifs de
`../textures_reelles` sont déjà faits : `textures_reelles.py` ne sert qu'à les refaire depuis le scan (voir
`../textures_reelles/LISEZMOI.md`).

Animations (sans Blender pour le calcul ; `src/` du survivant requis, trouvé à `../../../src` ou par la variable
`SURVIVANT_SRC`) :

```bash
$PY apercu_rapide.py apercu.png k_cou,k_ventre 8 profil,tq 240        # planche rapide (maillage allégé ../proxy.npz)
$PY apercu_anim.py -- creature_tex.blend apercu.png walk,k_frenesie 6 300 trois_quarts   # planche Cycles
$PY dump_proxy.py -- creature.blend ../proxy.npz 0.1                  # refaire le maillage allégé
$PY gif_morts.py ../../rendus/animations                               # GIF animés des 8 mises à mort et du déplacement
```

| Fichier | Rôle |
|---|---|
| `mon_common.py` | maths (courbes, repères, bruit), couleurs, conversion de repère Roblox <-> Blender, chemins du projet |
| `mon_skel.py` | squelette (pivots `J`, repère de tête `FH`/`UH`, mains), `rig_spec()` : 37 pièces |
| `mon_flesh.py` | anatomie de la créature : surfaces balayées à profil anatomique (tronc, membres, pieds), capsules et ellipsoïdes (côtes, rebord costal, sternum, colonne, omoplates, clavicules, bassin, articulations, tendons), tête et mâchoire, griffes et crocs |
| `mon_body.py` | crâne paramétrique (`head_radius`, gueule, mâchoire) ; contient aussi la première version « tendons noirs » |
| `mon_gen.py` | générateurs de brins (capsules, griffes, crocs, ellipsoïdes) |
| `mon_blend.py` | aides Blender : objets Curves, arbre Geometry Nodes de fusion SDF (congés, fermeture, lissage, report des attributs), décimation |
| `mon_build.py` | assemblage des maillages (numpy <-> Blender), décimation |
| `mon_cut.py` | découpe du corps continu en pièces (os le plus proche) et manchons rentrés sous la peau |
| `mon_tex.py` | dépliage UV (Smart UV Project), images, matière finale à textures |
| `mon_skin.py` | matière de peau : vraies textures de peau en projection triplanaire (grain de couleur, pores et plis, brillance), couches procédurales (marbrures, rougeurs, ecchymoses, veines, crasse, terre sur les pieds, griffures, rides, plis) et sang (frais, séché, croûtes) ; cuisson « sélection vers actif » |
| `mon_sang.py` | où est le sang : attributs `Sang` / `SangFrais` sur la peau haute définition (gueule, crocs, mains, griffes, coulures qui suivent la pente, éclaboussures) |
| `sang_decals.py` | textures des décalques de sang pour Roblox (flaque, 3 éclaboussures, traînée raccordable, sang sur l'écran, goutte) |
| `textures_reelles.py` | motifs de peau raccordables tirés d'un scan de tête réel (CC BY 3.0) |
| `mon_rig.py` | rig d'empties dans Blender, poses (présentation, test de pliage) |
| `mon_scene.py`, `mon_scene2.py` | scènes de rendu : brume claire, intérieur sombre en bois, lueur de la gueule |
| `mon_anim.py` | animation du rig de 37 pièces (+ `VictimeAncre`) : cinématique directe, IK des jambes (pieds plantés) et des bras, courbes, pistes, clips |
| `mon_clips.py` | repos, marche, course, saut, chute, atterrissage, hurlement, flairer, attaque |
| `mon_morts.py` | les 8 mises à mort : clips du monstre et de la victime (rig du survivant, `src/anim.py`), attaches gueule / mains, traînées, marqueurs |
| `exporter_roblox.py` | données d'animation pour Roblox (pistes réduites et quantifiées, base64), kit `.rbxmx`, données de test |
| `apercu_rapide.py`, `dump_proxy.py`, `apercu_anim.py` | planches d'aperçu (rapide sans Blender, ou Cycles) |
| `gif_morts.py` | GIF animés (moteur d'aperçu rapide) : phases enchaînées, sol qui défile, traînée de sang |
| `sons_monstre.py` | sons synthétisés (grognements, hurlements, morsures, déchirures, mastication, pas, cœur, toux...) |
| `construire.py`, `cuire_textures.py`, `rendus.py`, `exporter.py`, `verifier_export.py` | les étapes ci-dessus |

Construction (`construire.py`) : les formes anatomiques de tout le corps sont fusionnées en une seule peau (grille SDF,
congés, fermeture, lissage des positions), de même pour chaque main et pour la mâchoire. Cette peau continue sert à la
cuisson (`HD_*`). Pour le jeu, elle est décimée d'un bloc, puis découpée en pièces le long des courbes d'égale distance
entre deux os (triangles recoupés) : deux pièces voisines partagent exactement les mêmes sommets de bord et les mêmes
normales (normales personnalisées), donc aucun raccord ne se voit au repos. Une pièce trop dense est redécimée seule,
bord verrouillé. Chaque jointure a un manchon porté par la pièce enfant : la peau de la parente près de la frontière,
rentrée de 0,012 stud sous la surface, qui bouche le vide quand l'articulation plie.
