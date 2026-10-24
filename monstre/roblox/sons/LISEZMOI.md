# Sons du monstre

19 sons synthétisés par `monstre/blender/scripts/sons_monstre.py` (aucun enregistrement : libres de droits),
Ogg Vorbis, 44,1 kHz, mono. Ils sont joués par `MonstreClient` aux marqueurs des clips (`Son`), à la tête du monstre
(son 3D) ou sur l'écran de la victime (infection).

| Fichier | Durée | Quand |
|---|---:|---|
| `grognement.ogg` | 2,3 s | début des mises à mort, saisies, repos |
| `hurlement.ogg` | 4,0 s | quand il repère quelqu'un, après une mise à mort |
| `hurlement_court.ogg` | 1,8 s | début de la frénésie |
| `reniflement.ogg` | 1,1 s | flairer |
| `souffle.ogg` | 2,5 s | respiration au repos |
| `pas_lourd.ogg` | 1,1 s | pas (marche, course, atterrissage) |
| `saisie.ogg` | 0,5 s | il attrape la victime |
| `morsure.ogg` | 1,2 s | morsures |
| `dechirure.ogg` | 1,5 s | chair arrachée |
| `craquement.ogg` | 0,9 s | os qui craque (extraction) |
| `mastication.ogg` | 2,8 s | dévoration, extraction |
| `impact.ogg` | 1,0 s | coups (ventre, frénésie, renversement) |
| `chute_corps.ogg` | 1,6 s | corps qui tombe |
| `trainer.ogg` | 2,8 s | corps traîné au sol (répété) |
| `cri_victime.ogg` | 2,2 s | cri étouffé de la victime traînée |
| `eclaboussure.ogg` | 0,8 s | (réserve : sang qui gicle) |
| `battement.ogg` | 0,8 s | battements de cœur de l'infecté |
| `toux.ogg` | 1,2 s | toux de l'infecté |
| `acouphene.ogg` | 3,2 s | (réserve : sifflement d'oreilles) |

## Les mettre dans le jeu

1. Studio : *Affichage > Gestionnaire de ressources* > *Importer en masse* (*Bulk Import*), sélectionnez les 19
   fichiers `.ogg`. Roblox les vérifie (quelques minutes) ; l'import de sons est gratuit dans la limite mensuelle de
   votre compte.
2. Pour chaque son : clic droit > *Copier l'ID de la ressource*, puis collez-le dans
   `ReplicatedStorage.Monstre.MonstreConfig`, table `SONS`, sous la forme `"rbxassetid://123456789"` :
   ```lua
   SONS = {
       volume = 1,
       grognement = "rbxassetid://123456789",
       ...
   ```
3. Un son laissé à `""` est ignoré. Pour remplacer un son par un meilleur, importez le vôtre et changez son identifiant.

Avec Claude et le serveur MCP de Studio, l'étape 2 peut se faire par script une fois les identifiants connus (voir
`monstre/CLAUDE.md`).
