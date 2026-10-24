--[[
	Tests hors ligne du paquet Roblox du monstre (émulation de l'API, rbx_mock.lua) :
		cd monstre/roblox && luaurun test/rbx_mock.lua test/test_monstre.lua
	1. installation sur un import simulé (échelle 0,01, penché et tourné), erreurs (miroir, marqueur absent), réinstallation
	2. décodage des pistes (MonstreAnim) comparé au calcul Python (reference_poses.lua)
	3. chaîne complète : installateur (C0/C1) + lecteur + soudure de la victime sur l'ancre + joints, comparée aux
	   positions calculées en Python (fixtures.lua)
	4. jeu : serveur et client lancés, le monstre repère et poursuit le joueur, puis les 8 mises à mort de bout en bout
	   (caméra, coupure au noir, sang, cadavre, traînées, infection)
]]

local FIX = loadstring(readfile("test/fixtures.lua"))()
local REF = loadstring(readfile("test/reference_poses.lua"))()
local STATE = MOCK.STATE

local nOk, nKo = 0, 0
local function check(cond, msg)
	if cond then
		nOk += 1
	else
		nKo += 1
		MOCK.rawPrint("ÉCHEC : " .. tostring(msg))
	end
	return cond
end
local function section(t)
	MOCK.rawPrint("== " .. t)
end
local function v3(t)
	return Vector3.new(t[1], t[2], t[3])
end
local function near(a, b, tol)
	return (a - b).Magnitude <= (tol or 1e-3)
end
local function cf12(t)
	return CFrame.new(t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9], t[10], t[11], t[12])
end

local RS = game:GetService("ReplicatedStorage")
local SSS = game:GetService("ServerScriptService")
local SS = game:GetService("ServerStorage")
local SP = game:GetService("StarterPlayer")
local CS = game:GetService("CollectionService")
local Players = game:GetService("Players")
local Lighting = game:GetService("Lighting")

local SOURCES = {
	{ "Installateur", "ModuleScript", "src/Installateur.lua" },
	{ "MonstreAnim", "ModuleScript", "src/MonstreAnim.lua" },
	{ "MonstreConfig", "ModuleScript", "src/MonstreConfig.lua" },
	{ "MonstreDonnees", "ModuleScript", "src/MonstreDonnees.lua" },
	{ "MonstreOutils", "ModuleScript", "src/MonstreOutils.lua" },
	{ "MonstreServeur", "Script", "src/MonstreServeur.server.lua" },
	{ "MonstreClient", "LocalScript", "src/MonstreClient.client.lua" },
}

local function construireKit()
	local kit = Instance.new("Folder")
	kit.Name = "Monstre_Kit"
	for _, def in ipairs(SOURCES) do
		local s = Instance.new(def[2])
		s.Name = def[1]
		s.Source = readfile(def[3])
		if def[2] == "Script" then
			s.Disabled = true
		end
		s.Parent = kit
	end
	kit.Parent = workspace
	return kit
end

local SANG = { "SANG_Flaque", "SANG_Eclaboussure_1", "SANG_Eclaboussure_2", "SANG_Eclaboussure_3", "SANG_Trainee",
	"SANG_Ecran", "SANG_Goutte" }

