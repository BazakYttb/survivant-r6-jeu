# Survivant R6 articulé : consignes pour Claude (Roblox Studio via MCP)

Ce dossier contient un personnage Roblox au look R6 dont les bras et les jambes sont coupés au
coude et au genou (10 pièces), habillé en survivant, avec une anatomie complète à l'intérieur et
15 animations. L'utilisateur veut que **tu le modifies directement dans Roblox Studio** : poses,
animations, vitesses, radiographie, tests en jeu. Tu le fais avec les outils du **serveur MCP de
Roblox Studio** (serveur `Roblox_Studio` : `list_roblox_studios`, `execute_luau`,
`search_game_tree`, `inspect_instance`, `screen_capture`, `get_studio_state`, `start_stop_play`,
`get_console_output`, `script_read`, `multi_edit`, `character_navigation`, `user_keyboard_input`…).
Réponds en français.

## 1. Connexion

- Chaque outil demande un `studio_id` : appelle d'abord `list_roblox_studios`. S'il y a plusieurs
  Studio ouverts, compare les noms et les identifiants de place, et demande en cas de doute.
- Si les outils Roblox Studio sont absents, guide l'utilisateur : Studio > **Assistant** > menu
  **…** > **Manage MCP Servers** > **Enable Studio as MCP server**, puis **Assistant Settings** >
  **MCP Servers** > **Quick connect** > activer Claude Desktop ou Claude Code, et redémarrer le
  client (configuration manuelle : voir README, section 3). Le serveur tourne en local : Claude
  doit être sur le même ordinateur que Studio.

## 2. Vérifier l'installation, lire le guide

```lua
local m = game:GetService("ServerStorage"):FindFirstChild("SurvivantEditeur")
if not m then return "SurvivantEditeur absent" end
local E = require(m)
print(E.aide())   -- guide complet : conventions, arbre des articulations, animations, fonctions
print(E.info())   -- état actuel : rig, poses, animations, vitesses
```

Lis `E.aide()` une fois par session : c'est la référence (format des poses, sens des angles,
fonctions). Si le module ou `Workspace.Anatomie_R6` manque : l'utilisateur doit importer
`Anatomie_R6_Leger.fbx` (ou `Ultra`) avec *Importer 3D* (tu ne peux pas le faire à sa place), puis
exécuter `AnatomieR6_Setup.lua` et `SurvivantR6_Animations.lua` (fichiers de ce dossier). Ces
scripts sont gros (environ 90 et 180 Ko) : demande-lui plutôt de les coller dans la barre de
commande (ouvrir le fichier, Ctrl+A, Ctrl+C, coller, Entrée), puis vérifie le résultat.

## 3. Où sont les choses

