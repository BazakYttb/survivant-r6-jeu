# Tâche pour la session cloud : le monstre sans sang (textures recuites)

## Pourquoi

Le 24/10/2026, l'import 3D de `monstre/export/Monstre.fbx` (branche `monstre-blender`) dans Roblox Studio a été
**refusé par la modération de Roblox**, qui a aussi **averti le compte** de l'utilisateur : la texture `MAT_Ring1_L_1`
(peau tachée de sang) a été jugée contraire aux règles (« Roblox does not permit violent content and gore, including
excessive use of blood in images or videos »). Tout ce qui est importé est téléversé sur son compte et modéré ; un
nouvel avertissement pourrait mener à une suspension. Il faut donc une version **sans aucun sang ni rien qui y
ressemble**, en gardant la peau réaliste.

## À faire

Partir de la branche `monstre-blender` (scripts dans `monstre/blender/scripts/`, voir son `README.md` et
`monstre/RAPPORT_MONSTRE.md`). Blender 5.2 en module : `uv venv -p 3.13` puis `uv pip install "bpy==5.2.*"`.

1. **Peau sans sang ni blessure** : recuire les textures de jeu avec `SANG=non` (`cuire_textures.py`). Dans
   `mon_skin.py`, retirer aussi tout ce qui peut passer pour du sang ou une plaie : les **griffures rouge sombre** et
   les **ecchymoses** ; garder les rougeurs aux articulations très discrètes (pas de rouge vif). Garder le reste
   (vraies textures de peau, marbrures, veines, crasse, terre sur les pieds, rides et plis). Crocs et griffes propres
   (ivoire sale, gris), intérieur de la gueule **très sombre** (brun-noir, presque pas de rouge) : la lueur orangée est
   ajoutée dans Roblox par une pièce Neon.
2. **Export sans gabarits de sang** : `exporter.py` **sans** le 3e argument (pas de `SANG_*` dans `Monstre.fbx` /
   `Monstre.glb`), puis `verifier_export.py`. Mêmes noms de maillages, marqueurs `REF_*` et `GLOW_MOUTH`, `rig.json`
   inchangé.
3. **Contrôle automatique** : pour chaque texture de couleur exportée, proportion de pixels « rouge sang »
   (par exemple R > 0,3, R > 2 × G et R > 2 × B en sRGB) ; elle doit être nulle ou quasi nulle partout. Mets le
   tableau dans le rapport, avec la liste de toutes les images intégrées aux exports.
4. **Rendus de contrôle** (Cycles, comme avant) : trois quarts face, tête et gueule, une main ; regarde-les et
   assure-toi qu'aucune zone ne fait penser à du sang ou à une plaie. Ne refais pas les GIF ni les planches.
5. Ne touche pas aux animations, au paquet `monstre/roblox/` (la session locale coupe le sang du kit dans Studio) ni
   à `src/`, `roblox/`, `dist/`.

## Livrables

Sur une nouvelle branche nommée exactement `monstre-sans-sang`, partie de `monstre-blender` : `monstre/export/`
(`Monstre.fbx`, `Monstre.glb`, `rig.json` ; le repli `Monstre_couleurs_sommets.glb` peut rester tel quel),
`monstre/blender/Monstre.blend` à jour, les scripts modifiés, les rendus de contrôle dans `monstre/rendus/sans_sang/`,
et `monstre/RAPPORT_SANS_SANG.md` (commandes, durée, tableau des pixels rouges, liste des images, ce qui a changé).
Commit et push, pas de pull request.

Fini quand la branche `monstre-sans-sang` est poussée, que les exports ne contiennent ni gabarit `SANG_*` ni texture
avec du rouge sang, et que les rendus ne montrent ni sang ni plaie.
