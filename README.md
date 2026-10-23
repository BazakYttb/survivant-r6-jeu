# Survivant R6 articulé, anatomique et animé pour Roblox Studio

Un personnage **au format R6** habillé en **survivant** : bonnet en laine, veste de terrain ouverte
sur un t-shirt, sangles et sac à dos (sac de couchage, gourde), manches retroussées, bandage,
mitaines, jean usé rapiécé, bottes lacées, visage marqué (barbe de trois jours, pansement,
égratignure).

**R6 articulé** : la silhouette et les proportions restent celles du R6 (torse 2×2×1, tête 2×1×1,
membres de 1 stud de large), mais **chaque bras et chaque jambe est coupé en deux au coude et au
genou**. Les animations plient donc les coudes et les genoux, comme un R15, tout en gardant le
look R6. Les manches et le jean ont une articulation arrondie (charnière) : rien ne s'ouvre
quand le membre se plie.

**À l'intérieur**, une anatomie complète et détaillée, visible en mode radiographie :

- **Squelette complet** : crâne (calotte amovible, base, massif facial), mandibule, 32 dents, os
  hyoïde, 24 vertèbres (C1 à L5), sacrum, coccyx, 24 côtes, sternum, clavicules, omoplates, os
  coxaux, et pour chaque membre humérus, radius, ulna, 8 os du carpe, métacarpiens, phalanges,
  fémur, rotule, tibia, fibula, 7 os du tarse, métatarsiens, phalanges, sésamoïdes.
- **Articulations** : disques intervertébraux, cartilages articulaires (épaule, coude et tête
  radiale, poignet, hanche, genou et plateau tibial, cheville), bourrelets glénoïdiens et
  cotyloïdiens, ménisques, symphyse pubienne, articulations sacro-iliaques et
  sterno-claviculaires, cartilages costaux.
- **Ligaments et tendons** : croisés et collatéraux du genou, ligament rotulien, tendon
  quadricipital, tendon d'Achille, ligaments de la cheville, fascia plantaire, membrane
  interosseuse, collatéraux du coude, ligament annulaire, rétinaculum des fléchisseurs.
- **Organes** : cerveau (circonvolutions et sillons, lobes séparés), cervelet, tronc cérébral,
  yeux et muscles oculaires, langue, cœur (cavités, graisse épicardique, artères coronaires),
  poumons en 5 lobes, trachée, arbre bronchique, larynx, thyroïde, œsophage, diaphragme, foie,
  vésicule et voies biliaires, estomac, duodénum, pancréas, rate, reins, surrénales, uretères,
  vessie, intestin grêle, côlon (haustrations, bandelettes, appendices graisseux), appendice, rectum.
- **Vaisseaux et nerfs** : aorte et toutes ses grandes branches, veines caves, système porte,
  vaisseaux des membres jusqu'aux doigts, moelle épinière, queue de cheval, racines spinales,
  chaînes sympathiques, plexus brachial et lombo-sacré, nerfs sciatique, fémoral, médian, ulnaire,
  radial, vague, phrénique, etc.

Chaque os appartient à sa pièce (humérus au bras, radius, ulna et main à l'avant-bras, fémur et
rotule à la cuisse, tibia, fibula et pied à la jambe) ; les vaisseaux, nerfs et ligaments qui
traversent le coude ou le genou sont coupés en deux au niveau de l'articulation, chaque moitié
suivant sa pièce.

**224 MeshParts** : 211 pièces anatomiques + 13 pièces de tenue (`Survivor_*`, dont le bonnet et le
sac, masqués en radiographie). Toutes les couleurs sont « peintes » dans les maillages (couleurs de
sommets). Détail de chaque pièce : `LISTE_DES_PIECES.md`.

**15 animations** faites pour ce rig, compatibles avec Roblox (KeyframeSequence, Motor6D), avec un
contrôleur prêt à jouer : repos, marche, course, accroupi, marche accroupie, allongé, ramper, saut,
chute, atterrissage, s'allonger, se relever, **grimper**, **assis** et **outil en main**.

**Modifiable par Claude directement dans Roblox Studio** grâce au serveur MCP intégré à Studio et
au module `SurvivantEditeur` (voir la section 3).

Aperçus : dossier `apercus/` (`survivant_*.png`, `radiographie_*.png`, anatomie seule, et la vidéo
`animations_survivant.mp4`).

---

## Contenu

