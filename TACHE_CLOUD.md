# Tâche pour la session cloud : actions Blender corrigées (deuxième passe)

Le personnage et ses 15 animations ont été corrigés et testés dans Roblox Studio (voir
`CONVERSATION_RESUME.md`, section 10). Une première passe cloud a déjà produit la branche `blender-corrige`
(rapport `RAPPORT_BLENDER.md` sur cette branche) ; ne pas la modifier.

Depuis, deux changements sur `main` :
- `src/anim.py` : dans l'accroupi sur place, la botte droite (pied avant, écarté) roulait sur son bord intérieur
  et s'enfonçait de 0,07 stud dans le sol. Son tibia reste maintenant vertical vu de face (option `upright` de
  `solve_flat`, comme la marche accroupie) : semelle à plat, pointe tournée d'environ 13° vers l'extérieur ; le
  pied gauche ne change pas.
- `outils/maj_actions_blend.py` : interpolation **linéaire** forcée sur toutes les clés (Blender 5.2 créait des
  clés de Bézier malgré la préférence) ; le contrôle `--verifier` affiche maintenant le type d'interpolation.

L'utilisateur ne veut pas lancer Blender sur son PC (trop peu de mémoire) : c'est cette session qui le fait.

## À faire

1. Installer Blender 5.2 en module Python : `uv venv -p 3.13` puis `uv pip install "bpy==5.2.*"` (ou
   `pip install "bpy==5.2.*"` avec Python 3.13), hors du dépôt.
2. Mettre à jour les actions depuis la scène d'origine :
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
   | Survivant_Accroupi | 1,5° | 1,5° |

   Les autres actions restent sous 13°. Interpolation : `BEZIER` dans la scène d'origine, `LINEAR` partout dans
   la scène corrigée.
4. Bottes de l'accroupi : point le plus bas des maillages `Survivor_RightLowerLeg` et `Survivor_LeftLowerLeg`
   (sol à z = 0) sur les images de `Survivant_Accroupi` : vers −0,072 avant (bord intérieur de la botte droite),
   attendu vers −0,004 après (épaisseur de la semelle, comme au repos). Vérifier aussi que Marche, Course et
   Marche accroupie restent au-dessus de −0,03 comme dans la première passe.
5. Écrire `RAPPORT_BLENDER.md` : version de bpy, sortie des contrôles, mesures des bottes, durée.
6. Sur une nouvelle branche nommée exactement `blender-corrige-v2`, partie de `main` : ajouter
   `dist/Survivant_R6_Anime_corrige.blend` et `RAPPORT_BLENDER.md`, commit, push. Ne pas modifier `src/`,
   `roblox/`, `outils/` ni la scène d'origine ; ne pas ajouter l'environnement Python au dépôt.

Fini quand la branche `blender-corrige-v2` est poussée avec le fichier corrigé et le rapport, et que les
contrôles correspondent au tableau.
