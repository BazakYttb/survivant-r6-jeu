# Rapport : actions Blender corrigées

Session cloud du 23/10/2026, tâche décrite dans `TACHE_CLOUD.md`.

**Résultat.** `dist/Survivant_R6_Anime_corrige.blend` contient les 15 actions recalculées depuis `src/anim.py`
(commit `c6bf54c`) sur l'armature `Rig_R6_Articule` existante. Les deux contrôles donnent exactement les valeurs
du tableau de `TACHE_CLOUD.md`. Maillages, tenue, anatomie, armature et pistes NLA sont identiques à ceux de la
scène d'origine, qui n'a pas été modifiée.

## Environnement

| | |
|---|---|
| Blender | 5.2.3 LTS en module Python : `bpy` 5.2.3 (compilé le 22/10/2026, `e13b728c6880`, branche `blender-v5.2-release`) |
| Installation | `uv venv -p 3.13` puis `uv pip install "bpy==5.2.*"`, dans un environnement virtuel hors du dépôt (pas besoin de `blender -b`) |
| Python | 3.13.17, numpy 2.5.4 |
| Machine | conteneur Linux x86_64, 4 cœurs, 15 Go de mémoire |

## Commandes et durées

| Étape | Commande | Durée |
|---|---|---:|
| Installation | `uv pip install "bpy==5.2.*"` (roue de 384 Mio) | 2 min 10 s |
| Contrôle avant | `python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime.blend` | 4,2 s |
| Mise à jour | `python outils/maj_actions_blend.py dist/Survivant_R6_Anime.blend src dist/Survivant_R6_Anime_corrige.blend` | 27,8 s |
| Contrôle après | `python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime_corrige.blend` | 3,4 s |
| Contrôles complémentaires | scripts de la session (voir plus bas) | 35 à 50 s par scène |

De l'installation à la fin des contrôles : 14 minutes, analyse comprise.

Sortie de la mise à jour :

```
00:00.637  blend            | Read blend: "/home/user/survivant-r6-jeu/dist/Survivant_R6_Anime.blend"
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
00:00.539  blend            | Read blend: "/home/user/survivant-r6-jeu/dist/Survivant_R6_Anime.blend"
15 actions Survivant_*
Survivant_Accroupi           images 1-91 ; saut max   1.5° (Head, image 55) ; rotation max 105.8° (RightUpperLeg, image 30)
Survivant_Allonge            images 1-121 ; saut max   2.0° (Head, image 121) ; rotation max 136.0° (RightUpperArm, image 20)
Survivant_Assis              images 1-91 ; saut max   1.0° (Head, image 42) ; rotation max  90.0° (RightLowerLeg, image 1)
Survivant_Atterrissage       images 1-14 ; saut max 179.9° (LeftUpperLeg, image 11) ; rotation max 179.9° (LeftUpperLeg, image 1)
Survivant_Chute              images 1-28 ; saut max   2.8° (RightLowerArm, image 3) ; rotation max 123.0° (LeftUpperArm, image 23)
Survivant_Course             images 1-18 ; saut max  30.6° (RightLowerLeg, image 9) ; rotation max 111.9° (RightLowerLeg, image 11)
Survivant_Grimper            images 1-15 ; saut max 112.3° (LeftUpperArm, image 5) ; rotation max 174.5° (RightUpperArm, image 8)
Survivant_Marche             images 1-22 ; saut max  25.4° (LeftLowerLeg, image 5) ; rotation max  61.9° (LeftLowerLeg, image 6)
Survivant_MarcheAccroupie    images 1-31 ; saut max  10.6° (LeftLowerLeg, image 13) ; rotation max 126.1° (RightLowerLeg, image 13)
Survivant_Outil              images 1-121 ; saut max 180.0° (LeftUpperLeg, image 13) ; rotation max 180.0° (LeftUpperLeg, image 103)
Survivant_Ramper             images 1-43 ; saut max   7.2° (LeftUpperLeg, image 6) ; rotation max 145.2° (RightUpperArm, image 1)
Survivant_Repos              images 1-121 ; saut max 180.0° (LeftUpperLeg, image 13) ; rotation max 180.0° (LeftUpperLeg, image 103)
Survivant_SAllonger          images 1-29 ; saut max  41.6° (LeftUpperLeg, image 5) ; rotation max 179.9° (LeftUpperLeg, image 1)
Survivant_Saut               images 1-16 ; saut max  54.7° (RightUpperArm, image 4) ; rotation max 152.4° (RightUpperArm, image 6)
Survivant_SeRelever          images 1-35 ; saut max  29.7° (LeftUpperLeg, image 31) ; rotation max 178.3° (LeftUpperLeg, image 35)
```