| Dossier / fichier | Rôle |
|---|---|
| `dist/Anatomie_R6_Ultra.fbx` (ou `.glb`) | Modèle complet, 1,6 M triangles. Pour une scène d'exposition. |
| `dist/Anatomie_R6_Leger.fbx` (ou `.glb`) | Même modèle, anatomie simplifiée (834 000 triangles). Pour un jeu. |
| `dist/Survivant_R6_Anime.blend` | Scène Blender animée : armature R6 articulée, une action par animation. |
| `roblox/AnatomieR6_Setup.lua` | 1) Script à coller dans la barre de commande : construit le rig articulé du survivant. |
| `roblox/SurvivantR6_Animations.lua` | 2) Script à coller ensuite : crée les 15 animations, le contrôleur, le personnage jouable et l'éditeur `SurvivantEditeur`. |
| `roblox/AnatomieR6_Outils.lua` | Petits outils : radiographie, calotte du crâne, catégories, StarterCharacter… |
| `CLAUDE.md` | Consignes pour Claude (Claude Desktop ou Claude Code sur votre ordinateur) : comment modifier le personnage dans Studio. |
| `LISTE_DES_PIECES.md` | Les 224 pièces avec leur description. |
| `src/` | Générateur Python/Blender (pour modifier ou régénérer le modèle et les animations). |

Dans les packs `.zip`, tous les fichiers sont à la racine du dossier (sans `dist/` ni `roblox/`).
Packs `.zip` à télécharger : **Pack Roblox** (FBX léger), **Pack Ultra** (FBX complet), chacun avec
les trois scripts `.lua`, ce README, `CLAUDE.md`, la liste des pièces et `INSTALLATION_RAPIDE.txt` ;
**Pack Blender** (la scène `.blend` animée et la documentation).

---

## 1. Installer le personnage (5 minutes)

1. **Importer** : Studio > onglet *Accueil* ou *Avatar* > **Importer 3D** (*File > Import 3D*),
   choisissez `Anatomie_R6_Leger.fbx` (ou `Ultra`, ou les `.glb`).
2. Dans la fenêtre d'import :
   - laissez **Import Only As Model** coché ;
   - **ne cochez pas** *Merge Meshes* ;
   - vérifiez que **Ignore Vertex Colors** n'est **pas** coché (sinon les couleurs disparaissent) ;
   - l'unité (*Scale Unit*), *World Forward* / *World Up* et l'endroit d'insertion n'ont **aucune
     importance** : le script retrouve l'échelle et l'orientation grâce aux 4 petits marqueurs
     `REF_A`…`REF_D` contenus dans le fichier ;
   - si Studio propose un type de rig, choisissez *No Rig*.
   Cliquez sur *Import* et attendez la fin du téléversement des maillages.
3. Ouvrez la **barre de commande** (*Affichage > Barre de commande* / *View > Command Bar*).
4. Ouvrez `AnatomieR6_Setup.lua`, copiez **tout** le fichier, collez-le dans la barre de commande,
   Entrée.
5. Le modèle **`Anatomie_R6`** apparaît dans le Workspace : rig articulé complet
   (HumanoidRootPart, `Torso`, `Head`, `RightUpperArm`, `RightLowerArm`, `LeftUpperArm`,
   `LeftLowerArm`, `RightUpperLeg`, `RightLowerLeg`, `LeftUpperLeg`, `LeftLowerLeg`, Humanoid),
   habillé de la tenue du survivant (dossier `Anatomie_R6 > Peau`, opaque), et chaque pièce
   anatomique rangée dans `Anatomie_R6 > Anatomie > <pièce>` et soudée à sa pièce. Un résumé
   s'affiche dans la fenêtre *Output*. **Ctrl+Z** annule tout.

| Motor6D | Relie | Pivot |
|---|---|---|
| `RootJoint` | HumanoidRootPart → Torso | centre du torse (comme en R6) |
| `Neck` | Torso → Head | base du cou (comme en R6) |
| `RightShoulder` / `LeftShoulder` | Torso → bras (haut) | tête de l'humérus |
| `RightElbow` / `LeftElbow` | bras → avant-bras | axe du coude |
| `RightHip` / `LeftHip` | Torso → cuisse | hanche |
| `RightKnee` / `LeftKnee` | cuisse → jambe | axe du genou |

L'Humanoid est de type **R15** (`HipHeight` = 2) : c'est ce que Roblox attend d'un rig dont les
membres ont plusieurs pièces. Une main invisible `RightHand` (avec `RightGripAttachment`) est soudée
à l'avant-bras droit pour tenir les outils (*Tools*).

