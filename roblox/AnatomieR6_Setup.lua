--[[
	AnatomieR6_Setup.lua  --  survivant R6 articulé et anatomique (Roblox Studio)
	=====================================================================

	UTILISATION
	  1. Dans Roblox Studio : File > Import 3D (ou Avatar > Importer 3D), choisissez le fichier
	     FBX ou GLB anatomique (dist/). Importez-le tel quel : l'échelle, les axes « World
	     Forward / Up » et l'endroit d'insertion n'ont AUCUNE importance, le script les retrouve
	     grâce aux 4 petits marqueurs REF_A, REF_B, REF_C, REF_D contenus dans le fichier.
	  2. (Optionnel) Sélectionnez le ou les modèles importés. Sans sélection, le script traite
	     tous les modèles du Workspace qui contiennent un marqueur REF_A.
	  3. Affichage > Barre de commande (View > Command Bar), collez TOUT ce fichier, Entrée.
	  4. Le personnage « Anatomie_R6 » est créé (ou complété s'il existe déjà : on peut importer
	     plusieurs fichiers - tête, torse, membres - et relancer le script après chaque import).
	     Le résumé s'affiche dans la fenêtre Output. Ctrl+Z annule toute l'opération.

	R6 ARTICULÉ : coudes et genoux
	  La silhouette reste celle d'un R6 (torse 2x2x1, tête 2x1x1, membres de 1 stud), mais chaque
	  bras et chaque jambe est coupé en deux au coude et au genou, pour des animations plus
	  naturelles. 10 pièces : Torso, Head, RightUpperArm, RightLowerArm, LeftUpperArm,
	  LeftLowerArm, RightUpperLeg, RightLowerLeg, LeftUpperLeg, LeftLowerLeg ; 10 Motor6D :
	  RootJoint, Neck (comme en R6), RightShoulder, RightElbow, LeftShoulder, LeftElbow, RightHip,
	  RightKnee, LeftHip, LeftKnee. Humanoid de type R15 (HipHeight 2) et une main invisible
	  RightHand (RightGripAttachment) pour tenir les outils.

	Ce que fait le script
	  - calcule, pour chaque import, la similitude (échelle uniforme + rotation + translation)
	    qui ramène les marqueurs à leur position attendue dans l'espace du rig ;
	  - construit (ou réutilise) le rig articulé : HumanoidRootPart, les 10 pièces, Motor6D,
	    RightHand, Humanoid. Un ancien rig R6 à 6 pièces du même nom est renommé (conservé) ;
	  - habille le rig avec la tenue du survivant importée avec le modèle (pièces Survivor_* :
	    tête et visage, bonnet, veste, sac à dos, bras, avant-bras, cuisses, jambes et bottes),
	    soudée à chaque pièce ; les blocs Roblox du rig restent alors invisibles (ils ne servent
	    qu'aux collisions et aux Motor6D). La tenue est opaque ; SKIN_TRANSPARENCY, l'outil 2 ou
	    la touche R en jeu (radiographie) la rendent transparente pour voir l'anatomie ;
	  - déplace / met à l'échelle chaque MeshPart anatomique, la range dans
	    Anatomie_R6.Anatomie.<pièce> et la soude (WeldConstraint) à sa pièce (humérus au bras,
	    radius et ulna à l'avant-bras, fémur à la cuisse, tibia à la jambe...), de sorte qu'elle
	    suive les animations ;
	  - supprime les marqueurs et les conteneurs importés devenus vides.

	Les couleurs sont dans les couleurs de sommets des maillages : Roblox les multiplie par
	MeshPart.Color, d'où Color = blanc quand USE_VERTEX_COLORS = true.
	Utilitaires (peau, calvaria, catégories, StarterCharacter) : voir AnatomieR6_Outils.lua.
	Animations, contrôleur et éditeur (assistant IA via le serveur MCP de Studio) :
	SurvivantR6_Animations.lua.
]]

------------------------------------------------------------------------------------------
-- CONFIGURATION (modifiez les valeurs ci-dessous avant de coller le script)
------------------------------------------------------------------------------------------
local CONFIG = {
	-- Nom du Model créé dans le Workspace. S'il existe déjà, il est réutilisé (fusion de
	-- plusieurs imports dans le même personnage).
	RIG_NAME = "Anatomie_R6",

	-- PEAU / TENUE : l'apparence du survivant.
	--   "maillage" : la tenue importée avec le modèle (pièces Survivor_*). Les blocs Roblox du rig
	--                deviennent invisibles.
	--   "blocs"    : les 10 blocs Roblox du rig (tête SpecialMesh), aux couleurs SKIN_COLORS.
	--                Utilisé automatiquement pour les pièces sans Survivor_*.
	SKIN_MODE = "maillage",
	SKIN_TRANSPARENCY = 0, -- 0 = opaque (survivant), 0.7 = radiographie (anatomie visible), 1 = invisible
	SKIN_MATERIAL = Enum.Material.SmoothPlastic, -- matériau de la peau
	-- Couleurs des blocs (mode "blocs") : peau, veste olive, avant-bras nus, jean, bottes.
	SKIN_COLORS = {
		Head = Color3.fromRGB(212, 156, 120),
		Torso = Color3.fromRGB(72, 80, 48),
		RightUpperArm = Color3.fromRGB(72, 80, 48),
		LeftUpperArm = Color3.fromRGB(72, 80, 48),
		RightLowerArm = Color3.fromRGB(212, 156, 120),
		LeftLowerArm = Color3.fromRGB(212, 156, 120),
		RightUpperLeg = Color3.fromRGB(42, 54, 78),
		LeftUpperLeg = Color3.fromRGB(42, 54, 78),
		RightLowerLeg = Color3.fromRGB(98, 64, 40),
		LeftLowerLeg = Color3.fromRGB(98, 64, 40),
	},

	-- true  : Color = blanc -> on voit les couleurs de sommets (réalistes) cuites dans les maillages.
	-- false : couleur unie par pièce (couleur « base » du manifeste).
	USE_VERTEX_COLORS = true,

	-- true : HumanoidRootPart ancré (modèle d'exposition qui ne tombe pas).
	-- Le personnage jouable (SurvivantR6_Animations.lua ou l'outil 8) est, lui, désancré.
	ANCHOR_ROOT = true,

	-- true : visage Roblox classique (decal « face ») sur la tête quand elle est un bloc
	-- (mode "blocs"). La tenue importée a son propre visage (pièce Survivor_Face).
	SHOW_FACE = false,

	-- RenderFidelity = Precise : le maillage n'est jamais simplifié avec la distance.
	RENDER_FIDELITY_PRECISE = true,

	-- CollisionFidelity = Box : les pièces anatomiques n'ont pas de collision, une simple
	-- boîte économise beaucoup de mémoire et de temps de calcul dans Studio.
	COLLISION_FIDELITY_BOX = true,

	-- true : si une pièce de même nom existe déjà dans le rig (réimport d'une version
	-- corrigée), l'ancienne est supprimée et remplacée par la nouvelle.
	REPLACE_DUPLICATES = true,

	-- Nettoyage après traitement.
	DELETE_MARKERS = true, -- supprime REF_A..REF_D
	DELETE_EMPTY_SOURCES = true, -- supprime les modèles importés devenus vides

	-- Contrôles de cohérence des marqueurs.
	MARKER_WARN_RESIDUAL = 0.05, -- écart (studs) au-delà duquel on avertit
	MARKER_ABORT_RESIDUAL = 0.5, -- écart (studs) au-delà duquel l'import est refusé
	MARKER_SCALE_TOLERANCE = 0.03, -- écart relatif toléré entre les échelles AB / AC / AD

	-- Matériau, reflet et couleur de secours (si la pièce est absente du manifeste) par catégorie.
	CATEGORY = {
		bone = { Material = Enum.Material.SmoothPlastic, Reflectance = 0, Color = { 0.89, 0.85, 0.75 } },
		tooth = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.08, Color = { 0.96, 0.94, 0.86 } },
		cartilage = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.06, Color = { 0.78, 0.86, 0.9 } },
		disc = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.05, Color = { 0.82, 0.86, 0.88 } },
		ligament = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.04, Color = { 0.9, 0.88, 0.8 } },
		organ = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.04, Color = { 0.72, 0.36, 0.34 } },
		brain = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.03, Color = { 0.87, 0.73, 0.69 } },
		eye = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.1, Color = { 0.95, 0.94, 0.9 } },
		vessel = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.03, Color = { 0.7, 0.1, 0.1 } },
		nerve = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.02, Color = { 0.96, 0.88, 0.55 } },
		muscle = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.02, Color = { 0.6, 0.17, 0.15 } },
		gland = { Material = Enum.Material.SmoothPlastic, Reflectance = 0.03, Color = { 0.85, 0.6, 0.35 } },
		default = { Material = Enum.Material.SmoothPlastic, Reflectance = 0, Color = { 0.8, 0.78, 0.74 } },
	},
}

