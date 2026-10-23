--[[
	SurvivantEditeur  --  poser le survivant R6 articulé et modifier ses animations (ModuleScript)
	=====================================================================================

	Installé par SurvivantR6_Animations.lua dans ServerStorage, avec ses données d'origine dans le
	module enfant « Donnees ». Fait pour la barre de commande de Roblox Studio et pour un assistant
	IA connecté au serveur MCP de Studio (outil d'exécution de code Luau). Le mode d'emploi est le
	texte GUIDE ci-dessous ; E.aide() le renvoie complété (arbre des articulations, animations).

		local E = require(game:GetService("ServerStorage").SurvivantEditeur)
		print(E.aide())
]]

local GUIDE = [=[
SURVIVANT R6 ARTICULÉ : GUIDE POUR ASSISTANT IA (serveur MCP de Roblox Studio)
==============================================================================

Ce module (ServerStorage.SurvivantEditeur) sert à poser le personnage et à modifier ses
animations en Luau, depuis la barre de commande ou depuis un assistant IA connecté au serveur
MCP de Roblox Studio (outil d'exécution de code : execute_luau / run_code). Travaillez en MODE
ÉDITION (Studio arrêté). Chaque fonction renvoie un court compte rendu en français : affichez-le
avec print. Une erreur est un message clair en français (« SurvivantEditeur : ... »).

    local E = require(game:GetService("ServerStorage").SurvivantEditeur)
    print(E.info())        -- rig, articulations, animations, vitesses

1. LE RIG (Workspace.Anatomie_R6)
  Silhouette R6 (torse 2x2x1, tête 2x1x1, membres de 1 stud de large) mais bras et jambes coupés
  au coude et au genou : 10 pièces (Part), 10 Motor6D. Humanoid de type R15 (HipHeight 2),
  HumanoidRootPart ancré. Arbre « pièce - articulation (Motor6D), pivot dans l'espace du rig » :
{{ARBRE}}
  RightHand (invisible, soudée à RightLowerArm, avec RightGripAttachment) tient les outils.
  Tenue : dossier Peau (MeshParts Survivor_*) ; anatomie : dossiers Anatomie.<pièce> (os,
  organes, vaisseaux...), chaque maillage soudé à sa pièce. Ne renommez ni pièces ni Motor6D.

2. CONVENTIONS
  - Distances en studs, angles en DEGRÉS, temps en secondes.
  - Axes Roblox du personnage au repos : X = sa droite, Y = le haut, Z = l'arrière (il regarde
    vers -Z).
  - Une pose est {x, y, z, rx, ry, rz} : décalage (studs) et rotation (degrés) d'une pièce par
    rapport à sa pièce parente, autour du pivot de son articulation, dans les axes de la pièce
    parente (ceux du personnage quand elle est au repos). La rotation est
    CFrame.Angles(math.rad(rx), math.rad(ry), math.rad(rz)). {0, 0, 0, 0, 0, 0} = repos :
    debout, bras le long du corps.
  - Sens des angles :
      rx > 0 : ce qui est sous le pivot part vers l'AVANT (bras ou jambe levé devant), ce qui est
               au-dessus part vers l'arrière (tête ou torse basculé en arrière).
               Plier le coude = rx > 0 (0 à 150). Plier le genou = rx < 0 (0 à -150).
               Pencher le torse en avant = rx < 0 sur Torso ; baisser la tête = rx < 0 sur Head.
      ry > 0 : rotation vers la GAUCHE du personnage (vue de dessus : sens inverse des aiguilles
               d'une montre).
      rz > 0 : le bas part vers la DROITE du personnage, le haut vers sa gauche : écarter le bras
               droit = rz > 0, écarter le bras gauche = rz < 0, pencher la tête vers son épaule
               gauche = rz > 0.
  - x, y, z valent en général 0 ; c'est surtout le Torso (RootJoint) qui se déplace (y = -1
    accroupi, y = -2.45 allongé, z pour avancer / reculer le bassin).
  - Désignez une pièce par son nom (RightLowerArm) ou celui de son articulation (RightElbow) ;
    quelques noms français marchent aussi (« coude droit », « genou gauche », « tête »).

3. LES ANIMATIONS
  - KeyframeSequences dans ReplicatedStorage.SurvivantAnimations (celles que le jeu joue dans
    Studio), copies dans ServerStorage.RBX_ANIMSAVES.Anatomie_R6 (Éditeur d'animation de Roblox),
    identifiants publiés dans ReplicatedStorage.SurvivantAnimations.AnimationIds.<clé>.
  - Clés (clé = nom, libellé, durée) :
{{ANIMATIONS}}
  - « tool » est une animation partielle superposée : seules RightUpperArm et RightLowerArm sont
    animées, le reste du corps garde l'animation en cours.
  - Format de E.lireAnimation(clé) et de E.ecrireAnimation(clé, a) :
        {
          cle = "walk", nom = "Survivant_Marche", libelle = "Marche",
          duree = 0.7, boucle = true, priorite = "Movement",
          vitesse = 6,                 -- vitesse (studs/s) pour laquelle l'animation est faite
          pieces = { "Torso", "Head", ... },          -- pièces animées
          images = {                                  -- images clés, triées par temps
            { t = 0, poses = { Torso = {x, y, z, rx, ry, rz}, RightLowerArm = {...}, ... } },
            ...
          },
        }
    Entre deux images clés Roblox interpole linéairement. Une animation en boucle doit finir sur
    la pose du début (images t = 0 et t = duree identiques) : E.modifierPose s'en charge.
  - Toute écriture marque l'animation comme modifiée (attribut Survivant_Modifiee : relancer
    SurvivantR6_Animations.lua ne l'écrase pas) et vide son identifiant publié (l'ancien reste
    dans l'attribut AncienIdentifiant) : republiez-la avant de publier le jeu.
  - Vitesse de jeu : walk, run, crouchwalk, crawl et climb sont accélérées ou ralenties selon la
    vitesse du personnage (x0,45 à x1,8 de leur « vitesse ») ; les bottes restent plantées quand
    la vitesse du personnage est égale à celle de l'animation.

4. FONCTIONS (E = require(game:GetService("ServerStorage").SurvivantEditeur))
  E.aide()                                 ce guide
  E.info()                                 rig, articulations (pose actuelle), animations, vitesses
  E.radiographie(actif, transparence)      tenue transparente (true, 0.7) ou opaque (false)
  E.pose(nom, rx, ry, rz, x, y, z)         pose une articulation du rig du Workspace (aperçu, aucune
                                           animation modifiée) ; plusieurs à la fois :
                                           E.pose({ RightElbow = { rx = 90 }, Neck = { rx = -10, ry = 20 } })
  E.reinitialiserPose()                    remet le rig au repos
  E.apercu(clé, temps)                     montre l'animation à l'instant « temps » sur le rig
  E.lireAnimation(clé)                     renvoie la table décrite au point 3
  E.ecrireAnimation(clé, a)                remplace (ou crée) une animation à partir d'une telle table
  E.modifierPose(clé, temps, pièce, changements)
                                           change une pose à un instant (image clé créée si besoin) ;
                                           changements = { rx = 40 } (valeurs absolues)
                                           ou { rx = 10, relatif = true } (ajoutées)
  E.restaurerAnimation(clé)                remet la version d'origine (données du module Donnees)
  E.importerDepuisEditeur(clé)             reprend la version enregistrée par l'Éditeur d'animation
  E.vitesses({ marche =, course =, accroupi =, allonge = })
                                           vitesses en jeu (studs/s) des scripts Animate ;
                                           E.vitesses() les renvoie
  E.majPersonnageJouable()                 recopie le rig dans StarterPlayer.StarterCharacter

5. EXEMPLES (à envoyer tels quels à l'outil d'exécution de code)
    local E = require(game:GetService("ServerStorage").SurvivantEditeur)
    -- coude droit plus plié au milieu de la course, puis aperçu (capture : screen_capture)
    print(E.modifierPose("run", 0.28, "RightElbow", { rx = 10, relatif = true }))
    print(E.apercu("run", 0.28))

    -- tête 5° plus haute sur toute l'animation de repos
    local a = E.lireAnimation("idle")
    for _, img in ipairs(a.images) do
        local p = img.poses.Head
        if p then p[4] = p[4] + 5 end
    end
    print(E.ecrireAnimation("idle", a))

    -- nouvelle animation (à jouer par vos scripts : Animator:LoadAnimation)
    print(E.ecrireAnimation("salut", { nom = "Survivant_Salut", duree = 1, boucle = false,
        priorite = "Action", images = {
            { t = 0, poses = { RightUpperArm = {0, 0, 0, 0, 0, 0}, RightLowerArm = {0, 0, 0, 0, 0, 0} } },
            { t = 0.5, poses = { RightUpperArm = {0, 0, 0, 0, 0, 160}, RightLowerArm = {0, 0, 0, 30, 0, 0} } },
            { t = 1, poses = { RightUpperArm = {0, 0, 0, 0, 0, 0}, RightLowerArm = {0, 0, 0, 0, 0, 0} } },
        } }))

    -- tester en jeu : start_stop_play (ou bouton Jouer), puis Maj / C / X / R ;
    -- messages du jeu : get_console_output

6. À SAVOIR
  - E.pose et E.apercu ne changent que Motor6D.Transform du rig du Workspace (rien n'est
    enregistré) ; les fonctions qui écrivent s'annulent avec Ctrl+Z.
  - En jeu (Play), les animations modifiées ne sont prises en compte qu'au lancement suivant.
  - Gardez des angles naturels : coude 0 à 150, genou -150 à 0, épaule rx -60 à 180.
  - Après avoir modifié les pièces du rig (pas les animations), appelez E.majPersonnageJouable().
  - Jeu publié : Roblox ne joue que les animations publiées par le propriétaire du jeu ; dans
    Studio, les KeyframeSequences sont jouées directement.
]=]

local E = {}

local ServerStorage = game:GetService("ServerStorage")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local StarterPlayer = game:GetService("StarterPlayer")
local Workspace = workspace

local RIG_NAME = "Anatomie_R6"
local FOLDER_NAME = "SurvivantAnimations"
local RIG_LABEL = "R6 articulé"
local EPS_T = 1e-3 -- deux images clés plus proches (secondes) sont au même instant
local SPEED_CLIPS = { marche = "walk", course = "run", accroupi = "crouchwalk", allonge = "crawl" }
local SPEED_ORDER = { "marche", "course", "accroupi", "allonge" }

local function fail(msg)
	error("SurvivantEditeur : " .. msg, 0)
end

local function fmt(n)
	local s = string.format("%.3f", n)
	s = string.gsub(s, "0+$", "")
	s = string.gsub(s, "%.$", "")
	if s == "-0" then
		s = "0"
	end
	return s
end

local function round(v, digits)
	local m = 10 ^ digits
	local r = math.floor(v * m + 0.5) / m
	if r == 0 then
		r = 0 -- pas de « -0 »
	end
	return r
end

local function checkNumber(v, what)
	if type(v) ~= "number" or v ~= v or math.abs(v) == math.huge then
		fail(what .. " : nombre attendu, reçu " .. tostring(v) .. ".")
	end
	return v
end

------------------------------------------------------------------------------------------
-- Données (module Donnees) et description du rig
------------------------------------------------------------------------------------------
local DATA, INFO = nil, nil

local function data()
	if not DATA then
		local mod = script:FindFirstChild("Donnees")
		if not (mod and mod:IsA("ModuleScript")) then
			fail("module « Donnees » introuvable sous " .. script:GetFullName()
				.. " : relancez SurvivantR6_Animations.lua.")
		end
		local ok, res = pcall(require, mod)
		if not ok or type(res) ~= "table" or type(res.RIG) ~= "table" or type(res.ANIMS) ~= "table" then
			fail("module « Donnees » illisible (" .. tostring(res) .. ") : relancez SurvivantR6_Animations.lua.")
		end
		DATA = res
	end
	return DATA
end

local ACCENTS = { { "é", "e" }, { "è", "e" }, { "ê", "e" }, { "ë", "e" }, { "É", "e" }, { "È", "e" }, { "à", "a" },
	{ "â", "a" }, { "î", "i" }, { "ï", "i" }, { "ô", "o" }, { "ù", "u" }, { "û", "u" }, { "ü", "u" }, { "ç", "c" } }

local function normalize(s)
	s = string.lower(tostring(s))
	for _, r in ipairs(ACCENTS) do
		s = string.gsub(s, r[1], r[2])
	end
	return (string.gsub(s, "[%s_%-%.']", ""))
end

-- Noms français (normalisés) -> articulation.
local ALIASES = {
	tete = "Neck", cou = "Neck", nuque = "Neck",
	torse = "RootJoint", tronc = "RootJoint", corps = "RootJoint", bassin = "RootJoint", racine = "RootJoint",
	epauledroite = "RightShoulder", brasdroit = "RightShoulder",
	epaulegauche = "LeftShoulder", brasgauche = "LeftShoulder",
	coudedroit = "RightElbow", avantbrasdroit = "RightElbow",
	coudegauche = "LeftElbow", avantbrasgauche = "LeftElbow",
	hanchedroite = "RightHip", cuissedroite = "RightHip",
	hanchegauche = "LeftHip", cuissegauche = "LeftHip",
	genoudroit = "RightKnee", jambedroite = "RightKnee",
	genougauche = "LeftKnee", jambegauche = "LeftKnee",
}

local function cframe12(t)
	return CFrame.new(t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9], t[10], t[11], t[12])
end

local function rigInfo()
	if INFO then
		return INFO
	end
	local R = data().RIG
	local info = { order = R.poseOrder, parent = {}, joints = {}, jointList = {}, byPart = {}, lookup = {},
		labels = R.labels or {} }
	for _, p in ipairs(R.parts) do
		info.parent[p.name] = p.parent
	end
	for _, j in ipairs(R.joints) do
		local c0 = cframe12(j.c0)
		-- rot : rotation de C0 ; Motor6D.Transform est exprimée dans ce repère, les poses du module
		-- dans celui de la pièce parente.
		local e = { name = j.name, part0 = j.part0, part1 = j.part1, pivot = j.pivot, rot = c0 - c0.Position }
		info.joints[j.name] = e
		info.byPart[j.part1] = e
		table.insert(info.jointList, e)
		info.lookup[normalize(j.name)] = e
		info.lookup[normalize(j.part1)] = e
	end
	for alias, jointName in pairs(ALIASES) do
		if info.joints[jointName] then
			info.lookup[alias] = info.joints[jointName]
		end
	end
	INFO = info
	return info
end

local function jointNames()
	local names = {}
	for _, j in ipairs(rigInfo().jointList) do
		table.insert(names, j.name .. " (" .. j.part1 .. ")")
	end
	return table.concat(names, ", ")
end

local function resolveJoint(name)
	if type(name) ~= "string" then
		fail("nom d'articulation ou de pièce attendu (texte), reçu " .. tostring(name) .. ".")
	end
	local j = rigInfo().lookup[normalize(name)]
	if not j then
		fail("articulation ou pièce inconnue « " .. name .. " ». Noms valides : " .. jointNames() .. ".")
	end
	return j
end

-- Motor6D.Transform (repère de C0) <-> pose dans le repère de la pièce parente.
local function toParentFrame(j, cf)
	return j.rot * cf * j.rot:Inverse()
end
local function toJointFrame(j, cf)
	return j.rot:Inverse() * cf * j.rot
end

local POSE_FIELDS = { "x", "y", "z", "rx", "ry", "rz" }

local function cfToValues(cf)
	local rx, ry, rz = cf:ToEulerAnglesXYZ()
	return { cf.X, cf.Y, cf.Z, math.deg(rx), math.deg(ry), math.deg(rz) }
end

local function cfToList(cf)
	local v = cfToValues(cf)
	return { round(v[1], 4), round(v[2], 4), round(v[3], 4), round(v[4], 3), round(v[5], 3), round(v[6], 3) }
end

local function valuesToCF(v)
	return CFrame.new(v[1], v[2], v[3]) * CFrame.Angles(math.rad(v[4]), math.rad(v[5]), math.rad(v[6]))
end

-- {x, y, z, rx, ry, rz} ou { x = , ..., rz = } (champs absents = 0).
local function poseValues(p, where)
	if type(p) ~= "table" then
		fail(where .. " : pose attendue sous la forme {x, y, z, rx, ry, rz}.")
	end
	local out = {}
	for i, f in ipairs(POSE_FIELDS) do
		local v = p[i]
		if v == nil then
			v = p[f]
		end
		out[i] = checkNumber(v == nil and 0 or v, where .. ", " .. f)
	end
	return out
end

local function sameCFrame(a, b)
	local ca, cb = { a:GetComponents() }, { b:GetComponents() }
	for i = 1, 12 do
		if math.abs(ca[i] - cb[i]) > 1e-3 then
			return false
		end
	end
	return true
end

------------------------------------------------------------------------------------------
-- Rig et animations dans la place
------------------------------------------------------------------------------------------
local function getRig(required)
	local rig = Workspace:FindFirstChild(RIG_NAME)
	if rig and rig:IsA("Model") and rig:FindFirstChild("RightLowerArm") then
		return rig
	end
	if required then
		fail("rig « " .. RIG_NAME .. " » (R6 articulé) introuvable dans le Workspace : lancez AnatomieR6_Setup.lua.")
	end
	return nil
end

local function motorFor(rig, j)
	local m = rig:FindFirstChild(j.name, true)
	if m and m:IsA("Motor6D") then
		return m
	end
	for _, d in ipairs(rig:GetDescendants()) do
		if d:IsA("Motor6D") and d.Part1 and d.Part1.Name == j.part1 then
			return d
		end
	end
	return nil
end

local function animFolder()
	local f = ReplicatedStorage:FindFirstChild(FOLDER_NAME)
	if not f then
		fail("ReplicatedStorage." .. FOLDER_NAME .. " introuvable : lancez SurvivantR6_Animations.lua.")
	end
	return f
end

local function originalMeta(cle)
	for _, a in ipairs(data().ANIMS) do
		if a.key == cle or a.name == cle then
			return a
		end
	end
	return nil
end

local function keyOf(kfs)
	return kfs:GetAttribute("Survivant_Cle") or kfs.Name
end

local function sequences()
	local list = {}
	local f = ReplicatedStorage:FindFirstChild(FOLDER_NAME)
	if f then
		for _, c in ipairs(f:GetChildren()) do
			if c:IsA("KeyframeSequence") then
				table.insert(list, c)
			end
		end
	end
	local rank = {}
	for i, a in ipairs(data().ANIMS) do
		rank[a.key] = i
	end
	table.sort(list, function(a, b)
		local ra, rb = rank[keyOf(a)] or 1e6, rank[keyOf(b)] or 1e6
		if ra ~= rb then
			return ra < rb
		end
		return a.Name < b.Name
	end)
	return list
end

local function availableKeys()
	local keys = {}
	for _, kfs in ipairs(sequences()) do
		table.insert(keys, keyOf(kfs))
	end
	return #keys > 0 and table.concat(keys, ", ") or "aucune"
end

local function findSequence(cle)
	if type(cle) ~= "string" or cle == "" then
		fail("clé d'animation attendue (texte), par exemple \"walk\".")
	end
	local meta = originalMeta(cle)
	for _, kfs in ipairs(sequences()) do
		if kfs:GetAttribute("Survivant_Cle") == cle or kfs.Name == cle or (meta and kfs.Name == meta.name) then
			return kfs
		end
	end
	return nil
end

local function requireSequence(cle)
	animFolder()
	local kfs = findSequence(cle)
	if not kfs then
		fail("animation « " .. tostring(cle) .. " » introuvable. Clés : " .. availableKeys() .. ".")
	end
	return kfs
end

-- Images clés d'une KeyframeSequence : { { t, poses = { pièce = CFrame (Motor6D.Transform) } } } triées,
-- et la liste des pièces animées (poses de poids > 0).
local function readFrames(kfs)
	local info = rigInfo()
	local frames, keyed = {}, {}
	for _, kf in ipairs(kfs:GetChildren()) do
		if kf:IsA("Keyframe") then
			local fr = { t = kf.Time, poses = {} }
			for _, pose in ipairs(kf:GetDescendants()) do
				if pose:IsA("Pose") and pose.Weight > 0 and info.byPart[pose.Name] then
					fr.poses[pose.Name] = pose.CFrame
					keyed[pose.Name] = true
				end
			end
			table.insert(frames, fr)
		end
	end
	table.sort(frames, function(a, b)
		return a.t < b.t
	end)
	local parts = {}
	for _, name in ipairs(info.order) do
		if keyed[name] then
			table.insert(parts, name)
		end
	end
	return frames, parts
end

-- Pose (Motor6D.Transform) d'une pièce à l'instant t : interpolation linéaire entre les images
-- clés qui l'animent, comme Roblox ; nil si aucune image ne l'anime.
local function sampleFrames(frames, part, t)
	local before, after = nil, nil
	for _, fr in ipairs(frames) do
		if fr.poses[part] then
			if fr.t <= t + 1e-9 then
				before = fr
			end
			if fr.t >= t - 1e-9 and not after then
				after = fr
			end
		end
	end
	if before and after then
		if after.t - before.t < 1e-9 then
			return before.poses[part]
		end
		return before.poses[part]:Lerp(after.poses[part], (t - before.t) / (after.t - before.t))
	end
	local only = before or after
	return only and only.poses[part] or nil
end

local function newPose(name, cf, weight)
	local p = Instance.new("Pose")
	p.Name = name
	p.CFrame = cf
	p.Weight = weight
	p.EasingStyle = Enum.PoseEasingStyle.Linear
	p.EasingDirection = Enum.PoseEasingDirection.In
	return p
end

-- spec = { name, key, label, loop, priority, speed, parts = pièces animées, frames = readFrames(...) }.
-- Même structure que SurvivantR6_Animations.lua : poses imbriquées selon le rig, ancêtres non animés
-- d'une animation partielle en pose neutre de poids 0.
local function buildSequence(spec)
	local info = rigInfo()
	local kfs = Instance.new("KeyframeSequence")
	kfs.Name = spec.name
	kfs.Loop = spec.loop
	kfs.Priority = Enum.AnimationPriority[spec.priority]
	local keyed, needed, ordered = {}, {}, {}
	for _, name in ipairs(spec.parts) do
		keyed[name] = true
		local n = name
		while n and n ~= "HumanoidRootPart" do
			needed[n] = true
			n = info.parent[n]
		end
	end
	for _, name in ipairs(info.order) do
		if keyed[name] then
			table.insert(ordered, name)
		end
	end
	pcall(function()
		kfs:SetAttribute("Survivant_Cle", spec.key)
		kfs:SetAttribute("Survivant_Libelle", spec.label)
		kfs:SetAttribute("Survivant_Pieces", table.concat(ordered, ","))
		kfs:SetAttribute("Survivant_VitesseReference", spec.speed)
	end)
	for _, fr in ipairs(spec.frames) do
		local kf = Instance.new("Keyframe")
		kf.Time = fr.t
		local poses = { HumanoidRootPart = newPose("HumanoidRootPart", CFrame.new(), 0) }
		for _, name in ipairs(info.order) do
			if needed[name] then
				local cf = keyed[name] and fr.poses[name] or nil
				local p = newPose(name, cf or CFrame.new(), cf and 1 or 0)
				p.Parent = poses[info.parent[name]]
				poses[name] = p
			end
		end
		poses.HumanoidRootPart.Parent = kf
		kf.Parent = kfs
	end
	return kfs
end

-- Remplace l'animation `old` (ou celle du même nom) par `kfs` dans ReplicatedStorage et dans les
-- copies de l'Éditeur d'animation ; vide l'identifiant publié devenu périmé. Renvoie une note.
local function storeSequence(kfs, key, old, modified)
	local f = animFolder()
	local oldName = old and old.Name
	if old then
		old:Destroy()
	end
	local same = f:FindFirstChild(kfs.Name)
	if same and same:IsA("KeyframeSequence") then
		same:Destroy()
	end
	pcall(function()
		kfs:SetAttribute("Survivant_Modifiee", modified or nil)
	end)
	kfs.Parent = f
	local rig = getRig(false)
	if rig then
		local saves = ServerStorage:FindFirstChild("RBX_ANIMSAVES")
		if not saves then
			saves = Instance.new("Model")
			saves.Name = "RBX_ANIMSAVES"
			saves.Parent = ServerStorage
		end
		local entry = saves:FindFirstChild(rig.Name)
		if not (entry and entry:IsA("ObjectValue")) then
			entry = Instance.new("ObjectValue")
			entry.Name = rig.Name
			entry.Value = rig
			entry.Parent = saves
		end
		for _, n in ipairs({ kfs.Name, oldName }) do
			local c = entry:FindFirstChild(n)
			if c and c:IsA("KeyframeSequence") then
				c:Destroy()
			end
		end
		kfs:Clone().Parent = entry
	end
	local ids = f:FindFirstChild("AnimationIds")
	if not ids then
		ids = Instance.new("Folder")
		ids.Name = "AnimationIds"
		ids.Parent = f
	end
	local v = ids:FindFirstChild(key)
	if not (v and v:IsA("StringValue")) then
		if v then
			v:Destroy()
		end
		v = Instance.new("StringValue")
		v.Name = key
		v.Value = ""
		v.Parent = ids
	end
	local note = ""
	if v.Value ~= "" then
		pcall(function()
			v:SetAttribute("AncienIdentifiant", v.Value)
		end)
		v.Value = ""
		note = " Identifiant publié vidé (gardé dans l'attribut AncienIdentifiant) : republiez l'animation "
			.. "(clic droit > Save to Roblox) pour un jeu publié."
	end
	pcall(function()
		v:SetAttribute("Animation", kfs.Name)
		v:SetAttribute("Survivant_Rig", RIG_LABEL)
	end)
	return note
end

local function specFrom(kfs, key)
	local meta = originalMeta(key)
	return {
		name = kfs.Name, key = key, loop = kfs.Loop, priority = kfs.Priority.Name,
		label = kfs:GetAttribute("Survivant_Libelle") or (meta and meta.label) or key,
		speed = kfs:GetAttribute("Survivant_VitesseReference") or (meta and meta.speed),
	}
end

-- Enregistrement dans l'historique de Studio (Ctrl+Z) autour d'une modification.
local function recorded(label, fn, ...)
	local CHS = game:GetService("ChangeHistoryService")
	local rec = nil
	pcall(function()
		rec = CHS:TryBeginRecording("SurvivantEditeur", label)
	end)
	local res = table.pack(pcall(fn, ...))
	if rec then
		pcall(function()
			CHS:FinishRecording(rec, res[1] and Enum.FinishRecordingOperation.Commit or Enum.FinishRecordingOperation.Cancel)
		end)
	else
		pcall(function()
			CHS:SetWaypoint("SurvivantEditeur : " .. label)
		end)
	end
	if not res[1] then
		error(res[2], 0)
	end
	return table.unpack(res, 2, res.n)
end

local function animators(rig)
	local hum = rig:FindFirstChildOfClass("Humanoid")
	if not hum then
		fail("le rig n'a pas de Humanoid : relancez AnatomieR6_Setup.lua.")
	end
	local animator = hum:FindFirstChildOfClass("Animator")
	if not animator then
		animator = Instance.new("Animator")
		animator.Parent = hum
	end
	return animator
end

-- En mode édition, Studio ne replace les pièces d'après Motor6D.Transform que lorsque l'Animator avance :
-- StepAnimations(0) recalcule leurs positions (sans piste en cours, les Transform posés à la main restent).
local function refresh(rig)
	pcall(function()
		local hum = rig:FindFirstChildOfClass("Humanoid")
		local animator = hum and hum:FindFirstChildOfClass("Animator")
		if animator then
			animator:StepAnimations(0)
		end
	end)
end

-- Pose de l'Animator assez proche de celle des images clés (il interpole à 0,1° près).
local function closeCFrame(a, b)
	local _, angle = (a:Inverse() * b):ToAxisAngle()
	return math.abs(angle) < math.rad(1.5) and (a.Position - b.Position).Magnitude < 0.02
end

local function stopPreview(animator)
	local ok, list = pcall(function()
		return animator:GetPlayingAnimationTracks()
	end)
	if ok and type(list) == "table" then
		for _, tr in ipairs(list) do
			pcall(function()
				tr:Stop(0)
			end)
		end
	end
end

local function resetMotors(rig)
	local n = 0
	for _, d in ipairs(rig:GetDescendants()) do
		if d:IsA("Motor6D") then
			d.Transform = CFrame.new()
			n = n + 1
		end
	end
	return n
end

local function animateScripts()
	local list = {}
	local function add(parent)
		local s = parent and parent:FindFirstChild("Animate")
		if s and s:IsA("LocalScript") and string.find(s.Source, "VITESSE", 1, true) then
			table.insert(list, s)
		end
	end
	add(getRig(false))
	add(StarterPlayer:FindFirstChild("StarterCharacter"))
	add(StarterPlayer:FindFirstChild("StarterCharacterScripts"))
	return list
end

local function parseSpeeds(src)
	local body = string.match(src, "VITESSE%s*=%s*(%b{})")
	local out = {}
	if body then
		for k, v in string.gmatch(body, "([%a_]+)%s*=%s*(%-?[%d%.]+)") do
			out[k] = tonumber(v)
		end
	end
	return out
end

local function writeSource(scr, src)
	local ok = pcall(function()
		game:GetService("ScriptEditorService"):UpdateSourceAsync(scr, function()
			return src
		end)
	end)
	if not ok or scr.Source ~= src then
		scr.Source = src
	end
end

------------------------------------------------------------------------------------------
-- Fonctions
------------------------------------------------------------------------------------------
local function rigTree()
	local info = rigInfo()
	local children = {}
	for _, name in ipairs(info.order) do
		local p = info.parent[name]
		children[p] = children[p] or {}
		table.insert(children[p], name)
	end
	local lines = { "      HumanoidRootPart" }
	local function walk(parent, depth)
		for _, name in ipairs(children[parent] or {}) do
			local j = info.byPart[name]
			table.insert(lines, string.format("      %s%s - %s (pivot %s, %s, %s)%s", string.rep("  ", depth), name, j.name,
				fmt(j.pivot[1]), fmt(j.pivot[2]), fmt(j.pivot[3]), info.labels[name] and ("  " .. info.labels[name]) or ""))
			walk(name, depth + 1)
		end
	end
	walk("HumanoidRootPart", 1)
	return table.concat(lines, "\n")
end

local function animList()
	local lines = {}
	for _, a in ipairs(data().ANIMS) do
		table.insert(lines, string.format("      %-10s = %s, %s, %s s%s%s", a.key, a.name, a.label, fmt(a.length),
			a.loop and ", boucle" or ", une fois", a.speed and (", vitesse " .. fmt(a.speed)) or ""))
	end
	return table.concat(lines, "\n")
end

function E.aide()
	local ok, tree = pcall(rigTree)
	local ok2, anims = pcall(animList)
	local text = string.gsub(GUIDE, "{{ARBRE}}", function()
		return ok and tree or ("      (données indisponibles : " .. tostring(tree) .. ")")
	end)
	text = string.gsub(text, "{{ANIMATIONS}}", function()
		return ok2 and anims or ("      (données indisponibles : " .. tostring(anims) .. ")")
	end)
	return text
end

function E.info()
	local info = rigInfo()
	local lines, out = {}, { articulations = {}, animations = {} }
	local rig = getRig(false)
	if rig then
		local hum = rig:FindFirstChildOfClass("Humanoid")
		local nAnat, nSkin = 0, 0
		local anat, peau = rig:FindFirstChild("Anatomie"), rig:FindFirstChild("Peau")
		for _, d in ipairs(anat and anat:GetDescendants() or {}) do
			if d:IsA("BasePart") then
				nAnat = nAnat + 1
			end
		end
		for _, d in ipairs(peau and peau:GetDescendants() or {}) do
			if d:IsA("BasePart") then
				nSkin = nSkin + 1
			end
		end
		out.rig = rig:GetFullName()
		table.insert(lines, string.format("Rig : %s (%s ; Humanoid %s, HipHeight %s ; %d pièce(s) anatomique(s), %d de tenue ; "
			.. "tenue en mode « %s », transparence %s).", out.rig, RIG_LABEL, hum and hum.RigType.Name or "absent",
			hum and fmt(hum.HipHeight) or "?", nAnat, nSkin, tostring(rig:GetAttribute("Anat_ModePeau") or "?"),
			tostring(rig:GetAttribute("Anat_TransparencePeau") or 0)))
	else
		table.insert(lines, "Rig : introuvable dans le Workspace (lancez AnatomieR6_Setup.lua).")
	end
	table.insert(lines, "Articulations (Motor6D : Part0 > Part1, pivot ; pose actuelle si le rig n'est pas au repos) :")
	for _, j in ipairs(info.jointList) do
		local entry = { nom = j.name, part0 = j.part0, part1 = j.part1, pivot = j.pivot }
		local extra = ""
		local motor = rig and motorFor(rig, j)
		if rig and not motor then
			extra = " ; Motor6D ABSENT"
		elseif motor then
			entry.pose = cfToList(toParentFrame(j, motor.Transform))
			if not sameCFrame(motor.Transform, CFrame.new()) then
				local p = entry.pose
				extra = string.format(" ; pose rx %s, ry %s, rz %s", fmt(p[4]), fmt(p[5]), fmt(p[6]))
			end
		end
		table.insert(out.articulations, entry)
		table.insert(lines, string.format("  %-13s %s > %s, pivot (%s, %s, %s)%s", j.name, j.part0, j.part1,
			fmt(j.pivot[1]), fmt(j.pivot[2]), fmt(j.pivot[3]), extra))
	end
	local f = ReplicatedStorage:FindFirstChild(FOLDER_NAME)
	local ids = f and f:FindFirstChild("AnimationIds")
	if f then
		table.insert(lines, "Animations (ReplicatedStorage." .. FOLDER_NAME .. ") :")
		for _, kfs in ipairs(sequences()) do
			local key = keyOf(kfs)
			local frames, parts = readFrames(kfs)
			local v = ids and ids:FindFirstChild(key)
			local published = v and v:IsA("StringValue") and v.Value ~= "" and v.Value or nil
			local a = { cle = key, nom = kfs.Name, libelle = kfs:GetAttribute("Survivant_Libelle"),
				duree = #frames > 0 and frames[#frames].t or 0, boucle = kfs.Loop, priorite = kfs.Priority.Name,
				images = #frames, pieces = parts, vitesse = kfs:GetAttribute("Survivant_VitesseReference"),
				modifiee = kfs:GetAttribute("Survivant_Modifiee") == true, publiee = published }
			table.insert(out.animations, a)
			table.insert(lines, string.format("  %-10s %s « %s » : %s s, %s, %s, %d images clés%s%s%s%s", key, kfs.Name,
				tostring(a.libelle or ""), fmt(a.duree), a.boucle and "boucle" or "une fois", a.priorite, a.images,
				a.vitesse and (", vitesse " .. fmt(a.vitesse) .. " studs/s") or "",
				#parts < #info.order and (", pièces : " .. table.concat(parts, ", ")) or "",
				a.modifiee and ", MODIFIÉE" or "", published and (", publiée : " .. published) or ""))
		end
	else
		table.insert(lines, "Animations : ReplicatedStorage." .. FOLDER_NAME .. " absent (lancez SurvivantR6_Animations.lua).")
	end
	local scripts = animateScripts()
	if #scripts > 0 then
		out.vitesses = parseSpeeds(scripts[1].Source)
		local parts = {}
		for _, k in ipairs(SPEED_ORDER) do
			table.insert(parts, k .. " " .. tostring(out.vitesses[k] or "?"))
		end
		table.insert(lines, "Vitesses en jeu (script Animate, studs/s) : " .. table.concat(parts, ", ") .. ".")
	else
		table.insert(lines, "Vitesses en jeu : aucun script Animate du survivant (lancez SurvivantR6_Animations.lua).")
	end
	return table.concat(lines, "\n"), out
end

function E.radiographie(actif, transparence)
	if actif == nil then
		actif = true
	end
	local t = 0
	if actif then
		t = transparence == nil and 0.7 or checkNumber(transparence, "transparence")
		t = math.clamp(t, 0, 1)
	end
	local rig = getRig(true)
	return recorded("Radiographie", function()
		local n = 0
		for _, p in ipairs(rig:GetDescendants()) do
			if p:IsA("BasePart") and p:GetAttribute("Anat_Peau") then
				local pt = (t > 0 and p:GetAttribute("Anat_Accessoire")) and 1 or t
				p.Transparency = pt
				p:SetAttribute("Anat_TransparencePeau", pt)
				p:SetAttribute("Anat_Masque", nil)
				for _, c in ipairs(p:GetChildren()) do
					if c:IsA("Decal") then
						c.Transparency = pt
					end
				end
				n = n + 1
			end
		end
		rig:SetAttribute("Anat_TransparencePeau", t)
		return string.format("Radiographie %s : tenue à %s de transparence (%d pièce(s))%s.", actif and "activée" or
			"désactivée", fmt(t), n, (t > 0) and ", bonnet et sac masqués" or "")
	end)
end

function E.pose(nom, rx, ry, rz, x, y, z)
	local rig = getRig(true)
	local list = {}
	if type(nom) == "table" then
		for k, v in pairs(nom) do
			if type(v) ~= "table" then
				fail("E.pose({ Articulation = { rx = , ry = , rz = } }) attendu.")
			end
			table.insert(list, { k, v.rx or v[1] or 0, v.ry or v[2] or 0, v.rz or v[3] or 0, v.x or 0, v.y or 0, v.z or 0 })
		end
	else
		list[1] = { nom, rx or 0, ry or 0, rz or 0, x or 0, y or 0, z or 0 }
	end
	local done = {}
	stopPreview(animators(rig)) -- une piste d'aperçu en cours écraserait la pose
	for _, item in ipairs(list) do
		local j = resolveJoint(item[1])
		local motor = motorFor(rig, j)
		if not motor then
			fail("Motor6D « " .. j.name .. " » introuvable dans le rig : relancez AnatomieR6_Setup.lua.")
		end
		local v = {}
		for i, idx in ipairs({ 5, 6, 7, 2, 3, 4 }) do
			v[i] = checkNumber(item[idx], j.name .. " " .. POSE_FIELDS[i])
		end
		motor.Transform = toJointFrame(j, valuesToCF(v))
		table.insert(done, string.format("%s rx %s ry %s rz %s", j.name, fmt(v[4]), fmt(v[5]), fmt(v[6])))
	end
	table.sort(done)
	refresh(rig)
	return "Pose d'aperçu (aucune animation modifiée) : " .. table.concat(done, " ; ") .. "."
end

function E.reinitialiserPose()
	local rig = getRig(true)
	stopPreview(animators(rig))
	local n = resetMotors(rig)
	refresh(rig)
	return string.format("Rig au repos (%d articulations remises à zéro).", n)
end

function E.apercu(cle, temps)
	local rig = getRig(true)
	local kfs = requireSequence(cle)
	temps = checkNumber(temps == nil and 0 or temps, "temps")
	local frames, parts = readFrames(kfs)
	local duration = #frames > 0 and frames[#frames].t or 0
	temps = math.clamp(temps, 0, duration)
	local info = rigInfo()
	local animator = animators(rig)
	stopPreview(animator)
	resetMotors(rig)
	local method = "Animator"
	local ok, err = pcall(function()
		local id = game:GetService("KeyframeSequenceProvider"):RegisterKeyframeSequence(kfs)
		local anim = Instance.new("Animation")
		anim.Name = "SurvivantEditeur_Apercu"
		anim.AnimationId = id
		local track = animator:LoadAnimation(anim)
		track:Play(0, 1, 0)
		-- la première fois, l'animation enregistrée se charge en arrière-plan : attendre qu'elle soit prête
		local t0 = os.clock()
		while track.Length <= 0 and os.clock() - t0 < 3 do
			task.wait()
		end
		track.TimePosition = temps
		animator:StepAnimations(0.001)
		-- contrôle : l'Animator a-t-il bien posé le rig ?
		for _, name in ipairs(parts) do
			local j = info.byPart[name]
			local motor = motorFor(rig, j)
			local want = sampleFrames(frames, name, temps)
			if motor and want and not closeCFrame(motor.Transform, want) then
				error("pose de l'Animator différente des images clés (" .. name .. ")")
			end
		end
	end)
	if not ok then
		stopPreview(animator)
		resetMotors(rig)
		for _, name in ipairs(parts) do
			local motor = motorFor(rig, info.byPart[name])
			local want = sampleFrames(frames, name, temps)
			if motor and want then
				motor.Transform = want
			end
		end
		refresh(rig)
		method = "poses calculées par le module (" .. tostring(err) .. ")"
	end
	return string.format("Aperçu de « %s » (%s) à t = %s s sur %s, via %s. E.reinitialiserPose() remet le repos.",
		kfs.Name, keyOf(kfs), fmt(temps), RIG_NAME, method)
end

function E.lireAnimation(cle)
	local kfs = requireSequence(cle)
	local info = rigInfo()
	local frames, parts = readFrames(kfs)
	local key = keyOf(kfs)
	local meta = originalMeta(key)
	local out = {
		cle = key, nom = kfs.Name, libelle = kfs:GetAttribute("Survivant_Libelle") or (meta and meta.label) or key,
		duree = #frames > 0 and round(frames[#frames].t, 4) or 0, boucle = kfs.Loop, priorite = kfs.Priority.Name,
		vitesse = kfs:GetAttribute("Survivant_VitesseReference"), pieces = parts, images = {},
		modifiee = kfs:GetAttribute("Survivant_Modifiee") == true,
	}
	for _, fr in ipairs(frames) do
		local img = { t = round(fr.t, 4), poses = {} }
		for name, cf in pairs(fr.poses) do
			img.poses[name] = cfToList(toParentFrame(info.byPart[name], cf))
		end
		table.insert(out.images, img)
	end
	return out
end

local function writeAnimation(cle, d)
	if type(cle) ~= "string" or not string.match(cle, "^[%w_]+$") then
		fail("clé invalide « " .. tostring(cle) .. " » (lettres, chiffres et _ seulement, ex. \"walk\").")
	end
	if type(d) ~= "table" then
		fail("table d'animation attendue (même format que E.lireAnimation).")
	end
	local images = d.images or d.keyframes
	if type(images) ~= "table" or #images == 0 then
		fail("« images » doit être une liste non vide d'images clés { t = ..., poses = { ... } }.")
	end
	animFolder()
	local info = rigInfo()
	local existing = findSequence(cle)
	local meta = originalMeta(cle)
	local name = d.nom or (existing and existing.Name) or (meta and meta.name) or ("Survivant_" .. cle)
	if type(name) ~= "string" or name == "" then
		fail("« nom » invalide.")
	end
	local clash = animFolder():FindFirstChild(name)
	if clash and clash:IsA("KeyframeSequence") and clash ~= existing then
		fail("le nom « " .. name .. " » est déjà celui de l'animation « " .. keyOf(clash) .. " » : choisissez un autre nom.")
	end
	local loop = d.boucle
	if loop == nil then
		if existing then
			loop = existing.Loop
		else
			loop = meta ~= nil and meta.loop or false
		end
	end
	if type(loop) ~= "boolean" then
		fail("« boucle » doit valoir true ou false.")
	end
	local priority = d.priorite or (existing and existing.Priority.Name) or (meta and meta.priority) or "Action"
	if not pcall(function()
		return Enum.AnimationPriority[priority]
	end) then
		fail("priorité inconnue « " .. tostring(priority) .. " » (Idle, Movement, Action, Action2, Action3, Action4, Core).")
	end
	local label = d.libelle or (existing and existing:GetAttribute("Survivant_Libelle")) or (meta and meta.label) or cle
	local speed = d.vitesse
	if speed == nil then
		speed = (existing and existing:GetAttribute("Survivant_VitesseReference")) or (meta and meta.speed)
	elseif type(speed) ~= "number" or speed <= 0 then
		fail("« vitesse » doit être un nombre positif (studs/s) ou nil.")
	end

	local frames, keyed = {}, {}
	for i, img in ipairs(images) do
		local where = "image " .. i
		if type(img) ~= "table" then
			fail(where .. " : table { t = ..., poses = { ... } } attendue.")
		end
		local t = img.t
		if t == nil then
			t = img[1]
		end
		local poses = img.poses
		if poses == nil then
			poses = img[2]
		end
		checkNumber(t, where .. " (t)")
		if t < 0 then
			fail(where .. " : temps négatif.")
		end
		if type(poses) ~= "table" then
			fail(where .. " : « poses » doit être une table { Pièce = {x, y, z, rx, ry, rz} }.")
		end
		local fr = { t = t, poses = {} }
		for partName, p in pairs(poses) do
			local j = resolveJoint(partName)
			fr.poses[j.part1] = toJointFrame(j, valuesToCF(poseValues(p, where .. ", " .. tostring(partName))))
			keyed[j.part1] = true
		end
		table.insert(frames, fr)
	end
	table.sort(frames, function(a, b)
		return a.t < b.t
	end)
	for i = 2, #frames do
		if frames[i].t - frames[i - 1].t < EPS_T then
			fail("deux images clés au même instant (t = " .. fmt(frames[i].t) .. " s).")
		end
	end
	if d.pieces ~= nil then
		if type(d.pieces) ~= "table" then
			fail("« pieces » doit être une liste de noms de pièces.")
		end
		for _, n in ipairs(d.pieces) do
			keyed[resolveJoint(n).part1] = true
		end
	end
	local parts = {}
	for _, n in ipairs(info.order) do
		if keyed[n] then
			table.insert(parts, n)
		end
	end
	if #parts == 0 then
		fail("aucune pose : indiquez au moins une pièce dans « poses ».")
	end
	local kfs = buildSequence({ name = name, key = cle, label = label, loop = loop, priority = priority, speed = speed,
		parts = parts, frames = frames })
	local note = storeSequence(kfs, cle, existing, true)
	local loopNote = ""
	if loop and #frames > 1 then
		for _, n in ipairs(parts) do
			local a, b = frames[1].poses[n], frames[#frames].poses[n]
			if a and b and not sameCFrame(a, b) then
				loopNote = " Attention : la première et la dernière image diffèrent (" .. n .. "), la boucle sautera."
				break
			end
		end
	end
	return string.format("Animation « %s » (clé %s) écrite : %d images clés, %s s, %s, priorité %s, pièces : %s.%s%s",
		name, cle, #frames, fmt(frames[#frames].t), loop and "en boucle" or "une fois", priority,
		#parts == #info.order and "toutes" or table.concat(parts, ", "), note, loopNote)
end

function E.ecrireAnimation(cle, donnees)
	return recorded("Écrire l'animation " .. tostring(cle), writeAnimation, cle, donnees)
end

local CHANGE_INDEX = { x = 1, y = 2, z = 3, rx = 4, ry = 5, rz = 6 }

local function modifyPose(cle, temps, piece, changes)
	local kfs = requireSequence(cle)
	checkNumber(temps, "temps")
	local j = resolveJoint(piece)
	if type(changes) ~= "table" then
		fail("changements attendus, par exemple { rx = 40 } ou { rx = 10, relatif = true }.")
	end
	local relative = changes.relatif == true
	local set, any = {}, false
	for k, v in pairs(changes) do
		if k ~= "relatif" then
			local idx = CHANGE_INDEX[k] or ((type(k) == "number" and k >= 1 and k <= 6 and k == math.floor(k)) and k)
			if not idx then
				fail("changement inconnu « " .. tostring(k) .. " » (x, y, z, rx, ry, rz, relatif).")
			end
			set[idx] = checkNumber(v, tostring(k))
			any = true
		end
	end
	if not any then
		fail("aucun changement indiqué (x, y, z, rx, ry, rz).")
	end
	local key = keyOf(kfs)
	local frames, parts = readFrames(kfs)
	if #frames == 0 then
		fail("l'animation « " .. key .. " » n'a aucune image clé.")
	end
	local duration = frames[#frames].t
	if temps < -EPS_T or temps > duration + EPS_T then
		fail("temps hors de l'animation (0 à " .. fmt(duration) .. " s).")
	end
	temps = math.clamp(temps, 0, duration)
	local created = 0
	local function frameAt(t)
		for _, fr in ipairs(frames) do
			if math.abs(fr.t - t) < EPS_T then
				return fr
			end
		end
		local fr = { t = t, poses = {} }
		for _, n in ipairs(parts) do
			fr.poses[n] = sampleFrames(frames, n, t)
		end
		table.insert(frames, fr)
		table.sort(frames, function(a, b)
			return a.t < b.t
		end)
		created = created + 1
		return fr
	end
	local targets = { frameAt(temps) }
	if kfs.Loop and duration > EPS_T and (temps < EPS_T or math.abs(temps - duration) < EPS_T) then
		-- boucle : la première et la dernière image restent identiques
		local other = frameAt(temps < EPS_T and duration or 0)
		if other ~= targets[1] then
			table.insert(targets, other)
		end
	end
	local before, after
	for _, target in ipairs(targets) do
		local current = target.poses[j.part1] or sampleFrames(frames, j.part1, target.t) or CFrame.new()
		local vals = cfToValues(toParentFrame(j, current))
		before = before or cfToList(toParentFrame(j, current))
		for idx, v in pairs(set) do
			vals[idx] = relative and (vals[idx] + v) or v
		end
		target.poses[j.part1] = toJointFrame(j, valuesToCF(vals))
		after = after or cfToList(toParentFrame(j, target.poses[j.part1]))
	end
	local keyedNow = {}
	for _, n in ipairs(parts) do
		keyedNow[n] = true
	end
	keyedNow[j.part1] = true
	local newParts = {}
	for _, n in ipairs(rigInfo().order) do
		if keyedNow[n] then
			table.insert(newParts, n)
		end
	end
	local spec = specFrom(kfs, key)
	spec.parts, spec.frames = newParts, frames
	local note = storeSequence(buildSequence(spec), key, kfs, true)
	local function show(p)
		return string.format("{%s, %s, %s, %s, %s, %s}", fmt(p[1]), fmt(p[2]), fmt(p[3]), fmt(p[4]), fmt(p[5]), fmt(p[6]))
	end
	return string.format("« %s » à t = %s s, %s (%s) : %s -> %s%s%s.%s", key, fmt(temps), j.part1, j.name, show(before),
		show(after), created > 0 and string.format(" (%d image(s) clé(s) ajoutée(s))", created) or "",
		#targets > 1 and " ; première et dernière images de la boucle modifiées ensemble" or "", note)
end

function E.modifierPose(cle, temps, piece, changements)
	return recorded("Modifier une pose de " .. tostring(cle), modifyPose, cle, temps, piece, changements)
end

function E.restaurerAnimation(cle)
	if type(cle) ~= "string" then
		fail("clé d'animation attendue (texte).")
	end
	local meta = originalMeta(cle)
	if not meta then
		fail("pas de version d'origine pour « " .. cle .. " » (animations d'origine : " .. (function()
			local keys = {}
			for _, a in ipairs(data().ANIMS) do
				table.insert(keys, a.key)
			end
			return table.concat(keys, ", ")
		end)() .. ").")
	end
	return recorded("Restaurer l'animation " .. meta.key, function()
		animFolder()
		local frames = {}
		for _, k in ipairs(meta.keys) do
			local fr = { t = k[1], poses = {} }
			for i, name in ipairs(meta.parts) do
				local q = k[2][i]
				fr.poses[name] = CFrame.new(q[1], q[2], q[3], q[4], q[5], q[6], q[7])
			end
			table.insert(frames, fr)
		end
		local kfs = buildSequence({ name = meta.name, key = meta.key, label = meta.label, loop = meta.loop,
			priority = meta.priority, speed = meta.speed, parts = meta.parts, frames = frames })
		local note = storeSequence(kfs, meta.key, findSequence(meta.key), false)
		return string.format("Animation « %s » (%s) remise dans sa version d'origine (%d images clés).%s", meta.name,
			meta.key, #frames, note)
	end)
end

function E.importerDepuisEditeur(cle)
	local kfs = requireSequence(cle)
	local key = keyOf(kfs)
	local rig = getRig(true)
	local saves = ServerStorage:FindFirstChild("RBX_ANIMSAVES")
	local entry = saves and saves:FindFirstChild(rig.Name)
	local saved = entry and entry:FindFirstChild(kfs.Name)
	if not (saved and saved:IsA("KeyframeSequence")) then
		fail("aucune version « " .. kfs.Name .. " » dans ServerStorage.RBX_ANIMSAVES." .. rig.Name
			.. " (enregistrez-la depuis l'Éditeur d'animation sous ce nom).")
	end
	return recorded("Importer " .. kfs.Name .. " depuis l'Éditeur d'animation", function()
		local frames, parts = readFrames(saved)
		if #frames == 0 or #parts == 0 then
			fail("la version de l'Éditeur d'animation ne contient aucune pose du rig.")
		end
		local spec = specFrom(kfs, key)
		spec.loop, spec.priority = saved.Loop, saved.Priority.Name
		spec.parts, spec.frames = parts, frames
		local note = storeSequence(buildSequence(spec), key, kfs, true)
		return string.format("« %s » reprise de l'Éditeur d'animation : %d images clés, pièces : %s.%s", kfs.Name, #frames,
			#parts == #rigInfo().order and "toutes" or table.concat(parts, ", "), note)
	end)
end

function E.vitesses(tableau)
	local scripts = animateScripts()
	if #scripts == 0 then
		fail("aucun script Animate du survivant (rig, StarterCharacterScripts) : lancez SurvivantR6_Animations.lua.")
	end
	local current = parseSpeeds(scripts[1].Source)
	local function describe(sp)
		local parts = {}
		for _, k in ipairs(SPEED_ORDER) do
			local v = sp[k]
			local meta = originalMeta(SPEED_CLIPS[k])
			local ratio = (v and meta and meta.speed) and v / meta.speed or nil
			local warnTxt = ""
			if ratio and (ratio > 1.8 or ratio < 0.45) then
				warnTxt = ", les pieds glissent"
			end
			table.insert(parts, string.format("%s %s%s", k, v and fmt(v) or "?",
				ratio and string.format(" (animation x%s%s)", fmt(round(ratio, 2)), warnTxt) or ""))
		end
		return table.concat(parts, ", ")
	end
	if tableau == nil then
		return "Vitesses en jeu (studs/s) : " .. describe(current) .. ".", current
	end
	if type(tableau) ~= "table" then
		fail("table attendue, par exemple E.vitesses({ marche = 7, course = 18 }).")
	end
	local new = {}
	for k, v in pairs(current) do
		new[k] = v
	end
	for k, v in pairs(tableau) do
		if not SPEED_CLIPS[k] then
			fail("vitesse inconnue « " .. tostring(k) .. " » (marche, course, accroupi, allonge).")
		end
		checkNumber(v, k)
		if v <= 0 then
			fail(k .. " : vitesse positive attendue.")
		end
		new[k] = v
	end
	local literal = string.format("{ marche = %s, course = %s, accroupi = %s, allonge = %s }", fmt(new.marche or 6),
		fmt(new.course or 16), fmt(new.accroupi or 3), fmt(new.allonge or 1.5))
	return recorded("Vitesses du survivant", function()
		for _, scr in ipairs(scripts) do
			local src = string.gsub(scr.Source, "VITESSE%s*=%s*%b{}", function()
				return "VITESSE = " .. literal
			end, 1)
			writeSource(scr, src)
		end
		return string.format("Vitesses en jeu : %s ; %d script(s) Animate mis à jour (rig, StarterCharacterScripts).",
			describe(new), #scripts), new
	end)
end

function E.majPersonnageJouable()
	local rig = getRig(true)
	return recorded("Mettre à jour StarterCharacter", function()
		local old = StarterPlayer:FindFirstChild("StarterCharacter")
		local char = rig:Clone()
		char.Name = "StarterCharacter"
		local n = 0
		for _, d in ipairs(char:GetDescendants()) do
			if d:IsA("BasePart") then
				d.Anchored = false
				n = n + 1
			elseif d:IsA("Motor6D") then
				d.Transform = CFrame.new()
			end
		end
		local hrp = char:FindFirstChild("HumanoidRootPart")
		if hrp then
			char.PrimaryPart = hrp
		end
		local hum = char:FindFirstChildOfClass("Humanoid")
		if hum then
			local R = data().RIG
			hum.RigType = Enum.HumanoidRigType[R.rigType]
			hum.HipHeight = R.hipHeight
			pcall(function()
				hum.AutomaticScalingEnabled = false
			end)
			pcall(function()
				hum.RequiresNeck = false
			end)
		end
		-- le contrôleur du joueur tourne depuis StarterCharacterScripts (un « Animate » rangé dans le modèle
		-- serait remplacé au lancement par l'Animate R15 par défaut de Roblox)
		local note = ""
		local animate = char:FindFirstChild("Animate") or (old and old:FindFirstChild("Animate"))
		local scs = StarterPlayer:FindFirstChildOfClass("StarterCharacterScripts")
		local current = scs and scs:FindFirstChild("Animate")
		local ours = current and current:IsA("LocalScript") and string.find(current.Source, "VITESSE", 1, true) ~= nil
		if not ours then
			if animate and scs then
				if current then
					current:Destroy()
				end
				animate:Clone().Parent = scs
			else
				note = " Attention : pas de script Animate (lancez SurvivantR6_Animations.lua)."
			end
		end
		local inModel = char:FindFirstChild("Animate")
		if inModel then
			inModel:Destroy()
		end
		if old then
			old:Destroy()
		end
		char.Parent = StarterPlayer
		StarterPlayer.LoadCharacterAppearance = false -- l'avatar du joueur ne s'applique pas au survivant
		return string.format("StarterPlayer.StarterCharacter mis à jour depuis %s (%d pièces désancrées, articulations au "
			.. "repos).%s", RIG_NAME, n, note)
	end)
end

-- E.fonction(...) et E:fonction(...) marchent tous les deux.
for name, fn in pairs(E) do
	E[name] = function(first, ...)
		if first == E then
			return fn(...)
		end
		return fn(first, ...)
	end
end

return E