| Chemin | Contenu |
|---|---|
| `Workspace.Anatomie_R6` | rig d'exposition (HumanoidRootPart ancré) : `Torso`, `Head`, `RightUpperArm`, `RightLowerArm`, `LeftUpperArm`, `LeftLowerArm`, `RightUpperLeg`, `RightLowerLeg`, `LeftUpperLeg`, `LeftLowerLeg` ; Motor6D `RootJoint` (dans HumanoidRootPart), `Neck` (dans Torso), `RightShoulder`, `RightElbow`, `LeftShoulder`, `LeftElbow`, `RightHip`, `RightKnee`, `LeftHip`, `LeftKnee` (chacun dans sa pièce enfant : `RightElbow` dans `RightLowerArm`…) ; `RightHand` invisible (soudure `RightWrist`, `RightGripAttachment`) pour les outils ; dossiers `Peau` (tenue `Survivor_*`) et `Anatomie.<pièce>` (os, organes, vaisseaux…) ; LocalScript `Animate` (copie de référence, inactive dans le Workspace) |
| `StarterPlayer.StarterCharacter` | personnage jouable (copie désancrée du rig, sans script `Animate`) |
| `StarterPlayer.StarterCharacterScripts.Animate` | le contrôleur qui tourne en jeu (un `Animate` rangé dans le StarterCharacter serait remplacé au lancement par l'`Animate` R15 de Roblox, qui tord le rig) |
| `ReplicatedStorage.SurvivantAnimations` | les 15 `KeyframeSequence` `Survivant_*` jouées dans Studio, et `AnimationIds` (identifiants publiés) |
| `ServerStorage.RBX_ANIMSAVES.Anatomie_R6` | copies pour l'Éditeur d'animation de Roblox |
| `ServerStorage.SurvivantEditeur` (+ `Donnees`) | le module d'édition et les animations d'origine |

Clés des animations : `idle`, `walk`, `run`, `crouch`, `crouchwalk`, `prone`, `crawl`, `jump`,
`fall`, `land`, `liedown`, `getup`, `climb`, `sit`, `tool` (`tool` n'anime que le bras droit et se
superpose aux autres). Contrôleur : en haut du script `Animate`, `CONFIG` (vitesses `VITESSE`,
touches, caméra, radiographie) ; `E.vitesses()` lit et règle les vitesses dans les deux copies.

## 4. Façon de travailler

1. **Mode édition** : vérifie `get_studio_state` ; arrête le test (`start_stop_play`) avant de
   modifier quoi que ce soit de durable (ce qui est changé en jeu est perdu à l'arrêt).
2. **Passe par `SurvivantEditeur`** (`E.pose`, `E.apercu`, `E.modifierPose`, `E.lireAnimation` /
   `E.ecrireAnimation`, `E.restaurerAnimation`…) plutôt que d'écrire directement dans les
   `KeyframeSequence` ou les Motor6D : il garde les boucles fermées (`E.modifierPose`), marque
   les animations modifiées, vide les identifiants publiés devenus faux et rend chaque écriture
   annulable (Ctrl+Z). Avec `E.ecrireAnimation`, fais finir une boucle sur sa pose de départ.
3. **Montre le résultat** : après une modification, `E.apercu(clé, temps)` puis `screen_capture`
   (caméra sur le personnage), et décris ce qui a changé. Avance par petites touches et garde des
   angles naturels (coude 0 à 150, genou -150 à 0, épaule `rx` -60 à 180).
4. **Teste en jeu** si c'est utile : `start_stop_play`, puis `character_navigation` ou
   `user_keyboard_input` (Maj = courir, C = accroupi, X = allongé, R = radiographie, Espace =
   sauter), `screen_capture`, `get_console_output` ; arrête le test ensuite. Pour juger un glissement
   de pieds, la vitesse du personnage doit être celle de l'animation (`E.info()`).
5. **Remettre en état** : `E.restaurerAnimation(clé)` (version d'origine), `E.reinitialiserPose()`
   (rig au repos). Après un changement des pièces du rig ou de la tenue (pas des animations) :
   `E.majPersonnageJouable()`.
6. **Demande avant** toute opération destructrice (supprimer ou remplacer le rig, le
   StarterCharacter, des scripts de l'utilisateur) et ne touche pas au reste de sa place.
7. **Jeu publié** : une animation modifiée doit être republiée (clic droit sur la
   `KeyframeSequence` > *Save to Roblox…*) et son identifiant collé dans `AnimationIds` : rappelle-le.

## 5. Bon à savoir

- Les couleurs de la tenue et de l'anatomie sont des couleurs de sommets ; `MeshPart.Color` les
  **multiplie** (blanc = couleurs d'origine) : on peut assombrir ou teinter, pas éclaircir ni
  changer franchement de couleur. Pour une vraie nouvelle couleur, il faut modifier le générateur
  (`src/survivor.py`, projet complet) et réexporter le FBX.
- Transparence de la tenue : `E.radiographie(true, 0.7)` / `E.radiographie(false)` (le bonnet et
  le sac sont masqués en radiographie).
- Repère du personnage au repos : X = sa droite, Y = le haut, Z = l'arrière (il regarde vers -Z).
  Une pose `{x, y, z, rx, ry, rz}` est relative à la pièce parente, autour du pivot de
  l'articulation, rotation `CFrame.Angles(math.rad(rx), math.rad(ry), math.rad(rz))`.
- Le projet complet (pas seulement le pack) contient `src/` : modèle et animations procéduraux en
  Python/Blender (`anim.py`, `rig_spec.py`, `survivor.py`…) et `make_lua.py` qui régénère les
  scripts. Les modifications faites dans Studio avec `SurvivantEditeur` n'y sont pas reportées.

## 6. Contexte complet du projet

Historique résumé de la conversation qui a créé ce projet (demandes, rig, animations, scripts,
régénération, pièges) : @CONVERSATION_RESUME.md
