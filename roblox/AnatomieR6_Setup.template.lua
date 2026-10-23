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
--@@PARTS_TABLE@@

------------------------------------------------------------------------------------------
-- RIG R6 ARTICULÉ (généré par src/make_lua.py à partir de src/rig_spec.py : ne pas modifier)
-- Espace du rig = repère du HumanoidRootPart : X = droite du personnage, Y = haut, Z = arrière
-- (le personnage regarde vers -Z), sol à Y = -3. center / size : pièce au repos ; c0 / c1 :
-- Motor6D (x, y, z, R00..R22) ; pivot : centre de l'articulation dans l'espace du rig.
------------------------------------------------------------------------------------------
--@@RIG@@
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
--@@/RIG@@

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
