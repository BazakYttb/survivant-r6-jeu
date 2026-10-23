--[[
	test_setup.lua - tests hors ligne des scripts Roblox du survivant R6 articulé :
	AnatomieR6_Setup.lua, AnatomieR6_Outils.lua, SurvivantR6_Animations.lua, le contrôleur
	« Animate » et le module SurvivantEditeur, sur l'émulation rbx_mock.lua, avec un interpréteur
	Luau autonome exposant readfile/loadstring.

	cd roblox && luaurun test/rbx_mock.lua test/test_setup.lua
]]

local SETUP_PATH = "AnatomieR6_Setup.lua"
local TEMPLATE_PATH = "AnatomieR6_Setup.template.lua"
local OUTILS_PATH = "AnatomieR6_Outils.lua"

local STATE = MOCK.STATE
local failures, checks = 0, 0
local function check(cond, msg)
	checks = checks + 1
	if not cond then
		failures = failures + 1
		MOCK.rawPrint("  ÉCHEC : " .. msg)
	end
end
local function section(name)
	MOCK.rawPrint("== " .. name)
end

local function cfErr(a, b)
	local ax = { a:GetComponents() }
	local bx = { b:GetComponents() }
	local ep, er = 0, 0
	for i = 1, 3 do
		ep = math.max(ep, math.abs(ax[i] - bx[i]))
	end
	for i = 4, 12 do
		er = math.max(er, math.abs(ax[i] - bx[i]))
	end
	return ep, er
end
local function cfClose(a, b, epsP, epsR)
	local ep, er = cfErr(a, b)
	return ep < (epsP or 1e-6) and er < (epsR or epsP or 1e-6)
end
local function v3Err(a, b)
	return (a - b).Magnitude
end

-- Rotation aléatoire (axe-angle uniforme suffisant pour le test).
local function randomRotation()
	local axis
	repeat
		axis = Vector3.new(math.random() * 2 - 1, math.random() * 2 - 1, math.random() * 2 - 1)
	until axis.Magnitude > 0.1 and axis.Magnitude <= 1
	return CFrame.fromAxisAngle(axis, math.random() * 2 * math.pi)
end

local function readSource(path)
	local s, e = readfile(path)
	assert(s, e)
	return s
end

local function runSource(src, name)
	local f, e = loadstring(src, "@" .. name)
	assert(f, e)
	f()
end

local SETUP = readSource(SETUP_PATH)
local TEMPLATE = readSource(TEMPLATE_PATH)
local OUTILS = readSource(OUTILS_PATH)
local EXPECTED = (loadstring(readSource("test/expected_anims.lua"), "@expected_anims.lua"))()
local RIG, CLIPS = EXPECTED.RIG, EXPECTED.CLIPS
local function clipOf(key)
	for _, e in ipairs(CLIPS) do
		if e.key == key then
			return e
		end
	end
	return nil
end

local function runSetup(src)
	MOCK.quiet = true
	runSource(src or SETUP, SETUP_PATH)
	MOCK.quiet = false
end

local function vec(t)
	return Vector3.new(t[1], t[2], t[3])
end
local function cf12(t)
	return CFrame.new(t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9], t[10], t[11], t[12])
end
local PARTS10 = RIG.poseOrder
local SPEC, REST, PARENT = {}, {}, {}
for _, p in ipairs(RIG.parts) do
	SPEC[p.name] = p
	REST[p.name] = CFrame.new(vec(p.center))
	PARENT[p.name] = p.parent
end
local JOINT_OF = {}
for _, j in ipairs(RIG.joints) do
	JOINT_OF[j.part1] = j
end

-- Table PARTS du script généré (manifeste).
local PT
do
	local i0 = string.find(SETUP, "\nPARTS = {\n", 1, true)
	local i1 = string.find(SETUP, "\n}\n", i0, true)
	assert(i0 and i1, "table PARTS introuvable dans " .. SETUP_PATH)
	PT = (loadstring("local " .. string.sub(SETUP, i0 + 1, i1 + 1) .. "return PARTS", "@PARTS"))()
end

local MARKERS = {
	REF_A = Vector3.new(0, 0, 0),
	REF_B = Vector3.new(0, 2.2, 0),
	REF_C = Vector3.new(-1.5, 0, 0),
	REF_D = Vector3.new(0, 0, -0.6),
}

local function addBaseplate()
	local bp = Instance.new("Part")
	bp.Name = "Baseplate"
	bp.Size = Vector3.new(512, 16, 512)
	bp.CFrame = CFrame.new(0, -8, 0)
	bp.Anchored = true
	bp.Parent = workspace
	return bp
end