-- import simulé : repère du modèle -> monde = CFrame.new(T) * R, échelle s
local function importer(s, R, T, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "Monstre"
	local M = CFrame.new(T) * R
	local function piece(nom, c, taille)
		local p = Instance.new("MeshPart")
		p.Name = nom
		p.Size = taille * s
		p.CFrame = M * CFrame.new(c * s)
		p.Parent = m
		return p
	end
	for _, p in ipairs(FIX.monstre) do
		piece(p.name, v3(p.center), v3(p.size))
	end
	piece("MON_Chest_2", v3(FIX.monstre[3].center) + Vector3.new(0, 0.2, 0), Vector3.new(0.5, 0.5, 0.5))
	for nom, c in pairs(FIX.marqueurs) do
		if not (opts.sans and opts.sans == nom) then
			local mk = v3(c)
			if opts.miroir and nom == "REF_D" then
				mk = Vector3.new(mk.X, mk.Y, -mk.Z)
			end
			piece(nom, mk, Vector3.new(0.05, 0.05, 0.05))
		end
	end
	piece("GLOW_MOUTH", v3(FIX.glow), Vector3.new(0.05, 0.05, 0.05))
	for i, nom in ipairs(SANG) do
		local p = piece(nom, Vector3.new(6 + i, 0, 0), Vector3.new(1, 0.001, 1))
		local sa = Instance.new("SurfaceAppearance")
		sa.ColorMap = "rbxassetid://" .. (5000 + i)
		sa.Parent = p
	end
	m.Parent = workspace
	return m, M
end

local function compterMoteurs(m)
	local n = 0
	for _, d in ipairs(m:GetDescendants()) do
		if d:IsA("Motor6D") then
			n += 1
		end
	end
	return n
end

------------------------------------------------------------------------------------------------------------
section("1. Installation sur un import penché, tourné, à l'échelle 0,01")
MOCK.reset()
MOCK.quiet = true
local kit = construireKit()
local R0 = CFrame.Angles(0.35, 1.1, -0.25)
local imp, Mimp = importer(0.01, R0, Vector3.new(40, 12, -15))
local ok, modele, rapport = require(kit.Installateur)()
check(ok == true, "installation : " .. tostring(modele))
check(compterMoteurs(modele) == 38, "38 Motor6D (" .. compterMoteurs(modele) .. ")")
local hrp = modele:FindFirstChild("HumanoidRootPart")
check(hrp and near(hrp.Size, Vector3.new(2.4, 2.4, 1.6)), "taille du HumanoidRootPart")
check(hrp and near(hrp.CFrame.UpVector, Vector3.new(0, 1, 0), 1e-6), "monstre debout (axe Y vertical)")
local avantAttendu = -(R0.ZVector)
avantAttendu = Vector3.new(avantAttendu.X, 0, avantAttendu.Z).Unit
check(hrp and near(hrp.CFrame.LookVector, avantAttendu, 1e-6), "monstre face à sa direction d'origine")
local M2 = hrp.CFrame * CFrame.new(-Vector3.new(0, 7.128, 0.2904)) -- repère du modèle installé
local h = modele:FindFirstChildOfClass("Humanoid")
check(h and math.abs(h.HipHeight - 5.928) < 1e-6, "HipHeight 5,928")
check(h and h.RigType == Enum.HumanoidRigType.R15 and h.RequiresNeck == false and h.BreakJointsOnDeath == false,
	"Humanoid R15, RequiresNeck et BreakJointsOnDeath coupés")
check(CS:HasTag(modele, "Monstre"), "étiquette Monstre")
check(modele:FindFirstChild("REF_A", true) == nil and modele:FindFirstChild("GLOW_MOUTH", true) == nil, "marqueurs retirés")
local lueur = modele:FindFirstChild("Lueur")
check(lueur and lueur:FindFirstChildOfClass("PointLight") and lueur:FindFirstChildOfClass("WeldConstraint"), "lueur soudée à la tête")
check(lueur and near(lueur.Position, M2 * v3(FIX.glow), 1e-4), "lueur à GLOW_MOUTH")
-- tailles remises à l'échelle 1 et pivots cohérents
local tailleOk, pivOk, nPiv = true, true, 0
local donnees = require(RS.Monstre.MonstreDonnees)
local pivots = {}
for _, def in ipairs(donnees.rig.parts) do
	pivots[def.name] = v3(def.pivot)
end
for _, p in ipairs(FIX.monstre) do
	local part = modele:FindFirstChild(p.name, true)
	if not (part and near(part.Size, v3(p.size), 1e-4)) then
		tailleOk = false
	end
	if part and not near(part.Position, M2 * v3(p.center), 1e-3) then
		tailleOk = false
	end
end
for _, d in ipairs(modele:GetDescendants()) do
	if d:IsA("Motor6D") then
		local a = d.Part0.CFrame * d.C0
		local b = d.Part1.CFrame * d.C1
		if not (near(a.Position, b.Position, 1e-4) and near(a.Position, M2 * pivots[d.Name], 1e-3)) then
			pivOk = false
		end
		if not near(a.XVector, b.XVector, 1e-6) or not near(a.XVector, hrp.CFrame.XVector, 1e-6) then
			pivOk = false
		end
		nPiv += 1
	end
end
check(tailleOk, "pièces remises à l'échelle 1, à leur place")
check(pivOk and nPiv == 38, "Motor6D : C0 et C1 au pivot de l'articulation, axes du modèle")
local ancre = modele:FindFirstChild("VictimeAncrePart")
check(ancre and near(ancre.Position, M2 * v3(donnees.rig.victimRest), 1e-4), "pièce VictimeAncrePart au repos de la victime")
check(ancre and near(ancre.CFrame.LookVector, -hrp.CFrame.LookVector, 1e-6), "victime tournée vers le monstre")
local chest2 = modele:FindFirstChild("MON_Chest_2", true)
local wc = chest2 and chest2:FindFirstChildOfClass("WeldConstraint")
check(wc and wc.Part0 == modele:FindFirstChild("MON_Chest_1", true), "maillage supplémentaire soudé à sa pièce")
local effets = RS.Monstre:FindFirstChild("Effets")
check(effets and #effets:GetChildren() == #SANG, "gabarits de sang rangés")
check(effets and effets.SANG_Flaque.SurfaceAppearance.AlphaMode == Enum.AlphaMode.Transparency, "transparence par l'alpha")
check(effets and effets:GetAttribute("ImageGoutte") == "rbxassetid://5007", "image de la goutte pour les particules")
check(SSS:FindFirstChild("MonstreServeur") and SSS.MonstreServeur.Disabled == false, "MonstreServeur activé dans ServerScriptService")
local sps = SP:FindFirstChildOfClass("StarterPlayerScripts")
check(sps and sps:FindFirstChild("MonstreClient"), "MonstreClient dans StarterPlayerScripts")
check(SS:FindFirstChild("MonstreOutils") and SS:FindFirstChild("Monstre_Kit"), "MonstreOutils et le kit dans ServerStorage")
for _, d in ipairs(modele:GetDescendants()) do
	if d:IsA("BasePart") and d ~= hrp and d.CanCollide then
		check(false, "pièce qui collisionne : " .. d.Name)
	end
end
local rapportV, okV = require(SS.MonstreOutils).verifier()
check(okV, "MonstreOutils.verifier :\n" .. rapportV)
-- réinstallation : scripts mis à jour, rig intact
local ok2 = require(SS.Monstre_Kit.Installateur)()
check(ok2 == true and compterMoteurs(modele) == 38, "réinstallation sans import : scripts mis à jour")
-- erreurs
MOCK.reset()
kit = construireKit()
importer(1, CFrame.new(), Vector3.new(0, 0, 0), { miroir = true })
local okM, errM = require(kit.Installateur)()
check(okM == false and string.find(errM, "miroir"), "import en miroir refusé : " .. tostring(errM))
MOCK.reset()
kit = construireKit()
importer(1, CFrame.new(), Vector3.new(0, 0, 0), { sans = "REF_C" })
local okC, errC = require(kit.Installateur)()
check(okC == false and string.find(errC, "REF_C"), "REF_C absent : refusé (" .. tostring(errC) .. ")")

------------------------------------------------------------------------------------------------------------
section("2. Décodage des pistes (comparé au calcul Python)")
local MA = require(RS.Monstre.MonstreAnim)
MOCK.reset()
kit = construireKit()
local D = require(kit.MonstreDonnees)
MA.init(D)
local maxQ, maxP = 0, 0
for _, r in ipairs(REF) do
	local rig, key, t, piste = r[1], r[2], r[3], r[4]
	local p = MA.pose(rig, key, t)[piste]
	if not p then
		check(false, "piste absente " .. key .. "." .. piste)
	else
		local d = math.abs(p[1] * r[5] + p[2] * r[6] + p[3] * r[7] + p[4] * r[8])
		maxQ = math.max(maxQ, 1 - d)
		maxP = math.max(maxP, math.abs(p[5] - r[9]), math.abs(p[6] - r[10]), math.abs(p[7] - r[11]))
	end
end
check(maxQ < 3e-6 and maxP < 2e-6, string.format("poses identiques au Python (1-|q.q'| %.2e, position %.2e)", maxQ, maxP))
local nClips = 0
for k, _ in pairs(D.monstre) do
	check(MA.clip("monstre", k) ~= nil, "clip " .. k)
	nClips += 1
end
check(nClips == 21, "21 clips du monstre (" .. nClips .. ")")
local nv = 0
for k, _ in pairs(D.victime) do
	nv += 1
end
check(nv == 13, "13 clips de la victime (" .. nv .. ")")
-- boucles : la dernière clé égale la première
for k, c in pairs(D.monstre) do
	if c.loop then
		local a, b = MA.pose("monstre", k, 0), MA.pose("monstre", k, c.length - 1e-6)
		local pire = 0
		for nom, pa in pairs(a) do
			local pb = b[nom]
			pire = math.max(pire, 1 - math.abs(pa[1] * pb[1] + pa[2] * pb[2] + pa[3] * pb[3] + pa[4] * pb[4]))
		end
		check(pire < 1e-6, "boucle " .. k .. " fermée")
	end
end
-- marqueurs franchis (boucle)
local evts = {}
MA.marqueursEntre(MA.clip("monstre", "walk"), 1.5, 3.3, evts)
check(#evts == 3 and math.abs(evts[3][1] - 3.22) < 1e-9, "marqueurs de pas franchis sur une boucle (" .. #evts .. ")")

------------------------------------------------------------------------------------------------------------
section("3. Chaîne complète : installateur + lecteur + victime soudée + joints (comparée au Python)")
local function creerSurvivant(nom, cfRacine, joueur)
	local m = Instance.new("Model")
	m.Name = nom
	local parts = {}
	for _, p in ipairs(FIX.survivant.parts) do
		local part = Instance.new("Part")
		part.Name = p.name
		part.Size = v3(p.size)
		part.CFrame = cfRacine * CFrame.new(v3(p.center))
		part.Transparency = p.name == "HumanoidRootPart" and 1 or 0
		part.Parent = m
		parts[p.name] = part
	end
	for _, j in ipairs(FIX.survivant.joints) do
		local mo = Instance.new("Motor6D")
		mo.Name = j.name
		mo.Part0 = parts[j.part0]
		mo.Part1 = parts[j.part1]
		mo.C0 = cf12(j.C0)
		mo.C1 = cf12(j.C1)
		mo.Parent = j.name == "RootJoint" and parts.HumanoidRootPart or parts[j.part1]
	end
	-- tenue soudée (doit suivre dans le cadavre) et anatomie (ignorée)
	local veste = Instance.new("MeshPart")
	veste.Name = "Survivor_Torso"
	veste.Size = Vector3.new(2.1, 2.1, 1.1)
	veste.CFrame = parts.Torso.CFrame
	local peau = Instance.new("Folder")
	peau.Name = "Peau"
	peau.Parent = m
	veste.Parent = peau
	local w = Instance.new("WeldConstraint")
	w.Part0 = parts.Torso
	w.Part1 = veste
	w.Parent = veste
	local ana = Instance.new("Folder")
	ana.Name = "Anatomie"
	ana.Parent = m
	local os_ = Instance.new("MeshPart")
	os_.Name = "Torso_Sternum"
	os_.CFrame = parts.Torso.CFrame
	os_.Parent = ana
	local w2 = Instance.new("WeldConstraint")
	w2.Part0 = parts.Torso
	w2.Part1 = os_
	w2.Parent = os_
	local hum = Instance.new("Humanoid")
	hum.HipHeight = 2
	hum.Parent = m
	m.PrimaryPart = parts.HumanoidRootPart
	m.Parent = workspace
	if joueur then
		MOCK.setCharacter(joueur, m)
	end
	return m
end

MOCK.reset()
kit = construireKit()
importer(1, CFrame.new(), Vector3.new(0, 0, 0))
local okI, mon = require(kit.Installateur)()
check(okI, "installation (repère simple)")
MA.init(require(RS.Monstre.MonstreDonnees))
local hrpM = mon.HumanoidRootPart
local M2b = hrpM.CFrame * CFrame.new(-Vector3.new(0, 7.128, 0.2904))
local moteursM = MA.moteurs(mon, "monstre")
local vic = creerSurvivant("Victime_Chaine", mon.VictimeAncrePart.CFrame)
MOCK.solveJoints()
local soud = Instance.new("Weld")
soud.Part0 = mon.VictimeAncrePart
soud.Part1 = vic.HumanoidRootPart
soud.Parent = mon.VictimeAncrePart
local moteursV = MA.moteurs(vic, "victime")
hrpM.Anchored = true
for _, cas in ipairs(FIX.attendus) do
	local pm = MA.pose("monstre", cas.clip, cas.t)
	for nom, mo in pairs(moteursM) do
		local p = pm[nom]
		mo.Transform = p and MA.toCFrame(p) or CFrame.identity
	end
	local pv = cas.victime and MA.pose("victime", cas.clip, cas.t) or {}
	for nom, mo in pairs(moteursV) do
		local p = pv[nom]
		mo.Transform = p and MA.toCFrame(p) or CFrame.identity
	end
	MOCK.solveJoints()
	local pire = 0
	for nom, attendu in pairs(cas.monstre) do
		local mo = moteursM[nom]
		local piv = mo.Part1.CFrame * mo.C1.Position
		pire = math.max(pire, (piv - M2b * v3(attendu)).Magnitude)
	end
	check(pire < 2e-3, string.format("%s à %.3f s : pivots du monstre (écart %.4f)", cas.clip, cas.t, pire))
	if cas.victime then
		local pireV = 0
		for nom, attendu in pairs(cas.victime) do
			local part = vic:FindFirstChild(nom)
			pireV = math.max(pireV, (part.Position - M2b * v3(attendu)).Magnitude)
		end
		check(pireV < 2e-3, string.format("%s à %.3f s : victime soudée sur l'ancre (écart %.4f)", cas.clip, cas.t, pireV))
	end
end
-- cadavre : cinématique directe du serveur = joints
local poseV = MA.pose("victime", "k_contamination", 2.7)
local ancreCF = MA.ancre(mon, "k_contamination", 2.7)
local cfs = MA.cinematique(vic, "victime", poseV, ancreCF)
local pm = MA.pose("monstre", "k_contamination", 2.7)
for nom, mo in pairs(moteursM) do
	local p = pm[nom]
	mo.Transform = p and MA.toCFrame(p) or CFrame.identity
end
for nom, mo in pairs(moteursV) do
	local p = poseV[nom]
	mo.Transform = p and MA.toCFrame(p) or CFrame.identity
end
MOCK.solveJoints()
local pireC = 0
for part, cf in pairs(cfs) do
	if part:IsA("BasePart") and part.Parent == vic then
		pireC = math.max(pireC, (part.Position - cf.Position).Magnitude)
	end
end
check(pireC < 1e-4, string.format("cinématique du serveur (cadavre) = joints (écart %.5f)", pireC))

------------------------------------------------------------------------------------------------------------
section("4. Jeu : poursuite et mises à mort (serveur + client)")

local function nouvellePartie()
	MOCK.reset()
	MOCK.quiet = true
	local sol = Instance.new("Part")
	sol.Name = "Sol"
	sol.Anchored = true
	sol.Size = Vector3.new(600, 1, 600)
	sol.CFrame = CFrame.new(0, -0.5, 0)
	sol.Parent = workspace
	local k = construireKit()
	importer(1, CFrame.new(), Vector3.new(0, 0, 0))
	local okP, m = require(k.Installateur)()
	assert(okP, tostring(m))
	-- sons : identifiants factices pour compter les lectures
	local cfg = require(RS.Monstre.MonstreConfig)
	for nom, v in pairs(cfg.SONS) do
		if nom ~= "volume" then
			cfg.SONS[nom] = "rbxassetid://1" .. #nom
		end
	end
	cfg.INFECTION.delai = 1
	cfg.INFECTION.duree = 4
	cfg.TRAINER.duree_repas = 2
	MOCK.solveJoints()
	MOCK.autoSolve = true
	return m, cfg
end

-- le Humanoid du monstre marche vers MoveTo (le moteur physique n'est pas émulé)
local function avancerMonstre(m, dt)
	local hrp_ = m.HumanoidRootPart
	local h_ = m:FindFirstChildOfClass("Humanoid")
	local but = STATE[h_].moveTo
	if hrp_.Anchored or not but then
		hrp_.AssemblyLinearVelocity = Vector3.zero
		return
	end
	local d = Vector3.new(but.X - hrp_.Position.X, 0, but.Z - hrp_.Position.Z)
	if d.Magnitude < 0.05 then
		hrp_.AssemblyLinearVelocity = Vector3.zero
		return
	end
	local pas = math.min(d.Magnitude, h_.WalkSpeed * dt)
	local np = hrp_.Position + d.Unit * pas
	hrp_.CFrame = CFrame.lookAt(np, np + d.Unit)
	hrp_.AssemblyLinearVelocity = d.Unit * h_.WalkSpeed
end

local function pas(m, secondes, cond)
	local n = math.floor(secondes * 60 + 0.5)
	for _ = 1, n do
		MOCK.step(1 / 60)
		avancerMonstre(m, 1 / 60)
		if cond and cond() then
			return true
		end
	end
	return false
end

local mon4, cfg4 = nouvellePartie()
local joueur = Players.LocalPlayer
local hrp4 = mon4.HumanoidRootPart
local devant = hrp4.CFrame.LookVector
local perso = creerSurvivant("Testeur", CFrame.lookAt(hrp4.Position + devant * 30 - Vector3.new(0, 4.128, 0),
	hrp4.Position + devant * 31 - Vector3.new(0, 4.128, 0)), joueur)
MOCK.runScript(SSS.MonstreServeur)
MOCK.runScript(SP.StarterPlayerScripts.MonstreClient)
check(#MOCK.errors == 0, "scripts lancés sans erreur :\n" .. table.concat(MOCK.errors, "\n"))
local vuHurle = pas(mon4, 1.5, function()
	return mon4:GetAttribute("MA_Action") == "roar"
end)
check(vuHurle, "le monstre repère le joueur et hurle")
local clientAnime = false
for _, mo in pairs(MA.moteurs(mon4, "monstre")) do
	if mo.Transform ~= CFrame.identity then
		clientAnime = true
	end
end
check(clientAnime, "le client anime le monstre (Transform écrits)")
local debutPoursuite = hrp4.Position
local attaque = pas(mon4, 12, function()
	return (mon4:GetAttribute("MA_Sequence") or "") ~= ""
end)
check(attaque, "poursuite puis mise à mort (" .. tostring(mon4:GetAttribute("MA_Sequence")) .. ")")
check((hrp4.Position - debutPoursuite).Magnitude > 15, "le monstre s'est déplacé vers le joueur")
check(MOCK.sons.MA_hurlement and MOCK.sons.MA_hurlement > 0, "son du hurlement joué")
check(MOCK.sons.MA_pas_lourd and MOCK.sons.MA_pas_lourd > 0, "bruits de pas pendant la course")
check(mon4.VictimeAncrePart:FindFirstChild("MA_Soudure") ~= nil, "victime soudée sur l'ancre")
check(perso:GetAttribute("MA_EnMiseAMort") == true, "victime marquée")
pas(mon4, 0.4)
check(workspace.CurrentCamera.CameraType == Enum.CameraType.Scriptable, "caméra de la victime scénarisée")
local fini = pas(mon4, 60, function()
	return (mon4:GetAttribute("MA_Sequence") or "") == ""
end)
check(fini, "mise à mort terminée")
check(#MOCK.errors == 0, "aucune erreur pendant la mise à mort :\n" .. table.concat(MOCK.errors, "\n"))

-- chaque mise à mort, lancée par MonstreOutils sur le joueur
local O = require(SS.MonstreOutils)
local seq_trainer_attendu = { devoration = true, trainee = true }
local vueSubjective, distTete
local CLES = { "morsure_cou", "morsure_repetee", "devoration", "attaque_ventre", "trainee", "extraction", "frenesie", "contamination" }
for i, cle in ipairs(CLES) do
	local m, cfg = nouvellePartie()
	local hrpK = m.HumanoidRootPart
	local dv = hrpK.CFrame.LookVector
	local p = creerSurvivant("Testeur", CFrame.lookAt(hrpK.Position + dv * 4.5 - Vector3.new(0, 4.128, 0), hrpK.Position - Vector3.new(0, 4.128, 0)), joueur)
	MOCK.runScript(SSS.MonstreServeur)
	MOCK.runScript(SP.StarterPlayerScripts.MonstreClient)
	O.pause(true)
	local depart = hrpK.Position
	local okL = O.miseAMort(cle, p)
	check(okL, cle .. " : lancée")
	local vuNoir, vuCam, maxDecalques, vuEcran, camLoin = false, false, 0, false, 0
	local ecran = joueur.PlayerGui:FindFirstChild("MonstreEcran")
	local phases = {}
	local sons0 = 0
	for _, n in pairs(MOCK.sons) do
		sons0 += n
	end
	local finie = pas(m, 90, function()
		local ph = m:GetAttribute("MA_Phase")
		if ph and ph ~= "" then
			phases[ph] = true
			local cam = workspace.CurrentCamera
			if cam.CameraType == Enum.CameraType.Scriptable then
				local d = (cam.CFrame.Position - m.HumanoidRootPart.Position).Magnitude
				if d ~= d then
					d = math.huge
				end
				camLoin = math.max(camLoin, d)
			end
			if cam:FindFirstChild("SANG_Ecran") then
				vuEcran = true
			end
			-- vue subjective (morsure au cou, avant la morsure) : la caméra, à la tête de la victime, regarde le monstre
			local tph = workspace:GetServerTimeNow() - (m:GetAttribute("MA_PhaseDebut") or 0)
			if cle == "morsure_cou" and tph > 0.5 and tph < 0.9 and cam.CameraType == Enum.CameraType.Scriptable then
				local tete = m:FindFirstChild("MON_Head_1", true)
				local d = (tete.Position - cam.CFrame.Position).Unit
				vueSubjective = math.min(vueSubjective or 1, cam.CFrame.LookVector:Dot(d))
				distTete = math.max(distTete or 0, (cam.CFrame.Position - p.Head.Position).Magnitude)
			end
		end
		if ecran and ecran.Noir.BackgroundTransparency < 0.01 then
			vuNoir = true
		end
		if workspace.CurrentCamera.CameraType == Enum.CameraType.Scriptable then
			vuCam = true
		end
		local loc = workspace:FindFirstChild("MonstreEffetsLocaux")
		if loc then
			maxDecalques = math.max(maxDecalques, #loc:GetChildren())
		end
		return (m:GetAttribute("MA_Sequence") or "") == "" and next(phases) ~= nil
	end)
	check(finie, cle .. " : terminée")
	-- décalques : repère direct, posés à plat ; traînée allongée dans le sens du déplacement
	local loc = workspace:FindFirstChild("MonstreEffetsLocaux")
	local deplace = Vector3.new(m.HumanoidRootPart.Position.X - depart.X, 0, m.HumanoidRootPart.Position.Z - depart.Z)
	local nTrace, alignes, direct = 0, 0, true
	for _, dcl in ipairs(loc and loc:GetChildren() or {}) do
		local c = dcl.CFrame
		if not near(c.XVector:Cross(c.YVector), c.ZVector, 1e-6) or not near(c.YVector, Vector3.new(0, 1, 0), 1e-6) then
			direct = false
		end
		if dcl.Name == "SANG_Trainee" and deplace.Magnitude > 1 then
			nTrace += 1
			if math.abs(c.XVector:Dot(deplace.Unit)) > 0.8 then
				alignes += 1
			end
		end
	end
	check(direct, cle .. " : décalques à plat, repère direct")
	if seq_trainer_attendu and seq_trainer_attendu[cle] then
		check(nTrace > 5 and alignes >= nTrace * 0.8, string.format("%s : traînée de sang (%d décalques, %d alignés)", cle, nTrace, alignes))
	end
	local nph = 0
	for _ in pairs(phases) do
		nph += 1
	end
	local seq
	for _, s in ipairs(D.sequences) do
		if s.key == cle then
			seq = s
		end
	end
	check(nph == #seq.phases, string.format("%s : %d phase(s) jouée(s) sur %d", cle, nph, #seq.phases))
	check(vuCam, cle .. " : caméra scénarisée")
	if cle == "morsure_cou" then
		check(vueSubjective and vueSubjective > 0.9 and distTete < 1.5,
			string.format("morsure_cou : vue subjective tournée vers le monstre (%.2f, %.2f stud de la tête)", vueSubjective or -1, distTete or -1))
	end
	check(camLoin < 40, string.format("%s : caméra près de la scène (au plus %.1f studs du monstre)", cle, camLoin))
	local sons1 = 0
	for _, n in pairs(MOCK.sons) do
		sons1 += n
	end
	check(sons1 - sons0 >= 3, string.format("%s : sons joués (%d)", cle, sons1 - sons0))
	if cle == "morsure_cou" or cle == "morsure_repetee" or cle == "frenesie" then
		check(vuEcran, cle .. " : sang sur l'écran")
	end
	check(maxDecalques > 0, cle .. " : sang au sol (" .. maxDecalques .. " décalque(s))")
	if cle == "morsure_cou" or cle == "extraction" then
		check(vuNoir, cle .. " : coupure au noir")
	end
	if seq.trainer then
		check((hrpK.Position - depart).Magnitude > 10, string.format("%s : traînée (%.1f studs)", cle, (hrpK.Position - depart).Magnitude))
	end
	local h_ = p:FindFirstChildOfClass("Humanoid")
	if seq.fin == "mort" then
		check(h_.Health == 0, cle .. " : victime tuée")
		local corps = workspace:FindFirstChild("Cadavre_Testeur")
		check(corps ~= nil, cle .. " : cadavre posé")
		pas(m, 0.5)
		local cam = workspace.CurrentCamera
		local torseC = corps and corps:FindFirstChild("Torso")
		check(torseC and cam.CameraType == Enum.CameraType.Scriptable
			and (cam.CFrame.Position - torseC.Position).Magnitude < 14
			and cam.CFrame.LookVector:Dot((torseC.Position - cam.CFrame.Position).Unit) > 0.95,
			cle .. " : caméra sur le cadavre")
		if corps then
			check(corps:FindFirstChild("Survivor_Torso") ~= nil and corps:FindFirstChild("Torso_Sternum") == nil,
				cle .. " : cadavre avec la tenue, sans l'anatomie")
			local tor = corps:FindFirstChild("Torso")
			check(tor and tor.Anchored and tor.Position.Y < 4.5, cle .. " : cadavre au sol")
		end
	else
		check(h_.Health > 0, cle .. " : victime vivante")
		check(p:GetAttribute("MA_Infection") ~= nil and p:GetAttribute("MA_Releve") ~= nil, cle .. " : infection et relevé")
		check(m.VictimeAncrePart:FindFirstChild("MA_Soudure") == nil, cle .. " : victime relâchée")
		check(p.HumanoidRootPart.CanCollide == true and not h_.PlatformStand, cle .. " : physique rendue")
		pas(m, 3)
		local cc = Lighting:FindFirstChild("MonstreInfection")
		check(cc and cc.Enabled, cle .. " : symptômes de l'infection (écran)")
		h_.WalkSpeed = 16
		pas(m, 0.2)
		check(h_.WalkSpeed < 16, string.format("%s : vitesse réduite (%.1f)", cle, h_.WalkSpeed))
		check(workspace.CurrentCamera.CameraType == Enum.CameraType.Custom, cle .. " : caméra rendue au joueur")
	end
	check(m:GetAttribute("MA_Sequence") == "" and m.MA_Victime.Value == nil and not m.HumanoidRootPart.Anchored,
		cle .. " : monstre libéré")
	check(#MOCK.errors == 0, cle .. " : aucune erreur\n" .. table.concat(MOCK.errors, "\n"))
end

MOCK.rawPrint(string.format("\n%d vérifications, %d échec(s)", nOk + nKo, nKo))
if nKo > 0 then
	error("tests en échec")
end
