# Rapport : actions Blender corrigées (deuxième passe)

Session cloud du 23/10/2026, tâche décrite dans `TACHE_CLOUD.md`. La première passe est sur la branche
`blender-corrige`, qui n'a pas été modifiée.

**Résultat.** `dist/Survivant_R6_Anime_corrige.blend` contient les 15 actions recalculées par
`outils/maj_actions_blend.py` depuis `src/anim.py` (commit `99d9232` : botte droite de l'accroupi à plat, clés
linéaires), sur l'armature `Rig_R6_Articule` de la scène d'origine.

- Les deux contrôles donnent exactement les valeurs du tableau de `TACHE_CLOUD.md`.
- Interpolation : `BEZIER` dans les 15 actions de la scène d'origine, `LINEAR` dans les 15 actions de la scène
  corrigée.
- Point le plus bas des bottes dans l'accroupi : −0,0723 → **−0,0040**, soit l'épaisseur de la semelle, comme au
  repos. Marche, Course et Marche accroupie restent à −0,0042, −0,0104 et −0,0195 aux images clés, comme dans la
  première passe.
- Par rapport à la première passe, seuls changent l'interpolation des 15 actions et les clés des deux os de la
  jambe droite de l'accroupi. Maillages, tenue, anatomie, armature, pistes NLA et réglages de la scène sont
  identiques à ceux de la scène d'origine, qui n'a pas été modifiée.

## Environnement

| | |
|---|---|
| Blender | 5.2.3 LTS en module Python : `bpy` 5.2.3 (compilé le 22/10/2026, `e13b728c6880`, branche `blender-v5.2-release`), même build que la première passe |
| Installation | `uv venv -p 3.13` puis `uv pip install "bpy==5.2.*"`, dans un environnement virtuel hors du dépôt (dossier temporaire de la session) |
| Python | 3.13.17, numpy 2.5.4 |
| Machine | conteneur Linux x86_64, 4 cœurs, 15 Go de mémoire |

## Commandes et durées

