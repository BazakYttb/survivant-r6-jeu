# Le monstre : consignes pour Claude (Roblox Studio via MCP, et régénération)

Ce dossier contient le monstre du jeu de survie : modèle Blender (`blender/`), exports (`export/Monstre.fbx`,
`Monstre.glb`, `rig.json`), rendus (`rendus/`), et le paquet Roblox (`roblox/` : kit, scripts, données d'animation,
sons, tests). Le rapport complet est `RAPPORT_MONSTRE.md`. Réponds en français.

L'utilisateur veut que le monstre tourne dans **sa** place Roblox, avec ses 8 mises à mort. Une session dans le cloud
ne peut pas atteindre Studio : c'est à toi, sur son ordinateur, avec le serveur MCP de Roblox Studio
(`list_roblox_studios`, `execute_luau`, `get_studio_state`, `start_stop_play`, `screen_capture`, `get_console_output`,
`character_navigation`, `user_keyboard_input`…), de faire l'installation et les essais. Voir aussi le `CLAUDE.md` à la
racine (survivant, connexion MCP).

## 1. Où en est la place ?

```lua
local O = game:GetService("ServerStorage"):FindFirstChild("MonstreOutils")
if O then print(require(O).verifier()) else print("monstre non installé") end
```

## 2. Installer

L'utilisateur fait deux gestes dans Studio (pas d'outil MCP pour les fichiers locaux) :

1. *Importer 3D* : `monstre/export/Monstre.fbx` (réglages par défaut) ;
2. *Workspace > clic droit > Insérer depuis un fichier* : `monstre/roblox/Monstre_Kit.rbxmx`.

Puis toi, en mode édition : `execute_luau` avec `return require(workspace.Monstre_Kit.Installateur)()` et lis la
sortie. Si l'insertion du kit pose problème, construis-le depuis les sources sans copier-coller (méthode déjà utilisée
pour le survivant) : serveur local `python -m http.server 8000 --bind 127.0.0.1` lancé dans `monstre/roblox/src`,
`HttpService.HttpEnabled = true` le temps de la lecture, un `Folder` « Monstre_Kit » dans le Workspace avec les
ModuleScripts `Installateur`, `MonstreAnim`, `MonstreConfig`, `MonstreDonnees`, `MonstreOutils`, le Script
`MonstreServeur` (désactivé) et le LocalScript `MonstreClient`, dont tu poses `.Source` avec
`HttpService:GetAsync("http://127.0.0.1:8000/<fichier>")` ; remets `HttpEnabled` comme avant, puis lance
l'installateur. Il garde un `MonstreConfig` déjà présent (option `garderConfig = false` pour le remplacer).

Les victimes animées sont les personnages au rig du survivant R6 articulé (`StarterPlayer.StarterCharacter`, installé
par les scripts du survivant).

## 3. Essayer

1. `start_stop_play` (test), puis `execute_luau` côté serveur :
   ```lua
   local O = require(game.ServerStorage.MonstreOutils)
   O.pause(true) ; O.victimeTest() ; O.miseAMort("morsure_cou")
   ```
   Clés : `morsure_cou`, `morsure_repetee`, `devoration`, `attaque_ventre`, `trainee`, `extraction`, `frenesie`,
   `contamination`. Sans victime d'essai, elle vise le joueur le plus proche (sa caméra est alors scénarisée).
2. `screen_capture` pendant la mise à mort (les phases durent 2,2 à 5,4 s ; dévoration et traînée ont une phase de
   traînée de 6 à 10 s), `get_console_output` pour les erreurs (`[Monstre]`, `[MonstreClient]`).
3. Arrête le test avant toute modification durable.

Points à surveiller au premier essai (jamais vérifiés dans un vrai Studio, seulement en émulation) : position et
orientation après l'import (le monstre doit être debout, pieds au sol), victime bien collée aux mains et à la gueule,
`Motor6D.Transform` écrit dans `PreSimulation` qui passe bien par-dessus les animations du survivant, gabarits de sang
`SANG_*` transparents (`SurfaceAppearance.AlphaMode = Transparency` posé par l'installateur), particules (image de la
goutte lue dans `SurfaceAppearance.ColorMap` ; sinon fumée intégrée), recherche de chemin avec un agent de 2,4 de
rayon et 8 de haut, `StarterPlayer.LoadCharacterAppearance` (voir le CLAUDE.md racine).

## 4. Régler

Tout est dans `ReplicatedStorage.Monstre.MonstreConfig` (ModuleScript, à modifier en mode édition) : vitesses,
perception, portée, poids des mises à mort, destinations des traînées (étiquettes `MonstreTaniere`, `MonstreSortie`,
`MonstrePatrouille`), sang, caméra, infection, sons. Les sons (`monstre/roblox/sons/*.ogg`) doivent être importés par
l'utilisateur (gestionnaire de ressources) ; une fois les identifiants connus, écris-les dans la table `SONS` de
`MonstreConfig` (édition de sa source, puis vérifie en jouant un son).

## 5. Modifier les animations (projet Python, pas dans Studio)

Les animations sont calculées en Python (`blender/scripts/mon_anim.py` cadre et IK, `mon_clips.py` déplacement,
`mon_morts.py` mises à mort appariées avec la victime au rig du survivant, `../src/anim.py`), puis
`blender/scripts/exporter_roblox.py` régénère `roblox/src/MonstreDonnees.lua`, `roblox/Monstre_Kit.rbxmx` et les
données de test. Ensuite :

```bash
cd monstre/roblox && luaurun test/rbx_mock.lua test/test_monstre.lua    # 220 vérifications
```

(`luaurun` : voir `outils/luaurun`, à compiler avec les sources de Luau 0.740.) Dans Studio, il suffit alors de
réinsérer le kit et de relancer l'installateur (le rig existant est gardé, scripts et données remplacés, réglages
gardés). Aperçus rapides des poses : `python blender/scripts/apercu_rapide.py sortie.png k_cou,k_ventre 8`
(maillage allégé `proxy.npz` produit par `dump_proxy.py`) ; rendus Cycles : `apercu_anim.py`.

## 6. Prudence

- Mode édition pour tout changement durable ; demande avant de supprimer ou remplacer des éléments de l'utilisateur
  (modèle du monstre, StarterCharacter, scripts à lui).
- Contenu violent : rappelle le questionnaire de maturité de Roblox (voir `roblox/LISEZMOI.md`).
