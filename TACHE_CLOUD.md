# Tâche pour la session cloud : actions Blender corrigées

Le personnage et ses 15 animations ont été corrigés et testés dans Roblox Studio (voir
`CONVERSATION_RESUME.md`, section 10). Les animations viennent de `src/anim.py` ; la scène Blender
`dist/Survivant_R6_Anime.blend` (Blender 5.2) a encore les anciennes actions, avec les mêmes défauts : cuisse
gauche retournée de 180° (Repos, Atterrissage, Outil, et en transition dans S'allonger / Se relever), bras qui
tournent sur eux-mêmes dans Grimper, bottes sous le sol en fin de pas, cuisses dans le siège en position assise.

L'utilisateur ne veut pas lancer Blender sur son PC (trop peu de mémoire) : c'est cette session qui le fait.

## À faire

1. Installer Blender 5.2 en module Python : `pip install "bpy==5.2.*"` (wheels pour Python 3.13 ; sinon
   `uv venv -p 3.13 .venv && uv pip install "bpy==5.2.*"`). À défaut, l'archive Linux de Blender 5.2 LTS
   (download.blender.org) et `blender -b`.
2. Mettre à jour les actions (l'armature, les maillages et les pistes NLA restent tels quels) :
   `python outils/maj_actions_blend.py dist/Survivant_R6_Anime.blend src dist/Survivant_R6_Anime_corrige.blend`
3. Contrôler l'avant et l'après :
   `python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime.blend`
   `python outils/maj_actions_blend.py --verifier dist/Survivant_R6_Anime_corrige.blend`
   Valeurs attendues (plus grand saut de rotation d'un os entre deux images, calculé depuis `anim.py`) :

   | Action | avant | après |
   |---|---:|---:|
   | Survivant_Repos | 180,0° (LeftUpperLeg) | 1,8° |
   | Survivant_Atterrissage | 179,9° (LeftUpperLeg) | 29,9° |
   | Survivant_Outil | 180,0° (LeftUpperLeg) | 1,8° |
   | Survivant_SAllonger | 41,6° (LeftUpperLeg) | 20,3° |
   | Survivant_SeRelever | 29,7° (LeftUpperLeg) | 20,3° |
   | Survivant_Grimper | 112,3° (LeftUpperArm) | 54,4° (geste rapide vers le barreau) |
   | Survivant_Saut | 54,7° | 54,7° (bras qui montent, voulu) |
   | Survivant_Course | 30,6° | 30,6° |
   | Survivant_Marche | 25,4° | 25,4° |

   Les autres actions restent sous 13°. Un écart de quelques dixièmes de degré est normal (images clés).
4. Écrire `RAPPORT_BLENDER.md` : version de Blender / bpy utilisée, sortie des deux contrôles, durée.
5. Sur une branche nommée `blender-corrige` : ajouter `dist/Survivant_R6_Anime_corrige.blend` et
   `RAPPORT_BLENDER.md`, commit, push. Ne pas modifier `src/`, `roblox/` ni la scène d'origine ; ne pas
   ajouter l'environnement Python au dépôt.

Fini quand la branche `blender-corrige` est poussée avec le fichier corrigé et le rapport, et que les
contrôles correspondent au tableau.