## Contrôle après : `dist/Survivant_R6_Anime_corrige.blend`

```
00:00.505  blend            | Read blend: "/home/user/survivant-r6-jeu/dist/Survivant_R6_Anime_corrige.blend"
15 actions Survivant_*
Survivant_Accroupi           images 1-91 ; saut max   1.5° (Head, image 55) ; rotation max 105.8° (RightUpperLeg, image 30)
Survivant_Allonge            images 1-121 ; saut max   2.0° (Head, image 121) ; rotation max 136.0° (RightUpperArm, image 20)
Survivant_Assis              images 1-91 ; saut max   1.0° (Head, image 42) ; rotation max  90.0° (RightLowerLeg, image 1)
Survivant_Atterrissage       images 1-14 ; saut max  29.9° (RightUpperArm, image 3) ; rotation max  99.9° (RightUpperArm, image 1)
Survivant_Chute              images 1-28 ; saut max   2.8° (RightLowerArm, image 3) ; rotation max 123.0° (LeftUpperArm, image 23)
Survivant_Course             images 1-18 ; saut max  30.6° (RightLowerLeg, image 9) ; rotation max 111.9° (RightLowerLeg, image 11)
Survivant_Grimper            images 1-15 ; saut max  54.4° (RightUpperArm, image 12) ; rotation max 147.7° (RightLowerArm, image 11)
Survivant_Marche             images 1-22 ; saut max  25.4° (LeftLowerLeg, image 5) ; rotation max  61.9° (LeftLowerLeg, image 6)
Survivant_MarcheAccroupie    images 1-31 ; saut max  12.9° (LeftLowerLeg, image 15) ; rotation max 126.1° (RightLowerLeg, image 13)
Survivant_Outil              images 1-121 ; saut max   1.8° (Head, image 35) ; rotation max  73.9° (RightUpperArm, image 16)
Survivant_Ramper             images 1-43 ; saut max   7.2° (LeftUpperLeg, image 6) ; rotation max 145.2° (RightUpperArm, image 1)
Survivant_Repos              images 1-121 ; saut max   1.8° (Head, image 35) ; rotation max  19.0° (Head, image 49)
Survivant_SAllonger          images 1-29 ; saut max  20.3° (RightLowerLeg, image 5) ; rotation max 144.1° (RightUpperArm, image 26)
Survivant_Saut               images 1-16 ; saut max  54.7° (RightUpperArm, image 4) ; rotation max 152.4° (RightUpperArm, image 6)
Survivant_SeRelever          images 1-35 ; saut max  20.3° (LeftLowerLeg, image 22) ; rotation max 138.5° (RightUpperArm, image 3)
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
| Survivant_Saut | 54,7° | 54,7° | 54,7° | 54,7° |
| Survivant_Course | 30,6° | 30,6° | 30,6° | 30,6° |
| Survivant_Marche | 25,4° | 25,4° | 25,4° | 25,4° |
| les 6 autres | sous 13° | 1,0 à 10,6° | sous 13° | 1,0 à 12,9° (Marche accroupie) |

La cuisse gauche retournée (180°) n'apparaît plus nulle part : rotation maximale du Repos 180,0° → 19,0° (la tête).

## Contrôles complémentaires

Le contrôle du script ne regarde que les rotations aux images entières. Trois scripts de la session (hors dépôt,
lecture seule) ont aussi été lancés sur les deux scènes :

1. **Rien d'autre n'a changé.** L'empreinte SHA-256 des 227 objets (224 maillages, 817 585 sommets ; noms,
   parentage aux os, transformations, sommets, faces, matériaux, attributs) et des 11 os au repos est identique
   dans les deux scènes. Les 15 pistes NLA (muettes) pointent toujours vers leurs actions, sur l'emplacement
   `OBRig_R6_Articule` qui porte les 77 nouvelles courbes (11 os, position et quaternion), avec les mêmes plages
   d'images. Action active `Survivant_Marche`, scène à 30 i/s, images 1 à 22, comme avant.
2. **Les actions sont celles d'`anim.py`.** À chaque image de chaque action, les poses évaluées par Blender
   diffèrent de celles calculées par `anim.py` d'au plus 8·10⁻⁷ stud et 3·10⁻⁵° (précision des flottants).
   Dans l'ancienne scène, 5 actions étaient déjà identiques (Accroupi, Allongé, Ramper, Saut, Chute) ; les
   10 autres changent (de 0,08 à 1,4 stud, jusqu'à 180°).
3. **Plus de tour parasite entre deux images.** Dans l'ancienne scène, deux clés voisines avaient des quaternions
   de signes opposés dans Repos et Outil (produit scalaire −1,000) et dans Grimper (−0,955) : à la demi-image,
   l'os faisait presque un tour complet (jusqu'à 359,7° d'écart avec le plus court chemin entre ses deux
   voisines). Nouvelle scène : produit scalaire minimal +0,889, écart à la demi-image au plus 0,94° (Grimper),
   0,21° ailleurs.
4. **Bottes.** Point le plus bas des maillages `Survivor_RightLowerLeg` et `Survivor_LeftLowerLeg` aux images
   clés, sol à z = 0 (au repos : −0,004, l'épaisseur de la semelle) :

   | Action | avant | après | `anim.py` à 240 i/s |
   |---|---:|---:|---:|
   | Marche | −0,195 | −0,004 | −0,005 |
   | Course | −0,175 | −0,010 | −0,010 |
   | Marche accroupie | −0,310 | −0,019 | −0,022 |
   | Repos, Outil | −0,002 (−0,106 entre deux images) | −0,002 | −0,002 |
   | Atterrissage | −0,001 | −0,001 | −0,001 |

   Les valeurs « avant » retrouvent celles relevées dans `CONVERSATION_RESUME.md` (−0,19 / −0,17 / −0,31 stud).
5. **Assis.** Point le plus bas des cuisses (`Survivor_*UpperLeg`) : 1,393 → 2,393 ; bottes : 0,813 → 1,813.
   Le corps est relevé d'un stud (`SEAT_LIFT`). Avec le dessus du siège à z = 2,5 (centre du HumanoidRootPart
   0,5 stud au-dessus), les cuisses entraient de 1,1 stud dans le siège ; elles n'y entrent plus que de 0,1 stud
   côté genou, car la cuisse penche d'environ 5° vers l'avant (`anim.py` donne 2,386 avec ses volumes simplifiés).

## Remarques

- **Interpolation des clés : Bézier**, comme dans la scène d'origine. Le script règle la préférence `LINEAR`, mais
  `keyframe_insert` de Blender 5.2 ne la suit pas (vérifié : préférence à `LINEAR`, clé créée en `BEZIER`). Sans
  effet à 30 i/s, puisque chaque image est une clé : Blender affiche exactement les poses d'`anim.py`. Entre deux
  images (lecture à une autre cadence, flou de mouvement), la courbe s'écarte un peu du mouvement : jusqu'à
  −0,045 stud pour les bottes dans la course.
- **Saut, Chute, Grimper, Assis** : hauteur des bottes sans signification (en l'air, sur l'échelle ou sur le
  siège ; la racine ne se déplace pas dans la scène). Saut (−0,195 à l'image 2) et Chute (−0,141) sont
  identiques avant et après.
- **Accroupi** : −0,072, identique avant et après. C'est le bord intérieur de la botte droite : le pied droit est
  écarté (`CROUCH_FEET`) et le tibia penche d'environ 11° vers l'intérieur, sans cheville pour compenser
  (−0,076 avec les volumes simplifiés d'`anim.py`). Ce défaut est dans `anim.py`, donc aussi dans Roblox ; il
  n'était pas dans les corrections demandées.

## Fichiers

| Fichier | Taille | SHA-256 |
|---|---:|---|
| `dist/Survivant_R6_Anime_corrige.blend` (nouveau) | 43 743 726 octets | `afb87613d956d0e456bbb1f90c2055eabba17b85d2bf201c8c17836ba3e9efb8` |
| `dist/Survivant_R6_Anime.blend` (inchangé) | 43 743 860 octets | `45ae156a17dc30338aeb2738989f5ac94b3c4a38940857faefe520b222e32d49` |

Les deux scènes sont au format Blender 5.2 (en-tête `BLENDER17-01v0502`), compressées (zstd). `src/`, `roblox/`
et `outils/` ne sont pas modifiés, et l'environnement Python n'est pas dans le dépôt.
