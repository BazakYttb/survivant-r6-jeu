--[[
	SurvivantR6_Animations.lua  --  animations du survivant R6 articulé (Roblox Studio)
	=====================================================================================

	À coller dans la barre de commande APRÈS AnatomieR6_Setup.lua (Affichage > Barre de
	commande, collez TOUT ce fichier, Entrée). Ctrl+Z annule tout.

	Ce que fait le script
	  - crée les animations du rig articulé (coudes et genoux ; KeyframeSequence, une image clé
	    tous les 1/30 s au plus) dans ReplicatedStorage.SurvivantAnimations : repos, marche,
	    course, accroupi, marche accroupie, allongé, ramper, saut, chute, atterrissage,
	    s'allonger, se relever, grimper, assis, outil en main (bras droit seulement, superposée) ;
	  - les range aussi dans ServerStorage.RBX_ANIMSAVES pour l'éditeur d'animation (sélectionnez
	    le rig, Avatar > Éditeur d'animation, menu « … » > Charger) ;
	  - prépare ReplicatedStorage.SurvivantAnimations.AnimationIds : après avoir publié une
	    animation (clic droit sur la KeyframeSequence > « Save to Roblox… »), collez son
	    identifiant dans la valeur du même nom (les valeurs déjà remplies sont conservées, sauf
	    celles publiées pour l'ancien rig R6 à 6 pièces, qui ne conviennent plus) ;
	  - place le LocalScript « Animate » (contrôleur : Maj = courir, C = s'accroupir,
	    X = s'allonger, R = radiographie ; grimper, assis et outil automatiques) dans le rig
	    Anatomie_R6 (copie de référence) et dans StarterPlayer.StarterCharacterScripts (celui qui
	    tourne en jeu : un « Animate » rangé dans le StarterCharacter serait remplacé au lancement
	    par l'Animate R15 par défaut de Roblox) ;
	  - crée le personnage jouable StarterPlayer.StarterCharacter à partir du rig (réglable) ;
	  - enregistre le groupe de collision « SurvivantPosture » (le corps allongé ne soulève pas
	    le personnage) ;
	  - installe ServerStorage.SurvivantEditeur (ModuleScript, avec ses données dans le module
	    enfant « Donnees ») : fonctions pour poser le personnage et modifier les animations depuis
	    la barre de commande ou par un assistant IA connecté au serveur MCP de Roblox Studio.
	    Mode d'emploi : print(require(game.ServerStorage.SurvivantEditeur).aide())

	Tester : bouton Jouer (Play). Dans Studio, les animations non publiées sont jouées
	directement. Dans un jeu publié, il faut les publier (Roblox exige que les animations
	appartiennent au créateur du jeu) et coller les identifiants.
]]

local CONFIG = {
	RIG_NAME = "Anatomie_R6",
	-- true : crée / remplace StarterPlayer.StarterCharacter (copie du rig, désancrée).
	CREATE_STARTER_CHARACTER = true,
	-- true : StarterPlayer.LoadCharacterAppearance = false (pas de vêtements, d'accessoires ni de
	-- parties du corps de l'avatar du joueur par-dessus le survivant).
	KEEP_SURVIVOR_LOOK = true,
	-- true : les animations modifiées avec SurvivantEditeur (attribut Survivant_Modifiee) ne
	-- sont pas remplacées par les versions d'origine de ce script.
	KEEP_EDITED_ANIMATIONS = true,
	-- true : installe le module ServerStorage.SurvivantEditeur.
	INSTALL_EDITOR = true,
	COLLISION_GROUP = "SurvivantPosture",
}

--@@RIG@@

--@@ANIMS@@

local ANIMATE_SOURCE = --@@ANIMATE_SOURCE@@

local EDITOR_SOURCE = --@@EDITOR_SOURCE@@

------------------------------------------------------------------------------------------
local RIG_LABEL = "R6 articulé"
local Workspace = workspace
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local StarterPlayer = game:GetService("StarterPlayer")

-- Parent de chaque pièce dans la hiérarchie des poses (= Part0 de son Motor6D).
local PARENT = {}
for _, p in ipairs(RIG.parts) do
	PARENT[p.name] = p.parent
end

local report = { warnings = {}, notes = {} }
local function addWarning(msg)
	table.insert(report.warnings, msg)
	warn("[Survivant R6] " .. msg)
end
local function addNote(msg)
	table.insert(report.notes, msg)
end

local function getOrCreate(parent, className, name)
	local inst = parent:FindFirstChild(name)
	if inst and inst:IsA(className) then
		return inst, false
	end
	if inst then
		inst:Destroy()
	end
	inst = Instance.new(className)
	inst.Name = name
	inst.Parent = parent
	return inst, true
end

local function poseCFrame(t)
	return CFrame.new(t[1], t[2], t[3], t[4], t[5], t[6], t[7])
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

-- KeyframeSequence d'une animation. Les poses suivent la hiérarchie du rig (HumanoidRootPart >
-- Torso > Head, bras, jambes ; avant-bras et jambes sous leur bras / cuisse). Une animation
-- partielle (a.parts = quelques pièces, ex. « tool ») ne garde que ces pièces et leurs ancêtres ;
-- les ancêtres non animés ont une pose neutre de poids 0 (ils n'influencent pas l'animation).
local function buildSequence(a)
	local kfs = Instance.new("KeyframeSequence")
	kfs.Name = a.name
	kfs.Loop = a.loop
	kfs.Priority = Enum.AnimationPriority[a.priority]
	pcall(function()
		kfs:SetAttribute("Survivant_Cle", a.key)
		kfs:SetAttribute("Survivant_Libelle", a.label)
		kfs:SetAttribute("Survivant_Pieces", table.concat(a.parts, ","))
		if a.speed then
			kfs:SetAttribute("Survivant_VitesseReference", a.speed)
		end
	end)
	local column, needed = {}, {}
	for i, name in ipairs(a.parts) do
		column[name] = i
		local n = name
		while n and n ~= "HumanoidRootPart" do
			needed[n] = true
			n = PARENT[n]
		end
	end
	for _, k in ipairs(a.keys) do
		local kf = Instance.new("Keyframe")
		kf.Time = k[1]
		local poses = { HumanoidRootPart = newPose("HumanoidRootPart", CFrame.new(), 0) }
		for _, name in ipairs(RIG.poseOrder) do
			if needed[name] then
				local i = column[name]
				local p = newPose(name, i and poseCFrame(k[2][i]) or CFrame.new(), i and 1 or 0)
				p.Parent = poses[PARENT[name]]
				poses[name] = p
			end
		end
		poses.HumanoidRootPart.Parent = kf
		kf.Parent = kfs
	end
	return kfs
end

local function replaceChild(parent, inst)
	local old = parent:FindFirstChild(inst.Name)
	if old then
		old:Destroy()
	end
	inst.Parent = parent
end

-- Texte Lua d'une valeur (données du module Donnees) : nombres, chaînes, booléens, tables.
local function serialize(v, indent)
	indent = indent or ""
	local t = type(v)
	if t == "number" then
		if v ~= v or v == math.huge or v == -math.huge then
			error("nombre invalide dans les données")
		end
		if v == math.floor(v) and math.abs(v) < 1e15 then
			return string.format("%d", v)
		end
		return string.format("%.10g", v)
	elseif t == "string" then
		return string.format("%q", v)
	elseif t == "boolean" then
		return tostring(v)
	elseif t ~= "table" then
		error("type non sérialisable : " .. t)
	end
	local n = #v
	local keys = {}
	for k in pairs(v) do
		if not (type(k) == "number" and k >= 1 and k <= n and k == math.floor(k)) then
			table.insert(keys, k)
		end
	end
	table.sort(keys, function(a, b)
		return tostring(a) < tostring(b)
	end)
	local items = {}
	for i = 1, n do
		table.insert(items, serialize(v[i], indent .. "\t"))
	end
	for _, k in ipairs(keys) do
		local ks = (type(k) == "string" and string.match(k, "^[%a_][%w_]*$")) and k or ("[" .. serialize(k) .. "]")
		table.insert(items, ks .. " = " .. serialize(v[k], indent .. "\t"))
	end
	local inline = "{ " .. table.concat(items, ", ") .. " }"
	if #items == 0 then
		return "{}"
	elseif #inline <= 160 and not string.find(inline, "\n", 1, true) then
		return inline
	end
	return "{\n" .. indent .. "\t" .. table.concat(items, ",\n" .. indent .. "\t") .. ",\n" .. indent .. "}"
end

local function installAnimate(parent, where)
	local old = parent:FindFirstChild("Animate")
	if old then
		local ours = old:IsA("LocalScript") and string.find(old.Source, "VITESSE", 1, true) ~= nil
		if not ours then
			addWarning("Le script « Animate » qui était dans " .. where .. " (pas celui du survivant) a été remplacé.")
		end
		old:Destroy()
	end
	local ls = Instance.new("LocalScript")
	ls.Name = "Animate"
	ls.Source = ANIMATE_SOURCE
	ls.Parent = parent
	addNote("Contrôleur « Animate » installé dans " .. where .. ".")
	return ls
end

local function installEditor()
	local old = ServerStorage:FindFirstChild("SurvivantEditeur")
	if old then
		old:Destroy()
	end
	local module = Instance.new("ModuleScript")
	module.Name = "SurvivantEditeur"
	module.Source = EDITOR_SOURCE
	local donnees = Instance.new("ModuleScript")
	donnees.Name = "Donnees"
	donnees.Source = "-- Données d'origine du survivant R6 articulé (générées par SurvivantR6_Animations.lua) :\n"
		.. "-- RIG = pièces, Motor6D et pivots ; ANIMS = animations (poses {x, y, z, qx, qy, qz, qw} = Motor6D.Transform).\n"
		.. "-- Ne pas modifier : SurvivantEditeur s'en sert pour E.restaurerAnimation et la description du rig.\n"
		.. "return " .. serialize({ RIG = RIG, ANIMS = ANIMS }) .. "\n"
	donnees.Parent = module
	module.Parent = ServerStorage
	addNote("Éditeur installé : ServerStorage.SurvivantEditeur (mode d'emploi : "
		.. "print(require(game.ServerStorage.SurvivantEditeur).aide())).")
end

local function isJointedRig(model)
	return model:FindFirstChildOfClass("Humanoid") ~= nil and model:FindFirstChild("Torso") ~= nil
		and model:FindFirstChild("RightLowerArm") ~= nil and model:FindFirstChild("LeftLowerLeg") ~= nil
end

local function main()
	local rig = Workspace:FindFirstChild(CONFIG.RIG_NAME)
	if rig and not rig:IsA("Model") then
		rig = nil
	end
	if not rig then
		addWarning("Rig « " .. CONFIG.RIG_NAME .. " » introuvable : lancez d'abord AnatomieR6_Setup.lua. Les animations "
			.. "sont quand même créées.")
	elseif not isJointedRig(rig) then
		addWarning("« " .. CONFIG.RIG_NAME .. " » n'est pas le rig " .. RIG_LABEL .. " (coudes et genoux) : importez le "
			.. "nouveau modèle et relancez AnatomieR6_Setup.lua, puis ce script. Contrôleur et personnage jouable non "
			.. "installés.")
		rig = nil
	end

	-- 1) animations
	local folder = getOrCreate(ReplicatedStorage, "Folder", "SurvivantAnimations")
	local ids = getOrCreate(folder, "Folder", "AnimationIds")
	local built, frames, kept, cleared = {}, 0, {}, {}
	for _, a in ipairs(ANIMS) do
		local existing = folder:FindFirstChild(a.name)
		local kfs
		if CONFIG.KEEP_EDITED_ANIMATIONS and existing and existing:IsA("KeyframeSequence")
			and existing:GetAttribute("Survivant_Modifiee") == true then
			kfs = existing
			table.insert(kept, a.name)
		else
			kfs = buildSequence(a)
			replaceChild(folder, kfs)
			frames = frames + #a.keys
		end
		built[#built + 1] = kfs
		local v = ids:FindFirstChild(a.key)
		if not (v and v:IsA("StringValue")) then
			if v then
				v:Destroy()
			end
			v = Instance.new("StringValue")
			v.Name = a.key
			v.Value = ""
			v.Parent = ids
		elseif v:GetAttribute("Survivant_Rig") ~= RIG_LABEL and v.Value ~= "" then
			-- identifiant publié pour l'ancien rig R6 à 6 pièces : ses poses ne correspondent plus
			pcall(function()
				v:SetAttribute("AncienIdentifiant", v.Value)
			end)
			v.Value = ""
			table.insert(cleared, a.name)
		end
		pcall(function()
			v:SetAttribute("Animation", a.name)
			v:SetAttribute("Survivant_Rig", RIG_LABEL)
		end)
	end
	if #kept > 0 then
		addNote("Animations modifiées avec SurvivantEditeur conservées : " .. table.concat(kept, ", ")
			.. " (E.restaurerAnimation(clé) remet la version d'origine).")
	end
	if #cleared > 0 then
		addWarning("Identifiants publiés pour l'ancien rig R6 effacés (gardés dans l'attribut AncienIdentifiant) : "
			.. table.concat(cleared, ", ") .. ". Republiez ces animations pour un jeu publié.")
	end

	-- 2) copies pour l'éditeur d'animation
	if rig then
		local saves = getOrCreate(ServerStorage, "Model", "RBX_ANIMSAVES")
		local entry = saves:FindFirstChild(rig.Name)
		if not (entry and entry:IsA("ObjectValue")) then
			if entry then
				entry:Destroy()
			end
			entry = Instance.new("ObjectValue")
			entry.Name = rig.Name
			entry.Parent = saves
		end
		entry.Value = rig
		for _, kfs in ipairs(built) do
			replaceChild(entry, kfs:Clone())
		end
	end

	-- 3) groupe de collision
	local okGroup, errGroup = pcall(function()
		local PhysicsService = game:GetService("PhysicsService")
		if not PhysicsService:IsCollisionGroupRegistered(CONFIG.COLLISION_GROUP) then
			PhysicsService:RegisterCollisionGroup(CONFIG.COLLISION_GROUP)
		end
		PhysicsService:CollisionGroupSetCollidable(CONFIG.COLLISION_GROUP, "Default", false)
	end)
	if not okGroup then
		addWarning("Groupe de collision non créé (" .. tostring(errGroup) .. ") : allongé, le personnage peut tressauter.")
	end

	-- 4) contrôleur et personnage jouable
	if rig then
		installAnimate(rig, CONFIG.RIG_NAME)
		local anchored = rig:FindFirstChild("HumanoidRootPart")
		if CONFIG.CREATE_STARTER_CHARACTER then
			local old = StarterPlayer:FindFirstChild("StarterCharacter")
			if old then
				old:Destroy()
			end
			local char = rig:Clone()
			char.Name = "StarterCharacter"
			-- le contrôleur du joueur est dans StarterCharacterScripts (voir plus bas), pas dans le modèle
			local cloneAnimate = char:FindFirstChild("Animate")
			if cloneAnimate then
				cloneAnimate:Destroy()
			end
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
				hum.RigType = Enum.HumanoidRigType[RIG.rigType]
				hum.HipHeight = RIG.hipHeight
				pcall(function()
					hum.AutomaticScalingEnabled = false
				end)
				pcall(function()
					hum.RequiresNeck = false
				end)
			end
			char.Parent = StarterPlayer
			addNote("StarterPlayer.StarterCharacter créé (" .. n .. " pièces désancrées, Humanoid " .. RIG.rigType
				.. ", HipHeight " .. tostring(RIG.hipHeight) .. ") : le joueur incarne le survivant.")
			if CONFIG.KEEP_SURVIVOR_LOOK then
				-- propriété de StarterPlayer (Players n'en a pas) : sinon Roblox habille le survivant avec
				-- l'avatar du joueur et remplace ses membres R15 (RightUpperArm...) par ceux de l'avatar
				StarterPlayer.LoadCharacterAppearance = false
			end
		end
		-- Contrôleur du personnage jouable : dans StarterCharacterScripts. Au lancement, Roblox remplace le
		-- script « Animate » d'un StarterCharacter par son Animate R15 par défaut (danses, emotes...), dont
		-- les animations tordent ce rig ; il ne le fait pas si StarterCharacterScripts contient un « Animate ».
		if StarterPlayer:FindFirstChild("StarterCharacter") then
			local inModel = StarterPlayer.StarterCharacter:FindFirstChild("Animate")
			if inModel then
				inModel:Destroy()
			end
			local scs = StarterPlayer:FindFirstChildOfClass("StarterCharacterScripts")
			if scs then
				installAnimate(scs, "StarterPlayer.StarterCharacterScripts")
			else
				addWarning("StarterPlayer.StarterCharacterScripts introuvable : contrôleur du joueur non installé.")
			end
		end
		if anchored and anchored:IsA("BasePart") and not anchored.Anchored then
			addNote("Le rig du Workspace n'est pas ancré : il tombera au lancement du jeu.")
		end
	end

	-- 5) éditeur (barre de commande / assistant IA)
	if CONFIG.INSTALL_EDITOR then
		local okEditor, errEditor = pcall(installEditor)
		if not okEditor then
			addWarning("Éditeur SurvivantEditeur non installé : " .. tostring(errEditor))
		end
	end

	-- résumé
	local lines = { "", "============ SURVIVANT R6 ARTICULÉ : ANIMATIONS ============" }
	table.insert(lines, string.format("%d animations créées (%d images clés) dans ReplicatedStorage.SurvivantAnimations :",
		#built, frames))
	local names = {}
	for _, a in ipairs(ANIMS) do
		local partial = #a.parts < #RIG.poseOrder and " (superposée)" or ""
		table.insert(names, a.label .. (a.loop and "" or " (une fois)") .. partial)
	end
	table.insert(lines, "   " .. table.concat(names, ", "))
	for _, n in ipairs(report.notes) do
		table.insert(lines, "Note : " .. n)
	end
	if #report.warnings > 0 then
		table.insert(lines, "AVERTISSEMENTS (" .. #report.warnings .. ") :")
		for _, w in ipairs(report.warnings) do
			table.insert(lines, "   - " .. w)
		end
	end
	table.insert(lines, "Commandes en jeu : Maj = courir, C = s'accroupir, X = s'allonger, R = radiographie.")
	table.insert(lines, "Jeu publié : publiez chaque KeyframeSequence (clic droit > Save to Roblox) et collez les "
		.. "identifiants dans SurvivantAnimations.AnimationIds.")
	table.insert(lines, "============================================================")
	print(table.concat(lines, "\n"))
end

local ChangeHistoryService = game:GetService("ChangeHistoryService")
local recording = nil
do
	local ok, id = pcall(function()
		return ChangeHistoryService:TryBeginRecording("SurvivantR6", "Animations du survivant R6 articulé")
	end)
	if ok and id then
		recording = id
	else
		pcall(function()
			ChangeHistoryService:SetWaypoint("SurvivantR6 - avant")
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
		ChangeHistoryService:SetWaypoint("SurvivantR6 - après")
	end)
end
if not okMain then
	warn("[Survivant R6] ERREUR INATTENDUE : " .. tostring(errMain))
end
