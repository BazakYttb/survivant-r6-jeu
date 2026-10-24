# Vraies textures de peau (motifs raccordables)

Ces images sont tirées d'un **vrai scan 3D de tête humaine** et servent de détail à la peau du monstre (grain de
couleur, pores, ridules et plis, brillance). Elles sont posées en projection triplanaire sur la peau haute définition,
puis cuites dans les textures de jeu (`cuire_textures.py`).

| Fichier | Contenu | Zone du scan |
|---|---|---|
| `peau_couleur_1.png` | grain de couleur (rapport à la teinte locale, moyenne 0,5), 512 px | haut du crâne |
| `peau_couleur_2.png` | grain de couleur avec grains de beauté, 512 px | cou à gauche et nuque à droite |
| `peau_relief_pores_1.png` | relief fin (pores, ridules, plis), 16 bits, 1024 px | cou, des deux côtés |
| `peau_relief_pores_2.png` | relief fin (pores, ridules), 16 bits, 1024 px | côté du crâne, au-dessus de l'oreille |
| `peau_brillance.png` | détail de brillance (pores mats, plaques grasses), 512 px | mêmes zones que la couleur |

Fabrication (`../scripts/textures_reelles.py`) : zones de peau propre seulement (ni barbe, ni yeux, ni oreilles),
passe-haut (on garde le grain, pas l'éclairage ni la forme du visage), puis raccord sans couture (mélange avec la copie
décalée d'une demi-période, pondération qui garde le contraste).

## Source et licence

- **« Infinite, 3D Head Scan » de Lee Perry-Smith**, Infinite-Realities (http://www.ir-ltd.net/), d'après un travail
  sur www.triplegangers.com, sous licence **Creative Commons Attribution 3.0 Unported (CC BY 3.0)**.
  Fichiers d'origine : `Map-COL.jpg`, `Map-SPEC.jpg`, `Infinite-Level_02_Disp_NoSmoothUV-4096.jpg`, distribués avec
  three.js (`examples/models/gltf/LeePerrySmith/`, https://github.com/mrdoob/three.js).
- Ces motifs, et les textures du monstre qui les contiennent, sont des adaptations : **créditer l'auteur** dans le jeu,
  par exemple : « Détail de peau : Infinite, 3D Head Scan by Lee Perry-Smith (Infinite-Realities), CC BY 3.0 ».

Pour régénérer : récupérer les trois fichiers ci-dessus dans un dossier, puis
`python -I textures_reelles.py dossier_du_scan dossier_de_sortie`.