------------------------------------------------------------------------------------------
-- TABLE DES PIÈCES (générée par src/make_lua.py à partir de build/manifest.json)
-- PARTS[nom] = { region = "Head"|"Torso"|"RightUpperArm"|..., cat = "bone"|...|"skin", color = {r,g,b}, info = "..." }
-- region = pièce du rig à laquelle la pièce est soudée. Une pièce absente de la table est quand
-- même traitée (région d'après le préfixe du nom, sinon d'après sa position).
------------------------------------------------------------------------------------------
local PARTS = {}
PARTS = {
	["Head_Atlas_C1"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Atlas (1re vertèbre cervicale)"},
	["Head_Axis_C2"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Axis (2e vertèbre cervicale, dent de l'axis)"},
	["Head_Brain_L_Frontal"] = {region="Head", cat="brain", color={0.85,0.7,0.66}, info="Lobe frontal gauche"},
	["Head_Brain_L_Posterior"] = {region="Head", cat="brain", color={0.85,0.7,0.66}, info="Lobes pariétal, temporal et occipital gauche"},
	["Head_Brain_R_Frontal"] = {region="Head", cat="brain", color={0.85,0.7,0.66}, info="Lobe frontal droit"},
	["Head_Brain_R_Posterior"] = {region="Head", cat="brain", color={0.85,0.7,0.66}, info="Lobes pariétal, temporal et occipital droit"},
	["Head_Brainstem"] = {region="Head", cat="brain", color={0.9,0.82,0.74}, info="Tronc cérébral (mésencéphale, pont, bulbe), chiasma et bandelettes optiques, bulbes olfactifs"},
	["Head_Cerebellum"] = {region="Head", cat="brain", color={0.82,0.66,0.62}, info="Cervelet (hémisphères, vermis, lamelles)"},
	["Head_EyeMuscles"] = {region="Head", cat="muscle", color={0.6,0.17,0.15}, info="Muscles droits de l'œil (supérieur, inférieur, médial, latéral)"},
	["Head_Eye_L"] = {region="Head", cat="eye", color={0.95,0.94,0.9}, info="Globe oculaire gauche (sclère, iris, pupille, cornée)"},
	["Head_Eye_R"] = {region="Head", cat="eye", color={0.95,0.94,0.9}, info="Globe oculaire droit (sclère, iris, pupille, cornée)"},
	["Head_Hyoid"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Os hyoïde"},
	["Head_Mandible"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Mandibule (corps, branches, condyles, processus coronoïdes, foramens mentonniers)"},
	["Head_OpticNerves"] = {region="Head", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs optiques"},
	["Head_Skull_Base"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Base du crâne: temporaux, occipital, foramen magnum, mastoïdes"},
	["Head_Skull_Calvaria"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Calotte crânienne (amovible pour voir le cerveau)"},
	["Head_Skull_Face"] = {region="Head", cat="bone", color={0.89,0.85,0.75}, info="Massif facial: orbites, maxillaires, os zygomatiques, os nasaux"},
	["Head_SpinalCord"] = {region="Head", cat="nerve", color={0.93,0.88,0.78}, info="Moelle épinière cervicale haute"},
	["Head_Teeth_Lower"] = {region="Head", cat="tooth", color={0.96,0.94,0.86}, info="Dents inférieures (16)"},
	["Head_Teeth_Upper"] = {region="Head", cat="tooth", color={0.96,0.94,0.86}, info="Dents supérieures (16 : incisives, canines, prémolaires, molaires)"},
	["Head_Tongue"] = {region="Head", cat="organ", color={0.8,0.42,0.42}, info="Langue"},
	["Head_Vessels"] = {region="Head", cat="vessel", color={0.7,0.1,0.1}, info="Vaisseaux de la tête (carotides interne et externe, temporale superficielle, faciale, vertébrales, jugulaires internes)"},
	["LeftLowerArm_Arteries"] = {region="LeftLowerArm", cat="vessel", color={0.72,0.1,0.09}, info="Artères du bras gauche (axillaire, brachiale, radiale, ulnaire, arcades palmaires, digitales) - partie avant-bras"},
	["LeftLowerArm_Carpals"] = {region="LeftLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Os du carpe gauche (8 : scaphoïde, lunatum, triquetrum, pisiforme, trapèze, trapézoïde, capitatum, hamatum)"},
	["LeftLowerArm_Cartilage_RadialHead"] = {region="LeftLowerArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage de la tête radiale gauche"},
	["LeftLowerArm_Cartilage_Wrist"] = {region="LeftLowerArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage du poignet et disque triangulaire gauche"},
	["LeftLowerArm_Ligaments"] = {region="LeftLowerArm", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments gauche (collatéraux du coude, annulaire, rétinaculum des fléchisseurs) - partie avant-bras"},
	["LeftLowerArm_Metacarpals"] = {region="LeftLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Métacarpiens gauche (5)"},
	["LeftLowerArm_Nerves"] = {region="LeftLowerArm", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs du bras gauche (médian, ulnaire, radial, musculo-cutané) - partie avant-bras"},
	["LeftLowerArm_Phalanges"] = {region="LeftLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Phalanges des doigts gauche (14) et sésamoïdes du pouce"},
	["LeftLowerArm_Radius"] = {region="LeftLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Radius gauche (tête, tubérosité, styloïde, tubercule de Lister)"},
	["LeftLowerArm_Ulna"] = {region="LeftLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Ulna (cubitus) gauche (olécrane, processus coronoïde, tête, styloïde)"},
	["LeftLowerArm_Veins"] = {region="LeftLowerArm", cat="vessel", color={0.2,0.25,0.55}, info="Veines du bras gauche (brachiale, céphalique, basilique, médiane du coude, arcade dorsale) - partie avant-bras"},
	["LeftLowerLeg_Arteries"] = {region="LeftLowerLeg", cat="vessel", color={0.72,0.1,0.09}, info="Artères de la jambe gauche (fémorale, poplitée, tibiales, fibulaire, pédieuse) - partie jambe"},
	["LeftLowerLeg_Cartilage_Ankle"] = {region="LeftLowerLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage du dôme du talus gauche"},
	["LeftLowerLeg_Cartilage_TibialPlateau"] = {region="LeftLowerLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage du plateau tibial gauche"},
	["LeftLowerLeg_Fibula"] = {region="LeftLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Fibula (péroné) gauche"},
	["LeftLowerLeg_Ligaments"] = {region="LeftLowerLeg", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments gauche (croisés, collatéraux, cheville, fascia plantaire, membrane interosseuse) - partie jambe"},
	["LeftLowerLeg_Menisci"] = {region="LeftLowerLeg", cat="cartilage", color={0.85,0.87,0.86}, info="Ménisques médial et latéral gauche"},
	["LeftLowerLeg_Metatarsals"] = {region="LeftLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Métatarsiens gauche (5)"},
	["LeftLowerLeg_Nerves"] = {region="LeftLowerLeg", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs de la jambe gauche (sciatique, tibial, fibulaires, fémoral, saphène) - partie jambe"},
	["LeftLowerLeg_Phalanges"] = {region="LeftLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Phalanges des orteils gauche (14) et sésamoïdes"},
	["LeftLowerLeg_Tarsals"] = {region="LeftLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Os du tarse gauche (talus, calcanéus, naviculaire, cuboïde, 3 cunéiformes)"},
	["LeftLowerLeg_Tendons"] = {region="LeftLowerLeg", cat="ligament", color={0.92,0.9,0.82}, info="Tendons gauche (rotulien, quadricipital, calcanéen d'Achille) - partie jambe"},
	["LeftLowerLeg_Tibia"] = {region="LeftLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Tibia gauche (plateau, tubérosité, crête, malléole médiale)"},
	["LeftLowerLeg_Veins"] = {region="LeftLowerLeg", cat="vessel", color={0.2,0.25,0.55}, info="Veines de la jambe gauche (fémorale, grande et petite saphènes, tibiales) - partie jambe"},
	["LeftUpperArm_Arteries"] = {region="LeftUpperArm", cat="vessel", color={0.72,0.1,0.09}, info="Artères du bras gauche (axillaire, brachiale, radiale, ulnaire, arcades palmaires, digitales) - partie bras"},
	["LeftUpperArm_Cartilage_Elbow"] = {region="LeftUpperArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage huméral du coude gauche (trochlée, capitulum)"},
	["LeftUpperArm_Cartilage_Shoulder"] = {region="LeftUpperArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage de la tête humérale gauche"},
	["LeftUpperArm_Humerus"] = {region="LeftUpperArm", cat="bone", color={0.89,0.85,0.75}, info="Humérus gauche (tête, tubercules, sillon intertuberculaire, épicondyles, trochlée, capitulum)"},
	["LeftUpperArm_Ligaments"] = {region="LeftUpperArm", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments gauche (collatéraux du coude, annulaire, rétinaculum des fléchisseurs) - partie bras"},
	["LeftUpperArm_Nerves"] = {region="LeftUpperArm", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs du bras gauche (médian, ulnaire, radial, musculo-cutané) - partie bras"},
	["LeftUpperArm_Veins"] = {region="LeftUpperArm", cat="vessel", color={0.2,0.25,0.55}, info="Veines du bras gauche (brachiale, céphalique, basilique, médiane du coude, arcade dorsale) - partie bras"},
	["LeftUpperLeg_Arteries"] = {region="LeftUpperLeg", cat="vessel", color={0.72,0.1,0.09}, info="Artères de la jambe gauche (fémorale, poplitée, tibiales, fibulaire, pédieuse) - partie cuisse"},
	["LeftUpperLeg_Cartilage_Hip"] = {region="LeftUpperLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage de la tête fémorale gauche"},
	["LeftUpperLeg_Cartilage_Knee"] = {region="LeftUpperLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilages du genou gauche (condyles fémoraux, trochlée, rotule)"},
	["LeftUpperLeg_Femur"] = {region="LeftUpperLeg", cat="bone", color={0.89,0.85,0.75}, info="Fémur gauche (tête, col, trochanters, ligne âpre, condyles)"},
	["LeftUpperLeg_Ligaments"] = {region="LeftUpperLeg", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments gauche (croisés, collatéraux, cheville, fascia plantaire, membrane interosseuse) - partie cuisse"},
	["LeftUpperLeg_Nerves"] = {region="LeftUpperLeg", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs de la jambe gauche (sciatique, tibial, fibulaires, fémoral, saphène) - partie cuisse"},
	["LeftUpperLeg_Patella"] = {region="LeftUpperLeg", cat="bone", color={0.89,0.85,0.75}, info="Rotule gauche"},
	["LeftUpperLeg_Tendons"] = {region="LeftUpperLeg", cat="ligament", color={0.92,0.9,0.82}, info="Tendons gauche (rotulien, quadricipital, calcanéen d'Achille) - partie cuisse"},
	["LeftUpperLeg_Veins"] = {region="LeftUpperLeg", cat="vessel", color={0.2,0.25,0.55}, info="Veines de la jambe gauche (fémorale, grande et petite saphènes, tibiales) - partie cuisse"},
	["RightLowerArm_Arteries"] = {region="RightLowerArm", cat="vessel", color={0.72,0.1,0.09}, info="Artères du bras droit (axillaire, brachiale, radiale, ulnaire, arcades palmaires, digitales) - partie avant-bras"},
	["RightLowerArm_Carpals"] = {region="RightLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Os du carpe droit (8 : scaphoïde, lunatum, triquetrum, pisiforme, trapèze, trapézoïde, capitatum, hamatum)"},
	["RightLowerArm_Cartilage_RadialHead"] = {region="RightLowerArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage de la tête radiale droit"},
	["RightLowerArm_Cartilage_Wrist"] = {region="RightLowerArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage du poignet et disque triangulaire droit"},
	["RightLowerArm_Ligaments"] = {region="RightLowerArm", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments droit (collatéraux du coude, annulaire, rétinaculum des fléchisseurs) - partie avant-bras"},
	["RightLowerArm_Metacarpals"] = {region="RightLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Métacarpiens droit (5)"},
	["RightLowerArm_Nerves"] = {region="RightLowerArm", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs du bras droit (médian, ulnaire, radial, musculo-cutané) - partie avant-bras"},
	["RightLowerArm_Phalanges"] = {region="RightLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Phalanges des doigts droit (14) et sésamoïdes du pouce"},
	["RightLowerArm_Radius"] = {region="RightLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Radius droit (tête, tubérosité, styloïde, tubercule de Lister)"},
	["RightLowerArm_Ulna"] = {region="RightLowerArm", cat="bone", color={0.89,0.85,0.75}, info="Ulna (cubitus) droit (olécrane, processus coronoïde, tête, styloïde)"},
	["RightLowerArm_Veins"] = {region="RightLowerArm", cat="vessel", color={0.2,0.25,0.55}, info="Veines du bras droit (brachiale, céphalique, basilique, médiane du coude, arcade dorsale) - partie avant-bras"},
	["RightLowerLeg_Arteries"] = {region="RightLowerLeg", cat="vessel", color={0.72,0.1,0.09}, info="Artères de la jambe droite (fémorale, poplitée, tibiales, fibulaire, pédieuse) - partie jambe"},
	["RightLowerLeg_Cartilage_Ankle"] = {region="RightLowerLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage du dôme du talus droite"},
	["RightLowerLeg_Cartilage_TibialPlateau"] = {region="RightLowerLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage du plateau tibial droite"},
	["RightLowerLeg_Fibula"] = {region="RightLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Fibula (péroné) droite"},
	["RightLowerLeg_Ligaments"] = {region="RightLowerLeg", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments droite (croisés, collatéraux, cheville, fascia plantaire, membrane interosseuse) - partie jambe"},
	["RightLowerLeg_Menisci"] = {region="RightLowerLeg", cat="cartilage", color={0.85,0.87,0.86}, info="Ménisques médial et latéral droite"},
	["RightLowerLeg_Metatarsals"] = {region="RightLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Métatarsiens droite (5)"},
	["RightLowerLeg_Nerves"] = {region="RightLowerLeg", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs de la jambe droite (sciatique, tibial, fibulaires, fémoral, saphène) - partie jambe"},
	["RightLowerLeg_Phalanges"] = {region="RightLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Phalanges des orteils droite (14) et sésamoïdes"},
	["RightLowerLeg_Tarsals"] = {region="RightLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Os du tarse droite (talus, calcanéus, naviculaire, cuboïde, 3 cunéiformes)"},
	["RightLowerLeg_Tendons"] = {region="RightLowerLeg", cat="ligament", color={0.92,0.9,0.82}, info="Tendons droite (rotulien, quadricipital, calcanéen d'Achille) - partie jambe"},
	["RightLowerLeg_Tibia"] = {region="RightLowerLeg", cat="bone", color={0.89,0.85,0.75}, info="Tibia droite (plateau, tubérosité, crête, malléole médiale)"},
	["RightLowerLeg_Veins"] = {region="RightLowerLeg", cat="vessel", color={0.2,0.25,0.55}, info="Veines de la jambe droite (fémorale, grande et petite saphènes, tibiales) - partie jambe"},
	["RightUpperArm_Arteries"] = {region="RightUpperArm", cat="vessel", color={0.72,0.1,0.09}, info="Artères du bras droit (axillaire, brachiale, radiale, ulnaire, arcades palmaires, digitales) - partie bras"},
	["RightUpperArm_Cartilage_Elbow"] = {region="RightUpperArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage huméral du coude droit (trochlée, capitulum)"},
	["RightUpperArm_Cartilage_Shoulder"] = {region="RightUpperArm", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage de la tête humérale droit"},
	["RightUpperArm_Humerus"] = {region="RightUpperArm", cat="bone", color={0.89,0.85,0.75}, info="Humérus droit (tête, tubercules, sillon intertuberculaire, épicondyles, trochlée, capitulum)"},
	["RightUpperArm_Ligaments"] = {region="RightUpperArm", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments droit (collatéraux du coude, annulaire, rétinaculum des fléchisseurs) - partie bras"},
	["RightUpperArm_Nerves"] = {region="RightUpperArm", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs du bras droit (médian, ulnaire, radial, musculo-cutané) - partie bras"},
	["RightUpperArm_Veins"] = {region="RightUpperArm", cat="vessel", color={0.2,0.25,0.55}, info="Veines du bras droit (brachiale, céphalique, basilique, médiane du coude, arcade dorsale) - partie bras"},
	["RightUpperLeg_Arteries"] = {region="RightUpperLeg", cat="vessel", color={0.72,0.1,0.09}, info="Artères de la jambe droite (fémorale, poplitée, tibiales, fibulaire, pédieuse) - partie cuisse"},
	["RightUpperLeg_Cartilage_Hip"] = {region="RightUpperLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilage de la tête fémorale droite"},
	["RightUpperLeg_Cartilage_Knee"] = {region="RightUpperLeg", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilages du genou droite (condyles fémoraux, trochlée, rotule)"},
	["RightUpperLeg_Femur"] = {region="RightUpperLeg", cat="bone", color={0.89,0.85,0.75}, info="Fémur droite (tête, col, trochanters, ligne âpre, condyles)"},
	["RightUpperLeg_Ligaments"] = {region="RightUpperLeg", cat="ligament", color={0.92,0.9,0.82}, info="Ligaments droite (croisés, collatéraux, cheville, fascia plantaire, membrane interosseuse) - partie cuisse"},
	["RightUpperLeg_Nerves"] = {region="RightUpperLeg", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs de la jambe droite (sciatique, tibial, fibulaires, fémoral, saphène) - partie cuisse"},
	["RightUpperLeg_Patella"] = {region="RightUpperLeg", cat="bone", color={0.89,0.85,0.75}, info="Rotule droite"},
	["RightUpperLeg_Tendons"] = {region="RightUpperLeg", cat="ligament", color={0.92,0.9,0.82}, info="Tendons droite (rotulien, quadricipital, calcanéen d'Achille) - partie cuisse"},
	["RightUpperLeg_Veins"] = {region="RightUpperLeg", cat="vessel", color={0.2,0.25,0.55}, info="Veines de la jambe droite (fémorale, grande et petite saphènes, tibiales) - partie cuisse"},
	["Survivor_Backpack"] = {region="Torso", cat="gear", color={0.455,0.4,0.282}, info="Survivant : sac à dos, sac de couchage, gourde"},
	["Survivor_Face"] = {region="Head", cat="skin", color={0.133,0.094,0.078}, info="Survivant : visage (yeux, sourcils, bouche, pansement, égratignure)"},
	["Survivor_Hat"] = {region="Head", cat="gear", color={0.4,0.129,0.137}, info="Survivant : bonnet en laine et cheveux"},
	["Survivor_Head"] = {region="Head", cat="skin", color={0.831,0.612,0.471}, info="Survivant : tête (peau, barbe de trois jours, saleté)"},
	["Survivor_LeftLowerArm"] = {region="LeftLowerArm", cat="skin", color={0.831,0.612,0.471}, info="Survivant : avant-bras gauche (manche retroussée, montre, mitaine)"},
	["Survivor_LeftLowerLeg"] = {region="LeftLowerLeg", cat="skin", color={0.384,0.251,0.157}, info="Survivant : jambe gauche (jean, botte lacée)"},
	["Survivor_LeftUpperArm"] = {region="LeftUpperArm", cat="skin", color={0.282,0.314,0.188}, info="Survivant : bras gauche (manche de veste, coudière, écusson)"},
	["Survivor_LeftUpperLeg"] = {region="LeftUpperLeg", cat="skin", color={0.165,0.212,0.306}, info="Survivant : cuisse gauche (jean usé déchiré au genou, poche cargo)"},
	["Survivor_RightLowerArm"] = {region="RightLowerArm", cat="skin", color={0.831,0.612,0.471}, info="Survivant : avant-bras droit (manche retroussée, bandage taché de sang, mitaine)"},
	["Survivor_RightLowerLeg"] = {region="RightLowerLeg", cat="skin", color={0.384,0.251,0.157}, info="Survivant : jambe droite (jean, botte lacée)"},
	["Survivor_RightUpperArm"] = {region="RightUpperArm", cat="skin", color={0.282,0.314,0.188}, info="Survivant : bras droit (manche de veste, coudière)"},
	["Survivor_RightUpperLeg"] = {region="RightUpperLeg", cat="skin", color={0.165,0.212,0.306}, info="Survivant : cuisse droite (jean usé rapiécé au genou, poche cargo)"},
	["Survivor_Torso"] = {region="Torso", cat="skin", color={0.282,0.314,0.188}, info="Survivant : veste de terrain ouverte, t-shirt, sangles, ceinture, plaques militaires"},
	["Torso_AcetabularLabrum_L"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Bourrelet cotyloïdien gauche (articulation de la hanche)"},
	["Torso_AcetabularLabrum_R"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Bourrelet cotyloïdien droite (articulation de la hanche)"},
	["Torso_Adrenals"] = {region="Torso", cat="gland", color={0.86,0.62,0.26}, info="Glandes surrénales"},
	["Torso_Arteries_Abdomen"] = {region="Torso", cat="vessel", color={0.72,0.1,0.09}, info="Aorte abdominale, tronc cœliaque, mésentériques, rénales, gonadiques, iliaques"},
	["Torso_Arteries_Thorax"] = {region="Torso", cat="vessel", color={0.72,0.1,0.09}, info="Crosse et aorte thoracique, tronc brachio-céphalique, carotides, subclavières, vertébrales, thoraciques internes"},
	["Torso_BileDucts"] = {region="Torso", cat="organ", color={0.5,0.6,0.25}, info="Voies biliaires (canaux hépatiques, cystique, cholédoque) et canal pancréatique"},
	["Torso_Bladder"] = {region="Torso", cat="organ", color={0.86,0.74,0.64}, info="Vessie"},
	["Torso_BrachialPlexus"] = {region="Torso", cat="nerve", color={0.96,0.88,0.55}, info="Plexus brachial (racines, troncs, faisceaux) vers les nerfs du bras"},
	["Torso_Bronchi_L"] = {region="Torso", cat="organ", color={0.9,0.78,0.72}, info="Arbre bronchique gauche (souche, lobaires, segmentaires) - visible si les poumons sont transparents"},
	["Torso_Bronchi_R"] = {region="Torso", cat="organ", color={0.9,0.78,0.72}, info="Arbre bronchique droit (souche, lobaires, segmentaires) - visible si les poumons sont transparents"},
	["Torso_Clavicle_L"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Clavicule gauche"},
	["Torso_Clavicle_R"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Clavicule droite"},
	["Torso_Coccyx"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Coccyx (4 vertèbres soudées)"},
	["Torso_Colon_1"] = {region="Torso", cat="organ", color={0.82,0.62,0.5}, info="Côlon ascendant, caecum, appendice et côlon transverse (haustrations, bandelettes)"},
	["Torso_Colon_2"] = {region="Torso", cat="organ", color={0.82,0.62,0.5}, info="Côlon descendant, sigmoïde, rectum et canal anal"},
	["Torso_CoronaryVessels"] = {region="Torso", cat="vessel", color={0.7,0.1,0.1}, info="Artères coronaires (droite, interventriculaire antérieure, circonflexe) et veines cardiaques"},
	["Torso_CostalCartilage_L"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilages costaux gauches (côtes 1 à 10, rebord costal)"},
	["Torso_CostalCartilage_R"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilages costaux droites (côtes 1 à 10, rebord costal)"},
	["Torso_Diaphragm"] = {region="Torso", cat="muscle", color={0.6,0.16,0.14}, info="Diaphragme (coupoles, centre tendineux, piliers, orifices)"},
	["Torso_Discs_Cervical"] = {region="Torso", cat="disc", color={0.84,0.87,0.87}, info="Disques intervertébraux cervicales (anneau fibreux)"},
	["Torso_Discs_Lumbar"] = {region="Torso", cat="disc", color={0.84,0.87,0.87}, info="Disques intervertébraux lombaires (anneau fibreux)"},
	["Torso_Discs_Thoracic"] = {region="Torso", cat="disc", color={0.84,0.87,0.87}, info="Disques intervertébraux thoraciques (anneau fibreux)"},
	["Torso_Duodenum"] = {region="Torso", cat="organ", color={0.86,0.62,0.52}, info="Duodénum (bulbe, portions descendante, horizontale et ascendante)"},
	["Torso_Esophagus"] = {region="Torso", cat="organ", color={0.8,0.52,0.48}, info="Œsophage"},
	["Torso_Gallbladder"] = {region="Torso", cat="organ", color={0.32,0.5,0.24}, info="Vésicule biliaire"},
	["Torso_GlenoidLabrum_L"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Bourrelet glénoïdien gauche (articulation de l'épaule)"},
	["Torso_GlenoidLabrum_R"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Bourrelet glénoïdien droite (articulation de l'épaule)"},
	["Torso_GreatVessels"] = {region="Torso", cat="vessel", color={0.7,0.1,0.1}, info="Aorte ascendante, tronc et artères pulmonaires (bleu), veines caves, veines pulmonaires (rouge)"},
	["Torso_Heart"] = {region="Torso", cat="organ", color={0.55,0.13,0.12}, info="Cœur (ventricules, oreillettes, auricules, graisse épicardique dans les sillons)"},
	["Torso_HipBone_L"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Os coxal gauche (ilium, ischium, pubis, cotyle, trou obturé)"},
	["Torso_HipBone_R"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Os coxal droite (ilium, ischium, pubis, cotyle, trou obturé)"},
	["Torso_Intercostals_L"] = {region="Torso", cat="vessel", color={0.7,0.2,0.2}, info="Pédicules intercostaux gauches (veine, artère, nerf sous chaque côte)"},
	["Torso_Intercostals_R"] = {region="Torso", cat="vessel", color={0.7,0.2,0.2}, info="Pédicules intercostaux droits (veine, artère, nerf sous chaque côte)"},
	["Torso_Kidney_L"] = {region="Torso", cat="organ", color={0.56,0.2,0.14}, info="Rein gauche et bassinet"},
	["Torso_Kidney_R"] = {region="Torso", cat="organ", color={0.56,0.2,0.14}, info="Rein droit et bassinet"},
	["Torso_Larynx"] = {region="Torso", cat="cartilage", color={0.82,0.86,0.86}, info="Larynx (cartilage thyroïde / pomme d'Adam, cricoïde, aryténoïdes, épiglotte)"},
	["Torso_Liver"] = {region="Torso", cat="organ", color={0.48,0.15,0.1}, info="Foie (lobes droit, gauche, caudé, ligament falciforme, empreintes)"},
	["Torso_Lung_L_Lower"] = {region="Torso", cat="organ", color={0.84,0.55,0.56}, info="Poumon gauche - lobe inférieur"},
	["Torso_Lung_L_Upper"] = {region="Torso", cat="organ", color={0.84,0.55,0.56}, info="Poumon gauche - lobe supérieur (avec la lingula)"},
	["Torso_Lung_R_Lower"] = {region="Torso", cat="organ", color={0.84,0.55,0.56}, info="Poumon droit - lobe inférieur"},
	["Torso_Lung_R_Middle"] = {region="Torso", cat="organ", color={0.84,0.55,0.56}, info="Poumon droit - lobe moyen"},
	["Torso_Lung_R_Upper"] = {region="Torso", cat="organ", color={0.84,0.55,0.56}, info="Poumon droit - lobe supérieur"},
	["Torso_Nerves_Autonomic"] = {region="Torso", cat="nerve", color={0.96,0.88,0.55}, info="Nerfs phréniques et vagues (pneumogastriques), nerf laryngé récurrent"},
	["Torso_Nerves_Lumbosacral"] = {region="Torso", cat="nerve", color={0.96,0.88,0.55}, info="Plexus lombaire et sacré : nerfs fémoraux, obturateurs, sciatiques"},
	["Torso_Pancreas"] = {region="Torso", cat="gland", color={0.92,0.78,0.55}, info="Pancréas (tête, crochet, corps, queue)"},
	["Torso_PubicSymphysis"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Symphyse pubienne (disque fibrocartilagineux)"},
	["Torso_Rib_L01"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 1 gauche"},
	["Torso_Rib_L02"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 2 gauche"},
	["Torso_Rib_L03"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 3 gauche"},
	["Torso_Rib_L04"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 4 gauche"},
	["Torso_Rib_L05"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 5 gauche"},
	["Torso_Rib_L06"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 6 gauche"},
	["Torso_Rib_L07"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 7 gauche"},
	["Torso_Rib_L08"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 8 gauche"},
	["Torso_Rib_L09"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 9 gauche"},
	["Torso_Rib_L10"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 10 gauche"},
	["Torso_Rib_L11"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 11 gauche (flottante)"},
	["Torso_Rib_L12"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 12 gauche (flottante)"},
	["Torso_Rib_R01"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 1 droite"},
	["Torso_Rib_R02"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 2 droite"},
	["Torso_Rib_R03"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 3 droite"},
	["Torso_Rib_R04"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 4 droite"},
	["Torso_Rib_R05"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 5 droite"},
	["Torso_Rib_R06"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 6 droite"},
	["Torso_Rib_R07"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 7 droite"},
	["Torso_Rib_R08"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 8 droite"},
	["Torso_Rib_R09"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 9 droite"},
	["Torso_Rib_R10"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 10 droite"},
	["Torso_Rib_R11"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 11 droite (flottante)"},
	["Torso_Rib_R12"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Côte 12 droite (flottante)"},
	["Torso_SacroiliacCartilage"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Cartilages des articulations sacro-iliaques"},
	["Torso_Sacrum"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Sacrum (ailes, promontoire, foramens sacrés, crête sacrale)"},
	["Torso_Scapula_L"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Omoplate gauche (épine, acromion, processus coracoïde, cavité glénoïde)"},
	["Torso_Scapula_R"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Omoplate droite (épine, acromion, processus coracoïde, cavité glénoïde)"},
	["Torso_SmallIntestine_1"] = {region="Torso", cat="organ", color={0.92,0.66,0.58}, info="Intestin grêle - jéjunum"},
	["Torso_SmallIntestine_2"] = {region="Torso", cat="organ", color={0.9,0.68,0.6}, info="Intestin grêle - iléon"},
	["Torso_SpinalCord"] = {region="Torso", cat="nerve", color={0.93,0.88,0.78}, info="Moelle épinière (renflements, cône terminal), queue de cheval, filum terminal"},
	["Torso_SpinalNerves"] = {region="Torso", cat="nerve", color={0.96,0.88,0.55}, info="Racines des nerfs spinaux avec ganglions spinaux, chaînes sympathiques"},
	["Torso_Spleen"] = {region="Torso", cat="organ", color={0.46,0.12,0.2}, info="Rate"},
	["Torso_SternoclavicularDiscs"] = {region="Torso", cat="cartilage", color={0.8,0.86,0.9}, info="Disques articulaires sterno-claviculaires"},
	["Torso_Sternum"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Sternum (manubrium, corps, processus xiphoïde)"},
	["Torso_Stomach"] = {region="Torso", cat="organ", color={0.86,0.6,0.52}, info="Estomac (fundus, corps, antre, pylore, vaisseaux des courbures)"},
	["Torso_Thyroid"] = {region="Torso", cat="gland", color={0.62,0.22,0.18}, info="Glande thyroïde (deux lobes et isthme)"},
	["Torso_Trachea"] = {region="Torso", cat="organ", color={0.88,0.75,0.7}, info="Trachée (anneaux cartilagineux et paroi membraneuse postérieure)"},
	["Torso_Ureters"] = {region="Torso", cat="organ", color={0.88,0.76,0.62}, info="Uretères"},
	["Torso_Veins_Abdomen"] = {region="Torso", cat="vessel", color={0.2,0.25,0.55}, info="Veine cave inférieure, veines hépatiques, rénales, système porte, veines iliaques"},
	["Torso_Veins_Thorax"] = {region="Torso", cat="vessel", color={0.2,0.25,0.55}, info="Veine cave supérieure, troncs brachio-céphaliques, jugulaires internes, subclavières, azygos"},
	["Torso_Vertebra_C3"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre cervicale C3 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_C4"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre cervicale C4 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_C5"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre cervicale C5 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_C6"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre cervicale C6 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_C7"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre cervicale C7 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_L1"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre lombaire L1 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_L2"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre lombaire L2 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_L3"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre lombaire L3 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_L4"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre lombaire L4 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_L5"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre lombaire L5 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T1"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T1 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T10"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T10 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T11"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T11 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T12"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T12 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T2"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T2 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T3"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T3 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T4"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T4 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T5"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T5 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T6"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T6 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T7"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T7 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T8"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T8 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
	["Torso_Vertebra_T9"] = {region="Torso", cat="bone", color={0.89,0.85,0.75}, info="Vertèbre thoracique T9 (corps, pédicules, lames, processus épineux, transverses et articulaires)"},
}

------------------------------------------------------------------------------------------
-- RIG R6 ARTICULÉ (généré par src/make_lua.py à partir de src/rig_spec.py : ne pas modifier)
-- Espace du rig = repère du HumanoidRootPart : X = droite du personnage, Y = haut, Z = arrière
-- (le personnage regarde vers -Z), sol à Y = -3. center / size : pièce au repos ; c0 / c1 :
-- Motor6D (x, y, z, R00..R22) ; pivot : centre de l'articulation dans l'espace du rig.
------------------------------------------------------------------------------------------
local RIG = {
	rigType = "R15",
	hipHeight = 2,
	parts = {
		{ name = "HumanoidRootPart", center = {0, 0, 0}, size = {2, 2, 1} },
		{ name = "Torso", center = {0, 0, 0}, size = {2, 2, 1}, parent = "HumanoidRootPart" },
		{ name = "Head", center = {0, 1.5, 0}, size = {2, 1, 1}, parent = "Torso" },
		{ name = "RightUpperArm", center = {1.5, 0.5, 0}, size = {1, 1, 1}, parent = "Torso" },
		{ name = "RightLowerArm", center = {1.5, -0.5, 0}, size = {1, 1, 1}, parent = "RightUpperArm" },
		{ name = "LeftUpperArm", center = {-1.5, 0.5, 0}, size = {1, 1, 1}, parent = "Torso" },
		{ name = "LeftLowerArm", center = {-1.5, -0.5, 0}, size = {1, 1, 1}, parent = "LeftUpperArm" },
		{ name = "RightUpperLeg", center = {0.5, -1.475, 0}, size = {1, 0.95, 1}, parent = "Torso" },
		{ name = "RightLowerLeg", center = {0.5, -2.475, 0}, size = {1, 1.05, 1}, parent = "RightUpperLeg" },
		{ name = "LeftUpperLeg", center = {-0.5, -1.475, 0}, size = {1, 0.95, 1}, parent = "Torso" },
		{ name = "LeftLowerLeg", center = {-0.5, -2.475, 0}, size = {1, 1.05, 1}, parent = "LeftUpperLeg" },
	},
	joints = {
		{ name = "RootJoint", part0 = "HumanoidRootPart", part1 = "Torso", pivot = {0, 0, 0}, c0 = {0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0}, c1 = {0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0} },
		{ name = "Neck", part0 = "Torso", part1 = "Head", pivot = {0, 1, 0}, c0 = {0, 1, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0}, c1 = {0, -0.5, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0} },
		{ name = "RightShoulder", part0 = "Torso", part1 = "RightUpperArm", pivot = {1.2, 0.66, 0}, c0 = {1.2, 0.66, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {-0.3, 0.16, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "RightElbow", part0 = "RightUpperArm", part1 = "RightLowerArm", pivot = {1.5, 0, 0}, c0 = {0, -0.5, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0, 0.5, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "LeftShoulder", part0 = "Torso", part1 = "LeftUpperArm", pivot = {-1.2, 0.66, 0}, c0 = {-1.2, 0.66, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0.3, 0.16, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "LeftElbow", part0 = "LeftUpperArm", part1 = "LeftLowerArm", pivot = {-1.5, 0, 0}, c0 = {0, -0.5, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0, 0.5, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "RightHip", part0 = "Torso", part1 = "RightUpperLeg", pivot = {0.5, -1, 0}, c0 = {0.5, -1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0, 0.475, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "RightKnee", part0 = "RightUpperLeg", part1 = "RightLowerLeg", pivot = {0.5, -1.95, 0}, c0 = {0, -0.475, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0, 0.525, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "LeftHip", part0 = "Torso", part1 = "LeftUpperLeg", pivot = {-0.5, -1, 0}, c0 = {-0.5, -1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0, 0.475, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
		{ name = "LeftKnee", part0 = "LeftUpperLeg", part1 = "LeftLowerLeg", pivot = {-0.5, -1.95, 0}, c0 = {0, -0.475, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1}, c1 = {0, 0.525, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1} },
	},
	poseOrder = {"Torso", "Head", "RightUpperArm", "RightLowerArm", "LeftUpperArm", "LeftLowerArm", "RightUpperLeg", "RightLowerLeg", "LeftUpperLeg", "LeftLowerLeg"},
	hand = { name = "RightHand", part0 = "RightLowerArm", center = {1.5, -0.95, 0}, size = {0.3, 0.1, 0.3}, attachment = "RightGripAttachment", rotation = {1, 0, 0, 0, 0, 1, 0, -1, 0} },
	labels = {Torso = "Torse", Head = "Tête", RightUpperArm = "Bras droit (haut)", RightLowerArm = "Avant-bras droit", LeftUpperArm = "Bras gauche (haut)", LeftLowerArm = "Avant-bras gauche", RightUpperLeg = "Cuisse droite", RightLowerLeg = "Jambe droite (bas)", LeftUpperLeg = "Cuisse gauche", LeftLowerLeg = "Jambe gauche (bas)"},
}

------------------------------------------------------------------------------------------
-- CONSTANTES DÉRIVÉES (ne pas modifier)
------------------------------------------------------------------------------------------
local Workspace = workspace

-- Position attendue des marqueurs dans l'espace du rig (relatif au centre du Torso,
-- axes Roblox : le personnage regarde vers -Z, sa gauche est en -X).
local MARKER_EXPECTED = {
	A = Vector3.new(0, 0, 0),
	B = Vector3.new(0, 2.2, 0),
	C = Vector3.new(-1.5, 0, 0),
	D = Vector3.new(0, 0, -0.6),
}

local function vecOf(t)
	return Vector3.new(t[1], t[2], t[3])
end

local function cframeOf(t)
	return CFrame.new(t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9], t[10], t[11], t[12])
end

-- Les 10 pièces du corps, chaque parent avant ses enfants.
local PART_ORDER = RIG.poseOrder
local PART_SIZE, REST = {}, {}
for _, p in ipairs(RIG.parts) do
	PART_SIZE[p.name] = vecOf(p.size)
	-- Pose de repos dans l'espace du rig (= Part0.CFrame * C0 * C1:Inverse() avec Transform neutre).
	REST[p.name] = CFrame.new(vecOf(p.center))
end
local IS_BODY_PART = {}
for _, name in ipairs(PART_ORDER) do
	IS_BODY_PART[name] = true
end

-- Motor6D : RootJoint et Neck rangés dans leur Part0 (comme en R6 : HumanoidRootPart.RootJoint,
-- Torso.Neck), ceux des membres dans leur Part1 (comme en R15 : RightLowerArm.RightElbow).
local MOTORS = {}
for _, j in ipairs(RIG.joints) do
	local inPart0 = j.part0 == "HumanoidRootPart" or j.part1 == "Head"
	table.insert(MOTORS, {
		name = j.name, parent = inPart0 and j.part0 or j.part1, p0 = j.part0, p1 = j.part1,
		c0 = cframeOf(j.c0), c1 = cframeOf(j.c1),
	})
end

-- Anciennes régions R6 (fichiers d'avant les coudes et genoux : bras ou jambe d'un seul tenant) :
-- pièce du haut ou du bas selon la hauteur par rapport au coude / genou.
local LEGACY_LIMBS = {}
for _, j in ipairs(RIG.joints) do
	local limb, n = string.gsub(j.part0, "Upper", "")
	if n == 1 and j.part1 == (string.gsub(j.part0, "Upper", "Lower")) then
		LEGACY_LIMBS[limb] = { upper = j.part0, lower = j.part1, splitY = j.pivot[2] }
	end
end
-- Membres d'un ancien rig R6 à 6 pièces (il est renommé, pas réutilisé).
local LEGACY_R6_PARTS = { "Left Arm", "Right Arm", "Left Leg", "Right Leg" }

-- Boîtes (espace rig) pour le repli « par position » : centre et demi-dimensions.
-- La boîte de la tête est un peu agrandie (le crâne déborde du bloc 2x1x1).
local PART_BOX = {}
for _, name in ipairs(PART_ORDER) do
	local h = PART_SIZE[name] / 2
	if name == "Head" then
		h = Vector3.new(h.X, 0.75, 0.75)
	end
	table.insert(PART_BOX, { name = name, c = REST[name].Position, h = h })
end

-- Devine la catégorie d'une pièce absente du manifeste (l'ordre compte).
local CATEGORY_HINTS = {
	{ "Survivor_Hat", "gear" }, { "Survivor_Backpack", "gear" }, { "Survivor_", "skin" }, { "Skin_", "skin" },
	{ "Cartilage", "cartilage" }, { "Labr", "cartilage" }, { "Menisc", "disc" }, { "Disc", "disc" },
	{ "Ligament", "ligament" }, { "Tendon", "ligament" }, { "Fascia", "ligament" },
	{ "Retinacul", "ligament" }, { "Membrane", "ligament" },
	{ "Arter", "vessel" }, { "Vein", "vessel" }, { "Vessel", "vessel" }, { "Aorta", "vessel" },
	{ "SpinalCord", "nerve" }, { "Nerve", "nerve" }, { "Plexus", "nerve" }, { "Cauda", "nerve" },
	{ "Muscle", "muscle" }, { "Diaphragm", "muscle" },
	{ "Brain", "brain" }, { "Cerebel", "brain" },
	{ "Teeth", "tooth" }, { "Tooth", "tooth" }, { "Eye", "eye" },
	{ "Gland", "gland" }, { "Thyroid", "gland" }, { "Adrenal", "gland" },
	{ "Lung", "organ" }, { "Heart", "organ" }, { "Liver", "organ" }, { "Stomach", "organ" },
	{ "Kidney", "organ" }, { "Spleen", "organ" }, { "Pancreas", "organ" }, { "Intestin", "organ" },
	{ "Colon", "organ" }, { "Bladder", "organ" }, { "Rectum", "organ" }, { "Duoden", "organ" },
	{ "Esophag", "organ" }, { "Trachea", "organ" }, { "Bronch", "organ" }, { "Larynx", "organ" },
	{ "Tongue", "organ" }, { "Ureter", "organ" }, { "Appendix", "organ" },
}
local function partLabel(name)
	return (RIG.labels[name] or name) .. " (" .. name .. ")"
end

------------------------------------------------------------------------------------------
-- OUTILS
------------------------------------------------------------------------------------------
local function fmt(n, d)
	return string.format("%." .. tostring(d or 3) .. "f", n)
end

local function vecStr(v)
	return "(" .. fmt(v.X, 3) .. ", " .. fmt(v.Y, 3) .. ", " .. fmt(v.Z, 3) .. ")"
end

local function newReport()
	return {
		warnings = {},
		notes = {},
		sources = {},
		perPart = {},
		perCat = {},
		total = 0,
		replaced = 0,
		failed = 0,
		positional = {},
		unknown = {},
		removedJoints = 0,
		skin = 0,
		skinResult = nil,
	}
end

local function addWarning(report, msg)
	table.insert(report.warnings, msg)
	warn("[Anatomie R6] " .. msg)
end

local function addNote(report, msg)
	table.insert(report.notes, msg)
end

-- Noms candidats : le nom tel quel puis sans suffixes d'export (".001", "_Mesh", "_Geo").
local function nameCandidates(name)
	local list, seen = {}, {}
	local function add(n)
		if n ~= "" and not seen[n] then
			seen[n] = true
			table.insert(list, n)
		end
	end
	add(name)
	local n = name
	for _ = 1, 3 do
		n = string.gsub(n, "%s+$", "")
		n = string.gsub(n, "%.%d+$", "")
		n = string.gsub(n, "[%._]?[Mm]esh$", "")
		n = string.gsub(n, "[%._]?[Gg]eo$", "")
		add(n)
	end
	return list
end

-- "A".."D" si l'instance est un marqueur d'alignement, sinon nil.
local function markerLetter(inst)
	for _, n in ipairs(nameCandidates(inst.Name)) do
		local letter = string.match(n, "^REF_([ABCD])$")
		if letter then
			return letter
		end
	end
	return nil
end

-- Position monde d'un marqueur (BasePart, ou Model enveloppant le maillage).
local function markerPosition(inst)
	if inst:IsA("BasePart") then
		return inst.Position
	end
	if inst:IsA("Model") then
		local ok, cf = pcall(function()
			return (inst:GetBoundingBox())
		end)
		if ok and cf then
			return cf.Position
		end
	end
	for _, d in ipairs(inst:GetDescendants()) do
		if d:IsA("BasePart") then
			return d.Position
		end
	end
	return nil
end

local function selfAndDescendants(inst)
	local list = inst:GetDescendants()
	table.insert(list, 1, inst)
	return list
end

-- Vrai si `inst` est à l'intérieur d'un autre marqueur (maillage enveloppé dans un Model
-- « REF_A » par exemple) : on ne compte alors que l'enveloppe.
local function insideMarker(inst, root)
	local a = inst.Parent
	while a and a ~= game do
		if markerLetter(a) then
			return true
		end
		if a == root then
			break
		end
		a = a.Parent
	end
	return false
end

local function findRefAs(inst)
	local found = {}
	for _, d in ipairs(selfAndDescendants(inst)) do
		if markerLetter(d) == "A" and not insideMarker(d, inst) then
			table.insert(found, d)
		end
	end
	return found
end

local function countRefAs(inst)
	return #findRefAs(inst)
end

-- Conteneur d'un import = plus haut ancêtre du marqueur REF_A qui ne contient QUE ce REF_A
-- (sans dépasser `bound` s'il est donné ; jamais le Workspace ni un autre service).
local function containerFor(marker, bound)
	local best = nil
	local a = marker.Parent
	while a and a ~= game and a.Parent ~= game do
		if countRefAs(a) ~= 1 then
			break
		end
		best = a
		if a == bound then
			break
		end
		a = a.Parent
	end
	return best
end

local function isInRig(inst, rig)
	return rig ~= nil and (inst == rig or inst:IsDescendantOf(rig))
end

local function findContainers(report)
	local rig = Workspace:FindFirstChild(CONFIG.RIG_NAME)
	local requests = {} -- { marker = REF_A, bound = instance|nil }

	local selection = {}
	pcall(function()
		selection = game:GetService("Selection"):Get()
	end)

	for _, s in ipairs(selection) do
		if isInRig(s, rig) then
			addNote(report, "Sélection « " .. s.Name .. " » ignorée (fait partie du rig).")
		else
			local before = #requests
			local refs = findRefAs(s)
			if #refs > 0 then
				for _, m in ipairs(refs) do
					table.insert(requests, { marker = m, bound = s })
				end
			else
				-- Une pièce isolée a été sélectionnée : on remonte jusqu'à l'import qui la contient.
				local a = s.Parent
				while a and a ~= game do
					local f = findRefAs(a)
					if #f > 0 then
						for _, m in ipairs(f) do
							local c = containerFor(m, nil)
							if c and (s == c or s:IsDescendantOf(c)) then
								table.insert(requests, { marker = m, bound = nil })
							end
						end
						break
					end
					if a.Parent == game then
						break
					end
					a = a.Parent
				end
			end
			if #requests == before then
				addNote(report, "Sélection « " .. s.Name .. " » ignorée (aucun import contenant REF_A).")
			end
		end
	end

	if #selection > 0 and #requests == 0 then
		addNote(report, "La sélection ne contient aucun import anatomique : recherche dans tout le Workspace.")
	end
	if #requests == 0 then
		for _, d in ipairs(Workspace:GetDescendants()) do
			if markerLetter(d) == "A" and not isInRig(d, rig) then
				table.insert(requests, { marker = d, bound = nil })
			end
		end
	end

	local containers, seen = {}, {}
	for _, r in ipairs(requests) do
		local c = containerFor(r.marker, r.bound)
		if not c then
			addWarning(report, "Marqueur « " .. r.marker:GetFullName() .. " » posé directement dans le Workspace "
				.. "(ou import mélangé à un autre) : regroupez l'import dans un Model puis relancez.")
		elseif not seen[c] then
			seen[c] = true
			table.insert(containers, c)
		end
	end
	return containers
end

-- Marqueurs d'un conteneur : lettre -> { inst, pos } ; liste de toutes les instances marqueurs.
local function findMarkers(container, report)
	local markers, all = {}, {}
	for _, d in ipairs(selfAndDescendants(container)) do
		local letter = markerLetter(d)
		if letter and d ~= container and not insideMarker(d, container) then
			table.insert(all, d)
			if markers[letter] then
				addWarning(report, "Marqueur REF_" .. letter .. " en double dans « " .. container.Name
					.. " » : le premier est utilisé.")
			else
				local pos = markerPosition(d)
				if pos then
					markers[letter] = { inst = d, pos = pos }
				end
			end
		end
	end
	return markers, all
end

-- Repère orthonormé direct (Gram-Schmidt) construit à partir de deux vecteurs.
local function orthoFrame(u, v)
	if u.Magnitude < 1e-9 then
		return nil
	end
	local e1 = u.Unit
	local w = v - e1 * v:Dot(e1)
	if w.Magnitude < 1e-6 * math.max(v.Magnitude, 1e-9) then
		return nil
	end
	local e2 = w.Unit
	local e3 = e1:Cross(e2)
	return CFrame.fromMatrix(Vector3.new(0, 0, 0), e1, e2, e3)
end

-- Similitude import -> rig : p_rig = R * ((p - A) * scale) + A_attendu.
-- Retourne { scale, rot (CFrame de rotation pure), origin, residual } ou nil, raison.
local function solveTransform(markers, containerName, report)
	local A, B, C, D = markers.A, markers.B, markers.C, markers.D
	if not (A and B and C) then
		local missing = {}
		for _, l in ipairs({ "A", "B", "C" }) do
			if not markers[l] then
				table.insert(missing, "REF_" .. l)
			end
		end
		return nil, "marqueur(s) manquant(s) : " .. table.concat(missing, ", ")
	end
	local eA, eB, eC, eD = MARKER_EXPECTED.A, MARKER_EXPECTED.B, MARKER_EXPECTED.C, MARKER_EXPECTED.D
	local ab, ac = B.pos - A.pos, C.pos - A.pos
	if ab.Magnitude < 1e-7 or ac.Magnitude < 1e-7 then
		return nil, "marqueurs confondus (import de taille nulle ?)"
	end

	local scale = (eB - eA).Magnitude / ab.Magnitude
	local scaleAC = (eC - eA).Magnitude / ac.Magnitude
	if math.abs(scaleAC / scale - 1) > CONFIG.MARKER_SCALE_TOLERANCE then
		addWarning(report, "« " .. containerName .. " » : échelles incohérentes (AB " .. fmt(scale, 5)
			.. " / AC " .. fmt(scaleAC, 5) .. ") - mise à l'échelle non uniforme ?")
	end

	-- Miroir : signe du produit mixte (B-A)x(C-A).(D-A) comparé à celui attendu.
	if D then
		local ad = D.pos - A.pos
		local tripleImp = ab:Cross(ac):Dot(ad)
		local tripleExp = (eB - eA):Cross(eC - eA):Dot(eD - eA)
		local rel = math.abs(tripleImp) / (ab.Magnitude * ac.Magnitude * math.max(ad.Magnitude, 1e-9))
		if rel < 0.2 then
			addWarning(report, "« " .. containerName .. " » : REF_D presque coplanaire, impossible de vérifier "
				.. "l'absence de miroir.")
		elseif (tripleImp > 0) ~= (tripleExp > 0) then
			return nil, "IMPORT EN MIROIR (repère indirect détecté par REF_D). Les maillages sont inversés "
				.. "gauche/droite et ne peuvent pas être corrigés par une rotation : réimportez sans "
				.. "inversion d'axe (réglages World Forward / World Up cohérents, pas d'échelle négative)."
		end
		local scaleAD = (eD - eA).Magnitude / math.max(ad.Magnitude, 1e-9)
		if math.abs(scaleAD / scale - 1) > CONFIG.MARKER_SCALE_TOLERANCE then
			addWarning(report, "« " .. containerName .. " » : échelle AD incohérente (" .. fmt(scaleAD, 5)
				.. " au lieu de " .. fmt(scale, 5) .. ").")
		end
	else
		addWarning(report, "« " .. containerName .. " » : REF_D absent, impossible de détecter un import en miroir.")
	end

	local fImp = orthoFrame(ab, ac)
	local fExp = orthoFrame(eB - eA, eC - eA)
	if not fImp or not fExp then
		return nil, "marqueurs REF_A, REF_B, REF_C alignés : rotation indéterminée"
	end
	local rot = fExp * fImp:Inverse()

	-- Écart résiduel sur chaque marqueur.
	local residual = 0
	for letter, m in pairs(markers) do
		local p = rot * ((m.pos - A.pos) * scale) + eA
		residual = math.max(residual, (p - MARKER_EXPECTED[letter]).Magnitude)
	end
	if residual > CONFIG.MARKER_ABORT_RESIDUAL then
		return nil, "marqueurs incohérents (écart " .. fmt(residual, 3) .. " stud) : fichier modifié ou "
			.. "marqueurs déplacés ?"
	elseif residual > CONFIG.MARKER_WARN_RESIDUAL then
		addWarning(report, "« " .. containerName .. " » : écart des marqueurs " .. fmt(residual, 3) .. " stud.")
	end

	return { scale = scale, rot = rot, origin = A.pos, expectedA = eA, residual = residual }
end

-- CFrame importé -> CFrame dans l'espace du rig (relatif au Torso au repos).
local function toRigSpace(T, cf)
	local pos = T.rot * ((cf.Position - T.origin) * T.scale) + T.expectedA
	local rotOnly = T.rot * (cf - cf.Position)
	return CFrame.new(pos) * rotOnly
end

local function nearestPart(pos)
	local best, bestScore = "Torso", math.huge
	for _, b in ipairs(PART_BOX) do
		local d = pos - b.c
		local ox = math.max(math.abs(d.X) - b.h.X, 0)
		local oy = math.max(math.abs(d.Y) - b.h.Y, 0)
		local oz = math.max(math.abs(d.Z) - b.h.Z, 0)
		local outside = math.sqrt(ox * ox + oy * oy + oz * oz)
		local norm = math.max(math.abs(d.X) / b.h.X, math.abs(d.Y) / b.h.Y, math.abs(d.Z) / b.h.Z)
		local score = outside * 1000 + norm
		if score < bestScore then
			best, bestScore = b.name, score
		end
	end
	return best
end

-- Vrai si `region` désigne une pièce du rig ou une ancienne région R6 (bras / jambe entière).
local function isRegion(region)
	return region ~= nil and (IS_BODY_PART[region] == true or LEGACY_LIMBS[region] ~= nil)
end

-- Pièce du rig d'une région ; une ancienne région R6 est coupée au coude / genou selon la hauteur
-- `pos` (espace rig) de la pièce. nil si la région est inconnue.
local function resolveRegion(region, pos)
	if region == nil then
		return nil
	end
	if IS_BODY_PART[region] then
		return region
	end
	local legacy = LEGACY_LIMBS[(string.gsub(region, " ", ""))]
	if legacy then
		return pos.Y >= legacy.splitY and legacy.upper or legacy.lower
	end
	return nil
end

-- Région d'après le nom (comme src/rig_spec.py, region_of_name) : préfixe avant « _ » pour l'anatomie
-- (LeftUpperArm_Humerus) ; tenue Survivor_<pièce> / Skin_<pièce>, le visage et le bonnet allant sur
-- la tête, le sac sur le torse.
local SKIN_REGION = { Face = "Head", Hat = "Head", Backpack = "Torso" }
local function regionFromName(name)
	local skin = string.match(name, "^Survivor_(%a+)$") or string.match(name, "^Skin_(%a+)$")
	if skin then
		local r = SKIN_REGION[skin] or skin
		return isRegion(r) and r or nil
	end
	local prefix = string.match(name, "^(%a+)_")
	if isRegion(prefix) then
		return prefix
	end
	return nil
end

local function guessCategory(name)
	for _, h in ipairs(CATEGORY_HINTS) do
		if string.find(name, h[1], 1, true) then
			return h[2]
		end
	end
	return "bone"
end

-- Identifie une pièce : nom canonique, entrée du manifeste, région.
local function identify(part, container)
	for _, n in ipairs(nameCandidates(part.Name)) do
		if PARTS[n] then
			return n, PARTS[n], PARTS[n].region
		end
	end
	-- Hors manifeste : on garde le nom débarrassé de ses suffixes d'export (".001"...).
	local cands = nameCandidates(part.Name)
	for i = #cands, 1, -1 do
		local r = regionFromName(cands[i])
		if r then
			return cands[i], nil, r
		end
	end
	-- Maillage au nom générique enveloppé dans un Model / dossier portant le vrai nom.
	local a = part.Parent
	while a and a ~= Workspace and a ~= game do
		for _, n in ipairs(nameCandidates(a.Name)) do
			if PARTS[n] then
				return n, PARTS[n], PARTS[n].region
			end
		end
		if a == container then
			break
		end
		a = a.Parent
	end
	return part.Name, nil, nil
end

local function colorFromList(t)
	if type(t) == "table" and #t >= 3 then
		return Color3.new(t[1], t[2], t[3])
	end
	return Color3.new(1, 1, 1)
end

------------------------------------------------------------------------------------------
-- RIG R6
------------------------------------------------------------------------------------------
-- Réutilise l'enfant `name` s'il est du bon type (acceptClass, par défaut className), sinon le crée.
local function getOrCreate(parent, className, name, acceptClass)
	local inst = parent:FindFirstChild(name)
	if inst and inst:IsA(acceptClass or className) then
		return inst, false
	end
	inst = Instance.new(className)
	inst.Name = name
	inst.Parent = parent
	return inst, true
end

local function findGroundY(pos, exclude)
	local params = RaycastParams.new()
	local okFilter = pcall(function()
		params.FilterType = Enum.RaycastFilterType.Exclude
	end)
	if not okFilter then
		pcall(function()
			params.FilterType = Enum.RaycastFilterType.Blacklist
		end)
	end
	params.FilterDescendantsInstances = exclude
	pcall(function()
		params.IgnoreWater = true
	end)
	pcall(function()
		params.RespectCanCollide = true
	end)
	local origins = { pos + Vector3.new(0, 10, 0), Vector3.new(pos.X, pos.Y + 2000, pos.Z) }
	for _, o in ipairs(origins) do
		local ok, res = pcall(function()
			return Workspace:Raycast(o, Vector3.new(0, -10000, 0), params)
		end)
		if ok and res then
			return res.Position.Y, res.Instance
		end
	end
	return nil, nil
end

local DEFAULT_SKIN_COLORS = {
	Head = Color3.fromRGB(212, 156, 120),
	Torso = Color3.fromRGB(72, 80, 48),
	RightUpperArm = Color3.fromRGB(72, 80, 48),
	LeftUpperArm = Color3.fromRGB(72, 80, 48),
	RightLowerArm = Color3.fromRGB(212, 156, 120),
	LeftLowerArm = Color3.fromRGB(212, 156, 120),
	RightUpperLeg = Color3.fromRGB(42, 54, 78),
	LeftUpperLeg = Color3.fromRGB(42, 54, 78),
	RightLowerLeg = Color3.fromRGB(98, 64, 40),
	LeftLowerLeg = Color3.fromRGB(98, 64, 40),
}

local function skinColorFor(partName)
	local c = type(CONFIG.SKIN_COLORS) == "table" and CONFIG.SKIN_COLORS[partName]
	if typeof(c) == "Color3" then
		return c
	end
	return DEFAULT_SKIN_COLORS[partName] or Color3.new(1, 1, 1)
end

-- Attributs communs : Anat_Peau = élément de peau visible (utilisé par les outils).
local function setSkinAttributes(part, isSkin)
	pcall(function()
		part:SetAttribute("Anat_Peau", isSkin or nil)
		part:SetAttribute("Anat_TransparencePeau", CONFIG.SKIN_TRANSPARENCY)
		part:SetAttribute("Anat_Masque", nil)
	end)
end

-- Bloc Roblox du rig utilisé comme peau (mode "blocs").
local function applySkinBlock(part, partName)
	part.Transparency = CONFIG.SKIN_TRANSPARENCY
	part.Color = skinColorFor(partName)
	part.Material = CONFIG.SKIN_MATERIAL
	part.Reflectance = 0
	part.CastShadow = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	setSkinAttributes(part, true)
end

-- Bloc Roblox du rig remplacé par la peau importée : invisible (collisions et Motor6D seulement).
local function hideSkinBlock(part, partName)
	part.Transparency = 1
	part.Color = skinColorFor(partName)
	part.Material = CONFIG.SKIN_MATERIAL
	part.Reflectance = 0
	part.CastShadow = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	setSkinAttributes(part, false)
end

-- Pièce de tenue importée (Survivor_*) : visible ou non selon le mode.
local function setSkinMesh(part, visible)
	part.Transparency = visible and CONFIG.SKIN_TRANSPARENCY or 1
	setSkinAttributes(part, visible)
end

-- Vrai si le Model est un ancien rig R6 à 6 pièces (bras et jambes d'un seul tenant).
local function isLegacyRig(model)
	for _, n in ipairs(LEGACY_R6_PARTS) do
		if model:FindFirstChild(n) then
			return true
		end
	end
	return false
end

-- Construit ou complète le rig articulé.
-- Retourne { model, parts = {nom -> Part}, folders = {nom -> Folder}, anat, skin, created }.
local function ensureRig(placementPos, exclude, report)
	local rig = Workspace:FindFirstChild(CONFIG.RIG_NAME)
	if rig and not rig:IsA("Model") then
		addWarning(report, "« " .. CONFIG.RIG_NAME .. " » existe mais n'est pas un Model : un nouveau rig est créé.")
		rig = nil
	end
	if rig and isLegacyRig(rig) then
		local oldName = CONFIG.RIG_NAME .. "_ancien"
		rig.Name = oldName
		addWarning(report, "Ancien rig R6 à 6 pièces trouvé : renommé « " .. oldName .. " » (conservé, supprimez-le "
			.. "s'il ne sert plus). Un rig articulé neuf est créé.")
		rig = nil
	end
	local created = false
	local baseCF = nil
	if rig then
		local hrp = rig:FindFirstChild("HumanoidRootPart")
		local torso = rig:FindFirstChild("Torso")
		if hrp and hrp:IsA("BasePart") then
			baseCF = hrp.CFrame
		elseif torso and torso:IsA("BasePart") then
			baseCF = torso.CFrame
		end
		addNote(report, "Rig existant « " .. CONFIG.RIG_NAME .. " » réutilisé (fusion).")
	else
		rig = Instance.new("Model")
		rig.Name = CONFIG.RIG_NAME
		created = true
	end
	if not baseCF then
		local groundY, hit = findGroundY(placementPos, exclude)
		if groundY then
			baseCF = CFrame.new(placementPos.X, groundY + 3, placementPos.Z)
			addNote(report, "Rig posé au sol (" .. (hit and hit.Name or "?") .. ", Y = " .. fmt(groundY, 2) .. ").")
		else
			baseCF = CFrame.new(placementPos.X, 3, placementPos.Z)
			addNote(report, "Aucun sol trouvé sous l'import : Torso placé à Y = 3.")
		end
	end

	local parts = {}
	local hrp, newHrp = getOrCreate(rig, "Part", "HumanoidRootPart", "BasePart")
	if newHrp then
		hrp.CFrame = baseCF
	end
	hrp.Size = PART_SIZE.HumanoidRootPart
	hrp.Transparency = 1
	hrp.CanCollide = true
	hrp.CastShadow = false
	hrp.Anchored = CONFIG.ANCHOR_ROOT
	hrp.TopSurface = Enum.SurfaceType.Smooth
	hrp.BottomSurface = Enum.SurfaceType.Smooth
	parts.HumanoidRootPart = hrp

	for _, name in ipairs(PART_ORDER) do
		local p, isNew = getOrCreate(rig, "Part", name, "BasePart")
		if isNew then
			p.CFrame = baseCF * REST[name]
		end
		p.Size = PART_SIZE[name]
		p.Anchored = false
		p.CanCollide = (name == "Torso" or name == "Head")
		p.Massless = false
		applySkinBlock(p, name) -- apparence définitive fixée par finalizeSkin, après les imports
		parts[name] = p
	end

	local head = parts.Head
	local mesh = head:FindFirstChildOfClass("SpecialMesh")
	if not mesh then
		mesh = Instance.new("SpecialMesh")
		mesh.Name = "Mesh"
		mesh.Parent = head
	end
	mesh.MeshType = Enum.MeshType.Head
	mesh.Scale = Vector3.new(1.25, 1.25, 1.25)

	for _, m in ipairs(MOTORS) do
		local motor = getOrCreate(parts[m.parent], "Motor6D", m.name)
		motor.Part0 = parts[m.p0]
		motor.Part1 = parts[m.p1]
		motor.C0 = m.c0
		motor.C1 = m.c1
		motor.MaxVelocity = 0.1
	end

	-- Main invisible pour les outils (prise des rigs R15 : RightHand.RightGripAttachment), soudée à
	-- l'avant-bras droit au niveau de la paume.
	local H = RIG.hand
	local forearm = parts[H.part0]
	local wristC0 = CFrame.new(vecOf(H.center) - REST[H.part0].Position)
	local hand, newHand = getOrCreate(rig, "Part", H.name, "BasePart")
	if newHand then
		hand.CFrame = forearm.CFrame * wristC0
	end
	hand.Size = vecOf(H.size)
	hand.Transparency = 1
	hand.CanCollide = false
	hand.CanTouch = false
	hand.CanQuery = false
	hand.Massless = true
	hand.CastShadow = false
	hand.Anchored = false
	parts[H.name] = hand
	local grip = getOrCreate(hand, "Attachment", H.attachment)
	local r = H.rotation
	grip.CFrame = CFrame.new(0, 0, 0, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9])
	local wrist = getOrCreate(hand, "Weld", "RightWrist", "JointInstance")
	wrist.Part0 = forearm
	wrist.Part1 = hand
	wrist.C0 = wristC0
	wrist.C1 = CFrame.new()

	local humanoid = rig:FindFirstChildOfClass("Humanoid")
	if not humanoid then
		humanoid = Instance.new("Humanoid")
		humanoid.Parent = rig
	end
	-- Type R15 : la hauteur du personnage vient de HipHeight (2) et non de la longueur des jambes,
	-- et les outils se tiennent par RightHand.
	humanoid.RigType = Enum.HumanoidRigType[RIG.rigType]
	humanoid.HipHeight = RIG.hipHeight
	pcall(function()
		humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	end)
	-- Rig sur mesure : pas de mise à l'échelle automatique R15, et pas de mort « cou cassé » (le Neck
	-- relie Torso et Head, il n'y a pas d'UpperTorso comme dans un R15 standard).
	pcall(function()
		humanoid.AutomaticScalingEnabled = false
	end)
	pcall(function()
		humanoid.RequiresNeck = false
	end)

	rig.PrimaryPart = hrp
	pcall(function()
		rig:SetAttribute("Anat_Rig", "R6 articulé")
	end)

	local anat = getOrCreate(rig, "Folder", "Anatomie")
	local folders = {}
	for _, name in ipairs(PART_ORDER) do
		folders[name] = getOrCreate(anat, "Folder", name)
	end
	local skin = getOrCreate(rig, "Folder", "Peau")

	if rig.Parent ~= Workspace then
		rig.Parent = Workspace
	end
	return { model = rig, parts = parts, folders = folders, anat = anat, skin = skin, created = created }
end

-- Apparence finale de la peau, une fois tous les imports traités : pour chaque pièce, la tenue
-- importée (Survivor_*) remplace le bloc Roblox en mode "maillage" ; sinon le bloc sert de peau.
-- Les accessoires (bonnet, sac) ne remplacent aucun bloc : visibles en mode "maillage" seulement.
local function finalizeSkin(rig, report)
	local meshes, covers, count = {}, {}, 0
	for _, d in ipairs(rig.skin:GetDescendants()) do
		if d:IsA("BasePart") then
			local m = d:GetAttribute("Anat_Membre")
			if m and IS_BODY_PART[m] then
				meshes[m] = meshes[m] or {}
				table.insert(meshes[m], d)
				if not d:GetAttribute("Anat_Accessoire") then
					covers[m] = true
				end
				count = count + 1
			end
		end
	end
	local wantMesh = CONFIG.SKIN_MODE ~= "blocs"
	local nMesh, blocks = 0, {}
	for _, name in ipairs(PART_ORDER) do
		local block = rig.parts[name]
		if wantMesh and covers[name] then
			hideSkinBlock(block, name)
			nMesh = nMesh + 1
		else
			applySkinBlock(block, name)
			table.insert(blocks, name)
		end
		for _, m in ipairs(meshes[name] or {}) do
			setSkinMesh(m, wantMesh)
		end
	end

	-- Visage Roblox classique (decal) seulement si la tête est un bloc visible.
	local head = rig.parts.Head
	local face = head:FindFirstChild("face")
	if CONFIG.SHOW_FACE and not (wantMesh and covers.Head) then
		if not (face and face:IsA("Decal")) then
			face = Instance.new("Decal")
			face.Name = "face"
			face.Parent = head
		end
		face.Texture = "rbxasset://textures/face.png"
		face.Face = Enum.NormalId.Front
		face.Transparency = CONFIG.SKIN_TRANSPARENCY
	elseif face and face:IsA("Decal") then
		face:Destroy()
	end

	local mode = (nMesh == #PART_ORDER and "maillage") or (nMesh == 0 and "blocs") or "mixte"
	pcall(function()
		rig.model:SetAttribute("Anat_ModePeau", mode)
		rig.model:SetAttribute("Anat_TransparencePeau", CONFIG.SKIN_TRANSPARENCY)
	end)
	if wantMesh and count == 0 then
		addNote(report, "Aucune tenue importée (pièces Survivor_*) : les blocs Roblox servent de peau.")
	elseif wantMesh and #blocks > 0 then
		addNote(report, "Peau importée absente pour : " .. table.concat(blocks, ", ") .. " (blocs Roblox utilisés).")
	end
	return { mode = mode, meshes = count }
end

------------------------------------------------------------------------------------------
-- TRAITEMENT D'UN IMPORT
------------------------------------------------------------------------------------------
local function applyAnatomyProps(part, cat, entry)
	local catCfg = CONFIG.CATEGORY[cat] or CONFIG.CATEGORY.default
	part.CanCollide = false
	part.CanTouch = false
	part.CanQuery = false
	part.Massless = true
	part.CastShadow = true
	if CONFIG.USE_VERTEX_COLORS then
		part.Color = Color3.new(1, 1, 1)
	elseif entry and entry.color then
		part.Color = colorFromList(entry.color)
	else
		part.Color = colorFromList(catCfg.Color)
	end
	part.Material = catCfg.Material
	part.Reflectance = catCfg.Reflectance
	if CONFIG.RENDER_FIDELITY_PRECISE then
		pcall(function()
			part.RenderFidelity = Enum.RenderFidelity.Precise
		end)
	end
end

local function applySkinMeshProps(part, key, entry, partName)
	part.CanCollide = false
	part.CanTouch = false
	part.CanQuery = false
	part.Massless = true
	part.CastShadow = false
	if CONFIG.USE_VERTEX_COLORS then
		part.Color = Color3.new(1, 1, 1)
	elseif entry and entry.color then
		part.Color = colorFromList(entry.color)
	elseif string.find(key, "Face", 1, true) then
		part.Color = Color3.new(0.07, 0.07, 0.07)
	else
		part.Color = skinColorFor(partName)
	end
	part.Material = CONFIG.SKIN_MATERIAL
	part.Reflectance = 0
	if CONFIG.RENDER_FIDELITY_PRECISE then
		pcall(function()
			part.RenderFidelity = Enum.RenderFidelity.Precise
		end)
	end
end

local function processContainer(container, report, state)
	local cname = container.Name
	local markers, markerInsts = findMarkers(container, report)
	local T, why = solveTransform(markers, cname, report)
	if not T then
		local msg = "Import « " .. cname .. " » IGNORÉ : " .. tostring(why)
		addWarning(report, msg)
		print("[Anatomie R6] " .. msg)
		return
	end

	-- Pièces à traiter (tout BasePart du conteneur hors marqueurs).
	local isMarker = {}
	for _, m in ipairs(markerInsts) do
		isMarker[m] = true
		for _, d in ipairs(m:GetDescendants()) do
			isMarker[d] = true
		end
	end
	local list = {}
	for _, d in ipairs(selfAndDescendants(container)) do
		if d:IsA("BasePart") and not isMarker[d] then
			table.insert(list, d)
		end
	end
	if #list == 0 then
		addWarning(report, "Import « " .. cname .. " » : aucune pièce anatomique trouvée.")
		return
	end

	-- Le rig (créé au premier import traité, posé au sol sous REF_A).
	if not state.rig then
		local exclude = { container }
		for _, c in ipairs(state.containers) do
			table.insert(exclude, c)
		end
		local existing = Workspace:FindFirstChild(CONFIG.RIG_NAME)
		if existing then
			table.insert(exclude, existing)
		end
		state.rig = ensureRig(markers.A.pos, exclude, report)
	end
	local rig = state.rig

	-- 1) Photographie des CFrame / tailles d'origine AVANT toute modification.
	local snap = {}
	for i, p in ipairs(list) do
		snap[i] = { cf = p.CFrame, size = p.Size }
	end

	-- 2) Supprime les soudures / joints hérités de l'import (ils lieraient des membres entre eux).
	for _, d in ipairs(container:GetDescendants()) do
		if d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			if not isMarker[d] then
				report.removedJoints = report.removedJoints + 1
				d:Destroy()
			end
		end
	end

	-- Index des pièces déjà présentes dans le rig (pour le remplacement des doublons).
	local existingByName = {}
	for _, folder in ipairs({ rig.anat, rig.skin }) do
		for _, d in ipairs(folder:GetDescendants()) do
			if d:IsA("BasePart") then
				existingByName[d.Name] = d
			end
		end
	end

	local src = { name = cname, count = 0, scale = T.scale, residual = T.residual, rot = T.rot }
	table.insert(report.sources, src)

	-- 3) Déplacement, mise à l'échelle, propriétés, rangement, soudure.
	for i, p in ipairs(list) do
		local ok, err = pcall(function()
			local key, entry, region = identify(p, container)
			local rigCF = toRigSpace(T, snap[i].cf)
			local partName = resolveRegion(region, rigCF.Position)
			if not partName then
				partName = nearestPart(rigCF.Position)
				table.insert(report.positional, key .. " -> " .. partName)
			end
			if next(PARTS) ~= nil and not entry then
				table.insert(report.unknown, key)
			end
			local cat = (entry and entry.cat) or guessCategory(key)
			local isSkin = cat == "skin" or cat == "gear"
			local bodyPart = rig.parts[partName]

			-- Pose réelle de la pièce (le rig existant peut avoir été déplacé, tourné ou posé).
			local worldCF = bodyPart.CFrame * REST[partName]:Inverse() * rigCF

			if CONFIG.COLLISION_FIDELITY_BOX then
				pcall(function()
					p.CollisionFidelity = Enum.CollisionFidelity.Box
				end)
			end
			p.Anchored = true
			p.Size = snap[i].size * T.scale
			p.CFrame = worldCF
			if isSkin then
				applySkinMeshProps(p, key, entry, partName)
			else
				applyAnatomyProps(p, cat, entry)
			end

			if key ~= p.Name then
				p.Name = key
			end
			pcall(function()
				p:SetAttribute("Anat_Region", region or "?")
				p:SetAttribute("Anat_Membre", partName)
				p:SetAttribute("Anat_Categorie", cat)
				p:SetAttribute("Anat_Accessoire", cat == "gear" or nil)
				if entry and entry.info and entry.info ~= "" then
					p:SetAttribute("Anat_Info", entry.info)
				end
			end)

			local old = existingByName[key]
			if old and old ~= p then
				if state.placed[old] then
					-- Deux pièces de même nom dans ce lancement : on garde les deux.
					addWarning(report, "Nom en double dans l'import : « " .. key .. " » (les deux sont conservées).")
				elseif CONFIG.REPLACE_DUPLICATES then
					old:Destroy()
					report.replaced = report.replaced + 1
				else
					addWarning(report, "Doublon conservé : « " .. key .. " » existait déjà dans le rig.")
				end
			end
			existingByName[key] = p
			state.placed[p] = true

			p.Parent = isSkin and rig.skin or rig.folders[partName]

			local weld = Instance.new("WeldConstraint")
			weld.Name = "AnatomieWeld"
			weld.Part0 = bodyPart
			weld.Part1 = p
			weld.Parent = p
			p.Anchored = false

			if isSkin then
				report.skin = report.skin + 1
			else
				report.perPart[partName] = (report.perPart[partName] or 0) + 1
				report.perCat[cat] = (report.perCat[cat] or 0) + 1
			end
			report.total = report.total + 1
			src.count = src.count + 1
		end)
		if not ok then
			report.failed = report.failed + 1
			addWarning(report, "Échec sur « " .. tostring(p.Name) .. " » : " .. tostring(err))
		end
	end

	-- 4) Nettoyage : marqueurs puis conteneur s'il est vide.
	if CONFIG.DELETE_MARKERS then
		for _, m in ipairs(markerInsts) do
			if m.Parent then
				m:Destroy()
			end
		end
	end
	if CONFIG.DELETE_EMPTY_SOURCES and container.Parent and not container:IsA("BasePart") then
		local remaining = 0
		for _, d in ipairs(container:GetDescendants()) do
			if d:IsA("BasePart") then
				remaining = remaining + 1
			end
		end
		if remaining == 0 then
			container:Destroy()
		else
			addWarning(report, "« " .. cname .. " » n'est pas vide (" .. tostring(remaining)
				.. " pièce(s) restante(s)) : conservé.")
		end
	end
end

------------------------------------------------------------------------------------------
-- RÉSUMÉ
------------------------------------------------------------------------------------------
local function sortedKeys(t)
	local keys = {}
	for k in pairs(t) do
		table.insert(keys, k)
	end
	table.sort(keys)
	return keys
end

-- Complète `s` par des espaces jusqu'à n caractères (UTF-8 : « Tête » compte 4 caractères).
local function padRight(s, n)
	local len = utf8.len(s) or #s
	return s .. string.rep(" ", math.max(n - len, 0))
end

local function listPreview(list, maxN)
	local out = {}
	for i = 1, math.min(#list, maxN) do
		table.insert(out, list[i])
	end
	local s = table.concat(out, ", ")
	if #list > maxN then
		s = s .. ", ... (+" .. tostring(#list - maxN) .. ")"
	end
	return s
end

local function printSummary(report, state)
	local lines = {}
	local function L(s)
		table.insert(lines, s)
	end
	L("")
	L("================ ANATOMIE R6 : RÉSUMÉ ================")
	for i, s in ipairs(report.sources) do
		local rx, ry, rz = s.rot:ToEulerAnglesXYZ()
		L(string.format("Import %d « %s » : %d pièce(s) ; échelle trouvée %s (1 unité importée = %s stud) ; "
			.. "rotation XYZ (%s°, %s°, %s°) ; écart marqueurs %s stud",
			i, s.name, s.count, fmt(s.scale, 5), fmt(s.scale, 5), fmt(math.deg(rx), 1),
			fmt(math.deg(ry), 1), fmt(math.deg(rz), 1), fmt(s.residual, 4)))
	end
	if state.rig then
		local rig = state.rig
		L("Rig : " .. rig.model:GetFullName() .. (rig.created and " (créé)" or " (réutilisé)")
			.. " ; R6 articulé (10 pièces, coudes et genoux ; Humanoid " .. RIG.rigType .. ", HipHeight "
			.. tostring(RIG.hipHeight) .. ") ; Torso en " .. vecStr(rig.parts.Torso.Position))
		L("Pièces placées : " .. tostring(report.total) .. (report.failed > 0 and
			(" ; ÉCHECS : " .. tostring(report.failed)) or "") .. (report.replaced > 0 and
			(" ; remplacées : " .. tostring(report.replaced)) or ""))
		for _, name in ipairs(PART_ORDER) do
			L(string.format("   %s %4d nouvelle(s) ; %4d au total dans le rig", padRight(partLabel(name), 36),
				report.perPart[name] or 0, #rig.folders[name]:GetChildren()))
		end
		local sr = report.skinResult
		if sr then
			local how = {
				maillage = "tenue du survivant importée (Survivor_*)",
				blocs = "blocs Roblox" .. (CONFIG.SHOW_FACE and " + visage decal" or ""),
				mixte = "tenue importée + blocs Roblox pour les pièces sans Survivor_*",
			}
			L(string.format("Peau : mode « %s » - %s ; %d pièce(s) de peau importée(s) dans le rig "
				.. "(%d nouvelle(s)) ; transparence %s", sr.mode, how[sr.mode] or "?", sr.meshes, report.skin,
				fmt(CONFIG.SKIN_TRANSPARENCY, 2)))
		end
		local cats = {}
		for _, k in ipairs(sortedKeys(report.perCat)) do
			table.insert(cats, k .. " " .. tostring(report.perCat[k]))
		end
		if #cats > 0 then
			L("Catégories : " .. table.concat(cats, ", "))
		end
		if report.removedJoints > 0 then
			L("Soudures héritées de l'import supprimées : " .. tostring(report.removedJoints))
		end
		if #report.positional > 0 then
			L("Pièce du rig déduite de la position (" .. tostring(#report.positional) .. ") : "
				.. listPreview(report.positional, 12))
		end
		if #report.unknown > 0 then
			L("Pièces absentes du manifeste (" .. tostring(#report.unknown) .. ") : " .. listPreview(report.unknown, 12))
		end
		-- Pièces du manifeste encore absentes du rig (normal si tout n'a pas encore été importé).
		if next(PARTS) ~= nil then
			local present = {}
			for _, folder in ipairs({ rig.anat, rig.skin }) do
				for _, d in ipairs(folder:GetDescendants()) do
					if d:IsA("BasePart") then
						present[d.Name] = true
					end
				end
			end
			local missing = {}
			for _, k in ipairs(sortedKeys(PARTS)) do
				if not present[k] then
					table.insert(missing, k)
				end
			end
			if #missing > 0 then
				L("Pièces du manifeste pas encore dans le rig (" .. tostring(#missing) .. ") : "
					.. listPreview(missing, 15))
			else
				L("Toutes les pièces du manifeste sont présentes dans le rig.")
			end
		end
	end
	for _, n in ipairs(report.notes) do
		L("Note : " .. n)
	end
	if #report.warnings > 0 then
		L("AVERTISSEMENTS (" .. tostring(#report.warnings) .. ") :")
		for _, w in ipairs(report.warnings) do
			L("   - " .. w)
		end
	else
		L("Aucun avertissement.")
	end
	L("Annuler : Ctrl+Z. Outils (peau opaque/transparente, calvaria, catégories, StarterCharacter) : "
		.. "AnatomieR6_Outils.lua. Animations, contrôleur et éditeur : SurvivantR6_Animations.lua.")
	L("=======================================================")
	print(table.concat(lines, "\n"))
end

------------------------------------------------------------------------------------------
-- PROGRAMME PRINCIPAL
------------------------------------------------------------------------------------------
local function main()
	local report = newReport()
	local state = { rig = nil, containers = {}, placed = {} }
	local containers = findContainers(report)
	state.containers = containers
	if #containers == 0 then
		addWarning(report, "Aucun import anatomique trouvé (aucun Model contenant REF_A). Faites File > Import 3D "
			.. "du fichier FBX/GLB, puis relancez ce script (en sélectionnant le modèle importé si besoin).")
		printSummary(report, state)
		return
	end
	if CONFIG.SKIN_MODE ~= "maillage" and CONFIG.SKIN_MODE ~= "blocs" then
		addWarning(report, "SKIN_MODE « " .. tostring(CONFIG.SKIN_MODE) .. " » inconnu : \"maillage\" utilisé.")
		CONFIG.SKIN_MODE = "maillage"
	end
	for _, c in ipairs(containers) do
		local ok, err = pcall(processContainer, c, report, state)
		if not ok then
			addWarning(report, "Erreur pendant le traitement de « " .. tostring(c.Name) .. " » : " .. tostring(err))
		end
	end
	if state.rig then
		local ok, res = pcall(finalizeSkin, state.rig, report)
		if ok then
			report.skinResult = res
		else
			addWarning(report, "Erreur pendant la mise en place de la peau : " .. tostring(res))
		end
	end
	printSummary(report, state)
	if state.rig then
		pcall(function()
			game:GetService("Selection"):Set({ state.rig.model })
		end)
	end
end

local ChangeHistoryService = game:GetService("ChangeHistoryService")
local recording = nil
do
	local ok, id = pcall(function()
		return ChangeHistoryService:TryBeginRecording("AnatomieR6", "Installation du personnage anatomique R6")
	end)
	if ok and id then
		recording = id
	else
		pcall(function()
			ChangeHistoryService:SetWaypoint("AnatomieR6 - avant")
		end)
	end
end

local okMain, errMain = xpcall(main, function(e)
	return debug.traceback(tostring(e), 2)
end)

if recording then
	pcall(function()
		ChangeHistoryService:FinishRecording(recording, okMain and Enum.FinishRecordingOperation.Commit
			or Enum.FinishRecordingOperation.Cancel)
	end)
else
	pcall(function()
		ChangeHistoryService:SetWaypoint("AnatomieR6 - après")
	end)
end

if not okMain then
	warn("[Anatomie R6] ERREUR INATTENDUE : " .. tostring(errMain))
	if recording then
		warn("[Anatomie R6] Les modifications ont été annulées.")
	else
		warn("[Anatomie R6] Utilisez Ctrl+Z pour revenir à l'état précédent.")
	end
end