## 2. Installer les animations

1. Copiez **tout** `SurvivantR6_Animations.lua`, collez-le dans la barre de commande, Entrée.
2. Le script crée :
   - les 15 animations (`KeyframeSequence`) dans `ReplicatedStorage > SurvivantAnimations`, et une
     copie pour l'éditeur d'animation (`ServerStorage > RBX_ANIMSAVES`) ;
   - le dossier `SurvivantAnimations > AnimationIds` (identifiants des animations publiées) ;
   - le LocalScript **`Animate`** (contrôleur) dans le rig (copie de référence) et dans
     `StarterPlayer.StarterCharacterScripts` (celui qui tourne en jeu : rangé dans le StarterCharacter, il
     serait remplacé au lancement par l'`Animate` R15 par défaut de Roblox) ;
   - le personnage jouable `StarterPlayer > StarterCharacter` (copie désancrée du rig) ;
   - le groupe de collision `SurvivantPosture` (allongé, le corps ne soulève pas le personnage) ;
   - le module **`ServerStorage > SurvivantEditeur`** (édition par Claude ou par la barre de
     commande, voir la section 3).
3. Bouton **Jouer** (*Play*) :

| Touche | Action |
|---|---|
| Déplacement (ZQSD / WASD, flèches, manette) | marcher |
| **Maj** gauche (maintenir) | courir |
| **C** | s'accroupir / se relever (marche accroupie en se déplaçant) |
| **X** | s'allonger / se relever (ramper en se déplaçant) |
| **Espace** | sauter (saut, chute, atterrissage) |
| **R** | radiographie : tenue translucide, bonnet et sac masqués, anatomie visible |
| (automatique) | grimper (échelle, *TrussPart*), assis (*Seat*), outil en main (*Tool* équipé) |

Sur mobile, des boutons *Courir*, *Accroupi*, *Allongé* et *Radio* apparaissent. La caméra
s'abaisse accroupi et au ras du sol allongé.

### Jeu publié

Roblox n'autorise que les animations publiées par le créateur du jeu (ou son groupe). Dans
Studio, le contrôleur joue directement les `KeyframeSequence` (rien à faire). Pour un jeu publié :
clic droit sur chaque `KeyframeSequence` de `ReplicatedStorage > SurvivantAnimations` >
**Save to Roblox…**, puis collez l'identifiant obtenu dans la valeur de même nom de
`SurvivantAnimations > AnimationIds`. Les identifiants publiés pour l'ancien rig R6 à 6 pièces ne
conviennent plus (ils sont vidés) : republiez les nouvelles animations.

### Les animations

| Animation | Durée | Boucle | Vitesse prévue |
|---|---:|:---:|---:|
| Repos (`Survivant_Repos`) : respiration, regard qui balaie, coudes souples | 4,0 s | oui | — |
| Marche (`Survivant_Marche`) : bottes plantées, roulé talon-pointe, genoux qui plient | 0,70 s | oui | 6 studs/s |
| Course (`Survivant_Course`) : phase de vol, genoux hauts, bras pliés à 90° | 0,56 s | oui | 16 studs/s |
| Accroupi (`Survivant_Accroupi`) : genoux fléchis, regard aux aguets | 3,0 s | oui | — |
| Marche accroupie (`Survivant_MarcheAccroupie`) : appuis larges, pas silencieux | 1,0 s | oui | 2,6 studs/s |
| Allongé (`Survivant_Allonge`) : appui sur les avant-bras | 4,0 s | oui | — |
| Ramper (`Survivant_Ramper`) : coudes en appui, jambes en grenouille | 1,4 s | oui | 1 stud/s |
| Saut (`Survivant_Saut`) : bras en V | 0,50 s | non | — |
| Chute (`Survivant_Chute`) : bras levés qui battent l'air | 0,90 s | oui | — |
| Atterrissage (`Survivant_Atterrissage`) : genoux qui amortissent | 0,42 s | non | — |
| S'allonger (`Survivant_SAllonger`) | 0,95 s | non | — |
| Se relever (`Survivant_SeRelever`) | 1,15 s | non | — |
| Grimper (`Survivant_Grimper`) : mains et bottes sur les barreaux | 0,45 s | oui | 5 studs/s |
| Assis (`Survivant_Assis`) : mains sur les genoux | 3,0 s | oui | — |
| Outil en main (`Survivant_Outil`) : bras droit seul, superposé aux autres | 4,0 s | oui | — |

Chaque animation est calculée sur un modèle exact du rig articulé, puis échantillonnée à
30 images/s (300 images clés au total après simplification, écart < 0,5°). Pour la marche, la
course et la marche accroupie, le point d'appui de chaque botte recule exactement à la vitesse du
personnage (cinématique inverse hanche-genou-botte) : **les pieds ne glissent pas** à la vitesse
prévue ; pour grimper, mains et bottes restent sur des barreaux espacés de 1,125 stud. En jeu, le
contrôleur règle les vitesses (`CONFIG.VITESSE = { marche = 6, course = 16, accroupi = 3,
allonge = 1.5 }` en haut du script `Animate`) et accélère ou ralentit chaque animation dans la même
proportion, pour que les appuis restent calés. L'animation « outil en main » ne contient que le
bras droit : elle se superpose à la marche, à la course, etc.

Modifier une animation à la main : *Avatar > Éditeur d'animation*, sélectionnez `Anatomie_R6`,
menu « … » > *Charger* (*Load*). Ou demandez à Claude (section 3).

---

## 3. Modifier le personnage avec Claude, directement dans Roblox Studio

Roblox Studio contient un **serveur MCP** : une fois activé, Claude (l'application **Claude
Desktop** ou **Claude Code**, installée sur le **même ordinateur** que Studio) peut lire et
modifier la place ouverte : poser le survivant, retoucher une animation, changer une couleur,
lancer un test et faire une capture d'écran pour vérifier.

**Activer (une fois)**

1. Studio > **Assistant** > menu **…** > **Manage MCP Servers** > activez **Enable Studio as MCP
   server**.
2. **Assistant Settings** > **MCP Servers** > liste **Quick connect** > activez **Claude Desktop**
   ou **Claude Code**. S'ils n'apparaissent pas, installez-les puis redémarrez Studio.
   Configuration manuelle (fichier de configuration MCP du client), puis redémarrez le client :
   - Windows :
     `{"mcpServers": {"Roblox_Studio": {"command": "cmd.exe", "args": ["/c", "%LOCALAPPDATA%\\Roblox\\mcp.bat"]}}}`
   - macOS :
     `{"mcpServers": {"Roblox_Studio": {"command": "/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"}}}`
3. Ouvrez la place qui contient le survivant (après les étapes 1 et 2). Avec Claude Code, lancez-le
   dans le dossier décompressé : il lit `CLAUDE.md` (les conventions du rig et de l'éditeur).
   Avec Claude Desktop, glissez `CLAUDE.md` dans la conversation (ou dans un projet).

**Exemples de demandes**

- « Dans Studio, fais plier davantage les genoux du survivant dans la marche accroupie. »
- « Rends la course plus nerveuse : bras plus hauts, buste plus penché. »
- « Pose le survivant comme s'il visait avec un fusil, puis fais une capture d'écran. »
- « Assombris un peu la veste et montre l’anatomie en radiographie à 50 %. »
- « Lance le jeu, fais-le courir quelques secondes et dis-moi si les pieds glissent. »

Claude passe par le module `ServerStorage > SurvivantEditeur` (fonctions de pose et d'édition des
animations, données d'origine dans `SurvivantEditeur > Donnees` pour tout restaurer). Mode
d'emploi dans la barre de commande : `print(require(game.ServerStorage.SurvivantEditeur).aide())`.

| Fonction (`local E = require(game.ServerStorage.SurvivantEditeur)`) | Effet |
|---|---|
| `E.aide()`, `E.info()` | guide complet ; rig, articulations, animations et vitesses |
| `E.pose("RightElbow", 90)` ou `E.pose({ RightKnee = { rx = -60 }, Neck = { ry = 20 } })` | pose le rig du Workspace (aperçu, rien n'est enregistré) |
| `E.reinitialiserPose()` | remet le rig au repos |
| `E.apercu("run", 0.28)` | montre l'animation à cet instant sur le rig |
| `E.modifierPose("run", 0.28, "RightElbow", { rx = 10, relatif = true })` | change une pose d'une animation (image clé créée si besoin) |
| `E.lireAnimation("walk")` / `E.ecrireAnimation("walk", a)` | lit / réécrit (ou crée) une animation entière : images clés `{ t, poses = { Piece = {x, y, z, rx, ry, rz} } }` |
| `E.restaurerAnimation("walk")` | remet la version d'origine |
| `E.importerDepuisEditeur("walk")` | reprend la version enregistrée par l'Éditeur d'animation de Roblox |
| `E.vitesses({ marche = 7 })` | vitesses en jeu du contrôleur `Animate` |
| `E.radiographie(true, 0.7)` | tenue transparente (anatomie visible) ou opaque |
| `E.majPersonnageJouable()` | recopie le rig dans `StarterPlayer > StarterCharacter` |

Angles en degrés, autour du pivot de l'articulation, dans les axes de la pièce parente : plier le
coude = `rx > 0`, plier le genou = `rx < 0`, lever le bras devant = `rx > 0` sur l'épaule, écarter
le bras droit = `rz > 0` (le gauche : `rz < 0`), pencher le torse ou baisser la tête = `rx < 0`.
Les écritures s'annulent avec **Ctrl+Z** ; une animation modifiée est marquée (`Survivant_Modifiee`)
pour ne pas être écrasée si vous relancez le script d'installation, et son identifiant publié est
vidé (à republier avant de publier le jeu).

**Attention** : un client MCP connecté peut lire et modifier les places ouvertes dans Studio ;
ne connectez que des clients de confiance et gardez une copie de votre place.

---

## Réglages (en haut de `AnatomieR6_Setup.lua`)

| Réglage | Défaut | Effet |
|---|---|---|
| `SKIN_MODE` | `"maillage"` | `"maillage"` = tenue importée (`Survivor_*`) ; `"blocs"` = les 10 blocs Roblox du rig aux couleurs `SKIN_COLORS` |
| `SKIN_TRANSPARENCY` | `0` | Transparence de la tenue (0 = opaque, 0.7 = radiographie, 1 = invisible) |
| `SKIN_COLORS` | survivant | Couleurs des blocs en mode `"blocs"` |
| `USE_VERTEX_COLORS` | `true` | `false` = une couleur unie par pièce (si les couleurs de sommets ne s'affichent pas) |
| `ANCHOR_ROOT` | `true` | Modèle d'exposition ancré (ne tombe pas) ; le personnage jouable, lui, est désancré |
| `RENDER_FIDELITY_PRECISE` | `true` | Détail maximal à toute distance (mettre `false` pour de meilleures performances) |
| `CATEGORY` | — | Matériau et reflet par catégorie (os, organes, vaisseaux…) |

En haut de `SurvivantR6_Animations.lua` : `CREATE_STARTER_CHARACTER` (personnage jouable),
`KEEP_SURVIVOR_LOOK` (pas de vêtements de l'avatar du joueur par-dessus), `KEEP_EDITED_ANIMATIONS`
(les animations modifiées avec `SurvivantEditeur` ne sont pas écrasées en réinstallant),
`INSTALL_EDITOR` (module `SurvivantEditeur`). En haut du script `Animate` : vitesses, touches,
transparence de la radiographie, caméra, boutons tactiles.

## Outils (`AnatomieR6_Outils.lua`)

Chaque outil est un bloc `do … end` à coller seul dans la barre de commande : afficher/masquer la
tenue (1), **radiographie** (2, transparence réglable, bonnet et sac masqués), **retirer la calotte
du crâne pour voir le cerveau** (3), masquer une catégorie (4, par ex. tous les organes pour voir le
squelette), isoler le squelette (5), tout réafficher (6), compter les pièces (7), convertir le rig en
StarterCharacter (8), passer de la tenue importée aux blocs Roblox (9).

Astuce : les poumons cachent l'arbre bronchique ; rendez `Torso_Lung_*` semi-transparents
(Transparency 0.6) pour le voir.

---

## Blender (`Survivant_R6_Anime.blend`)

Armature `Rig_R6_Articule` dont les 11 os portent les noms des pièces du rig (`HumanoidRootPart`,
`Torso`, `Head`, `RightUpperArm`, `RightLowerArm`, `LeftUpperArm`, `LeftLowerArm`, `RightUpperLeg`,
`RightLowerLeg`, `LeftUpperLeg`, `LeftLowerLeg`) et partent des pivots des Motor6D (épaules,
coudes, hanches, genoux) : une pose dans Blender est le même mouvement que dans Roblox. La tenue
(collection `Survivant`) et l'anatomie (collection `Anatomie`) sont attachées aux os. Une action
par animation (30 images/s, interpolation linéaire comme Roblox) : choisissez-la dans *Dope Sheet >
Éditeur d'actions*, ou réactivez sa piste NLA. Les fichiers FBX/GLB de `dist/` sont, eux, en pose
de référence (non animés).

---

## Bon à savoir

- **Proportions R6** : le R6 a un torse énorme et des membres courts. L'anatomie est donc
  compressée verticalement dans les membres et légèrement élargie au niveau des épaules pour que
  les articulations tombent aux pivots du rig (le coude sur l'axe de la trochlée, le genou sur
  celui des condyles fémoraux). Chaque structure reste anatomiquement correcte (formes, repères,
  positions relatives), mais pas aux proportions exactes d'un humain.
- **Hanches** : comme en R6, le pivot de la hanche est sur la ligne du bas du torse ; quand la
  jambe se replie beaucoup (accroupi, ramper), la cuisse glisse un peu dans le torse (caché par la
  veste) et la tête du fémur s'écarte de sa cavité (visible en radiographie).
- **Performances** : la version Ultra (1,6 M triangles) est faite pour une scène d'exposition.
  Pour un jeu, utilisez la version `Leger` et/ou `RENDER_FIDELITY_PRECISE = false`.
- **Il n'y a pas de muscles squelettiques** : les seuls muscles modélisés sont le cœur, le
  diaphragme et les muscles de l'œil. L'anatomie tient entièrement à l'intérieur de la tenue.
- **Si les couleurs n'apparaissent pas** (tout est gris ou blanc) : réimportez en décochant
  *Ignore Vertex Colors*, ou passez `USE_VERTEX_COLORS = false` pour des couleurs unies.
- **Si le script refuse l'import « en miroir »** : réimportez avec les réglages *World Forward /
  World Up* par défaut.
- **Ancienne version (rig R6 à 6 pièces)** : réimportez le nouveau FBX et relancez les deux
  scripts ; l'ancien rig du même nom est renommé et conservé.
- **Scripts testés hors ligne** sur une émulation de l'API Roblox (6 470 vérifications : rig
  articulé, placement de chaque pièce du manifeste sur sa pièce du rig, imports à échelle/rotation
  quelconques, fusion de plusieurs imports, tenue importée ou en blocs, outils, installation des
  animations, contrôleur en jeu, chaque fonction de `SurvivantEditeur`, angles comparés à un
  calcul indépendant en Python), mais pas dans un vrai Roblox Studio. En cas de souci, copiez-moi
  le message de la fenêtre *Output*, ou demandez à Claude connecté à Studio de le lire.
- `SurvivantR6_Animations.lua` est gros (environ 180 Ko : les 15 animations, le contrôleur et
  l'éditeur) : le collage dans la barre de commande peut prendre quelques secondes.

---

## Régénérer ou modifier le modèle (`src/`)

Tout est procédural : chaque pièce est décrite en code (champs de distance signée + balayages de
tubes), maillée, lissée, décimée et colorée automatiquement ; chaque animation est une fonction du
temps sur un modèle cinématique du rig articulé (`rig_spec.py` : pièces, pivots, Motor6D).

```bash
pip install bpy scikit-image scipy pyfqmr     # Python 3.13 (bpy = Blender 5.2 en module)
cd src
python build.py -j 4                          # construit les 224 pièces -> build/parts/*.npz
python build.py 'Survivor_*' -j 4             # ou seulement certaines pièces
python export.py                              # FBX/GLB Ultra + Léger dans dist/
python export_blend_rig.py                    # scène Blender animée dans dist/
python make_lua.py                            # scripts Roblox (pièces, rig, animations, éditeur) et anims.json
python render_final.py                        # aperçus dans apercus/
python render_anim_video.py                   # vidéo des animations dans apercus/
python anim_preview.py ../build/prev/m.png walk,run --frames 8   # planche d'une animation
```

Fichiers principaux : `rig_spec.py` (le rig articulé, source unique pour tous les exports),
`head.py`, `torso_skel.py`, `torso_thorax.py`, `torso_abdomen.py`, `torso_vessels.py`, `arms.py`,
`legs.py` (une fonction par structure anatomique), `segments.py` (découpe au coude et au genou),
`survivor.py` (tenue du survivant, charnières des coudes et des genoux), `skin.py` (maintien de
l'anatomie à l'intérieur), `anim.py` (animations, cinématique inverse, export Roblox),
`landmarks.py` (repères anatomiques partagés), `maps.py` (projection des coordonnées anatomiques
réelles vers les blocs R6), `SPEC.md` (spécification technique).
