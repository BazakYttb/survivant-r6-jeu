# Tâche pour la session cloud : le monstre de tendons noirs, modélisé dans Blender

L'utilisateur veut, pour son jeu Roblox de survie, un monstre **ultra détaillé et terrifiant**, fidèle à l'image
`monstre/reference.webp`, et il veut qu'il soit **fait dans Blender** pour un résultat « incroyable ». Il ne veut pas
lancer Blender sur son PC (trop peu de mémoire) : toute la modélisation, les rendus et l'export se font ici.
Une session locale fera ensuite l'import dans Roblox Studio, le montage du rig et les tests en jeu.

## Ce que montre la référence

- Humanoïde très grand et décharné, voûté : dos rond, tête basse projetée vers l'avant, genoux un peu fléchis.
- Tout le corps est fait de **tendons / fibres noirs, mouillés et brillants**, enroulés et tressés autour d'une
  ossature ; faisceaux torsadés d'épaisseurs variées, trous par endroits (on voit à travers, surtout au torse et
  à la taille), côtes devinées, épaules hérissées de fibres.
- **Bras extrêmement longs** qui pendent jusqu'aux genoux, avant-bras décharnés, **longs doigts griffus**.
- Jambes longues et fines ; les **pieds se défont en racines** qui s'étalent sur le sol.
- Partout, des **filaments fins qui pendent et gouttent** (bras, torse, bassin, menton), comme du goudron.
- **Tête lisse, allongée, sans yeux**, inclinée vers le bas, avec une **fente de gueule** (crocs fins et une faible
  lueur orangée à l'intérieur).
- Couleurs : noir profond, reflets spéculaires gris clair, nuances brunes très sombres. Fond clair, brumeux.

## Point de départ (prototype, à dépasser largement)

`monstre/prototype/gen.py` est un premier jet en numpy (sans Blender), aperçu dans Studio
(`monstre/prototype/studio_*.jpg`). Il donne des **proportions et un découpage de rig qui conviennent**
(dictionnaire `J`, repère de la tête `FH`/`UH`, `rig_spec()`) : monstre d'environ 11 studs de haut dans sa posture
voûtée, 37 pièces rigides. Mais le rendu est trop régulier : cage thoracique en ressort, bras en colonnes de câbles
droits, crâne en œuf lisse sans détail. Reprends ce qui sert (ossature, pivots, idées de faisceaux, gouttes,
racines, griffes, crocs), et fais beaucoup mieux avec les outils de Blender.

## Moyens dans Blender (suggestions, pas des obligations)

- Environnement : `uv venv -p 3.13` puis `uv pip install "bpy==5.2.*"` (marche dans ce conteneur, roue d'environ
  384 Mio). Rendus avec **Cycles en CPU** (pas de GPU ici ; EEVEE probablement indisponible sans affichage).
- Tendons : courbes Blender (splines avec rayon par point pour l'effilement, bevel rond) générées en Python le long
  des os : faisceaux torsadés et irréguliers, fibres qui se croisent en surface, tendons qui **se décollent du corps
  en arcs** puis y reviennent (trous traversants), côtes irrégulières et en partie cassées, épines le long de la
  colonne, filaments qui pendent avec une goutte au bout, racines aux pieds. Geometry Nodes (Curve to Mesh, rayon
  bruité) est une bonne alternative.
- Détail organique : modificateurs Displace (textures de bruit), Subdivision là où ça aide, Remesh/voxel pour une
  masse sombre au cœur du torse si besoin ; crâne : sphère déformée sculptée par déplacement, tendons plaqués
  dessus (Shrinkwrap), orbites creuses, fente de gueule, crocs en aiguille, mâchoire séparée entrouverte.
- Matière : Principled BSDF noir (couleurs de sommets ou procédurales), rugosité 0,15 à 0,35 (mouillé), nuances
  brun-rouge très sombres dans les creux ; intérieur de la gueule rouge sombre ; crocs gris-jaune terne ; griffes
  noires à pointe plus claire.
- Itère sur le rendu en comparant avec la référence (silhouette, densité des fibres, gouttes, tête, mains).

## Contraintes Roblox (impératives)

- **Au plus 20 000 triangles par maillage** (limite de l'import 3D de Roblox) : plusieurs maillages par pièce si
  besoin. Total visé : 150 000 à 300 000 triangles.
- **Rig rigide, sur mesure** (pas de R15) : chaque maillage appartient à **une seule pièce** du rig et bouge en bloc
  avec elle (comme le prototype). Pièces : bassin, 3 segments de colonne, cou, tête, mâchoire, haut de bras,
  avant-bras, main, doigts (2 segments chacun) et pouce, cuisse, tibia, pied. Les maillages sont **coupés aux
  articulations avec un recouvrement** pour qu'aucun trou ne s'ouvre quand l'articulation plie. Nom des objets :
  `MON_<Pièce>_<n>` (ex. `MON_Forearm_R_1`), pièces nommées comme dans `rig_spec()` du prototype.
- Faces simple face, normales vers l'extérieur, pas de trou sur les surfaces visibles.
- Couleurs de sommets exportées (Roblox les importe) ; textures PBR (couleur, normale, rugosité, 1024 px max,
  avec UV) seulement si le temps le permet : l'import les transforme en SurfaceAppearance.
- **Repère et échelle** : 1 unité Blender = 1 stud ; documente la correspondance d'axes. Ajoute 4 **marqueurs**
  (petits cubes de 0,05) nommés `REF_A`, `REF_B`, `REF_C`, `REF_D` aux positions Roblox (studs, Y vers le haut, le
  monstre regarde vers −Z, sa droite est +X) A = (0, 5, 0), B = (0, 7, 0), C = (1,5, 5, 0), D = (0, 5, −1), et un
  marqueur `GLOW_MOUTH` (petit cube) là où doit se trouver la lueur de la gueule : un script Studio s'en servira pour
  retrouver échelle et orientation quelle que soit l'interprétation des unités à l'import.
- `monstre/export/rig.json` : pour chaque pièce, son parent, le pivot de son articulation et le nom de
  l'articulation, en coordonnées Roblox (studs), plus la liste des maillages de chaque pièce.

## Livrables (branche `monstre-blender`, partie de `main`)

- `monstre/blender/Monstre.blend` (scène complète, compressée).
- `monstre/export/Monstre.glb` (et `Monstre.fbx` si possible), avec les marqueurs ; `monstre/export/rig.json`.
- `monstre/rendus/*.png` : rendus Cycles à 1024 px sur fond clair et brumeux comme la référence : trois quarts face
  (comme la référence), profil, dos, gros plan de la tête et de la gueule, gros plan d'une main.
- `monstre/RAPPORT_MONSTRE.md` : versions (Blender/bpy), méthode, liste des maillages avec leurs triangles et leur
  pièce, rig, marqueurs, réglages d'export, comparaison avec la référence, limites connues.
- Ne pas modifier `src/`, `roblox/`, `dist/` ni le reste du dépôt ; pas d'environnement Python dans le dépôt ;
  pas de pull request.

Fini quand la branche `monstre-blender` est poussée avec ces fichiers, que chaque maillage respecte la limite de
triangles, et que les rendus sont terrifiants et fidèles à la référence.
