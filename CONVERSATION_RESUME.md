# Survivant R6 articulé et anatomique : conversation résumée (pour reprendre en local)

Ce fichier résume toute la conversation (plusieurs sessions Claude dans le cloud, octobre 2026)
qui a produit ce projet. Il sert de contexte à une nouvelle session Claude sur votre ordinateur
(Claude Code lancé dans ce dossier, ou Claude Desktop avec ce fichier joint). Langue de travail :
français.

---

## 1. Ce que l'utilisateur a demandé (dans l'ordre)

1. « Test », puis : un personnage **Roblox R6** avec une **anatomie ultra réaliste à
   l'intérieur** (os, organes, articulations, vaisseaux, nerfs), importable dans Roblox Studio
   (Blender autorisé). Puis « continue » ×2.
2. « Je ne peux pas télécharger le modèle, il faut que je puisse le télécharger et qu'il soit
   vraiment très ressemblant à un modèle R6 (comme dans les screens) » → page de téléchargement
   (.zip) et peau R6 « noob » fidèle.
3. « N'utilise pas le noob au final, fais un perso format R6 qui ressemble à un **survivant**,
   avec les organes à l'intérieur ; ajoute des **animations compatibles Roblox : course, marche,
   marche accroupie, allongée** ; modifie sur mon PC en direct (Roblox Studio et Blender
   ouverts) ; animations de haute qualité. » → impossible d'agir sur le PC depuis le cloud :
   livré sous forme de fichiers + scripts.