| Étape | Commande | Durée |
|---|---|---:|
| Installation | `uv pip install "bpy==5.2.*"` (12 paquets, dont la roue bpy d'environ 384 Mio) | 10 min 26 s |
| Contrôle avant | `python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime.blend` | 2,6 s |
| Mise à jour | `python outils/maj_actions_blend.py dist/Survivant_R6_Anime.blend src dist/Survivant_R6_Anime_corrige.blend` | 14,5 s |
| Contrôle après | `python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime_corrige.blend` | 3,4 s |
| Bottes et contrôles complémentaires | scripts de la session, hors dépôt (voir plus bas) | 15 à 25 s par lot |

De l'installation à la fin des contrôles : 22 minutes, analyse comprise. L'installation a pris 10 min 26 s,
contre 2 min 10 s lors de la première passe, parce que le réseau du conteneur était lent (environ 0,5 Mo/s).

Sortie de la mise à jour :

```
00:00.490  blend            | Read blend: "/home/user/survivant-r6-jeu/dist/Survivant_R6_Anime.blend"
Survivant_Repos: 77 courbes remplacées, 121 images
Survivant_Marche: 77 courbes remplacées, 22 images
Survivant_Course: 77 courbes remplacées, 18 images
Survivant_Accroupi: 77 courbes remplacées, 91 images
Survivant_MarcheAccroupie: 77 courbes remplacées, 31 images
Survivant_Allonge: 77 courbes remplacées, 121 images
Survivant_Ramper: 77 courbes remplacées, 43 images
Survivant_Saut: 77 courbes remplacées, 16 images
Survivant_Chute: 77 courbes remplacées, 28 images
Survivant_Atterrissage: 77 courbes remplacées, 14 images
Survivant_SAllonger: 77 courbes remplacées, 29 images
Survivant_SeRelever: 77 courbes remplacées, 35 images
Survivant_Grimper: 77 courbes remplacées, 15 images
Survivant_Assis: 77 courbes remplacées, 91 images
Survivant_Outil: 77 courbes remplacées, 121 images
Info: Saved copy as "Survivant_R6_Anime_corrige.blend"
enregistré : dist/Survivant_R6_Anime_corrige.blend
```

## Contrôle avant : `dist/Survivant_R6_Anime.blend`

```
00:00.394  blend            | Read blend: "/home/user/survivant-r6-jeu/dist/Survivant_R6_Anime.blend"
15 actions Survivant_*
Survivant_Accroupi           images 1-91 ; saut max   1.5° (Head, image 55) ; rotation max 105.8° (RightUpperLeg, image 30) ; interpolation BEZIER
Survivant_Allonge            images 1-121 ; saut max   2.0° (Head, image 121) ; rotation max 136.0° (RightUpperArm, image 20) ; interpolation BEZIER
Survivant_Assis              images 1-91 ; saut max   1.0° (Head, image 42) ; rotation max  90.0° (RightLowerLeg, image 1) ; interpolation BEZIER
Survivant_Atterrissage       images 1-14 ; saut max 179.9° (LeftUpperLeg, image 11) ; rotation max 179.9° (LeftUpperLeg, image 1) ; interpolation BEZIER
Survivant_Chute              images 1-28 ; saut max   2.8° (RightLowerArm, image 3) ; rotation max 123.0° (LeftUpperArm, image 23) ; interpolation BEZIER
Survivant_Course             images 1-18 ; saut max  30.6° (RightLowerLeg, image 9) ; rotation max 111.9° (RightLowerLeg, image 11) ; interpolation BEZIER
Survivant_Grimper            images 1-15 ; saut max 112.3° (LeftUpperArm, image 5) ; rotation max 174.5° (RightUpperArm, image 8) ; interpolation BEZIER
Survivant_Marche             images 1-22 ; saut max  25.4° (LeftLowerLeg, image 5) ; rotation max  61.9° (LeftLowerLeg, image 6) ; interpolation BEZIER
Survivant_MarcheAccroupie    images 1-31 ; saut max  10.6° (LeftLowerLeg, image 13) ; rotation max 126.1° (RightLowerLeg, image 13) ; interpolation BEZIER
Survivant_Outil              images 1-121 ; saut max 180.0° (LeftUpperLeg, image 13) ; rotation max 180.0° (LeftUpperLeg, image 103) ; interpolation BEZIER
Survivant_Ramper             images 1-43 ; saut max   7.2° (LeftUpperLeg, image 6) ; rotation max 145.2° (RightUpperArm, image 1) ; interpolation BEZIER
Survivant_Repos              images 1-121 ; saut max 180.0° (LeftUpperLeg, image 13) ; rotation max 180.0° (LeftUpperLeg, image 103) ; interpolation BEZIER
Survivant_SAllonger          images 1-29 ; saut max  41.6° (LeftUpperLeg, image 5) ; rotation max 179.9° (LeftUpperLeg, image 1) ; interpolation BEZIER
Survivant_Saut               images 1-16 ; saut max  54.7° (RightUpperArm, image 4) ; rotation max 152.4° (RightUpperArm, image 6) ; interpolation BEZIER
Survivant_SeRelever          images 1-35 ; saut max  29.7° (LeftUpperLeg, image 31) ; rotation max 178.3° (LeftUpperLeg, image 35) ; interpolation BEZIER
```

## Contrôle après : `dist/Survivant_R6_Anime_corrige.blend`

```
00:00.435  blend            | Read blend: "/home/user/survivant-r6-jeu/dist/Survivant_R6_Anime_corrige.blend"
15 actions Survivant_*
Survivant_Accroupi           images 1-91 ; saut max   1.5° (Head, image 55) ; rotation max 106.2° (RightUpperLeg, image 29) ; interpolation LINEAR
Survivant_Allonge            images 1-121 ; saut max   2.0° (Head, image 121) ; rotation max 136.0° (RightUpperArm, image 20) ; interpolation LINEAR
Survivant_Assis              images 1-91 ; saut max   1.0° (Head, image 42) ; rotation max  90.0° (RightLowerLeg, image 1) ; interpolation LINEAR
Survivant_Atterrissage       images 1-14 ; saut max  29.9° (RightUpperArm, image 3) ; rotation max  99.9° (RightUpperArm, image 1) ; interpolation LINEAR
Survivant_Chute              images 1-28 ; saut max   2.8° (RightLowerArm, image 3) ; rotation max 123.0° (LeftUpperArm, image 23) ; interpolation LINEAR
Survivant_Course             images 1-18 ; saut max  30.6° (RightLowerLeg, image 9) ; rotation max 111.9° (RightLowerLeg, image 11) ; interpolation LINEAR
Survivant_Grimper            images 1-15 ; saut max  54.4° (RightUpperArm, image 12) ; rotation max 147.7° (RightLowerArm, image 11) ; interpolation LINEAR
Survivant_Marche             images 1-22 ; saut max  25.4° (LeftLowerLeg, image 5) ; rotation max  61.9° (LeftLowerLeg, image 6) ; interpolation LINEAR
Survivant_MarcheAccroupie    images 1-31 ; saut max  12.9° (LeftLowerLeg, image 15) ; rotation max 126.1° (RightLowerLeg, image 13) ; interpolation LINEAR
Survivant_Outil              images 1-121 ; saut max   1.8° (Head, image 35) ; rotation max  73.9° (RightUpperArm, image 16) ; interpolation LINEAR
Survivant_Ramper             images 1-43 ; saut max   7.2° (LeftUpperLeg, image 6) ; rotation max 145.2° (RightUpperArm, image 1) ; interpolation LINEAR
Survivant_Repos              images 1-121 ; saut max   1.8° (Head, image 35) ; rotation max  19.0° (Head, image 49) ; interpolation LINEAR
Survivant_SAllonger          images 1-29 ; saut max  20.3° (RightLowerLeg, image 5) ; rotation max 144.1° (RightUpperArm, image 26) ; interpolation LINEAR
Survivant_Saut               images 1-16 ; saut max  54.7° (RightUpperArm, image 4) ; rotation max 152.4° (RightUpperArm, image 6) ; interpolation LINEAR
Survivant_SeRelever          images 1-35 ; saut max  20.3° (LeftLowerLeg, image 22) ; rotation max 138.5° (RightUpperArm, image 3) ; interpolation LINEAR
```

## Comparaison au tableau de `TACHE_CLOUD.md`

Plus grand saut de rotation d'un os entre deux images :

| Action | avant attendu | avant obtenu | après attendu | après obtenu |
|---|---:|---:|---:|---:|
| Survivant_Repos | 180,0° (LeftUpperLeg) | 180,0° (LeftUpperLeg) | 1,8° | 1,8° (Head) |
| Survivant_Atterrissage | 179,9° (LeftUpperLeg) | 179,9° (LeftUpperLeg) | 29,9° | 29,9° (RightUpperArm) |
| Survivant_Outil | 180,0° (LeftUpperLeg) | 180,0° (LeftUpperLeg) | 1,8° | 1,8° (Head) |
| Survivant_SAllonger | 41,6° (LeftUpperLeg) | 41,6° (LeftUpperLeg) | 20,3° | 20,3° (RightLowerLeg) |
| Survivant_SeRelever | 29,7° (LeftUpperLeg) | 29,7° (LeftUpperLeg) | 20,3° | 20,3° (LeftLowerLeg) |
| Survivant_Grimper | 112,3° (LeftUpperArm) | 112,3° (LeftUpperArm) | 54,4° | 54,4° (RightUpperArm, image 12) |
| Survivant_Saut | 54,7° | 54,7° | 54,7° | 54,7° (RightUpperArm) |
| Survivant_Course | 30,6° | 30,6° | 30,6° | 30,6° (RightLowerLeg) |
| Survivant_Marche | 25,4° | 25,4° | 25,4° | 25,4° (LeftLowerLeg) |
| Survivant_Accroupi | 1,5° | 1,5° (Head) | 1,5° | 1,5° (Head) |
| les 5 autres | sous 13° | 1,0 à 10,6° | sous 13° | 1,0 à 12,9° (Marche accroupie) |

**Interpolation** : `BEZIER` dans les 15 actions de la scène d'origine, `LINEAR` dans les 15 actions de la scène
corrigée. Chaque action a 77 courbes (11 os, position et quaternion), et toutes leurs clés sont en `LINEAR`.

Par rapport à la première passe, `--verifier` donne les mêmes lignes, à deux différences près : l'interpolation,
et la rotation maximale de l'accroupi, 105,8° (RightUpperLeg, image 30) → 106,2° (RightUpperLeg, image 29),
parce que la cuisse droite est orientée autrement.

## Bottes

Point le plus bas des sommets des maillages `Survivor_RightLowerLeg` et `Survivor_LeftLowerLeg` (parentés aux os
de la jambe, sans modificateur ni forme), sol à z = 0, évalué par Blender à chaque image de l'action. Au repos,
sans action, les deux bottes sont à −0,0040 : c'est l'épaisseur de la semelle.

**Aux images clés** :

| Action | scène d'origine | première passe | cette passe | `anim.py` à 240 i/s |
|---|---:|---:|---:|---:|
| Accroupi, botte droite | −0,0723 (image 39) | −0,0723 | **−0,0040** (image 85) | −0,0040 |
| Accroupi, botte gauche | +0,0027 | +0,0027 | +0,0027 | +0,0027 |
| Marche | −0,1948 | −0,0042 | −0,0042 | −0,0051 |
| Course | −0,1754 | −0,0104 | −0,0104 | −0,0104 |
| Marche accroupie | −0,3096 | −0,0195 | −0,0195 | −0,0220 |
| Repos, Outil | −0,0023 | −0,0023 | −0,0023 | −0,0023 |
| Atterrissage | −0,0010 | −0,0010 | −0,0010 | −0,0010 |

La dernière colonne ne dépend pas des clés de la scène : les maillages sont déplacés directement avec les poses
d'`anim.py`, 240 fois par seconde. En marche accroupie, son minimum (−0,0220) tombe entre deux images à 30 i/s.

**Orientation des bottes dans l'accroupi**, mesurée sur les os de la scène, sur les 91 images :

| | tibia / verticale | semelle penchée sur le côté | pointe vers l'extérieur |
|---|---:|---:|---:|
| botte droite, avant | 9,4 à 10,8° | 9,4 à 10,8° (sur son bord intérieur) | 0° |
| botte droite, après | 0,0° | 0,0° (à plat) | 12,5 à 13,9° |
| botte gauche, avant et après | 6,7 à 8,0° | 6,7 à 8,0° | 0° |

C'est ce que décrit `TACHE_CLOUD.md` : semelle à plat, pointe tournée d'environ 13° vers l'extérieur, pied gauche
inchangé. Dans `Survivant_Accroupi`, seules les clés de `RightUpperLeg` (jusqu'à 0,36 sur la position, voir les
remarques) et de `RightLowerLeg` (3,7·10⁻³) changent ; les 9 autres os ont exactement les mêmes clés.

**Entre deux images** : la scène est évaluée tous les 1/10 d'image et comparée à Roblox, qui interpole lui aussi
linéairement entre ses images clés (position linéaire et slerp de chaque `Motor6D.Transform`).

| Action | première passe (Bézier) | cette passe (linéaire) | Roblox, mêmes images à 30 i/s | Roblox, clés publiées | `anim.py` continu |
|---|---:|---:|---:|---:|---:|
| Accroupi | −0,0723 | −0,0040 | −0,0040 | −0,0040 (16 clés) | −0,0040 |
| Marche | −0,0163 | −0,0056 | −0,0056 | −0,0056 (22 clés) | −0,0051 |
| Course | −0,0494 | −0,0343 | −0,0343 | −0,0335 (18 clés) | −0,0104 |
| Marche accroupie | −0,0216 | −0,0199 | −0,0199 | −0,0218 (29 clés) | −0,0220 |
| Atterrissage | −0,0149 | −0,0217 | −0,0217 | −0,0201 (14 clés) | −0,0010 |

Les « clés publiées » sont les images clés réduites que `make_lua.py` écrit dans
`roblox/SurvivantR6_Animations.lua` (`anim.reduce_keys`) ; leur nombre est celui du fichier.

## Contrôles complémentaires

Le contrôle du script ne regarde que les rotations aux images entières. D'autres scripts de la session ont aussi
été lancés, hors dépôt et en lecture seule sur les scènes ; ils ont fourni les mesures ci-dessus et les points
suivants :

1. **Rien d'autre n'a changé.** Une empreinte de chaque scène a été calculée sur les 227 objets (224 maillages,
   817 585 sommets) : géométrie, attributs, matériaux, parentage aux os et transformations. Elle couvre aussi les
   11 os au repos, les 15 pistes NLA et les réglages de la scène. Ces derniers sont inchangés : 30 i/s, images 1 à
   22, action active `Survivant_Marche` sur l'emplacement `OBRig_R6_Articule`. Les pistes NLA sont toujours
   muettes et pointent vers les mêmes actions, avec les mêmes plages d'images. Les actions gardent le même nombre
   de courbes et de clés. Entre la scène d'origine et la scène corrigée, l'empreinte ne diffère que par
   l'interpolation des 15 actions.
2. **Les actions sont celles d'`anim.py`.** À chaque image de chaque action, les poses évaluées par Blender
   s'écartent de celles calculées depuis `anim.py` d'au plus 8·10⁻⁷ stud et 3·10⁻⁵°, soit la précision des
   flottants.
3. **Comparaison avec la première passe.** Les 14 actions autres que l'accroupi ont exactement les mêmes valeurs
   de clés que dans `blender-corrige` ; seule leur interpolation change.
4. **Pas de tour parasite entre deux images.** Le produit scalaire entre les quaternions de deux clés voisines
   vaut au moins +0,888 (Saut ; +0,889 pour Grimper). Il est positif partout. À la demi-image, la rotation
   donnée par Blender est sur le plus court chemin entre les deux clés à 5·10⁻⁶° près, comme le slerp de Roblox.
   Avec les clés de Bézier de la première passe, elle s'en écartait jusqu'à 6,1° (Grimper).

## Remarques

- **Course entre deux images : −0,034.** Au décollement de la pointe (image 4,5), la botte descend 0,024 stud
  plus bas qu'aux images clés, pendant 1/60 s. Roblox fait exactement la même chose avec les mêmes images
  (−0,0343), et −0,0335 avec les 18 clés publiées. La cause : la botte pivote vite sur sa pointe, et
  l'interpolation linéaire entre deux poses espacées de 1/30 s coupe l'arc par la corde. Le mouvement continu
  d'`anim.py` ne descend pas sous −0,0104. Ce n'est donc pas un défaut de la mise à jour Blender : les clés
  linéaires réduisent le creux (−0,049 avec les clés de Bézier de la première passe). Le critère « au-dessus de
  −0,03 » de la première passe portait sur les images clés, où la course est à −0,0104. Même mécanisme, en plus
  faible, au début de l'atterrissage (−0,022 entre les images 2 et 3, −0,020 avec les clés publiées). Pour
  supprimer ces creux, il faudrait des clés plus serrées dans `anim.py` (échantillonnage ou `reduce_keys`), pas
  dans la scène.
- **Accroupi : la correction supprime aussi un bond du pied droit.** Dans l'ancienne version, la cuisse droite
  est presque horizontale. Sa composante verticale oscille entre 0,177 et 0,218 avec la respiration, autour du
  seuil de 0,2 en dessous duquel `_snap` ne corrige plus la hauteur de la botte. Sur la moitié des images, la
  botte restait enfoncée de 0,07 stud. Sur l'autre moitié, `_snap` la remontait en faisant glisser la cuisse de
  0,37 stud dans le torse, ce qui déplaçait aussi le pied de 0,36 stud vers l'arrière. Le pied passait d'un état
  à l'autre aux images 21, 49 et 74 : sur le maillage, le centre de la semelle saute de 0,36 stud entre les
  images 73 et 74. `--verifier` ne pouvait pas le voir, car il ne contrôle que les rotations. Avec le tibia
  vertical, la botte est déjà au sol et `_snap` n'a plus rien à corriger : le glissement reste à 0, et le pied
  bouge d'au plus 0,003 stud entre deux images.
- **Accroupi : il reste une petite dérive de la botte droite.** Avec le tibia vertical, la cible du pied est un
  peu hors de portée : la jambe est trop courte d'au plus 0,054 stud, et le glissement est bloqué à 0. Le pied
  dérive donc lentement de 0,05 stud d'avant en arrière au rythme de la respiration (boucle de 3 s). Il se
  soulève aussi d'au plus 0,007 stud, sans jamais descendre sous −0,004. La botte gauche, inchangée, dérive de
  0,03 stud. Si on veut un pied parfaitement immobile, on peut rapprocher un peu `CROUCH_FEET['Right']` dans
  `anim.py`.

## Fichiers

| Fichier | Taille | SHA-256 |
|---|---:|---|
| `dist/Survivant_R6_Anime_corrige.blend` (nouveau) | 43 741 761 octets | `c44e7a218c062c1264f8f06a06c996a0a486be9131d62412eaba9c82a5dde966` |
| `dist/Survivant_R6_Anime.blend` (inchangé) | 43 743 860 octets | `45ae156a17dc30338aeb2738989f5ac94b3c4a38940857faefe520b222e32d49` |

Les deux scènes sont au format Blender 5.2 (en-tête `BLENDER17-01v0502`), compressées (zstd). `src/`, `roblox/`
et `outils/` ne sont pas modifiés. L'environnement Python n'est pas dans le dépôt, et la branche
`blender-corrige` (première passe) n'a pas été touchée.