--[[ Crée un import factice.
	spec.k      : unités importées par stud du rig (l'échelle à retrouver vaut 1/k)
	spec.rot    : rotation (CFrame) appliquée par l'import
	spec.origin : position monde de REF_A
	spec.mirror : true -> marqueurs en miroir
	spec.parts  : { {name=, rig=CFrame (espace rig), size=Vector3, parent=<nom parent ou nil>, class=,
	              seg = pièce du rig attendue (anatomie), skin = pièce du rig attendue (tenue), gear = } }
	Retourne le Model et la table name -> {inst, rig, size, seg, skin, gear}
]]
local function makeImport(spec)
	local model = Instance.new("Model")
	model.Name = spec.name or "anatomie_r6"
	local k, rot, origin = spec.k, spec.rot, spec.origin
	local M = CFrame.new(origin) * rot
	local function toImp(rigCF)
		local p = rigCF.Position
		if spec.mirror then
			p = Vector3.new(-p.X, p.Y, p.Z)
		end
		local pos = M * (p * k)
		return CFrame.new(pos) * (rot * rigCF.Rotation)
	end
	local byName, info = {}, {}
	local sub = Instance.new("Model")
	sub.Name = "Groupe"
	sub.Parent = model
	local folder = Instance.new("Folder")
	folder.Name = "Dossier"
	folder.Parent = sub
	for _, pd in ipairs(spec.parts) do
		local p = Instance.new(pd.class or "MeshPart")
		p.Name = pd.name
		p.Size = pd.size * k
		p.CFrame = toImp(pd.rig)
		p.Anchored = true
		p.Color = Color3.new(0.5, 0.5, 0.5)
		local parent = model
		if pd.parent == "sub" then
			parent = sub
		elseif pd.parent == "folder" then
			parent = folder
		elseif pd.parent then
			parent = byName[pd.parent]
		end
		p.Parent = parent
		byName[pd.name] = p
		info[pd.key or pd.name] = { inst = p, rig = pd.rig, size = pd.size, seg = pd.seg, skin = pd.skin, gear = pd.gear,
			name = pd.key or pd.name }
	end
	for name, pos in pairs(MARKERS) do
		if not (spec.skip and spec.skip[name]) then
			local m = Instance.new("MeshPart")
			m.Name = name
			m.Size = Vector3.new(0.02, 0.02, 0.02) * k
			m.CFrame = toImp(CFrame.new(pos)) * randomRotation()
			m.Anchored = true
			m.Parent = spec.markerParent and byName[spec.markerParent] or model
		end
	end
	model.Parent = spec.into or workspace
	return model, info
end

local function rigOf()
	return workspace:FindFirstChild("Anatomie_R6")
end

local function welds(p)
	local list = {}
	for _, c in ipairs(p:GetChildren()) do
		if c:IsA("WeldConstraint") or c:IsA("JointInstance") then
			table.insert(list, c)
		end
	end
	return list
end

-- Vérifie les pièces anatomiques placées : CFrame relative à leur pièce du rig = CFrame attendue en espace rig.
local function checkPlaced(info, label, eps)
	eps = eps or 1e-6
	local rig = rigOf()
	for key, d in pairs(info) do
		if d.seg then
			local p = rig:FindFirstChild(key, true)
			check(p ~= nil, label .. " : pièce " .. key .. " absente du rig")
			if p then
				check(p.Parent == rig.Anatomie[d.seg], label .. " : " .. key .. " rangée dans "
					.. p.Parent:GetFullName() .. " au lieu de " .. d.seg)
				local part = rig[d.seg]
				local expected = part.CFrame * REST[d.seg]:Inverse() * d.rig
				local ep, er = cfErr(p.CFrame, expected)
				check(ep < eps and er < eps, string.format("%s : %s mal placée (pos %.2e, rot %.2e)", label, key, ep, er))
				check(v3Err(p.Size, d.size) < eps, label .. " : taille de " .. key .. " = " .. tostring(p.Size)
					.. " au lieu de " .. tostring(d.size))
				check(p.Anchored == false and p.CanCollide == false and p.CanTouch == false and p.CanQuery == false
					and p.Massless == true and p.CastShadow == true, label .. " : propriétés physiques de " .. key)
				local w = welds(p)
				check(#w == 1 and w[1]:IsA("WeldConstraint") and w[1].Part0 == part and w[1].Part1 == p,
					label .. " : soudure de " .. key .. " à " .. d.seg)
				check(p:GetAttribute("Anat_Membre") == d.seg, label .. " : attribut Anat_Membre de " .. key)
				check(type(p:GetAttribute("Anat_Categorie")) == "string", label .. " : attribut Anat_Categorie de " .. key)
			end
		end
	end
end

local SURV = {
	Head = Color3.fromRGB(212, 156, 120), Torso = Color3.fromRGB(72, 80, 48),
	RightUpperArm = Color3.fromRGB(72, 80, 48), LeftUpperArm = Color3.fromRGB(72, 80, 48),
	RightLowerArm = Color3.fromRGB(212, 156, 120), LeftLowerArm = Color3.fromRGB(212, 156, 120),
	RightUpperLeg = Color3.fromRGB(42, 54, 78), LeftUpperLeg = Color3.fromRGB(42, 54, 78),
	RightLowerLeg = Color3.fromRGB(98, 64, 40), LeftLowerLeg = Color3.fromRGB(98, 64, 40),
}
local DEFAULT_T = 0
local R_ROOT = CFrame.new(0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0)

local function motorParent(j)
	return (j.part0 == "HumanoidRootPart" or j.part1 == "Head") and j.part0 or j.part1
end

-- skinBlocks : pièces dont le bloc Roblox sert de peau (nil = toutes, mode "blocs") ;
-- face : decal « face » attendu sur la tête-bloc (SHOW_FACE ou outil 9).
local function checkRigStructure(label, skinBlocks, transp, face, model)
	transp = transp or DEFAULT_T
	local rig = model or rigOf()
	check(rig ~= nil and rig:IsA("Model"), label .. " : rig absent")
	if not rig then
		return
	end
	local hum = rig:FindFirstChildOfClass("Humanoid")
	check(hum ~= nil and hum.RigType == Enum.HumanoidRigType.R15 and hum.HipHeight == RIG.hipHeight
		and hum.AutomaticScalingEnabled == false and hum.RequiresNeck == false,
		label .. " : Humanoid R15, HipHeight " .. tostring(RIG.hipHeight) .. ", sans mise à l'échelle")
	local hrp = rig.HumanoidRootPart
	check(rig.PrimaryPart == hrp, label .. " : PrimaryPart")
	check(hrp.Transparency == 1 and hrp.CanCollide == true and (model ~= nil or hrp.Anchored == true), label .. " : HRP")
	check(v3Err(hrp.Size, vec(SPEC.HumanoidRootPart.size)) < 1e-9, label .. " : taille HRP")
	for _, name in ipairs(PARTS10) do
		local p = rig:FindFirstChild(name)
		check(p ~= nil and p:IsA("BasePart"), label .. " : pièce " .. name)
		if p then
			check(v3Err(p.Size, vec(SPEC[name].size)) < 1e-9, label .. " : taille " .. name)
			check(p.CanCollide == (name == "Torso" or name == "Head"), label .. " : CanCollide de " .. name)
			local isBlock = skinBlocks == nil or skinBlocks[name] == true
			check(math.abs(p.Transparency - (isBlock and transp or 1)) < 1e-9 and p.CastShadow == false
				and p.Material == Enum.Material.SmoothPlastic and p.Color == SURV[name],
				label .. " : peau du bloc " .. name .. " (Transparency " .. tostring(p.Transparency) .. ")")
			check((p:GetAttribute("Anat_Peau") == true) == isBlock, label .. " : attribut Anat_Peau du bloc " .. name)
			check(p.Anchored == false, label .. " : " .. name .. " doit être désancré")
			check(cfClose(hrp.CFrame:Inverse() * p.CFrame, REST[name]), label .. " : " .. name .. " au repos")
		end
	end
	for _, n in ipairs({ "Left Arm", "Right Arm", "Left Leg", "Right Leg" }) do
		check(rig:FindFirstChild(n) == nil, label .. " : pas de membre R6 « " .. n .. " »")
	end
	local mesh = rig.Head:FindFirstChildOfClass("SpecialMesh")
	check(mesh ~= nil and mesh.MeshType == Enum.MeshType.Head and v3Err(mesh.Scale, Vector3.new(1.25, 1.25, 1.25)) < 1e-9,
		label .. " : SpecialMesh de la tête")
	local decal = rig.Head:FindFirstChild("face")
	if face and (skinBlocks == nil or skinBlocks.Head) then
		check(decal ~= nil and decal:IsA("Decal") and decal.Texture == "rbxasset://textures/face.png"
			and decal.Face == Enum.NormalId.Front and math.abs(decal.Transparency - transp) < 1e-9,
			label .. " : visage decal sur la tête-bloc")
	else
		check(decal == nil, label .. " : pas de decal « face »")
	end
	-- Motor6D : noms, rangement, Part0/Part1, C0/C1 = RIG, cohérence Part0*C0 == Part1*C1, pivots.
	local nMotors = 0
	for _, d in ipairs(rig:GetDescendants()) do
		if d:IsA("Motor6D") then
			nMotors = nMotors + 1
		end
	end
	check(nMotors == #RIG.joints and #RIG.joints == 10, label .. " : 10 Motor6D (" .. nMotors .. ")")
	for _, j in ipairs(RIG.joints) do
		local motor = rig[motorParent(j)]:FindFirstChild(j.name)
		check(motor ~= nil and motor.ClassName == "Motor6D", label .. " : Motor6D " .. j.name .. " dans " .. motorParent(j))
		if motor then
			check(motor.Part0 == rig[j.part0] and motor.Part1 == rig[j.part1], label .. " : Part0/Part1 de " .. j.name)
			check(cfClose(motor.C0, cf12(j.c0), 1e-12) and cfClose(motor.C1, cf12(j.c1), 1e-12), label .. " : C0/C1 de " .. j.name)
			check(cfClose(motor.Part0.CFrame * motor.C0, motor.Part1.CFrame * motor.C1),
				label .. " : " .. j.name .. " incohérent avec la pose des pièces")
			check(v3Err((motor.Part0.CFrame * motor.C0).Position, hrp.CFrame * vec(j.pivot)) < 1e-6,
				label .. " : pivot de " .. j.name)
		end
	end
	-- Main pour les outils.
	local H = RIG.hand
	local hand = rig:FindFirstChild(H.name)
	check(hand ~= nil and hand:IsA("BasePart") and hand.Transparency == 1 and hand.CanCollide == false
		and hand.Massless == true and hand.Anchored == false and v3Err(hand.Size, vec(H.size)) < 1e-9, label .. " : RightHand")
	if hand then
		local att = hand:FindFirstChild(H.attachment)
		check(att ~= nil and att:IsA("Attachment") and cfClose(att.CFrame, CFrame.new(0, 0, 0, table.unpack(H.rotation)), 1e-12),
			label .. " : RightGripAttachment")
		local wrist = hand:FindFirstChildWhichIsA("JointInstance")
		check(wrist ~= nil and wrist.Part0 == rig[H.part0] and wrist.Part1 == hand, label .. " : main soudée à " .. H.part0)
		if wrist then
			check(cfClose(wrist.Part0.CFrame * wrist.C0, hand.CFrame * wrist.C1), label .. " : soudure de la main cohérente")
		end
		check(v3Err(hand.Position, hrp.CFrame * vec(H.center)) < 1e-6, label .. " : main au niveau de la paume")
	end
	local anat = rig:FindFirstChild("Anatomie")
	check(anat ~= nil and #anat:GetChildren() == #PARTS10, label .. " : dossier Anatomie (10 sous-dossiers)")
	for _, name in ipairs(PARTS10) do
		check(anat ~= nil and anat:FindFirstChild(name) ~= nil, label .. " : dossier Anatomie." .. name)
	end
	check(rig:FindFirstChild("Peau") ~= nil, label .. " : dossier Peau")
end

local function countWarn(pattern)
	local n = 0
	for _, w in ipairs(MOCK.warnings) do
		if string.find(w, pattern, 1, true) then
			n = n + 1
		end
	end
	return n
end
local function printedContains(pattern)
	for _, s in ipairs(MOCK.printed) do
		if string.find(s, pattern, 1, true) then
			return true
		end
	end
	return false
end

local function standardParts()
	local R = randomRotation
	return {
		{ name = "Head_Skull_Face", rig = CFrame.new(0, 1.55, -0.1) * R(), size = Vector3.new(0.9, 0.7, 0.8), seg = "Head" },
		{ name = "Head_Skull_Calvaria", rig = CFrame.new(0, 1.85, 0.05) * R(), size = Vector3.new(0.95, 0.5, 1.0),
			parent = "Head_Skull_Face", seg = "Head" },
		{ name = "Torso_Rib_Supplementaire", rig = CFrame.new(-0.6, 0.3, 0.0) * R(), size = Vector3.new(0.5, 0.2, 0.7),
			parent = "sub", seg = "Torso" },
		{ name = "LeftUpperArm_Humerus.001", key = "LeftUpperArm_Humerus", rig = CFrame.new(-1.45, 0.4, 0.02) * R(),
			size = Vector3.new(0.12, 0.9, 0.12), parent = "folder", seg = "LeftUpperArm" },
		{ name = "RightUpperLeg_Nerves", rig = CFrame.new(0.52, -1.5, 0.05) * R(), size = Vector3.new(0.2, 0.9, 0.3),
			parent = "Torso_Rib_Supplementaire", seg = "RightUpperLeg" },
		{ name = "Mystere", rig = CFrame.new(-0.45, -2.3, 0.1) * R(), size = Vector3.new(0.1, 0.1, 0.1), seg = "LeftLowerLeg" },
		{ name = "Objet_Inconnu", rig = CFrame.new(1.45, -0.7, 0.1) * R(), size = Vector3.new(0.1, 0.1, 0.1),
			seg = "RightLowerArm" },
		{ name = "RightLowerArm_Ulna", rig = CFrame.new(1.4, -0.5, 0.0) * R(), size = Vector3.new(0.1, 0.8, 0.1),
			seg = "RightLowerArm" },
		{ name = "Head_Eye_L", class = "Part", rig = CFrame.new(-0.2, 1.6, -0.45) * R(), size = Vector3.new(0.1, 0.1, 0.1),
			seg = "Head" },
		-- anciennes régions R6 (bras / jambe d'un seul tenant) : coupées au coude / genou selon la hauteur
		{ name = "LeftArm_Ancien", rig = CFrame.new(-1.5, -0.6, 0) * R(), size = Vector3.new(0.1, 0.4, 0.1),
			seg = "LeftLowerArm" },
		{ name = "RightLeg_Ancien", rig = CFrame.new(0.5, -1.5, 0) * R(), size = Vector3.new(0.1, 0.4, 0.1),
			seg = "RightUpperLeg" },
	}
end

-- Pièces de la tenue, imports avec tenue
local SKIN_SEGMENTS = { "RightUpperArm", "RightLowerArm", "LeftUpperArm", "LeftLowerArm", "RightUpperLeg", "RightLowerLeg",
	"LeftUpperLeg", "LeftLowerLeg" }
local function skinPartsSpec(only)
	local R = randomRotation
	local all = {
		{ name = "Survivor_Head", rig = CFrame.new(0, 1.5, 0) * R(), size = Vector3.new(1.26, 1.26, 1.26), skin = "Head" },
		{ name = "Survivor_Face", rig = CFrame.new(0, 1.55, -0.6) * R(), size = Vector3.new(0.56, 0.47, 0.1), skin = "Head",
			parent = "sub" },
		{ name = "Survivor_Hat", rig = CFrame.new(0, 1.95, 0.05) * R(), size = Vector3.new(1.4, 0.6, 1.4), skin = "Head",
			gear = true },
		{ name = "Survivor_Torso", rig = CFrame.new(0, 0, 0) * R(), size = Vector3.new(2.1, 2.2, 1.3), skin = "Torso" },
		{ name = "Survivor_Backpack", rig = CFrame.new(0, 0.1, 0.85) * R(), size = Vector3.new(1.45, 1.95, 0.8),
			skin = "Torso", gear = true, parent = "folder" },
	}
	for i, seg in ipairs(SKIN_SEGMENTS) do
		local c = REST[seg].Position
		local pd = { name = "Survivor_" .. seg, rig = CFrame.new(c) * R(), size = Vector3.new(1.05, 1.03, 1.08), skin = seg }
		if i == 1 then
			pd.name, pd.key = "Survivor_RightUpperArm.001", "Survivor_RightUpperArm"
		elseif i == 3 then
			pd.parent = "folder"
		end
		table.insert(all, pd)
	end
	local out = {}
	for _, pd in ipairs(all) do
		if not only or only[pd.key or pd.name] then
			table.insert(out, pd)
		end
	end
	return out
end
local function withSkin(only)
	local list = standardParts()
	for _, pd in ipairs(skinPartsSpec(only)) do
		table.insert(list, pd)
	end
	return list
end
-- transp : transparence attendue des pièces visibles ; gearT : celle des accessoires (défaut = transp)
local function checkSkinPlaced(info, label, visible, transp, eps, gearT)
	eps = eps or 1e-6
	transp = transp or DEFAULT_T
	local rig = rigOf()
	local n = 0
	for key, d in pairs(info) do
		if d.skin then
			n = n + 1
			local p = rig:FindFirstChild(key, true)
			check(p ~= nil, label .. " : tenue " .. key .. " absente du rig")
			if p then
				check(p.Parent == rig.Peau, label .. " : " .. key .. " rangée dans " .. p.Parent:GetFullName())
				local part = rig[d.skin]
				local ep, er = cfErr(p.CFrame, part.CFrame * REST[d.skin]:Inverse() * d.rig)
				check(ep < eps and er < eps, string.format("%s : %s mal placée (pos %.2e, rot %.2e)", label, key, ep, er))
				check(v3Err(p.Size, d.size) < eps, label .. " : taille de " .. key)
				check(p.Anchored == false and p.CanCollide == false and p.CanTouch == false and p.CanQuery == false
					and p.Massless == true and p.CastShadow == false, label .. " : propriétés physiques de " .. key)
				check(p.Material == Enum.Material.SmoothPlastic and p.Color == Color3.new(1, 1, 1),
					label .. " : matériau / couleur (sommets) de " .. key)
				local expT = visible and ((d.gear and gearT) or transp) or 1
				check(math.abs(p.Transparency - expT) < 1e-9, label .. " : transparence de " .. key
					.. " = " .. tostring(p.Transparency) .. " au lieu de " .. tostring(expT))
				check((p:GetAttribute("Anat_Peau") == true) == visible, label .. " : attribut Anat_Peau de " .. key)
				check(p:GetAttribute("Anat_Categorie") == (d.gear and "gear" or "skin") and p:GetAttribute("Anat_Membre") == d.skin,
					label .. " : attributs de " .. key)
				check(p:GetAttribute("Anat_Accessoire") == (d.gear and true or nil), label .. " : attribut Anat_Accessoire de " .. key)
				local w = welds(p)
				check(#w == 1 and w[1].Part0 == part and w[1].Part1 == p, label .. " : soudure de " .. key)
			end
		end
	end
	return n
end
local NSKIN = 5 + #SKIN_SEGMENTS

-- Outils (blocs « do ... end » de AnatomieR6_Outils.lua)
local chunks = {}
for title, body in string.gmatch(OUTILS, "%-%- >>> (OUTIL %d+[^\n]*)\n(.-)\nend\n") do
	table.insert(chunks, { title = title, src = body .. "\nend\n" })
end
local function runTool(i)
	MOCK.quiet = true
	MOCK.printed, MOCK.warnings = {}, {}
	runSource(chunks[i].src, "Outils#" .. i)
	MOCK.quiet = false
end

-- Animations et contrôleur
local RS = game:GetService("ReplicatedStorage")
local SS = game:GetService("ServerStorage")
local SP = game:GetService("StarterPlayer")
local ANIMS_SRC = readSource("SurvivantR6_Animations.lua")
local ANIMATE_SRC = readSource("SurvivantR6_Animate.client.lua")
local EDITOR_SRC = readSource("SurvivantEditeur.module.lua")
local function runAnims(src)
	MOCK.quiet = true
	MOCK.printed, MOCK.warnings = {}, {}
	runSource(src or ANIMS_SRC, "SurvivantR6_Animations.lua")
	MOCK.quiet = false
end
local function sortedKeyframes(kfs)
	local list = kfs:GetChildren()
	table.sort(list, function(a, b)
		return a.Time < b.Time
	end)
	return list
end
-- Vérifie la hiérarchie des poses d'une image clé : HumanoidRootPart (poids 0) > Torso > ... selon le rig ;
-- pièces animées : poids 1 ; ancêtres non animés d'une animation partielle : neutres, poids 0.
local function treeOk(kf, parts)
	local keyed, needed, nNeeded = {}, {}, 0
	for _, n in ipairs(parts) do
		keyed[n] = true
		local a = n
		while a and a ~= "HumanoidRootPart" do
			if not needed[a] then
				needed[a] = true
				nNeeded = nNeeded + 1
			end
			a = PARENT[a]
		end
	end
	local root = kf:FindFirstChild("HumanoidRootPart")
	if not (root and root:IsA("Pose") and #kf:GetChildren() == 1 and root.Weight == 0 and cfClose(root.CFrame, CFrame.new())) then
		return false, "racine"
	end
	local n = 0
	for _, p in ipairs(root:GetDescendants()) do
		if not p:IsA("Pose") then
			return false, "objet " .. p.Name
		end
		n = n + 1
		if not needed[p.Name] or p.Parent.Name ~= PARENT[p.Name] then
			return false, "pose " .. p.Name .. " sous " .. p.Parent.Name
		end
		if keyed[p.Name] then
			if p.Weight ~= 1 then
				return false, "poids de " .. p.Name
			end
		elseif p.Weight ~= 0 or not cfClose(p.CFrame, CFrame.new()) then
			return false, "ancêtre non neutre " .. p.Name
		end
		if p.EasingStyle ~= Enum.PoseEasingStyle.Linear then
			return false, "interpolation de " .. p.Name
		end
	end
	return n == nNeeded, "nombre de poses " .. n .. " / " .. nNeeded
end
local function checkSequences(folder, label)
	local nSeq = 0
	for _, e in ipairs(CLIPS) do
		local kfs = folder and folder:FindFirstChild(e.name)
		check(kfs ~= nil and kfs:IsA("KeyframeSequence"), label .. " : KeyframeSequence " .. e.name)
		if kfs then
			nSeq = nSeq + 1
			check(kfs.Loop == e.loop and kfs.Priority == Enum.AnimationPriority[e.priority], label .. " : Loop/Priority de " .. e.name)
			check(kfs:GetAttribute("Survivant_Cle") == e.key and kfs:GetAttribute("Survivant_Libelle") == e.label
				and kfs:GetAttribute("Survivant_Pieces") == table.concat(e.parts, ",")
				and kfs:GetAttribute("Survivant_VitesseReference") == e.speed, label .. " : attributs de " .. e.name)
			local kfList = sortedKeyframes(kfs)
			check(#kfList == e.nkeys, string.format("%s : %s : %d images clés au lieu de %d", label, e.name, #kfList, e.nkeys))
			check(math.abs(kfList[1].Time) < 1e-9 and math.abs(kfList[#kfList].Time - e.length) < 1e-3,
				label .. " : durée de " .. e.name)
			local okTree, why = true, ""
			for _, kf in ipairs(kfList) do
				local ok, w = treeOk(kf, e.parts)
				if not ok then
					okTree, why = false, w
				end
			end
			check(okTree, label .. " : hiérarchie des poses de " .. e.name .. " (" .. why .. ")")
			for _, smp in ipairs(e.samples) do
				local kf = kfList[smp.k]
				local pose = kf and kf:FindFirstChild(smp.part, true)
				local ep, er = math.huge, math.huge
				if pose then
					ep, er = cfErr(pose.CFrame, cf12(smp.cf))
				end
				check(ep < 2e-3 and er < 3e-3 and math.abs(kf.Time - smp.t) < 1e-3,
					string.format("%s : pose %s de %s (image %d) : écart pos %.2e rot %.2e", label, smp.part, e.name, smp.k, ep, er))
			end
		end
	end
	return nSeq
end
local function installAll(opts)
	opts = opts or {}
	MOCK.reset()
	addBaseplate()
	makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 8, 0), parts = withSkin() })
	runSetup()
	runAnims()
end
local function spawnCharacter(opts)
	opts = opts or {}
	installAll()
	if opts.publish then
		RS.SurvivantAnimations.AnimationIds.walk.Value = opts.publish
	end
	if opts.noFolder then
		RS.SurvivantAnimations:Destroy()
	end
	MOCK.isStudio = opts.studio ~= false
	local char = SP.StarterCharacter:Clone()
	char.Name = "Testeur"
	char.Parent = workspace
	local ls = char:FindFirstChild("Animate")
	if opts.source then
		ls.Source = opts.source
	end
	MOCK.quiet = true
	MOCK.printed, MOCK.warnings = {}, {}
	local f, e = loadstring("local script = ...\n" .. ls.Source, "@Animate")
	assert(f, e)
	f(ls)
	MOCK.quiet = false
	return char
end
local function track(key)
	for _, tr in ipairs(MOCK.tracks) do
		if tr.Animation.Name == key then
			return tr
		end
	end
	return nil
end
local function playingKeys()
	local out = {}
	for _, tr in ipairs(MOCK.tracks) do
		if tr.IsPlaying then
			table.insert(out, tr.Animation.Name)
		end
	end
	table.sort(out)
	return table.concat(out, ",")
end
local function press(action, state, inputType)
	local a = MOCK.actions[action]
	assert(a, "action " .. action .. " non liée")
	a.fn(action, state or Enum.UserInputState.Begin, { UserInputType = inputType or Enum.UserInputType.Keyboard })
end
local function setVel(char, x, z)
	char.HumanoidRootPart.AssemblyLinearVelocity = Vector3.new(x, 0, z or 0)
end

local rig

math.randomseed(12345)

----------------------------------------------------------------------------------------
section("1. Import simple (échelle 37.5, rotation et translation quelconques)")
do
MOCK.reset()
local bp = addBaseplate()
local rot1 = randomRotation()
local imp1, info1 = makeImport({ k = 37.5, rot = rot1, origin = Vector3.new(120, 260, -75), parts = standardParts() })
-- soudure héritée de l'import (doit être supprimée)
local oldWeld = Instance.new("WeldConstraint")
oldWeld.Part0 = info1.Head_Skull_Face.inst
oldWeld.Part1 = info1.Torso_Rib_Supplementaire.inst
oldWeld.Parent = info1.Head_Skull_Face.inst
-- maillage au nom générique dans un Model portant le vrai nom
local wrapper = Instance.new("Model")
wrapper.Name = "Head_Eye_R"
wrapper.Parent = imp1
local generic = Instance.new("MeshPart")
generic.Name = "Mesh"
local eyeRig = CFrame.new(0.2, 1.6, -0.45) * randomRotation()
generic.Size = Vector3.new(0.1, 0.1, 0.1) * 37.5
generic.CFrame = CFrame.new((CFrame.new(Vector3.new(120, 260, -75)) * rot1) * (eyeRig.Position * 37.5)) * (rot1 * eyeRig.Rotation)
generic.Parent = wrapper
info1.Head_Eye_R = { inst = generic, rig = eyeRig, size = Vector3.new(0.1, 0.1, 0.1), seg = "Head" }

runSetup()
checkRigStructure("1")
rig = rigOf()
local torso = rig and rig.Torso
check(torso ~= nil and cfClose(torso.CFrame, CFrame.new(120, 3, -75), 1e-9),
	"1 : Torso posé au sol sous REF_A, face à -Z (" .. tostring(torso and torso.CFrame) .. ")")
check(rig:GetAttribute("Anat_Rig") == "R6 articulé", "1 : attribut Anat_Rig")
checkPlaced(info1, "1")
check(imp1.Parent == nil, "1 : le modèle importé vidé doit être supprimé")
check(STATE[oldWeld].destroyed == true, "1 : la soudure héritée doit être supprimée")
check(rig:FindFirstChild("REF_A", true) == nil, "1 : marqueurs supprimés")
check(rig:FindFirstChild("Head_Eye_R", true) ~= nil, "1 : maillage générique renommé d'après son Model")
local face = rig:FindFirstChild("Head_Skull_Face", true)
check(face.Color == Color3.new(1, 1, 1), "1 : Color blanc (couleurs de sommets)")
check(face.Material == Enum.Material.SmoothPlastic and face.Reflectance == 0, "1 : matériau os")
check(face.RenderFidelity == Enum.RenderFidelity.Precise, "1 : RenderFidelity Precise")
check(face.CollisionFidelity == Enum.CollisionFidelity.Box, "1 : CollisionFidelity Box")
check(face:GetAttribute("Anat_Info") ~= nil, "1 : attribut Anat_Info")
local eye = rig:FindFirstChild("Head_Eye_L", true)
check(eye:GetAttribute("Anat_Categorie") == "eye" and math.abs(eye.Reflectance - 0.1) < 1e-9, "1 : catégorie eye")
local rib = rig:FindFirstChild("Torso_Rib_Supplementaire", true)
check(rib:GetAttribute("Anat_Categorie") == "bone", "1 : catégorie devinée pour une pièce hors manifeste")
check(rig:FindFirstChild("LeftArm_Ancien", true):GetAttribute("Anat_Region") == "LeftArm",
	"1 : région d'origine (ancienne région R6) gardée en attribut")
check(MOCK.chsLog[1] == "begin:AnatomieR6" and MOCK.chsLog[2] == "finish:Commit", "1 : enregistrement d'historique ("
	.. table.concat(MOCK.chsLog, ",") .. ")")
check(printedContains("RÉSUMÉ") and printedContains(string.format("%.5f", 1 / 37.5)), "1 : résumé imprimé avec l'échelle")
check(printedContains("R6 articulé (10 pièces, coudes et genoux"), "1 : rig articulé décrit dans le résumé")
check(printedContains("Avant-bras droit (RightLowerArm)"), "1 : comptage par pièce dans le résumé")
check(printedContains("Pièce du rig déduite de la position") and printedContains("Mystere -> LeftLowerLeg")
	and printedContains("Objet_Inconnu -> RightLowerArm"), "1 : repli par position signalé")
check(printedContains("Pièces absentes du manifeste"), "1 : pièces hors manifeste signalées")
check(#MOCK.warnings == 0, "1 : aucun avertissement attendu, reçu : " .. table.concat(MOCK.warnings, " | "))

----------------------------------------------------------------------------------------
section("2. Second import fusionné dans le rig déplacé/tourné (unités 0.01, remplacement)")
-- L'utilisateur déplace et tourne le rig (les soudures entraînent toutes les pièces).
local G = CFrame.new(-30, 0, 44) * CFrame.Angles(0, math.rad(73), 0)
local pivot = rig.HumanoidRootPart.CFrame
for _, d in ipairs(rig:GetDescendants()) do
	if d:IsA("BasePart") then
		d.CFrame = G * pivot * (pivot:Inverse() * d.CFrame)
	end
end
local oldFace = rig:FindFirstChild("Head_Skull_Face", true)
local parts2 = {
	{ name = "Head_Skull_Face", rig = CFrame.new(0, 1.5, -0.12) * randomRotation(), size = Vector3.new(0.8, 0.7, 0.8), seg = "Head" },
	{ name = "Torso_Liver", rig = CFrame.new(0.3, -0.4, -0.1) * randomRotation(), size = Vector3.new(0.6, 0.4, 0.5), seg = "Torso" },
	{ name = "LeftUpperLeg_Femur", rig = CFrame.new(-0.45, -1.5, 0) * randomRotation(), size = Vector3.new(0.15, 0.9, 0.15),
		seg = "LeftUpperLeg" },
	{ name = "RightLowerLeg_Tibia", rig = CFrame.new(0.5, -2.45, 0) * randomRotation(), size = Vector3.new(0.12, 0.9, 0.12),
		seg = "RightLowerLeg" },
}
local imp2, info2 = makeImport({ name = "import2", k = 0.01, rot = randomRotation(), origin = Vector3.new(5, 1, 3),
	parts = parts2 })
MOCK.warnings = {}
runSetup()
checkRigStructure("2")
checkPlaced(info2, "2")
checkPlaced({ Torso_Rib_Supplementaire = info1.Torso_Rib_Supplementaire, RightUpperLeg_Nerves = info1.RightUpperLeg_Nerves },
	"2 (anciennes pièces)")
check(STATE[oldFace].destroyed == true, "2 : l'ancienne Head_Skull_Face doit être remplacée")
local nFace = 0
for _, d in ipairs(rig:GetDescendants()) do
	if d.Name == "Head_Skull_Face" then
		nFace = nFace + 1
	end
end
check(nFace == 1, "2 : une seule Head_Skull_Face après remplacement (" .. nFace .. ")")
check(rigOf() == rig, "2 : le rig doit être réutilisé")
check(cfClose(rig.HumanoidRootPart.CFrame, G * pivot, 1e-9), "2 : le rig existant ne doit pas bouger")
check(printedContains("remplacées : 1"), "2 : remplacement signalé dans le résumé")
check(imp2.Parent == nil, "2 : import 2 supprimé")

----------------------------------------------------------------------------------------
section("3. Import en miroir : refusé, rien n'est modifié")
local nBefore = #rig.Anatomie:GetDescendants()
local imp3 = makeImport({ name = "miroir", k = 1, rot = randomRotation(), origin = Vector3.new(0, 10, 0), mirror = true,
	parts = { { name = "Torso_Sternum", rig = CFrame.new(0, 0.5, -0.4), size = Vector3.new(0.2, 0.6, 0.1), seg = "Torso" } } })
MOCK.warnings = {}
runSetup()
check(countWarn("MIROIR") >= 1, "3 : avertissement miroir attendu")
check(imp3.Parent == workspace, "3 : l'import en miroir doit rester en place")
check(imp3:FindFirstChild("REF_A") ~= nil, "3 : marqueurs de l'import refusé conservés")
check(#rig.Anatomie:GetDescendants() == nBefore, "3 : aucune pièce ajoutée")
imp3:Destroy()

end

----------------------------------------------------------------------------------------
section("4. Sélection : seul l'import sélectionné est traité (sélection d'une pièce imbriquée)")
do
MOCK.reset()
addBaseplate()
local impA, infoA = makeImport({ name = "A", k = 2.54, rot = randomRotation(), origin = Vector3.new(-50, 20, 0),
	parts = standardParts() })
local impB = makeImport({ name = "B", k = 1, rot = randomRotation(), origin = Vector3.new(50, 20, 0),
	parts = { { name = "Torso_Heart", rig = CFrame.new(0.1, 0.4, -0.2), size = Vector3.new(0.3, 0.3, 0.3), seg = "Torso" } } })
MOCK.selection = { infoA.RightUpperLeg_Nerves.inst }
MOCK.allowRecording = false -- TryBeginRecording indisponible -> SetWaypoint
runSetup()
checkRigStructure("4")
checkPlaced(infoA, "4")
check(impA.Parent == nil, "4 : import A traité et supprimé")
check(impB.Parent == workspace and impB:FindFirstChild("REF_A") ~= nil, "4 : import B non sélectionné intact")
check(cfClose(rigOf().Torso.CFrame, CFrame.new(-50, 3, 0), 1e-9), "4 : rig posé sous l'import A")
check(MOCK.chsLog[1] == "begin:AnatomieR6" and MOCK.chsLog[2] == "waypoint:AnatomieR6 - avant"
	and MOCK.chsLog[3] == "waypoint:AnatomieR6 - après", "4 : repli SetWaypoint (" .. table.concat(MOCK.chsLog, ",") .. ")")
check(MOCK.selection[1] == rigOf(), "4 : le rig est sélectionné à la fin")
end

----------------------------------------------------------------------------------------
section("5. Deux imports dans un même dossier, sans sélection, sans sol, REF_D absent")
do
MOCK.reset()
local holder = Instance.new("Folder")
holder.Name = "Imports"
holder.Parent = workspace
local impC, infoC = makeImport({ name = "C", k = 100, rot = randomRotation(), origin = Vector3.new(7, -40, 9),
	into = holder, skip = { REF_D = true },
	parts = { { name = "LeftLowerArm_Radius", rig = CFrame.new(-1.6, -0.6, 0) * randomRotation(),
		size = Vector3.new(0.1, 0.8, 0.1), seg = "LeftLowerArm" } } })
local impD, infoD = makeImport({ name = "D", k = 0.3, rot = randomRotation(), origin = Vector3.new(70, 5, 9),
	into = holder, markerParent = "RightLowerLeg_Tibia",
	parts = { { name = "RightLowerLeg_Tibia", rig = CFrame.new(0.5, -2.4, 0) * randomRotation(),
		size = Vector3.new(0.12, 0.9, 0.12), seg = "RightLowerLeg" } } })
runSetup()
checkRigStructure("5")
checkPlaced(infoC, "5")
checkPlaced(infoD, "5")
check(math.abs(rigOf().Torso.Position.Y - 3) < 1e-9, "5 : sans sol, Torso à Y = 3")
check(countWarn("REF_D absent") == 1, "5 : avertissement REF_D absent")
check(impC.Parent == nil and impD.Parent == nil, "5 : les deux imports sont traités")
check(holder.Parent == workspace, "5 : le dossier parent (non import) est conservé")
end

----------------------------------------------------------------------------------------
section("6. REF_C absent : import refusé ; aucun import : message")
do
MOCK.reset()
addBaseplate()
local impE = makeImport({ name = "E", k = 1, rot = CFrame.new(), origin = Vector3.new(0, 5, 0), skip = { REF_C = true },
	parts = { { name = "Torso_Sternum", rig = CFrame.new(0, 0.5, -0.4), size = Vector3.new(0.2, 0.6, 0.1), seg = "Torso" } } })
runSetup()
check(countWarn("REF_C") >= 1 and impE.Parent == workspace, "6 : import sans REF_C refusé")
check(rigOf() == nil, "6 : pas de rig créé si rien n'est traité")
MOCK.reset()
runSetup()
check(countWarn("Aucun import anatomique") == 1, "6 : message quand il n'y a aucun import")
end

----------------------------------------------------------------------------------------
section("7. Gabarit sans table (PARTS vide), USE_VERTEX_COLORS = false, ancien rig R6")
do
MOCK.reset()
addBaseplate()
local impF, infoF = makeImport({ k = 3, rot = randomRotation(), origin = Vector3.new(1, 2, 3), parts = standardParts() })
runSetup(TEMPLATE)
checkRigStructure("7")
checkPlaced(infoF, "7")
check(not printedContains("Pièces absentes du manifeste"), "7 : pas de liste « hors manifeste » sans table")
MOCK.reset()
addBaseplate()
local impG, infoG = makeImport({ k = 3, rot = randomRotation(), origin = Vector3.new(1, 2, 3), parts = standardParts() })
local patched, nsub = string.gsub(SETUP, "USE_VERTEX_COLORS = true,", "USE_VERTEX_COLORS = false,")
check(nsub == 1, "7 : option USE_VERTEX_COLORS trouvée dans le script")
runSetup(patched)
checkPlaced(infoG, "7b")
local face7 = rigOf():FindFirstChild("Head_Skull_Face", true)
check(face7.Color == Color3.new(0.89, 0.85, 0.75), "7b : couleur du manifeste (" .. tostring(face7.Color) .. ")")
local rib7 = rigOf():FindFirstChild("Torso_Rib_Supplementaire", true)
check(rib7.Color == Color3.new(0.89, 0.85, 0.75), "7b : couleur de catégorie de secours (" .. tostring(rib7.Color) .. ")")
-- ancien rig R6 à 6 pièces du même nom : renommé, conservé, un rig articulé neuf est créé
MOCK.reset()
addBaseplate()
local legacy = Instance.new("Model")
legacy.Name = "Anatomie_R6"
for _, n in ipairs({ "HumanoidRootPart", "Torso", "Head", "Left Arm", "Right Arm", "Left Leg", "Right Leg" }) do
	local p = Instance.new("Part")
	p.Name = n
	p.Anchored = true
	p.CFrame = CFrame.new(200, 3, 0)
	p.Parent = legacy
end
Instance.new("Humanoid").Parent = legacy
legacy.Parent = workspace
local impL, infoL = makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 4, 0), parts = standardParts() })
runSetup()
checkRigStructure("7c")
checkPlaced(infoL, "7c")
check(legacy.Parent == workspace and legacy.Name == "Anatomie_R6_ancien" and legacy:FindFirstChild("Left Arm") ~= nil,
	"7c : ancien rig R6 renommé et conservé")
check(countWarn("Ancien rig R6") == 1, "7c : avertissement ancien rig")
end

----------------------------------------------------------------------------------------
section("7d. Import de tout le manifeste : chaque pièce soudée à sa pièce du rig")
do
MOCK.reset()
addBaseplate()
local names = {}
for name in pairs(PT) do
	table.insert(names, name)
end
table.sort(names)
local fullSpec, perRegion, nSkin = {}, {}, 0
for _, name in ipairs(names) do
	local e = PT[name]
	check(SPEC[e.region] ~= nil and e.region ~= "HumanoidRootPart", "7d : région valide pour " .. name .. " (" .. tostring(e.region) .. ")")
	local c = REST[e.region] or CFrame.new()
	local h = vec(SPEC[e.region] and SPEC[e.region].size or { 1, 1, 1 }) * 0.3
	local pos = c.Position + Vector3.new((math.random() * 2 - 1) * h.X, (math.random() * 2 - 1) * h.Y, (math.random() * 2 - 1) * h.Z)
	local isSkin = e.cat == "skin" or e.cat == "gear"
	local pd = { name = name, rig = CFrame.new(pos) * randomRotation(), size = Vector3.new(0.2, 0.3, 0.25) }
	if isSkin then
		pd.skin, pd.gear = e.region, e.cat == "gear"
		nSkin = nSkin + 1
	else
		pd.seg = e.region
		perRegion[e.region] = (perRegion[e.region] or 0) + 1
	end
	table.insert(fullSpec, pd)
end
local impFull, infoFull = makeImport({ name = "complet", k = 100 / 28, rot = randomRotation(), origin = Vector3.new(0, 30, 0),
	parts = fullSpec })
runSetup()
rig = rigOf()
checkRigStructure("7d", {})
checkPlaced(infoFull, "7d", 1e-5)
for _, name in ipairs(PARTS10) do
	check(#rig.Anatomie[name]:GetChildren() == (perRegion[name] or 0), string.format("7d : %d pièce(s) dans Anatomie.%s (%d)",
		perRegion[name] or 0, name, #rig.Anatomie[name]:GetChildren()))
end
local skinOk = true
for key, d in pairs(infoFull) do
	if d.skin then
		local p = rig.Peau:FindFirstChild(key)
		local w = p and welds(p)
		if not (p and p:GetAttribute("Anat_Membre") == d.skin and #w == 1 and w[1].Part0 == rig[d.skin]
			and cfClose(p.CFrame, rig[d.skin].CFrame * REST[d.skin]:Inverse() * d.rig, 1e-5)) then
			skinOk = false
			MOCK.rawPrint("    tenue mal placée : " .. key)
		end
	end
end
check(skinOk and #rig.Peau:GetChildren() == nSkin, "7d : " .. nSkin .. " pièces de tenue soudées à leur pièce du rig")
check(rig:GetAttribute("Anat_ModePeau") == "maillage", "7d : tenue complète -> mode maillage")
check(printedContains("Toutes les pièces du manifeste sont présentes dans le rig."), "7d : manifeste complet")
check(not printedContains("Pièces absentes du manifeste") and not printedContains("déduite de la position"),
	"7d : toutes les pièces reconnues par le manifeste")
check(#MOCK.warnings == 0, "7d : aucun avertissement (" .. table.concat(MOCK.warnings, " | ") .. ")")
end

----------------------------------------------------------------------------------------
section("8. Outils")
do
MOCK.reset()
addBaseplate()
local impH, infoH = makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 4, 0), parts = standardParts() })
runSetup()
check(#chunks == 9, "8 : 9 outils attendus, trouvés " .. #chunks)
-- l'outil 9 connaît les 10 pièces du rig
do
	local listed = {}
	for n in string.gmatch(string.match(chunks[9].src, "for _, name in ipairs(%b())"), '"(%a+)"') do
		listed[n] = true
	end
	local all = true
	for _, n in ipairs(PARTS10) do
		all = all and listed[n] == true
	end
	check(all, "8 : l'outil 9 liste les 10 pièces du rig")
end
rig = rigOf()
local calv = rig:FindFirstChild("Head_Skull_Calvaria", true)
check(rig.Head:FindFirstChild("face") == nil, "8 : pas de visage decal par défaut (SHOW_FACE = false)")
runTool(1)
check(rig.Torso.Transparency == 1 and rig.Head.Transparency == 1 and rig.RightLowerLeg.Transparency == 1,
	"outil 1 : peau (blocs) masquée")
runTool(2)
check(math.abs(rig.Torso.Transparency - 0.7) < 1e-9 and math.abs(rig.LeftLowerArm.Transparency - 0.7) < 1e-9,
	"outil 2 : radiographie 0.7")
runTool(3)
check(calv.Transparency == 1 and calv:GetAttribute("Anat_Masque") == true, "outil 3 : calvaria masquée")
runSource(string.gsub(chunks[3].src, "local VISIBLE = false", "local VISIBLE = true"), "Outils#3b")
check(calv.Transparency == 0 and calv:GetAttribute("Anat_Masque") == nil, "outil 3 : calvaria réaffichée")
runSource(string.gsub(chunks[4].src, '{ "organ" }', '{ "eye", "nerve" }', 1), "Outils#4")
check(rig:FindFirstChild("Head_Eye_L", true).Transparency == 1 and rig:FindFirstChild("RightUpperLeg_Nerves", true).Transparency == 1
	and rig:FindFirstChild("Head_Skull_Face", true).Transparency == 0, "outil 4 : catégories eye+nerve masquées")
runTool(5)
check(rig:FindFirstChild("Head_Skull_Face", true).Transparency == 0 and rig:FindFirstChild("Head_Eye_L", true).Transparency == 1
	and rig.Torso.Transparency == 1, "outil 5 : squelette isolé")
runTool(6)
local allBack = true
for _, d in ipairs(rig.Anatomie:GetDescendants()) do
	if d:IsA("BasePart") and d.Transparency ~= 0 then
		allBack = false
	end
end
check(allBack and math.abs(rig.Torso.Transparency - 0.7) < 1e-9, "outil 6 : tout réaffiché (transparence de l'outil 2)")
runTool(7)
check(printedContains("par catégorie") and printedContains("par pièce") and printedContains("RightLowerArm 2"),
	"outil 7 : comptage par pièce du rig imprimé")
rig.RightLowerArm.RightElbow.Transform = CFrame.Angles(1, 0, 0) -- rig posé (aperçu de l'éditeur)
runTool(8)
local sc = game:GetService("StarterPlayer"):FindFirstChild("StarterCharacter")
check(sc ~= nil and sc:IsA("Model"), "outil 8 : StarterCharacter créé")
if sc then
	local anchored = 0
	for _, d in ipairs(sc:GetDescendants()) do
		if d:IsA("BasePart") and d.Anchored then
			anchored = anchored + 1
		end
	end
	check(anchored == 0, "outil 8 : toutes les pièces désancrées")
	check(sc.PrimaryPart == sc.HumanoidRootPart, "outil 8 : PrimaryPart")
	local hum8 = sc:FindFirstChildOfClass("Humanoid")
	check(hum8.RigType == Enum.HumanoidRigType.R15 and hum8.HipHeight == 2 and hum8.AutomaticScalingEnabled == false,
		"outil 8 : Humanoid R15, HipHeight 2")
	check(cfClose(sc.RightLowerArm.RightElbow.Transform, CFrame.new()), "outil 8 : articulations remises au repos")
	local w = sc:FindFirstChild("Head_Skull_Face", true):FindFirstChildOfClass("WeldConstraint")
	check(w.Part0 == sc.Head and w.Part1 == sc:FindFirstChild("Head_Skull_Face", true), "outil 8 : soudures remappées sur la copie")
	local elbow = sc.RightLowerArm.RightElbow
	check(elbow.Part0 == sc.RightUpperArm and elbow.Part1 == sc.RightLowerArm and sc.Torso.Neck.Part1 == sc.Head,
		"outil 8 : Motor6D remappés sur la copie")
	check(sc.RightHand.RightWrist.Part0 == sc.RightLowerArm, "outil 8 : main remappée sur la copie")
	check(rigOf().HumanoidRootPart.Anchored == true, "outil 8 : le rig d'origine reste ancré")
end
check(game:GetService("Players").LoadCharacterAppearance == false, "outil 8 : apparence du joueur désactivée")
check(countWarn("Pas de script « Animate »") == 1, "outil 8 : avertit qu'il manque le contrôleur")
end

----------------------------------------------------------------------------------------
section("9. Tenue du survivant (Survivor_*) : mode maillage, blocs, mixte, accessoires, outils")
do

-- 9a : import complet (anatomie + tenue), unités en centimètres
MOCK.reset()
addBaseplate()
local impS, infoS = makeImport({ name = "complet", k = 100 / 28, rot = randomRotation(), origin = Vector3.new(10, 50, 20),
	parts = withSkin() })
runSetup()
checkRigStructure("9a", {})
checkPlaced(infoS, "9a")
check(checkSkinPlaced(infoS, "9a", true) == NSKIN, "9a : " .. NSKIN .. " pièces de tenue")
rig = rigOf()
check(rig:GetAttribute("Anat_ModePeau") == "maillage", "9a : mode maillage")
check(#rig.Peau:GetChildren() == NSKIN, "9a : dossier Peau complet")
check(printedContains("mode « maillage »") and printedContains(NSKIN .. " pièce(s) de peau"), "9a : tenue dans le résumé")
check(#MOCK.warnings == 0, "9a : aucun avertissement, reçu : " .. table.concat(MOCK.warnings, " | "))
check(impS.Parent == nil, "9a : import supprimé")

local skinHead, hat, pack = rig.Peau.Survivor_Head, rig.Peau.Survivor_Hat, rig.Peau.Survivor_Backpack
runTool(1)
check(skinHead.Transparency == 1 and hat.Transparency == 1 and pack.Transparency == 1 and rig.Torso.Transparency == 1,
	"9a outil 1 : tenue masquée, blocs toujours invisibles")
runTool(6)
check(skinHead.Transparency == 0 and hat.Transparency == 0 and rig.Torso.Transparency == 1 and rig.Head:FindFirstChild("face") == nil,
	"9a outil 6 : tenue réaffichée (opaque), blocs invisibles, pas de decal")
runTool(2)
check(math.abs(skinHead.Transparency - 0.7) < 1e-9 and math.abs(rig.Peau.Survivor_Face.Transparency - 0.7) < 1e-9
	and math.abs(rig.Peau.Survivor_LeftLowerLeg.Transparency - 0.7) < 1e-9
	and hat.Transparency == 1 and pack.Transparency == 1 and rig.Head.Transparency == 1,
	"9a outil 2 : radiographie (tenue 0.7, accessoires masqués), blocs invisibles")
runTool(5)
check(skinHead.Transparency == 1 and rig.Peau.Survivor_LeftUpperLeg.Transparency == 1, "9a outil 5 : tenue masquée")
runTool(6)
check(math.abs(skinHead.Transparency - 0.7) < 1e-9 and hat.Transparency == 1, "9a outil 6 : retour à la radiographie")
runTool(9)
checkRigStructure("9a outil 9 (blocs)", nil, 0.7, true)
check(checkSkinPlaced(infoS, "9a outil 9 (blocs)", false) == NSKIN and rig:GetAttribute("Anat_ModePeau") == "blocs",
	"9a outil 9 : passage en mode blocs")
runSource(string.gsub(chunks[9].src, 'local MODE = "blocs"', 'local MODE = "maillage"', 1), "Outils#9b")
checkRigStructure("9a outil 9 (maillage)", {}, 0.7)
check(checkSkinPlaced(infoS, "9a outil 9 (maillage)", true, 0.7) == NSKIN and rig:GetAttribute("Anat_ModePeau") == "maillage",
	"9a outil 9 : retour au mode maillage")
runSource(string.gsub(chunks[2].src, "local TRANSPARENCE = 0.7", "local TRANSPARENCE = 0", 1), "Outils#2b")
check(checkSkinPlaced(infoS, "9a outil 2 (opaque)", true, 0) == NSKIN, "9a outil 2 : tenue de nouveau opaque, accessoires visibles")
runTool(7)
check(printedContains("Tenue : mode « maillage », " .. NSKIN .. " pièce(s)"), "9a outil 7 : tenue comptée")
runTool(8)
local sc9 = game:GetService("StarterPlayer"):FindFirstChild("StarterCharacter")
local sh = sc9 and sc9:FindFirstChild("Peau") and sc9.Peau:FindFirstChild("Survivor_RightLowerArm")
local w9 = sh and sh:FindFirstChildOfClass("WeldConstraint")
check(w9 ~= nil and w9.Part0 == sc9.RightLowerArm and w9.Part1 == sh, "9a outil 8 : tenue soudée à la copie jouable")

-- 9b : réimport du torse seul (remplacement) dans le rig existant
local oldTorsoSkin = rig.Peau.Survivor_Torso
local impS2, infoS2 = makeImport({ name = "tenue2", k = 1, rot = randomRotation(), origin = Vector3.new(-5, 5, 5),
	parts = skinPartsSpec({ Survivor_Torso = true }) })
runSetup()
check(STATE[oldTorsoSkin].destroyed == true and #rig.Peau:GetChildren() == NSKIN, "9b : Survivor_Torso remplacée")
checkSkinPlaced(infoS2, "9b", true)
check(rig:GetAttribute("Anat_ModePeau") == "maillage", "9b : toujours en mode maillage")

-- 9c : SKIN_MODE = "blocs" : la tenue importée est rangée mais cachée, les blocs servent de peau
MOCK.reset()
addBaseplate()
local impB2, infoB2 = makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 8, 0), parts = withSkin() })
local patchedB, nB = string.gsub(SETUP, 'SKIN_MODE = "maillage",', 'SKIN_MODE = "blocs",')
check(nB == 1, "9c : option SKIN_MODE trouvée")
runSetup(patchedB)
checkRigStructure("9c")
check(checkSkinPlaced(infoB2, "9c", false) == NSKIN and rigOf():GetAttribute("Anat_ModePeau") == "blocs", "9c : mode blocs")
MOCK.reset()
addBaseplate()
makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 8, 0), parts = standardParts() })
runSetup((string.gsub(SETUP, "SHOW_FACE = false,", "SHOW_FACE = true,")))
checkRigStructure("9c visage", nil, DEFAULT_T, true)

-- 9d : tenue partielle (tête et avant-bras droit) : mode mixte
MOCK.reset()
addBaseplate()
local impM, infoM = makeImport({ k = 2, rot = randomRotation(), origin = Vector3.new(0, 8, 0),
	parts = withSkin({ Survivor_Head = true, Survivor_Face = true, Survivor_Hat = true, Survivor_RightLowerArm = true }) })
runSetup()
local blocks9d = {}
for _, n in ipairs(PARTS10) do
	blocks9d[n] = (n ~= "Head" and n ~= "RightLowerArm") or nil
end
checkRigStructure("9d", blocks9d)
check(checkSkinPlaced(infoM, "9d", true) == 4 and rigOf():GetAttribute("Anat_ModePeau") == "mixte", "9d : mode mixte")
check(printedContains("Peau importée absente pour"), "9d : pièces sans tenue importée signalées")

-- 9e : accessoire seul sur la tête (bonnet sans Survivor_Head) : la tête-bloc reste visible sous le bonnet
MOCK.reset()
addBaseplate()
local impHat, infoHat = makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 8, 0),
	parts = withSkin({ Survivor_Hat = true }) })
runSetup()
checkRigStructure("9e")
check(checkSkinPlaced(infoHat, "9e", true) == 1 and rigOf():GetAttribute("Anat_ModePeau") == "blocs",
	"9e : bonnet visible, tous les blocs servent de peau")

-- 9f : gabarit sans table + couleurs unies : catégories devinées (skin / gear), couleurs par défaut
MOCK.reset()
addBaseplate()
makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 8, 0), parts = withSkin() })
runSetup((string.gsub(TEMPLATE, "USE_VERTEX_COLORS = true,", "USE_VERTEX_COLORS = false,")))
rig = rigOf()
check(#rig.Peau:GetChildren() == NSKIN and rig:GetAttribute("Anat_ModePeau") == "maillage", "9f : tenue reconnue sans table")
check(rig.Peau.Survivor_Torso.Color == SURV.Torso and rig.Peau.Survivor_LeftLowerLeg.Color == SURV.LeftLowerLeg
	and rig.Peau.Survivor_RightLowerArm.Color == SURV.RightLowerArm
	and rig.Peau.Survivor_Face.Color == Color3.new(0.07, 0.07, 0.07), "9f : couleurs unies par défaut")
check(rig.Peau.Survivor_Hat:GetAttribute("Anat_Categorie") == "gear" and rig.Peau.Survivor_Backpack:GetAttribute("Anat_Accessoire") == true,
	"9f : bonnet et sac reconnus comme accessoires")
MOCK.reset()
addBaseplate()
makeImport({ k = 1, rot = randomRotation(), origin = Vector3.new(0, 8, 0), parts = withSkin() })
runSetup((string.gsub(SETUP, "USE_VERTEX_COLORS = true,", "USE_VERTEX_COLORS = false,")))
local st = rigOf().Peau.Survivor_Torso.Color
check(math.abs(st.R - 0.282) < 1e-6 and math.abs(st.G - 0.314) < 1e-6 and math.abs(st.B - 0.188) < 1e-6,
	"9f : couleur du manifeste pour la tenue (" .. tostring(st) .. ")")
end

----------------------------------------------------------------------------------------
section("10. Installation des animations (SurvivantR6_Animations.lua)")
do
installAll()
local folder = RS:FindFirstChild("SurvivantAnimations")
check(folder ~= nil, "10 : dossier ReplicatedStorage.SurvivantAnimations")
check(checkSequences(folder, "10") == #CLIPS and #CLIPS == 15, "10 : 15 animations")
local overlay = nil
for _, e in ipairs(CLIPS) do
	if #e.parts < #PARTS10 then
		overlay = e
	end
end
check(overlay ~= nil and overlay.key == "tool" and table.concat(overlay.parts, ",") == "RightUpperArm,RightLowerArm",
	"10 : animation superposée « tool » (bras droit seulement)")
local ids = folder and folder:FindFirstChild("AnimationIds")
check(ids ~= nil and #ids:GetChildren() == #CLIPS, "10 : AnimationIds (une valeur par animation)")
check(ids.walk:GetAttribute("Animation") == "Survivant_Marche" and ids.walk:GetAttribute("Survivant_Rig") == "R6 articulé",
	"10 : attributs des identifiants")
local rig10 = rigOf()
local saves = SS:FindFirstChild("RBX_ANIMSAVES")
local entry = saves and saves:FindFirstChild("Anatomie_R6")
check(entry ~= nil and entry:IsA("ObjectValue") and entry.Value == rig10 and #entry:GetChildren() == #CLIPS,
	"10 : copies pour l'éditeur d'animation (ServerStorage.RBX_ANIMSAVES)")
check(entry and checkSequences(entry, "10 (RBX_ANIMSAVES)") == #CLIPS, "10 : copies identiques")
check(MOCK.collision.groups.SurvivantPosture == true and MOCK.collision.collidable["SurvivantPosture|Default"] == false,
	"10 : groupe de collision SurvivantPosture sans collision avec Default")
local animate = rig10:FindFirstChild("Animate")
check(animate ~= nil and animate:IsA("LocalScript") and animate.Source == ANIMATE_SRC, "10 : contrôleur Animate dans le rig")
local sc10 = SP:FindFirstChild("StarterCharacter")
check(sc10 ~= nil and sc10:FindFirstChild("Animate") ~= nil and sc10:FindFirstChild("Peau") ~= nil
	and sc10.HumanoidRootPart.Anchored == false, "10 : StarterCharacter jouable avec contrôleur et tenue")
if sc10 then
	checkRigStructure("10 StarterCharacter", {}, DEFAULT_T, false, sc10)
end
check(game:GetService("Players").LoadCharacterAppearance == false, "10 : apparence du joueur désactivée")
-- éditeur et données
local editorModule = SS:FindFirstChild("SurvivantEditeur")
check(editorModule ~= nil and editorModule:IsA("ModuleScript") and editorModule.Source == EDITOR_SRC,
	"10 : module ServerStorage.SurvivantEditeur installé")
local donnees = editorModule and editorModule:FindFirstChild("Donnees")
check(donnees ~= nil and donnees:IsA("ModuleScript"), "10 : module Donnees")
local D = donnees and require(donnees)
check(type(D) == "table" and type(D.RIG) == "table" and type(D.ANIMS) == "table", "10 : Donnees renvoie { RIG, ANIMS }")
if type(D) == "table" then
	check(table.concat(D.RIG.poseOrder, ",") == table.concat(PARTS10, ",") and D.RIG.hipHeight == RIG.hipHeight
		and #D.RIG.joints == 10, "10 : Donnees.RIG conforme")
	local same = true
	for i, j in ipairs(RIG.joints) do
		local dj = D.RIG.joints[i]
		for c = 1, 12 do
			same = same and math.abs(dj.c0[c] - j.c0[c]) < 1e-9 and math.abs(dj.c1[c] - j.c1[c]) < 1e-9
		end
		same = same and dj.name == j.name and dj.part0 == j.part0 and dj.part1 == j.part1
	end
	check(same, "10 : Donnees.RIG.joints = RIG")
	local okAnims = #D.ANIMS == #CLIPS
	for i, e in ipairs(CLIPS) do
		local a = D.ANIMS[i]
		okAnims = okAnims and a.key == e.key and a.name == e.name and #a.keys == e.nkeys and a.loop == e.loop
			and table.concat(a.parts, ",") == table.concat(e.parts, ",")
	end
	check(okAnims, "10 : Donnees.ANIMS = animations installées")
end
check(printedContains("15 animations créées") and printedContains("(superposée)") and #MOCK.warnings == 0,
	"10 : résumé imprimé sans avertissement (" .. table.concat(MOCK.warnings, " | ") .. ")")
check(printedContains("SurvivantEditeur"), "10 : éditeur signalé dans le résumé")
check(MOCK.chsLog[#MOCK.chsLog - 1] == "begin:SurvivantR6" and MOCK.chsLog[#MOCK.chsLog] == "finish:Commit",
	"10 : historique (" .. table.concat(MOCK.chsLog, ",") .. ")")
-- relance : pas de doublon, identifiants publiés conservés
ids.walk.Value = "1234567"
runAnims()
local count = 0
for _, c in ipairs(folder:GetChildren()) do
	if c.Name == "Survivant_Marche" then
		count = count + 1
	end
end
check(count == 1 and ids.walk.Value == "1234567" and #SP:GetChildren() == 2,
	"10 : relance sans doublon, identifiant publié conservé")
-- identifiant publié pour l'ancien rig R6 (valeur sans attribut Survivant_Rig) : effacé et gardé à part
ids.run.Value = "777"
ids.run:SetAttribute("Survivant_Rig", nil)
runAnims()
check(ids.run.Value == "" and ids.run:GetAttribute("AncienIdentifiant") == "777" and ids.walk.Value == "1234567"
	and countWarn("ancien rig R6") == 1, "10 : identifiant de l'ancien rig R6 effacé (gardé dans AncienIdentifiant)")
-- sans rig : animations créées quand même, avertissement
MOCK.reset()
runAnims()
check(RS:FindFirstChild("SurvivantAnimations") ~= nil and countWarn("introuvable") == 1 and SS:FindFirstChild("SurvivantEditeur") ~= nil,
	"10 : sans rig, animations et éditeur créés, avertissement")
-- ancien rig R6 (6 pièces) : pas de contrôleur ni de personnage jouable
MOCK.reset()
local old10 = Instance.new("Model")
old10.Name = "Anatomie_R6"
for _, n in ipairs({ "HumanoidRootPart", "Torso", "Head", "Left Arm", "Right Arm", "Left Leg", "Right Leg" }) do
	local p = Instance.new("Part")
	p.Name = n
	p.Parent = old10
end
Instance.new("Humanoid").Parent = old10
old10.Parent = workspace
runAnims()
check(countWarn("n'est pas le rig R6 articulé") == 1 and old10:FindFirstChild("Animate") == nil
	and SP:FindFirstChild("StarterCharacter") == nil and RS:FindFirstChild("SurvivantAnimations") ~= nil,
	"10 : ancien rig R6 refusé (animations créées, pas de contrôleur)")
end

----------------------------------------------------------------------------------------
section("11. Contrôleur en jeu (LocalScript Animate)")
do

local char = spawnCharacter()
local hum = char:FindFirstChildOfClass("Humanoid")
check(hum:FindFirstChildOfClass("Animator") ~= nil, "11 : Animator créé")
local studioAll = true
for _, e in ipairs(CLIPS) do
	local tr = track(e.key)
	if not (tr and string.sub(tr.AnimationId, 1, 10) == "rbxtemp://" and tr.Looped == e.loop
		and tr.Priority == Enum.AnimationPriority[e.priority] and STATE[tr.kfs].props.Name == e.name) then
		studioAll = false
	end
end
check(studioAll and #MOCK.tracks == #CLIPS, "11 : les 15 animations chargées depuis les KeyframeSequences (Studio)")
check(not string.find(ANIMATE_SRC, "rbxassetid://1", 1, true) and not string.find(ANIMATE_SRC, "ROBLOX_R6", 1, true),
	"11 : plus d'animations R6 de Roblox en secours")
check(#MOCK.warnings == 0, "11 : pas d'avertissement dans Studio (" .. table.concat(MOCK.warnings, " | ") .. ")")
check(MOCK.actions.SurvivantCourse and MOCK.actions.SurvivantCourse.touch == true and MOCK.actions.SurvivantCourse.keys[1] == Enum.KeyCode.LeftShift
	and MOCK.actions.SurvivantAccroupi.keys[1] == Enum.KeyCode.C and MOCK.actions.SurvivantAllonge.keys[1] == Enum.KeyCode.X
	and MOCK.actions.SurvivantRadio.keys[1] == Enum.KeyCode.R and MOCK.actions.SurvivantAllonge.title == "Allongé",
	"11 : actions liées (clavier + boutons tactiles)")
local gui = MOCK.localPlayer.PlayerGui:FindFirstChild("SurvivantAide")
check(gui ~= nil and gui.Texte.Text ~= "", "11 : rappel des commandes à l'écran")
MOCK.step(1 / 60, 3)
check(playingKeys() == "idle" and hum.WalkSpeed == 6, "11 : au repos (" .. playingKeys() .. ")")
MOCK.step(13, 1)
check(MOCK.localPlayer.PlayerGui:FindFirstChild("SurvivantAide") == nil, "11 : rappel retiré après 12 s")
local walkRef = clipOf("walk").speed
setVel(char, 4.5, 0)
MOCK.step(1 / 60, 2)
check(playingKeys() == "walk" and math.abs(track("walk").Speed - 4.5 / walkRef) < 1e-6, "11 : marche à 4,5 studs/s")
press("SurvivantCourse", Enum.UserInputState.Begin)
check(hum.WalkSpeed == 16, "11 : Maj -> vitesse de course")
setVel(char, 0, -15)
MOCK.step(1 / 60, 2)
check(playingKeys() == "run" and math.abs(track("run").Speed - 15 / 16) < 1e-6, "11 : course")
press("SurvivantCourse", Enum.UserInputState.End)
MOCK.step(1 / 60, 1)
check(hum.WalkSpeed == 6, "11 : Maj relâchée -> marche")
-- accroupi
setVel(char, 0, 0)
press("SurvivantAccroupi")
MOCK.step(1 / 60, 2)
check(playingKeys() == "crouch" and hum.WalkSpeed == 3, "11 : C -> accroupi (" .. playingKeys() .. ")")
setVel(char, 2, 0)
MOCK.step(1 / 60, 2)
check(playingKeys() == "crouchwalk" and math.abs(track("crouchwalk").Speed - 2 / clipOf("crouchwalk").speed) < 1e-6,
	"11 : marche accroupie")
MOCK.step(1 / 60, 90)
check((hum.CameraOffset - Vector3.new(0, -1.15, 0)).Magnitude < 0.01, "11 : caméra abaissée en accroupi")
press("SurvivantCourse", Enum.UserInputState.Begin)
check(hum.WalkSpeed == 16, "11 : sprint depuis accroupi -> debout")
press("SurvivantCourse", Enum.UserInputState.End)
-- allongé
setVel(char, 0, 0)
press("SurvivantAllonge")
MOCK.step(1 / 60, 1)
check(track("liedown").IsPlaying and hum.WalkSpeed == 0 and char.Torso.CollisionGroup == "SurvivantPosture"
	and char.Head.CollisionGroup == "SurvivantPosture" and hum:GetStateEnabled(Enum.HumanoidStateType.Jumping) == false,
	"11 : X -> s'allonger (transition, immobile, collisions du corps coupées, saut désactivé)")
press("SurvivantAccroupi")
MOCK.step(1 / 60, 60)
check(not track("liedown").IsPlaying and track("prone").IsPlaying and hum.WalkSpeed == 1.5,
	"11 : allongé après la transition (C ignoré pendant la transition)")
setVel(char, 1.2, 0)
MOCK.step(1 / 60, 2)
check(track("crawl").IsPlaying and not track("prone").IsPlaying
	and math.abs(track("crawl").Speed - math.clamp(1.2 / clipOf("crawl").speed, 0.45, 1.8)) < 1e-6,
	"11 : ramper (" .. tostring(track("crawl").Speed) .. ")")
MOCK.step(1 / 60, 90)
check((hum.CameraOffset - Vector3.new(0, -2.3, -1.1)).Magnitude < 0.01, "11 : caméra au ras du sol allongé")
setVel(char, 0, 0)
press("SurvivantAllonge")
MOCK.step(1 / 60, 1)
check(track("getup").IsPlaying and hum.WalkSpeed == 0 and char.Torso.CollisionGroup == "SurvivantPosture",
	"11 : X -> se relever (transition)")
MOCK.step(1 / 60, 75)
check(not track("getup").IsPlaying and track("idle").IsPlaying and hum.WalkSpeed == 6 and char.Torso.CollisionGroup == "Default"
	and hum:GetStateEnabled(Enum.HumanoidStateType.Jumping) == true, "11 : debout après la transition, collisions rétablies")
-- saut, chute, atterrissage
hum:ChangeState(Enum.HumanoidStateType.Jumping)
check(track("jump").IsPlaying, "11 : saut")
hum:ChangeState(Enum.HumanoidStateType.Freefall)
MOCK.step(1 / 60, 40)
check(track("fall").IsPlaying and not track("jump").IsPlaying, "11 : la chute prend le relais du saut")
hum:ChangeState(Enum.HumanoidStateType.Landed)
check(track("land").IsPlaying and not track("fall").IsPlaying, "11 : atterrissage")
hum:ChangeState(Enum.HumanoidStateType.Running)
MOCK.step(1 / 60, 30)
-- grimper : animation du survivant, vitesse = vitesse d'escalade / vitesse de l'animation
hum:ChangeState(Enum.HumanoidStateType.Climbing)
MOCK.step(1 / 60, 2)
check(track("climb").IsPlaying and not track("idle").IsPlaying and not track("walk").IsPlaying,
	"11 : grimper remplace l'animation de fond (" .. playingKeys() .. ")")
local climbOk = true
for _, c in ipairs({ { 5, 1 }, { 2.5, 0.5 }, { 20, 1.8 }, { -5, -1 }, { 0, 0 } }) do
	MOCK.fire(hum, "Climbing", c[1])
	if math.abs(track("climb").Speed - c[2]) > 1e-9 then
		climbOk = false
	end
end
check(climbOk, "11 : vitesse de l'escalade (x1 à 5 studs/s, à l'envers en descendant, figée à l'arrêt, max x1,8)")
hum:ChangeState(Enum.HumanoidStateType.Running)
MOCK.step(1 / 60, 2)
check(not track("climb").IsPlaying and track("idle").IsPlaying, "11 : fin de l'escalade, retour au repos")
-- assis
hum:ChangeState(Enum.HumanoidStateType.Seated)
setVel(char, 3, 0)
MOCK.step(1 / 60, 3)
check(track("sit").IsPlaying and not track("idle").IsPlaying and not track("walk").IsPlaying, "11 : assis (" .. playingKeys() .. ")")
hum:ChangeState(Enum.HumanoidStateType.Jumping)
check(not track("sit").IsPlaying and track("jump").IsPlaying, "11 : sauter quitte le siège")
hum:ChangeState(Enum.HumanoidStateType.Landed)
hum:ChangeState(Enum.HumanoidStateType.Running)
setVel(char, 0, 0)
MOCK.step(1 / 60, 30)
-- outil en main : animation superposée sur le bras droit
local tool = Instance.new("Tool")
tool.Parent = char
check(track("tool").IsPlaying and track("idle").IsPlaying, "11 : outil en main (bras droit), le reste continue")
press("SurvivantAllonge")
MOCK.step(1 / 60, 2)
check(not track("tool").IsPlaying, "11 : outil baissé en s'allongeant")
MOCK.step(1 / 60, 60)
press("SurvivantAllonge")
MOCK.step(1 / 60, 80)
check(track("tool").IsPlaying and track("idle").IsPlaying, "11 : outil repris une fois debout")
hum:ChangeState(Enum.HumanoidStateType.Climbing)
check(not track("tool").IsPlaying, "11 : outil baissé en grimpant")
hum:ChangeState(Enum.HumanoidStateType.Running)
check(track("tool").IsPlaying, "11 : outil repris après l'escalade")
tool.Parent = nil
check(not track("tool").IsPlaying, "11 : outil rangé")
-- grimper depuis allongé : le personnage se redresse
press("SurvivantAllonge")
MOCK.step(1 / 60, 70)
hum:ChangeState(Enum.HumanoidStateType.Climbing)
MOCK.step(1 / 60, 2)
check(track("climb").IsPlaying and hum.WalkSpeed == 6 and char.Torso.CollisionGroup == "Default", "11 : grimper depuis allongé")
hum:ChangeState(Enum.HumanoidStateType.Running)
MOCK.step(1 / 60, 2)
-- radiographie
local headSkin, hatPart = char.Peau.Survivor_Head, char.Peau.Survivor_Hat
press("SurvivantRadio")
check(math.abs(headSkin.Transparency - 0.72) < 1e-9 and hatPart.Transparency == 1, "11 : R -> radiographie")
press("SurvivantRadio")
check(headSkin.Transparency == 0 and hatPart.Transparency == 0, "11 : R -> tenue restaurée")
-- mort
hum:ChangeState(Enum.HumanoidStateType.Dead)
MOCK.fire(hum, "Died")
setVel(char, 5, 0)
MOCK.step(1 / 60, 5)
check(playingKeys() == "" and MOCK.actions.SurvivantCourse == nil, "11 : mort : animations arrêtées, actions libérées")
-- mobile : bouton Courir = interrupteur
char = spawnCharacter()
hum = char:FindFirstChildOfClass("Humanoid")
press("SurvivantCourse", Enum.UserInputState.Begin, Enum.UserInputType.Touch)
press("SurvivantCourse", Enum.UserInputState.End, Enum.UserInputType.Touch)
check(hum.WalkSpeed == 16, "11 : bouton tactile Courir = interrupteur")
press("SurvivantCourse", Enum.UserInputState.Begin, Enum.UserInputType.Touch)
check(hum.WalkSpeed == 6, "11 : second appui -> marche")
-- jeu publié : seules les animations publiées sont chargées, un avertissement liste les autres
char = spawnCharacter({ studio = false, publish = "987654" })
check(track("walk") ~= nil and track("walk").AnimationId == "rbxassetid://987654", "11 : identifiant publié utilisé")
check(#MOCK.tracks == 1 and track("idle") == nil and track("liedown") == nil, "11 : animations non publiées ignorées")
local listed = {}
for n in string.gmatch(MOCK.warnings[1] or "", "Survivant_%a+") do
	listed[n] = true
end
local nListed = 0
for _ in pairs(listed) do
	nListed = nListed + 1
end
check(#MOCK.warnings == 1 and nListed == #CLIPS - 1 and listed.Survivant_Repos and listed.Survivant_Outil
	and not listed.Survivant_Marche and string.find(MOCK.warnings[1], "Save to Roblox", 1, true) ~= nil,
	"11 : un seul avertissement listant les animations à publier")
setVel(char, 3, 0)
MOCK.step(1 / 60, 3)
check(track("walk").IsPlaying, "11 : jeu publié : la marche publiée est jouée")
Instance.new("Tool").Parent = char
setVel(char, 0, 0)
MOCK.step(1 / 60, 3)
check(playingKeys() == "", "11 : jeu publié : pas d'erreur sans les autres animations")
-- Studio sans le dossier des animations : un avertissement
spawnCharacter({ noFolder = true })
check(#MOCK.warnings == 1 and countWarn("Animations introuvables") == 1 and #MOCK.tracks == 0, "11 : Studio sans animations")
end

----------------------------------------------------------------------------------------
section("12. Éditeur (ServerStorage.SurvivantEditeur) : API pour la barre de commande et l'assistant IA")
do
installAll()
rig = rigOf()
local E = require(SS.SurvivantEditeur)
check(type(E) == "table", "12 : require du module")
local API = { "aide", "info", "radiographie", "pose", "reinitialiserPose", "apercu", "lireAnimation", "ecrireAnimation",
	"modifierPose", "restaurerAnimation", "importerDepuisEditeur", "vitesses", "majPersonnageJouable" }
local apiOk = true
for _, n in ipairs(API) do
	apiOk = apiOk and type(E[n]) == "function"
end
check(apiOk, "12 : fonctions de l'API présentes")
local function errOf(fn, ...)
	local ok, err = pcall(fn, ...)
	return (not ok) and tostring(err) or nil
end
local function motorOf(part)
	return rig:FindFirstChild(JOINT_OF[part].name, true)
end
local expectedClip = clipOf
local function deg2cf(p)
	return CFrame.new(p[1], p[2], p[3]) * CFrame.Angles(math.rad(p[4]), math.rad(p[5]), math.rad(p[6]))
end

-- aide / info
local guide = E.aide()
check(type(guide) == "string" and string.find(guide, "GUIDE POUR ASSISTANT IA", 1, true) ~= nil
	and string.find(guide, "RightLowerArm - RightElbow (pivot 1.5, 0, 0)", 1, true) ~= nil
	and string.find(guide, "walk       = Survivant_Marche", 1, true) ~= nil
	and not string.find(guide, "{{", 1, true), "12 : aide() complétée (arbre des articulations, animations)")
local infoText, infoTable = E.info()
check(type(infoText) == "string" and string.find(infoText, "RightElbow", 1, true) ~= nil
	and string.find(infoText, "Survivant_Outil", 1, true) ~= nil and string.find(infoText, "marche 6", 1, true) ~= nil
	and #infoTable.articulations == 10 and #infoTable.animations == #CLIPS and infoTable.vitesses.course == 16,
	"12 : info() (texte et table)")
local infoColon = E:info()
check(type(infoColon) == "string" and infoColon == infoText, "12 : E:info() marche aussi (deux-points)")

-- radiographie
local msg = E.radiographie(true, 0.6)
check(math.abs(rig.Peau.Survivor_Head.Transparency - 0.6) < 1e-9 and rig.Peau.Survivor_Hat.Transparency == 1
	and rig:GetAttribute("Anat_TransparencePeau") == 0.6 and string.find(msg, "activée", 1, true) ~= nil,
	"12 : radiographie(true, 0.6)")
E.radiographie(false)
check(rig.Peau.Survivor_Head.Transparency == 0 and rig.Peau.Survivor_Hat.Transparency == 0, "12 : radiographie(false)")

-- pose : conventions d'angles (repère de la pièce parente : X droite, Y haut, Z arrière)
local function partCF(part, motor) -- position de la pièce donnée par son Motor6D (Part0 au repos)
	local j = JOINT_OF[part]
	local p0 = REST[j.part0] or CFrame.new()
	return p0 * cf12(j.c0) * motor.Transform * cf12(j.c1):Inverse()
end
E.pose("RightElbow", 90, 0, 0)
local elbow = motorOf("RightLowerArm")
check(cfClose(elbow.Transform, CFrame.Angles(math.rad(90), 0, 0), 1e-9), "12 : pose RightElbow rx 90")
check((partCF("RightLowerArm", elbow) * Vector3.new(0, -0.5, 0)).Z < -0.4, "12 : coude plié (rx > 0) : la main part vers l'avant")
E.pose("genou gauche", -90, 0, 0)
check((partCF("LeftLowerLeg", motorOf("LeftLowerLeg")) * Vector3.new(0, -0.5, 0)).Z > 0.4,
	"12 : genou plié (rx < 0) : le pied part vers l'arrière")
E.pose("RightShoulder", 0, 0, 90)
check((partCF("RightUpperArm", motorOf("RightUpperArm")) * Vector3.new(0, -0.5, 0)).X > 1.2,
	"12 : bras droit écarté (rz > 0) : la main part vers la droite")
E.pose("tête", -20, 30, 0)
local neck = motorOf("Head")
check(cfClose(R_ROOT * neck.Transform * R_ROOT:Inverse(), CFrame.Angles(math.rad(-20), math.rad(30), 0), 1e-9),
	"12 : pose de la tête dans les axes du personnage (Neck)")
local headTop = partCF("Head", neck) * Vector3.new(0, 0.5, 0)
local headFront = partCF("Head", neck) * Vector3.new(0, 0, -0.5)
check(headTop.Z < -0.1 and headFront.X < -0.1, "12 : tête baissée (rx < 0) vers l'avant et tournée (ry > 0) vers sa gauche")
E.pose({ LeftElbow = { rx = 45 }, Torso = { rx = -10, y = -0.5 } })
local rootM = motorOf("Torso")
check(cfClose(motorOf("LeftLowerArm").Transform, CFrame.Angles(math.rad(45), 0, 0), 1e-9)
	and cfClose(R_ROOT * rootM.Transform * R_ROOT:Inverse(), CFrame.new(0, -0.5, 0) * CFrame.Angles(math.rad(-10), 0, 0), 1e-9),
	"12 : pose de plusieurs articulations (table, noms de pièces)")
check((partCF("Torso", rootM) * Vector3.new(0, 1, 0)).Z < -0.1, "12 : torse penché en avant (rx < 0)")
local e1 = errOf(E.pose, "Queue", 10, 0, 0)
check(e1 ~= nil and string.find(e1, "inconnue", 1, true) ~= nil and string.find(e1, "RightElbow", 1, true) ~= nil,
	"12 : nom inconnu -> erreur claire listant les noms valides")
msg = E.reinitialiserPose()
local allRest = true
for _, d in ipairs(rig:GetDescendants()) do
	if d:IsA("Motor6D") and not cfClose(d.Transform, CFrame.new()) then
		allRest = false
	end
end
check(allRest and string.find(msg, "10 articulations", 1, true) ~= nil, "12 : reinitialiserPose()")

-- apercu (Animator:StepAnimations, puis calcul direct si l'Animator ne marche pas)
local walkE = expectedClip("walk")
local smp = walkE.samples[#walkE.samples] -- dernière image (pièce LeftLowerLeg)
local midSmp = nil
for _, s in ipairs(walkE.samples) do
	if s.k > 1 and s.k < walkE.nkeys and s.part == "RightLowerArm" then
		midSmp = s
	end
end
MOCK.stepCalls = 0
msg = E.apercu("walk", midSmp.t)
local ep, er = cfErr(motorOf("RightLowerArm").Transform, cf12(midSmp.cf))
check(ep < 2e-3 and er < 3e-3 and MOCK.stepCalls > 0 and string.find(msg, "Animator", 1, true) ~= nil,
	string.format("12 : apercu via l'Animator (écart %.1e / %.1e) : %s", ep, er, msg))
MOCK.stepAnimationsDisabled = true
msg = E.apercu("Survivant_Marche", smp.t)
ep, er = cfErr(motorOf(smp.part).Transform, cf12(smp.cf))
check(ep < 2e-3 and er < 3e-3 and string.find(msg, "poses calculées", 1, true) ~= nil, "12 : apercu sans Animator (calcul direct)")
MOCK.stepAnimationsDisabled = false
local toolE = expectedClip("tool")
local tsmp = toolE.samples[1]
E.apercu("tool", tsmp.t)
ep, er = cfErr(motorOf(tsmp.part).Transform, cf12(tsmp.cf))
check(ep < 2e-3 and er < 3e-3 and cfClose(motorOf("Torso").Transform, CFrame.new()) and cfClose(motorOf("Head").Transform, CFrame.new()),
	"12 : apercu de l'animation superposée (bras droit seulement)")
check(errOf(E.apercu, "danse") ~= nil and string.find(errOf(E.apercu, "danse"), "walk", 1, true) ~= nil,
	"12 : apercu d'une animation inconnue -> erreur listant les clés")
E.reinitialiserPose()

-- lireAnimation
local a = E.lireAnimation("walk")
check(a.cle == "walk" and a.nom == "Survivant_Marche" and a.libelle == walkE.label and a.boucle == true
	and a.priorite == walkE.priority and a.vitesse == walkE.speed and #a.images == walkE.nkeys
	and table.concat(a.pieces, ",") == table.concat(PARTS10, ",") and math.abs(a.duree - walkE.length) < 1e-3,
	"12 : lireAnimation : description")
local function checkReadSamples(anim, e, label)
	local okAll, worst = true, ""
	for _, s in ipairs(e.samples) do
		local p = anim.images[s.k] and anim.images[s.k].poses[s.part]
		if not p then
			okAll, worst = false, "pose absente " .. s.part
		else
			local ep2, er2 = cfErr(deg2cf(p), cf12(s.rig))
			if ep2 > 2e-3 or er2 > 3e-3 then
				okAll, worst = false, string.format("%s image %d (%.1e / %.1e)", s.part, s.k, ep2, er2)
			end
			if math.abs(s.deg[5]) < 80 then
				for i = 1, 6 do
					if math.abs(p[i] - s.deg[i]) > (i <= 3 and 2e-3 or 0.3) then
						okAll, worst = false, string.format("%s image %d composante %d : %g au lieu de %g", s.part, s.k, i, p[i], s.deg[i])
					end
				end
			end
		end
	end
	check(okAll, label .. " (" .. worst .. ")")
end
for _, e in ipairs(CLIPS) do
	checkReadSamples(E.lireAnimation(e.key), e, "12 : lireAnimation(" .. e.key .. ") : poses dans les axes du personnage")
end
local at = E.lireAnimation("tool")
local onlyArm = true
for _, img in ipairs(at.images) do
	for n in pairs(img.poses) do
		if n ~= "RightUpperArm" and n ~= "RightLowerArm" then
			onlyArm = false
		end
	end
end
check(table.concat(at.pieces, ",") == "RightUpperArm,RightLowerArm" and onlyArm, "12 : lireAnimation(tool) : bras droit seulement")

-- ecrireAnimation : aller-retour, identifiant publié vidé, copies de l'éditeur, historique
local idsE = RS.SurvivantAnimations.AnimationIds
idsE.idle.Value = "555"
local idleE = expectedClip("idle")
local before = E.lireAnimation("idle")
MOCK.chsLog = {}
msg = E.ecrireAnimation("idle", before)
local after = E.lireAnimation("idle")
local same = #after.images == #before.images
for i, img in ipairs(before.images) do
	for n, p in pairs(img.poses) do
		local q = after.images[i] and after.images[i].poses[n]
		for c = 1, 6 do
			same = same and q ~= nil and math.abs(q[c] - p[c]) < 2e-3
		end
	end
end
check(same, "12 : ecrireAnimation(lireAnimation(...)) ne change rien")
local idleK = RS.SurvivantAnimations.Survivant_Repos
check(idleK:GetAttribute("Survivant_Modifiee") == true and idleK:GetAttribute("Survivant_Cle") == "idle"
	and idleK.Priority == Enum.AnimationPriority.Idle and idleK.Loop == true, "12 : animation réécrite marquée modifiée")
check(idsE.idle.Value == "" and idsE.idle:GetAttribute("AncienIdentifiant") == "555" and string.find(msg, "republiez", 1, true) ~= nil,
	"12 : identifiant publié vidé (gardé dans AncienIdentifiant)")
local okTree2 = true
for _, kf in ipairs(idleK:GetChildren()) do
	okTree2 = okTree2 and (treeOk(kf, PARTS10))
end
check(okTree2 and #idleK:GetChildren() == idleE.nkeys, "12 : hiérarchie des poses réécrite")
local idleList = sortedKeyframes(idleK)
local okSamples = true
for _, s in ipairs(idleE.samples) do
	local pose = idleList[s.k]:FindFirstChild(s.part, true)
	local ep3, er3 = cfErr(pose.CFrame, cf12(s.cf))
	okSamples = okSamples and ep3 < 2e-3 and er3 < 3e-3
end
check(okSamples, "12 : poses réécrites identiques à l'original")
local copy = SS.RBX_ANIMSAVES.Anatomie_R6:FindFirstChild("Survivant_Repos")
check(copy ~= nil and copy:GetAttribute("Survivant_Modifiee") == true and #copy:GetChildren() == idleE.nkeys
	and #SS.RBX_ANIMSAVES.Anatomie_R6:GetChildren() == #CLIPS, "12 : copie de l'Éditeur d'animation mise à jour")
check(MOCK.chsLog[1] == "begin:SurvivantEditeur" and MOCK.chsLog[2] == "finish:Commit", "12 : écriture annulable (Ctrl+Z)")
-- nouvelle animation
msg = E.ecrireAnimation("salut", { nom = "Survivant_Salut", duree = 1, boucle = false, priorite = "Action", images = {
	{ t = 0, poses = { RightUpperArm = { 0, 0, 0, 0, 0, 0 }, RightLowerArm = { 0, 0, 0, 0, 0, 0 } } },
	{ t = 0.5, poses = { RightUpperArm = { 0, 0, 0, 0, 0, 160 }, coude_droit = { rx = 30 } } },
	{ t = 1, poses = { RightUpperArm = { 0, 0, 0, 0, 0, 0 }, RightLowerArm = { 0, 0, 0, 0, 0, 0 } } },
} })
local salut = RS.SurvivantAnimations:FindFirstChild("Survivant_Salut")
check(salut ~= nil and salut.Loop == false and salut.Priority == Enum.AnimationPriority.Action and #salut:GetChildren() == 3
	and idsE:FindFirstChild("salut") ~= nil and salut:GetAttribute("Survivant_Cle") == "salut", "12 : nouvelle animation créée")
local salutList = sortedKeyframes(salut)
local okSalut = true
for _, kf in ipairs(salutList) do
	okSalut = okSalut and (treeOk(kf, { "RightUpperArm", "RightLowerArm" }))
end
local up = salutList[2]:FindFirstChild("RightUpperArm", true)
check(okSalut and cfClose(up.CFrame, CFrame.Angles(0, 0, math.rad(160)), 1e-9)
	and cfClose(salutList[2]:FindFirstChild("RightLowerArm", true).CFrame, CFrame.Angles(math.rad(30), 0, 0), 1e-9),
	"12 : poses de la nouvelle animation (superposée, bras droit)")
check(string.find(E.info(), "salut", 1, true) ~= nil, "12 : la nouvelle animation apparaît dans info()")
-- erreurs : rien n'est modifié
local nChildren = #RS.SurvivantAnimations:GetChildren()
MOCK.chsLog = {}
local e2 = errOf(E.ecrireAnimation, "pas bon!", { images = { { t = 0, poses = {} } } })
check(e2 ~= nil and string.find(e2, "clé invalide", 1, true) ~= nil, "12 : clé invalide")
check(MOCK.chsLog[2] == "finish:Cancel", "12 : écriture refusée annulée dans l'historique")
local e3 = errOf(E.ecrireAnimation, "idle", { images = {} })
check(e3 ~= nil and string.find(e3, "non vide", 1, true) ~= nil, "12 : liste d'images vide")
local e4 = errOf(E.ecrireAnimation, "idle", { images = { { t = 0, poses = { Aile = { 0, 0, 0, 0, 0, 0 } } } } })
check(e4 ~= nil and string.find(e4, "inconnue", 1, true) ~= nil, "12 : pièce inconnue")
local e5 = errOf(E.ecrireAnimation, "idle", { images = { { t = 0, poses = { Head = { 0, 0, 0, 0, 0, 0 } } },
	{ t = 0.0001, poses = { Head = { 0, 0, 0, 0, 0, 0 } } } } })
check(e5 ~= nil and string.find(e5, "même instant", 1, true) ~= nil, "12 : deux images au même instant")
local e6 = errOf(E.ecrireAnimation, "idle", { images = { { t = 0, poses = { Head = { 0, 0, 0, "x", 0, 0 } } } } })
check(e6 ~= nil and string.find(e6, "nombre attendu", 1, true) ~= nil, "12 : valeur non numérique")
local e10 = errOf(E.ecrireAnimation, "walk", { nom = "Survivant_Course", images = { { t = 0, poses = { Head = {} } } } })
check(e10 ~= nil and string.find(e10, "déjà celui de l'animation « run »", 1, true) ~= nil
	and RS.SurvivantAnimations:FindFirstChild("Survivant_Course") ~= nil, "12 : nom déjà pris par une autre animation refusé")
check(#RS.SurvivantAnimations:GetChildren() == nChildren and RS.SurvivantAnimations:FindFirstChild("Survivant_Repos") == idleK,
	"12 : erreurs sans effet sur les animations")
check(string.find(E.ecrireAnimation("idle", { boucle = true, images = { { t = 0, poses = { Head = { 0, 0, 0, 0, 0, 0 } } },
	{ t = 1, poses = { Head = { 0, 0, 0, 10, 0, 0 } } } } }), "la boucle sautera", 1, true) ~= nil,
	"12 : boucle dont la fin diffère du début signalée")
E.restaurerAnimation("idle")

-- modifierPose
local runE = expectedClip("run")
local r0 = E.lireAnimation("run")
local kMid = math.floor(#r0.images / 2)
local tMid = r0.images[kMid].t
local p0 = r0.images[kMid].poses.RightLowerArm
msg = E.modifierPose("run", tMid, "RightElbow", { rx = 45 })
local r1 = E.lireAnimation("run")
local p1 = r1.images[kMid].poses.RightLowerArm
check(#r1.images == #r0.images and math.abs(p1[4] - 45) < 1e-2 and math.abs(p1[5] - p0[5]) < 1e-2 and math.abs(p1[6] - p0[6]) < 1e-2
	and string.find(msg, "RightLowerArm", 1, true) ~= nil, "12 : modifierPose (valeur absolue) sur une image clé existante")
E.modifierPose("run", tMid, "coude droit", { rx = 5, relatif = true })
check(math.abs(E.lireAnimation("run").images[kMid].poses.RightLowerArm[4] - 50) < 1e-2, "12 : modifierPose relatif (+5°)")
local untouched = true
for i, img in ipairs(r0.images) do
	if i ~= kMid then
		local q = E.lireAnimation("run").images[i].poses.RightLowerArm
		for c = 1, 6 do
			untouched = untouched and math.abs(q[c] - img.poses.RightLowerArm[c]) < 2e-3
		end
	end
end
check(untouched, "12 : les autres images clés ne bougent pas")
-- image clé insérée entre deux images : les autres pièces gardent leur pose interpolée
local oldKfs = RS.SurvivantAnimations.Survivant_Course:Clone()
local tNew = (r0.images[2].t + r0.images[3].t) / 2
msg = E.modifierPose("run", tNew, "Head", { ry = 15 })
local r2 = E.lireAnimation("run")
local newImg = nil
for _, img in ipairs(r2.images) do
	if math.abs(img.t - tNew) < 1e-3 then
		newImg = img
	end
end
local interpOk = newImg ~= nil and #r2.images == #r0.images + 1 and math.abs(newImg.poses.Head[5] - 15) < 1e-2
if newImg then
	local torsoKfs = sortedKeyframes(RS.SurvivantAnimations.Survivant_Course)
	local inserted = nil
	for _, kf in ipairs(torsoKfs) do
		if math.abs(kf.Time - tNew) < 1e-3 then
			inserted = kf
		end
	end
	local want = MOCK.kfsPoseAt(oldKfs, "RightUpperLeg", tNew)
	interpOk = interpOk and inserted ~= nil and cfClose(inserted:FindFirstChild("RightUpperLeg", true).CFrame, want, 1e-6)
end
check(interpOk and string.find(msg, "ajoutée", 1, true) ~= nil, "12 : modifierPose entre deux images : image clé ajoutée, poses interpolées")
-- boucle : modifier t = 0 modifie aussi la dernière image
E.modifierPose("run", 0, "Neck", { rz = 12 })
local r3 = E.lireAnimation("run")
local first, last = r3.images[1].poses.Head, r3.images[#r3.images].poses.Head
check(math.abs(first[6] - 12) < 1e-2 and math.abs(last[6] - 12) < 1e-2 and math.abs(first[5] - last[5]) < 1e-2,
	"12 : boucle : première et dernière images modifiées ensemble")
local e7 = errOf(E.modifierPose, "run", 0.1, "Head", { tourne = 3 })
check(e7 ~= nil and string.find(e7, "changement inconnu", 1, true) ~= nil, "12 : changement inconnu")
local e8 = errOf(E.modifierPose, "run", 99, "Head", { rx = 3 })
check(e8 ~= nil and string.find(e8, "hors de l'animation", 1, true) ~= nil, "12 : temps hors de l'animation")
check(RS.SurvivantAnimations.Survivant_Course:GetAttribute("Survivant_Modifiee") == true, "12 : animation modifiée marquée")
-- modifier une pièce non animée d'une animation partielle : elle devient animée
E.modifierPose("tool", 0, "Neck", { rx = -8 })
local at2 = E.lireAnimation("tool")
check(table.concat(at2.pieces, ",") == "Head,RightUpperArm,RightLowerArm" and at2.images[1].poses.Head ~= nil
	and at2.images[2].poses.Head == nil, "12 : pièce ajoutée à l'animation superposée (clé seulement aux instants modifiés)")

-- relance de l'installateur : les animations modifiées sont conservées
runAnims()
local kept = RS.SurvivantAnimations.Survivant_Course
check(kept:GetAttribute("Survivant_Modifiee") == true and #kept:GetChildren() == #r0.images + 1
	and printedContains("Animations modifiées avec SurvivantEditeur conservées"), "12 : relancer l'installateur garde les modifications")
E = require(SS.SurvivantEditeur) -- nouveau module installé

-- restaurerAnimation
msg = E.restaurerAnimation("run")
local restored = RS.SurvivantAnimations.Survivant_Course
check(#restored:GetChildren() == runE.nkeys and restored:GetAttribute("Survivant_Modifiee") == nil
	and string.find(msg, "origine", 1, true) ~= nil, "12 : restaurerAnimation remet la version d'origine")
local runList = sortedKeyframes(restored)
local okRestore = true
for _, s in ipairs(runE.samples) do
	local ep4, er4 = cfErr(runList[s.k]:FindFirstChild(s.part, true).CFrame, cf12(s.cf))
	okRestore = okRestore and ep4 < 2e-3 and er4 < 3e-3
end
check(okRestore, "12 : poses d'origine restaurées")
check(errOf(E.restaurerAnimation, "salut") ~= nil, "12 : pas de version d'origine pour une animation créée")

-- importerDepuisEditeur : reprend la version enregistrée par l'Éditeur d'animation
local crouchCopy = SS.RBX_ANIMSAVES.Anatomie_R6.Survivant_Accroupi
local firstKf = sortedKeyframes(crouchCopy)[1]
firstKf:FindFirstChild("Head", true).CFrame = CFrame.Angles(0.3, 0, 0)
msg = E.importerDepuisEditeur("crouch")
local crouchK = RS.SurvivantAnimations.Survivant_Accroupi
check(cfClose(sortedKeyframes(crouchK)[1]:FindFirstChild("Head", true).CFrame, CFrame.Angles(0.3, 0, 0), 1e-9)
	and crouchK:GetAttribute("Survivant_Modifiee") == true and string.find(msg, "reprise", 1, true) ~= nil,
	"12 : importerDepuisEditeur")

-- vitesses (sources des scripts Animate)
local speedsText, speeds = E.vitesses()
check(speeds.marche == 6 and speeds.course == 16 and speeds.accroupi == 3 and speeds.allonge == 1.5
	and string.find(speedsText, "course 16", 1, true) ~= nil, "12 : vitesses() lit les vitesses")
MOCK.sourceUpdates = 0
msg = E.vitesses({ course = 18 })
local line = "VITESSE = { marche = 6, course = 18, accroupi = 3, allonge = 1.5 },"
check(string.find(rig.Animate.Source, line, 1, true) ~= nil and string.find(SP.StarterCharacter.Animate.Source, line, 1, true) ~= nil
	and MOCK.sourceUpdates == 2, "12 : vitesses({ course = 18 }) via ScriptEditorService (rig et StarterCharacter)")
MOCK.scriptEditorDisabled = true
E.vitesses({ marche = 7 })
check(string.find(SP.StarterCharacter.Animate.Source, "marche = 7, course = 18", 1, true) ~= nil, "12 : vitesses sans ScriptEditorService")
MOCK.scriptEditorDisabled = false
check(string.find(E.vitesses({ course = 40 }), "glissent", 1, true) ~= nil, "12 : vitesse trop forte signalée")
E.vitesses({ course = 18 })
check(errOf(E.vitesses, { vole = 3 }) ~= nil and errOf(E.vitesses, { marche = -1 }) ~= nil, "12 : vitesse inconnue ou négative refusée")
local speedSrc = SP.StarterCharacter.Animate.Source
-- majPersonnageJouable
E.pose("RightElbow", 70, 0, 0)
local oldSC = SP.StarterCharacter
msg = E.majPersonnageJouable()
local newSC = SP:FindFirstChild("StarterCharacter")
check(newSC ~= nil and newSC ~= oldSC and oldSC.Parent == nil and #SP:GetChildren() == 2, "12 : StarterCharacter remplacé")
if newSC then
	checkRigStructure("12 majPersonnageJouable", {}, DEFAULT_T, false, newSC)
	check(cfClose(newSC.RightLowerArm.RightElbow.Transform, CFrame.new()) and newSC.Animate.Source == rig.Animate.Source,
		"12 : copie au repos, avec le contrôleur")
end
-- le contrôleur du personnage jouable utilise les nouvelles vitesses
local charE = SP.StarterCharacter:Clone()
charE.Parent = workspace
MOCK.quiet = true
local fE = loadstring("local script = ...\n" .. charE.Animate.Source, "@Animate")
fE(charE.Animate)
MOCK.quiet = false
MOCK.step(1 / 60, 2)
check(charE.Humanoid.WalkSpeed == 7 and string.find(speedSrc, "marche = 7", 1, true) ~= nil, "12 : nouvelles vitesses en jeu")
-- sans données : erreur claire
SS.SurvivantEditeur.Donnees:Destroy()
local E2 = require(SS.SurvivantEditeur:Clone())
local e9 = errOf(E2.info)
check(e9 ~= nil and string.find(e9, "Donnees", 1, true) ~= nil, "12 : module Donnees absent -> erreur claire")
end

MOCK.rawPrint(string.format("\n%d vérifications, %d échec(s)", checks, failures))
if failures > 0 then
	error("TESTS EN ÉCHEC")
end