4. « Pour avoir des animations plus stylées et jolies, **divise les jambes et bras en deux**
   (coudes et genoux). Et fais en sorte que **tu puisses le modifier directement sur Roblox**. »
   → rig « R6 articulé » à 10 pièces, 15 animations refaites, module `SurvivantEditeur` +
   instructions pour le **serveur MCP de Roblox Studio** (Claude sur le PC de l'utilisateur).
5. « Donne-moi la conversation compressée pour que je puisse l'utiliser en local » → ce fichier.

Remarque : une session cloud ne peut pas atteindre Studio. L'édition en direct demande une
session Claude sur l'ordinateur de l'utilisateur (Claude Desktop, ou Claude Code / `claude
remote-control` lancé dans ce dossier) avec le serveur MCP de Studio activé.

---

## 2. État livré (fin de la dernière session)

- **Page de téléchargement + visionneuse 3D** (artifact privé) :
  https://claude.ai/artifact/EsApa5xRWeiXekKc73xRDD
  Visionneuse three.js (tenue opaque / radiographie / sans tenue, calques anatomiques, clic =
  nom de la pièce, 15 animations sur un sol en damier qui défile à la vitesse du clip) et
  3 packs : **Roblox** (FBX léger 834 k triangles + scripts + docs, 28,5 Mo), **Ultra** (FBX
  1,6 M triangles, 53,6 Mo), **Blender** (`Survivant_R6_Anime.blend`, 43,6 Mo). Les zips sont
  servis en morceaux base64 de 12 Mo (`dl/<pack>.<sha8>.<i>.txt`, index `dl/packs.json`).
- **224 MeshParts** : 211 pièces anatomiques + 13 pièces de tenue `Survivor_*`.
- **Scripts Roblox** testés hors ligne : 6 470 vérifications, 0 échec (émulation de l'API
  Roblox). **Jamais lancés dans un vrai Roblox Studio.**
- Rendus dans `apercus/` (16 images, dont `survivant_course.png`, `radiographie_course.png`,
  `survivant_accroupi.png`). La **vidéo** `apercus/animations_survivant.mp4` (13 séquences,
  ~35 s, dont grimper avec échelle, assis sur un siège, torche en main) était encore en rendu
  à la fin de la session cloud (environ 8 s par image) ; la version présente dans le dossier peut
  être l'ancienne (rig R6 à 6 pièces).

---

## 3. Le personnage

**Tenue survivant** (`src/survivor.py`) : bonnet en laine rouge, cheveux, visage marqué (barbe,
pansement, égratignure), veste olive ouverte sur t-shirt, sangles et sac à dos (sac de couchage,
gourde), manches retroussées, bandage, mitaines, montre, jean usé rapiécé (genou troué), bottes
lacées. Couleurs cuites en couleurs de sommets (Roblox les multiplie par `MeshPart.Color` :
blanc = couleurs d'origine, on peut seulement assombrir/teinter).

**Anatomie** (régions = pièces du rig) : squelette complet (crâne avec calotte amovible,
32 dents, 24 vertèbres, côtes, bassin, mains et pieds os par os), cartilages (épaule, coude,
tête radiale, poignet, hanche, genou, plateau tibial, cheville), ménisques, ligaments et tendons,
organes (cerveau en lobes, cœur, poumons 5 lobes, arbre bronchique, foie, estomac, intestins,
reins…), vaisseaux et nerfs jusqu'aux doigts. Pas de muscles squelettiques.

**Rig « R6 articulé »** (`src/rig_spec.py`, source unique de vérité) :
- Look R6 (torse 2×2×1, tête 2×1×1, membres 1 stud) mais 10 pièces : `Torso`, `Head`,
  `RightUpperArm`, `RightLowerArm`, `LeftUpperArm`, `LeftLowerArm`, `RightUpperLeg`,
  `RightLowerLeg`, `LeftUpperLeg`, `LeftLowerLeg` (+ `HumanoidRootPart`).
- Motor6D : `RootJoint` (dans HRP), `Neck` (dans Torso) avec les rotations C0/C1 du R6 ;
  `RightShoulder`, `RightElbow`, `LeftShoulder`, `LeftElbow`, `RightHip`, `RightKnee`, `LeftHip`,
  `LeftKnee` (rotations identité, rangés dans leur Part1 comme en R15).
- Pivots (espace du rig, X = droite du perso, Y = haut, Z = arrière, il regarde vers -Z, centre
  HRP = origine, sol à Y = -3) : épaules (±1.2, 0.66, 0), coudes (±1.5, 0, 0), hanches
  (±0.5, -1, 0), genoux (±0.5, -1.95, 0). Centres : bras haut (±1.5, 0.5, 0), avant-bras
  (±1.5, -0.5, 0), cuisse (±0.5, -1.475, 0) taille (1, 0.95, 1), jambe (±0.5, -2.475, 0) taille
  (1, 1.05, 1). Plans de coupe Blender Z = 3.0 (coude) et 1.05 (genou).
- Humanoid **R15**, `HipHeight` 2 ; main invisible `RightHand` (soudure `RightWrist`,
  `RightGripAttachment` rotation (1,0,0, 0,0,1, 0,-1,0)) pour les outils.
- Repères : Blender = (-x, z, y+3) ; Roblox = (-X, Z-3, Y). `Motor6D.Transform` d'une pose :
  T = C0⁻¹ · W_part0⁻¹ · W_part1 · C1.
- Angles : flexion du coude = rotation +X (la main va vers l'avant), flexion du genou = -X.
  Dans `SurvivantEditeur` : coude plié `rx > 0`, genou plié `rx < 0`, bras levé devant `rx > 0`,
  bras droit écarté `rz > 0` (gauche `rz < 0`), torse penché / tête baissée `rx < 0`.
- Tenue : manches et jambes du jean en deux morceaux avec charnière demi-cylindrique autour de
  l'axe du coude/genou (rien ne s'ouvre en pliant). Anatomie : os rangés dans leur segment ;
  ligaments, vaisseaux, nerfs, tendons qui traversent l'articulation coupés au plan de coupe
  (`segments.py`, `meshops.clip_plane`).

---

## 4. Les 15 animations (`src/anim.py`)

| Clé | Nom Roblox | Durée | Boucle | Priorité | Vitesse prévue |
|---|---|---:|:---:|---|---:|
| idle | Survivant_Repos | 4,0 s | oui | Idle | — |
| walk | Survivant_Marche | 0,70 s | oui | Movement | 6 |
| run | Survivant_Course | 0,56 s | oui | Movement | 16 |
| crouch | Survivant_Accroupi | 3,0 s | oui | Idle | — |
| crouchwalk | Survivant_MarcheAccroupie | 1,0 s | oui | Movement | 2,6 |
| prone | Survivant_Allonge | 4,0 s | oui | Idle | — |
| crawl | Survivant_Ramper | 1,4 s | oui | Movement | 1,0 |
| jump | Survivant_Saut | 0,50 s | non | Action | — |
| fall | Survivant_Chute | 0,90 s | oui | Action | — |
| land | Survivant_Atterrissage | 0,42 s | non | Action | — |
| liedown | Survivant_SAllonger | 0,95 s | non | Action | — |
| getup | Survivant_SeRelever | 1,15 s | non | Action | — |
| climb | Survivant_Grimper | 0,45 s | oui | Movement | 5 |
| sit | Survivant_Assis | 3,0 s | oui | Core | — |
| tool | Survivant_Outil | 4,0 s | oui | Action | — (bras droit seul, superposé) |

300 images clés au total (échantillonnage 30 i/s puis simplification, écart < 0,5°).
Techniques :
- **Marche / course / marche accroupie** : classe `Gait` à appuis plantés : la botte roule
  talon (0,53) puis pointe (0,59) sur un point de contact qui recule exactement à la vitesse du
  clip ; profil de genou + léger « télescopage » de la cuisse dans le torse (caché par la veste)
  résolus image par image (`solve_rocker`), IK 2 os pour la marche accroupie
  (`mode='ik'`). Paramètres : WALK (T 0,7, v 6, duty 0,58, genou appui 7–11°, pic 62°),
  RUN (0,56, 16, 0,31, 20–22°, pic 112°), CROUCH_WALK (1,0, 2,6, 0,62, pic 118°, buste 24°).
- **Allongé / ramper** : poses des bras résolues hors ligne (moindres carrés) pour que les
  avant-bras restent au sol ; jambes « en grenouille ».
- **Saut** : bras en V (bras levé : abduction négative = vers l'extérieur). **Chute** : bras
  levés et écartés, avant-bras pliés vers le haut (twist -58), qui battent. **Atterrissage** :
  part de la pose de chute, genoux qui amortissent.
- **Grimper** : mains et bottes sur des barreaux espacés de 1,125 stud qui descendent à
  5 studs/s (`rung_path`, `solve_rung`, `CLIMB_Z = -0.95`), main droite avec botte gauche.
- **Assis** : cuisses horizontales, mains sur les genoux. **Outil** : bras droit levé devant.
- Contrôle visuel fait sur le vrai maillage (planches `anim_preview.py`) pour les 15 clips.

---

## 5. Scripts Roblox (`roblox/`)

- `AnatomieR6_Setup.lua` (≈ 90 Ko, généré depuis `.template.lua`) : à coller dans la barre de
  commande après *Importer 3D* du FBX. Retrouve échelle/orientation grâce aux marqueurs
  `REF_A..REF_D` (Blender (0,0,3), (0,0,5.2), (1.5,0,3), (0,-0.6,3)), construit le rig
  articulé, habille avec `Survivor_*` (dossier `Peau`), range et soude chaque pièce dans
  `Anatomie.<pièce>`. Un ancien rig R6 du même nom est renommé `Anatomie_R6_ancien`. Réglages :
  `SKIN_MODE` ("maillage"/"blocs"), `SKIN_TRANSPARENCY`, `SKIN_COLORS`, `USE_VERTEX_COLORS`,
  `ANCHOR_ROOT`, `RENDER_FIDELITY_PRECISE`, `CATEGORY`…
- `SurvivantR6_Animations.lua` (≈ 180 Ko) : crée les 15 `KeyframeSequence`
  (`ReplicatedStorage.SurvivantAnimations` + copies `ServerStorage.RBX_ANIMSAVES.Anatomie_R6`),
  `AnimationIds`, le LocalScript `Animate`, `StarterPlayer.StarterCharacter` (R15, HipHeight 2),
  le groupe de collision `SurvivantPosture` et le module `ServerStorage.SurvivantEditeur`
  (+ `Donnees`). Poses imbriquées selon la hiérarchie du rig ; clip partiel `tool` : ancêtres
  non animés avec `Weight = 0`. Options : `CREATE_STARTER_CHARACTER`, `KEEP_SURVIVOR_LOOK`,
  `KEEP_EDITED_ANIMATIONS`, `INSTALL_EDITOR`.
- `Animate` (contrôleur) : Maj = courir, C = accroupi, X = allongé/ramper, Espace = sauter,
  R = radiographie ; grimper, assis, outil automatiques ; boutons tactiles ; vitesses
  `CONFIG.VITESSE = { marche = 6, course = 16, accroupi = 3, allonge = 1.5 }`, chaque clip
  accéléré/ralenti dans la même proportion (×0,45 à ×1,8). Plus d'animations R6 de Roblox en
  secours ; jeu publié : clips sans identifiant ignorés avec un avertissement.
- `AnatomieR6_Outils.lua` : 9 outils (tenue, radiographie, calotte, catégories, squelette,
  tout réafficher, compter, StarterCharacter R15, blocs/maillage).
- `SurvivantEditeur.module.lua` (source, intégré à l'installateur) : `E.aide()`, `E.info()`,
  `E.radiographie(actif, t)`, `E.pose(nom, rx, ry, rz [, x, y, z])` ou `E.pose({...})`,
  `E.reinitialiserPose()`, `E.apercu(clé, temps)`, `E.lireAnimation(clé)`,
  `E.ecrireAnimation(clé, a)`, `E.modifierPose(clé, temps, pièce, {rx=…, relatif=true})`,
  `E.restaurerAnimation(clé)`, `E.importerDepuisEditeur(clé)`, `E.vitesses({...})`,
  `E.majPersonnageJouable()`. Pose = `{x, y, z, rx, ry, rz}` (studs, degrés) relative à la pièce
  parente autour du pivot. Écritures annulables (ChangeHistoryService), animation marquée
  `Survivant_Modifiee`, identifiant publié vidé (gardé dans `AncienIdentifiant`).
- Tests : `cd roblox && luaurun test/rbx_mock.lua test/test_setup.lua` (6 470 vérifications).
  `luaurun` = petit interpréteur Luau maison exposant `readfile` et `loadstring` (source dans
  `outils/luaurun/main.cpp`, à compiler avec les sources de Luau 0.740 ; voir le Makefile).
  `test/expected_anims.lua` est régénéré par `make_lua.py` (angles calculés en Python).

**Non vérifié dans un vrai Studio** : (1) le clip partiel `tool` suppose que Roblox ignore les
poses de poids 0 (sinon le corps se fige quand un outil est tenu) ; (2) Humanoid R15 sur ce corps
sans UpperTorso (hauteur via HipHeight 2, `RequiresNeck` et mise à l'échelle auto désactivés,
prise d'outil par `RightHand`) ; (3) aperçus en mode édition (`E.apercu` a un repli qui pose les
Motor6D directement) ; (4) taille de l'installateur (180 Ko) dans la barre de commande.

---

## 6. Modifier le personnage avec Claude dans Studio (serveur MCP officiel)

Source : https://create.roblox.com/docs/en-us/studio/mcp.md
1. Studio > **Assistant** > **…** > **Manage MCP Servers** > **Enable Studio as MCP server**.
2. **Assistant Settings** > **MCP Servers** > **Quick connect** > activer Claude Desktop ou
   Claude Code (sinon config manuelle : Windows `{"mcpServers":{"Roblox_Studio":{"command":
   "cmd.exe","args":["/c","%LOCALAPPDATA%\\Roblox\\mcp.bat"]}}}` ; macOS
   `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP`). Le serveur est local (stdio).
3. Outils : `list_roblox_studios` (donne le `studio_id` exigé par tous les appels),
   `execute_luau`, `search_game_tree`, `inspect_instance`, `script_read`, `multi_edit`,
   `get_studio_state`, `start_stop_play`, `get_console_output`, `screen_capture`,
   `character_navigation`, `user_keyboard_input`… Un client MCP peut lire et modifier les places
   ouvertes.
4. Démarrage type : `local E = require(game:GetService("ServerStorage").SurvivantEditeur)
   print(E.aide()) print(E.info())`. Travailler en mode édition, passer par `SurvivantEditeur`,
   vérifier chaque changement avec `E.apercu` + `screen_capture`. Détails : `CLAUDE.md`.

---

## 7. Projet et régénération (`src/`)

Environnement utilisé : Python 3.13, `bpy` 5.2.2 (Blender en module), numpy 2.5, scipy 1.18,
scikit-image 0.26, pyfqmr 0.5, pillow, playwright (tests de la visionneuse), ffmpeg (vidéo).

```bash
cd src
python build.py -j 4                 # 224 pièces -> build/parts/*.npz + build/manifest.json (long)
python export.py                     # dist/Anatomie_R6_{Ultra,Leger}.{fbx,glb} + marqueurs REF_*
python export_viewer.py              # viewer/anatomie.glb + parts.json
python export_blend_rig.py           # dist/Survivant_R6_Anime.blend (armature Rig_R6_Articule, 15 actions)
python make_lua.py                   # roblox/*.lua générés + test/expected_anims.lua + viewer/anims.json
python make_parts_list.py            # LISTE_DES_PIECES.md
python render_final.py               # apercus/*.png (dont poses animées)
python render_anim_video.py          # apercus/animations_survivant.mp4 (long : ~2 h sur 4 cœurs)
python make_packs.py                 # dist/*.zip + viewer/dl/ (morceaux base64) + anatomie_glb.txt
python anim_preview.py OUT.png walk,run --frames 6   # planche de contrôle d'animations
```

Fichiers clés : `rig_spec.py` (rig), `anim.py` (animations, IK, exports), `survivor.py` (tenue,
charnières), `arms.py` / `legs.py` (+ `segments.py`, découpe coude/genou), `head.py`,
`torso_*.py`, `skin.py`, `maps.py`, `landmarks.py`, `meshops.py` (`clip_plane`…), `sdf.py`,
`parts.py`, `build.py`, `anim_preview.py`, `blend_lib.py`, `SPEC.md`. Les dossiers `build/` et
`dist/` (gros) ne sont pas dans l'archive de contexte : les FBX et le .blend sont dans les packs
de la page ; `build/parts` se régénère avec `build.py`.

**Après toute modification de `anim.py` ou `rig_spec.py` : relancer `make_lua.py`, les tests
Luau, puis `export_blend_rig.py` et `make_packs.py`.** Les modifications faites dans Studio avec
`SurvivantEditeur` ne sont pas reportées dans `src/`.

---

## 8. Leçons et pièges rencontrés

- Maillages SDF retournés (normales vers l'intérieur) : corrigé dans `sdf.mesh_sdf` /
  `meshops.orient_outward` ; les MeshParts Roblox sont à une seule face.
- Cycles avec `use_persistent_data` perdait les couleurs de sommets (bonnet noir) : désactivé.
- Pieds qui glissaient (×4 à ×7 dans la toute première version) : appuis plantés + vitesses du
  contrôleur calées sur les clips.
- IK des jambes : choisir la bonne branche (genou vers l'avant), passage talon → pointe, ordre de
  rotation des jambes Rx·Rz·Ry (pas de blocage de cardan accroupi), décomposition 3D exacte avec
  torsion de la cuisse.
- Bras levés : avec l'ordre Rz·Rx, une abduction positive ramène la main vers la tête ; utiliser
  une abduction négative (ou un twist) pour écarter les bras levés.
- Objets Blender joints : appliquer les transformations après `join` avant de leur imposer une
  `matrix_world`.
- Page artifact : 64 Mo max par publication, 256 Mo par version, 16 Mo par fichier texte ;
  publier en étapes en remplaçant pack par pack (index `packs.json` intermédiaire) pour que les
  téléchargements marchent toujours.

## 9. Pistes possibles ensuite

- Premier vrai test dans Studio (import, scripts, Play, outil tenu, grimper sur un TrussPart,
  s'asseoir sur un Seat), avec Claude connecté via MCP qui lit l'Output.
- Publier les animations (Save to Roblox) et remplir `AnimationIds` pour un jeu publié.
- Retouches d'animations via `SurvivantEditeur`, ou dans `anim.py` puis régénération.

---

## 10. Session locale du 23/10/2026 : premier vrai test dans Roblox Studio

Faite avec Claude Desktop sur le PC de l'utilisateur (Studio connecté par MCP), à partir du pack Ultra
(FBX importé avec *Importer 3D* : échelle 0,01 retrouvée par les marqueurs, écart 0,0000 stud, 224 pièces,
aucun avertissement). Les scripts ont été envoyés à Studio sans copier-coller : petit serveur HTTP local
(`python -m http.server --bind 127.0.0.1`) et `HttpService:GetAsync` en activant `HttpEnabled` le temps
de la lecture, puis `loadstring`. La reconstruction complète (`build.py`) n'a pas été lancée : trop de
mémoire pour ce PC (15 Go, ~400 Mo libres) ; `make_lua.py` reproduit les scripts à l'octet près.

**Défauts trouvés et corrigés**
- Contrôleur jamais lancé : au démarrage, Roblox remplace l'`Animate` rangé dans le StarterCharacter par son
  `Animate` R15 par défaut (danses, emotes) dont les animations tordent ce rig (mêmes noms de pièces que
  le R15). Le contrôleur est maintenant installé dans `StarterPlayer.StarterCharacterScripts` (installateur,
  `E.majPersonnageJouable`, outil 8).
- `Players.LoadCharacterAppearance` n'existe pas (erreur avalée par un `pcall`) : c'est
  `StarterPlayer.LoadCharacterAppearance`. Sans ça, l'avatar du joueur s'appliquait au survivant.
- `anim.py`, `_angles_from_points` : jambe presque tendue avec 2° d'hyperextension, la torsion de la cuisse
  tombait sur ±180° (botte retournée) dans le repos, l'atterrissage, s'allonger et se relever. La torsion
  reste dans ±90° (hyperextension minime à la place) ; pieds du repos et de l'atterrissage un peu avancés
  (`STAND_FEET`, `LAND_FEET`) : genoux souples, plus d'hyperextension.
- Grimper : l'IK des bras (abduction calculée en Rz·Rx) est singulière bras tendu devant, le haut du bras
  faisait un tour sur lui-même avec deux sauts de 64 à 77° par image. Nouvelle `arm_world_pole` : rotation
  construite directement avec un vecteur de coude (`CLIMB_ELBOW`, coudes vers le bas et l'extérieur).
- Bottes sous le sol en fin de pas (pas de cheville : la pointe descend quand le tibia avance) : -0,19 stud
  en marche, -0,17 en course, -0,31 en marche accroupie. `Gait._lift_profile` : la cuisse glisse dans le
  torse (jusqu'à `SWING_SLIDE`) puis le genou se lève pour le reste, profil élargi et lissé.
- Assis : le `SeatWeld` de Roblox met le centre du HumanoidRootPart 0,5 stud au-dessus du siège pour ce rig
  (C0 (0, 0.5, 0), C1 (0, -0.5, 0)) ; cuisses dans le siège. `SEAT_LIFT = 1` dans `sit()`.
- Saut : une animation non bouclée qui finit s'efface d'elle-même en 0,3 s et `Stop()` n'y peut plus rien
  (pose du saut mêlée à l'atterrissage). Le saut est chargé en boucle (`HOLD_AT_END`), sa dernière pose est
  tenue, la chute prend le relais 0,15 s après la fin du clip ; l'atterrissage s'arrête si le personnage
  repart en l'air.
- Course : Maj gauche basculait aussi le Shift Lock (même priorité). Action de course en priorité haute
  (`CONFIG.COURSE_PRIORITAIRE`), le Shift Lock reste sur Maj droite.
- `SurvivantEditeur` en mode édition : poser `Motor6D.Transform` ne déplace pas les pièces ;
  `Animator:StepAnimations(0)` les replace (`refresh`). `E.apercu` rejetait à tort la pose de l'Animator
  (tolérance 1e-3, l'Animator interpole à 0,1° près) et la première lecture d'un clip se charge en
  arrière-plan (attente de `track.Length > 0`).

**Vérifié dans Studio (Play)** : marche 6 studs/s (clip x1,00), course 16 (x1,00), accroupi 3 (x1,15),
ramper 1,5 (x1,50), s'allonger / se relever (groupe de collision), saut / chute / atterrissage, grimper sur
un TrussPart (x0,82 à 4,2 studs/s), assis sur un Seat, outil tenu (clip partiel : le bras droit se lève,
les jambes continuent de marcher, poses de poids 0 bien ignorées), radiographie (squelette complet visible).
Aucune erreur des scripts du survivant dans la console.

**Contrôle des animations** (`python anim.py` et un balayage à 60 i/s) : plus aucun saut de rotation hors
des gestes rapides voulus (jambes en course, bras au saut, main qui attrape le barreau), aucune botte sous le
sol pendant un appui ou un balancement.

**Scène Blender** : les 15 actions de `Survivant_R6_Anime.blend` viennent du même `anim.py`. Le script
`outils/maj_actions_blend.py` les recalcule sur l'armature existante (maillages et pistes NLA conservés).

**Suite (même jour)** : première passe cloud (branche `blender-corrige`, `RAPPORT_BLENDER.md`) : actions
recalculées, contrôles conformes, maillages et NLA identiques. Elle a relevé deux points, corrigés ensuite sur
`main` : dans l'accroupi sur place, la botte droite (pied avant écarté) roulait sur son bord intérieur et entrait
de 0,07 stud dans le sol (tibia penché vers la hanche ; `solve_flat(..., upright=True)` pour ce pied, comme la
marche accroupie) ; les clés Blender étaient en Bézier (`keyframe_insert` de Blender 5.2 ignore la préférence),
`maj_actions_blend.py` force maintenant l'interpolation linéaire. Deuxième passe cloud : branche
`blender-corrige-v2` (`TACHE_CLOUD.md`).
