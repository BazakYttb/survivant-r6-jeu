# Le monstre dans Roblox : installation et utilisation

Ce dossier contient tout ce qu'il faut pour faire vivre le monstre dans une place Roblox : rig, déplacements, IA
(patrouille, repérage, poursuite), 8 mises à mort scénarisées avec caméra, sang, sons et infection.

| Fichier | Rôle |
|---|---|
| `Monstre_Kit.rbxmx` | le kit à insérer dans Studio : installateur, modules et scripts (sources ci-dessous) |
| `src/Installateur.lua` | monte le rig sur le modèle importé (marqueurs → échelle et orientation), range tout |
| `src/MonstreAnim.lua` | lecteur d'animations (partagé serveur / clients) |
| `src/MonstreDonnees.lua` | animations du monstre (21 clips) et de la victime (13 clips), rig, séquences — généré |
| `src/MonstreConfig.lua` | **réglages** : vitesses, perception, mises à mort actives, sang, caméra, infection, sons |
| `src/MonstreServeur.server.lua` | IA et déroulement des mises à mort (serveur) |
| `src/MonstreClient.client.lua` | animation, caméra, sang, sons, infection (chaque client) |
| `src/MonstreOutils.lua` | commandes d'essai (barre de commande, ou Claude par le serveur MCP de Studio) |
| `sons/` | 19 sons synthétisés (.ogg) à importer, voir `sons/LISEZMOI.md` |
| `test/` | tests hors ligne (émulation de l'API Roblox) : `luaurun test/rbx_mock.lua test/test_monstre.lua` |

## Installer (Roblox Studio, mode édition)

1. **Importer le modèle** : *Accueil > Importer 3D* (ou *Avatar > Importer 3D*), fichier `monstre/export/Monstre.fbx`
   (ou `Monstre.glb`). Laissez les réglages par défaut ; l'échelle et l'orientation importent peu (elles sont retrouvées
   grâce aux marqueurs `REF_A` à `REF_D`). Les textures sont intégrées au fichier.
2. **Insérer le kit** : clic droit sur *Workspace* > *Insérer depuis un fichier…* > `monstre/roblox/Monstre_Kit.rbxmx`
   (ou glisser le fichier dans la fenêtre de Studio).
3. **Lancer l'installation** dans la barre de commande (*Affichage > Barre de commande*) :
   ```lua
   require(workspace.Monstre_Kit.Installateur)()
   ```
   La sortie (*Output*) résume ce qui a été fait. Tout est annulable avec Ctrl+Z. Si plusieurs imports du monstre sont
   dans la place, sélectionnez celui à installer avant. Options :
   `require(workspace.Monstre_Kit.Installateur)({ position = Vector3.new(0, 0, 0), garderConfig = false })`
   (`garderConfig = false` remplace un MonstreConfig déjà modifié).

Résultat :

- `Workspace.Monstre` : le modèle (37 MeshParts sous 20 000 triangles), `HumanoidRootPart` (2,4 × 2,4 × 1,6),
  38 Motor6D (37 pièces + `VictimeAncre`), `Humanoid` (R15, HipHeight 5,928), lueur de la gueule (pièce Neon et
  PointLight), étiquette `Monstre` ;
- `ReplicatedStorage.Monstre` : `MonstreAnim`, `MonstreConfig`, `MonstreDonnees`, `Effets` (gabarits de sang `SANG_*`) ;
- `ServerScriptService.MonstreServeur`, `StarterPlayer.StarterPlayerScripts.MonstreClient`,
  `ServerStorage.MonstreOutils`, et le kit rangé dans `ServerStorage.Monstre_Kit` (pour réinstaller).

Vérifier : `print(require(game.ServerStorage.MonstreOutils).verifier())`.

Les victimes sont les personnages des joueurs. Leurs animations de mise à mort sont faites pour le **survivant R6
articulé** de ce projet (`StarterPlayer.StarterCharacter`, voir le `CLAUDE.md` à la racine) ; avec un autre avatar,
le monstre les saisit quand même mais leur corps n'est pas animé.

## Essayer

Lancez le test (F5). Le monstre patrouille ; s'il vous voit (70 studs devant lui) ou vous entend courir (26 studs),
il hurle et vous poursuit ; à 5,5 studs il déclenche une mise à mort tirée au hasard. Pour essayer une mise à mort
précise, dans la barre de commande pendant le test (côté serveur) :

```lua
local O = require(game.ServerStorage.MonstreOutils)
O.pause(true)                 -- l'IA s'arrête
O.victimeTest()               -- un survivant d'essai devant le monstre (copie du StarterCharacter)
O.miseAMort("frenesie")       -- sur la victime la plus proche (vous, ou le survivant d'essai)
print(O.liste())              -- les 8 mises à mort et leurs phases
```

Clés : `morsure_cou`, `morsure_repetee`, `devoration`, `attaque_ventre`, `trainee`, `extraction`, `frenesie`,
`contamination`. Gestes : `O.geste("roar")` (hurlement), `"sniff"` (flairer), `"attack"` (attaque).

## Les 8 mises à mort

| Clé | Ce qui se passe | Caméra de la victime |
|---|---|---|
| 🩸 `morsure_cou` | saisie par les épaules, soulevée et plaquée contre lui, morsure au cou ; coupure au noir, éclaboussures, sang sur l'écran, il secoue la tête puis lâche le corps | vue de la victime → coupure → plan de côté → corps au sol |
| 🦷 `morsure_repetee` | tenue d'une main, quatre morsures rapides (tirée vers la gueule à chaque fois), puis jetée sur le côté | par-dessus l'épaule de la victime → suit le corps |
| 👹 `devoration` | renversée, saisie par la cheville, traînée vers l'obscurité (partie étiquetée `MonstreTaniere`, sinon loin des autres joueurs), il s'agenouille et la dévore ; sons de mastication | reste à distance, fixe, et suit le monstre des yeux |
| 💀 `attaque_ventre` | élan, griffes plantées dans le ventre (la victime est soulevée), torsion, retrait ; elle se plie, tombe à genoux puis sur le côté — rien de l'intérieur du corps n'est montré | plan de côté, tremblement à l'impact |
| 🩸 `trainee` | renversée, saisie par la cheville et tirée hors de la pièce (partie `MonstreSortie`), elle s'agrippe au sol ; longue traînée de sang | depuis la tête de la victime, tournée vers le monstre qui la tire |
| 🫀 `extraction` | plaquée au sol (main gauche sur la poitrine), il s'acharne penché sur elle ; coupure au noir ; il se relève, la main portée à la gueule, le corps au sol | de face → derrière l'épaule du monstre (son dos cache tout) → noir → retour |
| 🐺 `frenesie` | renversée, douze coups de griffes et morsures en deux secondes, caméra qui tremble, puis **silence soudain** (tous les sons coupés) et le monstre se fige | vue de la victime, tremblements, puis plan figé |
| ☣️ `contamination` | morsure à l'avant-bras, jetée au sol face contre terre, **laissée vivante** ; elle se relève ; quelques secondes plus tard les symptômes commencent | par-dessus son épaule, puis caméra rendue au joueur |

Symptômes de l'infection (`CONFIG.INFECTION`) : image qui se désature et verdit, voile sombre, flou qui bat au rythme
du cœur, battements et toux, caméra qui tangue, vitesse de marche réduite (jusqu'à 60 %), peau et tenue qui se teintent
peu à peu. Par défaut la victime reste en vie (`issue = "rien"`) ; `issue = "mort"` la tue à la fin de `duree`, et
`degats_par_seconde` lui retire de la vie.

Après une mise à mort, la victime est remplacée par un **cadavre posé** (copie ancrée de sa tenue, à la dernière pose)
et réapparaît ; le cadavre disparaît après `CONFIG.SANG.duree_cadavre` secondes.

## Préparer la place (facultatif)

Étiquetez des parties avec l'éditeur d'étiquettes (*Affichage > Éditeur d'étiquettes*) :

- `MonstrePatrouille` : points de patrouille (sinon il erre autour de sa position de départ) ;
- `MonstreTaniere` : coin sombre où il traîne ses proies pour les dévorer ;
- `MonstreSortie` : porte ou sortie par laquelle il tire sa victime (traînée) ;
- `Survivant` : sur un modèle avec Humanoid, pour en faire une victime d'essai.

## Réglages (`ReplicatedStorage.Monstre.MonstreConfig`)

Vitesses (`marche` 5,5 et `course` 20 : vitesses des clips, pieds plantés), perception (`vue`, `angle_vue`, `ouie`,
`oubli`), portée d'attaque, temps de repos, poids de chaque mise à mort (0 la désactive), traînées (destinations,
distances, durée du repas), sang (`actif`, `decalques`, `particules`, `ecran`, `quantite`, durées), caméra (active,
force des tremblements, champ), infection, sons (identifiants et volume), vie du monstre (infinie par défaut).

## Sons

Les 19 sons de `sons/` sont à importer dans Roblox (gestionnaire de ressources), puis leurs identifiants à coller dans
`MonstreConfig.SONS` : voir `sons/LISEZMOI.md`. Un son sans identifiant est simplement ignoré.

## Comment ça marche

- **Pas d'AnimationTrack** : chaque client calcule la pose à partir de `MonstreDonnees` (pistes par articulation,
  clés réduites à 0,5 degré près) et écrit `Motor6D.Transform` à chaque image (`RunService.PreSimulation`, après
  l'Animator : la victime est animée par-dessus les animations du survivant). Rien n'est à publier sur Roblox, et
  ça marche en jeu publié comme dans Studio.
- **Synchronisation** : le serveur publie l'état dans des attributs du modèle (`MA_Action`, `MA_Sequence`,
  `MA_Phase`, `MA_PhaseDebut` sur l'horloge `workspace:GetServerTimeNow()`, `MA_Graine`) et `MA_Victime`
  (ObjectValue). Tous les clients jouent la même phase au même instant ; le sang (positions et tirages) est le même pour
  tous (graine partagée).
- **Victime** : son HumanoidRootPart est soudé (Weld) à la pièce `VictimeAncrePart`, portée par le Motor6D
  `VictimeAncre` du monstre, animé comme les autres articulations : la victime suit les mains et la gueule du monstre.
  Pendant la mise à mort elle est sans masse, sans collisions, `PlatformStand`, commandes coupées ; le
  HumanoidRootPart du monstre est ancré (il glisse le long du chemin pendant les traînées, corps tourné de 180 degrés
  dans le clip).
- **Marqueurs** des clips : `Son`, `Eclaboussure`, `Flaque`, `Trace`, `Morsure`, `Coup`, `Impact`, `Retrait`,
  `Tremble`, `Camera`, `Coupure`, `Ecran`, `Silence`, `Infection`, `Lacher`.

## Maturité du contenu

Le sang réaliste et les mises à mort de ce kit relèvent des catégories de violence et de sang du questionnaire de
maturité de Roblox (*Créateur > Paramètres de l'expérience > Maturité et conformité*). Remplissez-le honnêtement : avec
le sang à fond, l'expérience sera probablement classée pour un public âgé (catégorie la plus restrictive). Pour un
public plus jeune, réduisez dans `MonstreConfig.SANG` (`actif = false` coupe tout le sang ajouté en jeu ; les textures
du monstre restent tachées de sang) et retirez les mises à mort les plus crues (`MISES_A_MORT`).

## Limites connues

- **Jamais lancé dans un vrai Roblox Studio** : tout a été vérifié hors ligne avec une émulation de l'API (220
  vérifications : installation sur un import penché et à l'échelle 0,01, poses comparées au calcul Python à 2
  millièmes de stud près, poursuite, les 8 mises à mort de bout en bout, cadavre, traînées, infection). Le premier
  essai dans Studio reste à faire (voir `../CLAUDE.md` pour le faire avec Claude et le serveur MCP de Studio).
- Le monstre est grand (10,6 studs) : la recherche de chemin le fait passer par des ouvertures de 8 studs de haut ; sa
  tête (sans collision) traverse alors le linteau.
- Les sons sont synthétisés (aucun enregistrement) : remplacez-les par de meilleurs si vous en avez.
- La victime est animée seulement si elle a le rig du survivant R6 articulé.
