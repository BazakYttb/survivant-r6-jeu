--[[
	MonstreServeur (Script, ServerScriptService) : intelligence du monstre et déroulement des mises à mort.

	Le serveur décide (patrouille, poursuite, choix et déroulement des mises à mort, cadavre, infection) et publie l'état
	dans des attributs du modèle du monstre ; chaque client anime le monstre et la victime à partir de ces attributs
	(MonstreClient), ce qui garde les animations synchronisées sans rien publier sur Roblox.
		MA_Action / MA_ActionDebut : geste en cours (hurlement, flairer, attaque) et heure de début (horloge du serveur)
		MA_Sequence : mise à mort en cours (clé de MonstreDonnees.sequences) ; MA_Phase / MA_PhaseDebut : clip en cours
		MA_Graine : graine du hasard partagé (éclaboussures) ; ObjectValue MA_Victime : la victime
	Les victimes sont les personnages des joueurs et les modèles étiquetés CONFIG.ETIQUETTE_VICTIME (essais).
]]

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local PathfindingService = game:GetService("PathfindingService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local dossier = ReplicatedStorage:WaitForChild("Monstre")
local CONFIG = require(dossier:WaitForChild("MonstreConfig"))
local DATA = require(dossier:WaitForChild("MonstreDonnees"))
local MA = require(dossier:WaitForChild("MonstreAnim")).init(DATA)

local SEQ = {}
for _, s in ipairs(DATA.sequences) do
	SEQ[s.key] = s
end

local AVANCE = 0.12 -- les clients commencent une phase un peu après l'annonce (latence)
local HRP_Y = DATA.rig.hrp.center[2] -- hauteur du centre du HumanoidRootPart au-dessus du sol

local function maintenant()
	return workspace:GetServerTimeNow()
end

local function log(...)
	if CONFIG.DEBUG then
		print("[Monstre]", ...)
	end
end

local function plat(v)
	return Vector3.new(v.X, 0, v.Z)
end

local function attendreJusqua(t)
	while maintenant() < t do
		task.wait(math.min(0.1, math.max(t - maintenant(), 0.01)))
	end
end

------------------------------------------------------------------------------------------------------------
-- victimes
------------------------------------------------------------------------------------------------------------
local function humanoideVivant(modele)
	local h = modele and modele:FindFirstChildOfClass("Humanoid")
	return h and h.Health > 0 and modele:FindFirstChild("HumanoidRootPart") and h or nil
end

local function victimesPossibles()
	local out = {}
	for _, p in ipairs(Players:GetPlayers()) do
		local c = p.Character
		if c and humanoideVivant(c) and not c:GetAttribute("MA_EnMiseAMort") and not c:GetAttribute("MA_Ignore") then
			table.insert(out, c)
		end
	end
	for _, m in ipairs(CollectionService:GetTagged(CONFIG.ETIQUETTE_VICTIME)) do
		if m:IsA("Model") and humanoideVivant(m) and not m:GetAttribute("MA_EnMiseAMort") then
			table.insert(out, m)
		end
	end
	return out
end

------------------------------------------------------------------------------------------------------------
-- le monstre
------------------------------------------------------------------------------------------------------------
local Monstre = {}
Monstre.__index = Monstre
local MONSTRES = {}

function Monstre.new(modele)
	local self = setmetatable({}, Monstre)
	self.modele = modele
	self.hum = modele:FindFirstChildOfClass("Humanoid")
	self.hrp = modele:FindFirstChild("HumanoidRootPart")
	self.ancrePart = modele:FindFirstChild("VictimeAncrePart", true)
	self.ancreMoteur = modele:FindFirstChild("VictimeAncre", true)
	assert(self.hum and self.hrp and self.ancrePart and self.ancreMoteur, "modèle du monstre incomplet : relancez l'installateur")
	self.depart = self.hrp.Position
	self.etat = "patrouille"
	self.occupe = false
	self.reposJusqua = 0
	self.derniereVue = 0
	self.dernierHurlement = -100
	self.victimeVal = modele:FindFirstChild("MA_Victime") or Instance.new("ObjectValue")
	self.victimeVal.Name = "MA_Victime"
	self.victimeVal.Value = nil
	self.victimeVal.Parent = modele
	for nom, v in pairs({ MA_Action = "", MA_ActionDebut = 0, MA_Sequence = "", MA_Phase = "", MA_PhaseDebut = 0, MA_Graine = 0 }) do
		modele:SetAttribute(nom, v)
	end
	self.hum.MaxHealth = CONFIG.VIE
	self.hum.Health = CONFIG.VIE
	self.hum.WalkSpeed = CONFIG.VITESSE.marche
	self.hrp.Anchored = false
	pcall(function()
		self.hrp:SetNetworkOwner(nil)
	end)
	self.params = RaycastParams.new()
	self.params.FilterType = Enum.RaycastFilterType.Exclude
	self.params.FilterDescendantsInstances = { modele }
	return self
end

-- geste (clip non bouclé du monstre) : attributs pour les clients, attente de la fin
function Monstre:geste(cle, bloquant)
	local c = DATA.monstre[cle]
	if not c then
		return
	end
	local debut = maintenant() + AVANCE
	self.modele:SetAttribute("MA_ActionDebut", debut)
	self.modele:SetAttribute("MA_Action", cle)
	if bloquant ~= false then
		self.hum:MoveTo(self.hrp.Position)
		attendreJusqua(debut + c.length)
		if self.modele:GetAttribute("MA_Action") == cle then
			self.modele:SetAttribute("MA_Action", "")
		end
	end
end

function Monstre:yeux()
	return self.hrp.Position + Vector3.new(0, 2.8, 0)
end

function Monstre:voit(c)
	local root = c:FindFirstChild("HumanoidRootPart")
	if not root then
		return false
	end
	local o = self:yeux()
	local d = root.Position - o
	if d.Magnitude > CONFIG.DETECTION.vue then
		return false
	end
	local f = plat(d)
	if f.Magnitude > 2 then
		local cosA = self.hrp.CFrame.LookVector:Dot(f.Unit)
		if cosA < math.cos(math.rad(CONFIG.DETECTION.angle_vue / 2)) then
			return false
		end
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { self.modele, c }
	return workspace:Raycast(o, d, params) == nil
end

function Monstre:entend(c)
	local root = c:FindFirstChild("HumanoidRootPart")
	if not root then
		return false
	end
	local dist = (root.Position - self.hrp.Position).Magnitude
	return dist < CONFIG.DETECTION.ouie and plat(root.AssemblyLinearVelocity).Magnitude > 10
end

function Monstre:chercherCible()
	local meilleure, dmin = nil, math.huge
	for _, c in ipairs(victimesPossibles()) do
		local root = c.HumanoidRootPart
		local dist = (root.Position - self.hrp.Position).Magnitude
		if dist < dmin and (self:voit(c) or self:entend(c) or (c == self.cible and dist < 12)) then
			meilleure, dmin = c, dist
		end
	end
	return meilleure, dmin
end

-- se déplace vers pos (chemin recalculé quand le but bouge)
function Monstre:allerVers(pos, vitesse)
	self.hum.WalkSpeed = vitesse
	local t = maintenant()
	if not self.chemin or t - self.cheminT > 0.8 or (pos - self.cheminBut).Magnitude > 4 then
		self.cheminT, self.cheminBut = t, pos
		local path = PathfindingService:CreatePath({ AgentRadius = 2.4, AgentHeight = 8, AgentCanJump = true,
			WaypointSpacing = 4 })
		local ok = pcall(function()
			path:ComputeAsync(self.hrp.Position, pos)
		end)
		if ok and path.Status == Enum.PathStatus.Success then
			self.chemin = path:GetWaypoints()
			self.wi = math.min(2, #self.chemin)
		else
			self.chemin = { { Position = pos, Action = Enum.PathWaypointAction.Walk } }
			self.wi = 1
		end
	end
	local wp = self.chemin[self.wi]
	while wp and plat(wp.Position - self.hrp.Position).Magnitude < 3 and self.wi < #self.chemin do
		self.wi += 1
		wp = self.chemin[self.wi]
	end
	if wp then
		if wp.Action == Enum.PathWaypointAction.Jump then
			self.hum.Jump = true
		end
		self.hum:MoveTo(wp.Position)
	end
end

function Monstre:arret()
	self.chemin = nil
	self.hum:MoveTo(self.hrp.Position)
end

function Monstre:pointPatrouille()
	local tags = CollectionService:GetTagged(CONFIG.PATROUILLE.etiquette)
	if #tags > 0 then
		local p = tags[math.random(1, #tags)]
		if p:IsA("BasePart") then
			return p.Position
		end
	end
	local a = math.random() * math.pi * 2
	local r = CONFIG.PATROUILLE.rayon * (0.3 + 0.7 * math.random())
	return self.depart + Vector3.new(math.cos(a) * r, 0, math.sin(a) * r)
end

function Monstre:choisirMiseAMort()
	local total, liste = 0, {}
	for cle, poids in pairs(CONFIG.MISES_A_MORT) do
		if SEQ[cle] and poids > 0 and cle ~= self.derniereMiseAMort then
			total += poids
			table.insert(liste, { cle, poids })
		end
	end
	if total <= 0 then
		return self.derniereMiseAMort
	end
	table.sort(liste, function(a, b)
		return a[1] < b[1]
	end)
	local r = math.random() * total
	for _, e in ipairs(liste) do
		r -= e[2]
		if r <= 0 then
			return e[1]
		end
	end
	return liste[#liste][1]
end

function Monstre:penser()
	local cible, dist = self:chercherCible()
	local t = maintenant()
	if cible then
		if cible ~= self.cible then
			self.cible = cible
			if self.etat ~= "chasse" and CONFIG.DETECTION.hurle_a_la_vue and t - self.dernierHurlement > 12 then
				self.dernierHurlement = t
				self.hrp.CFrame = CFrame.lookAt(self.hrp.Position, self.hrp.Position + plat(cible.HumanoidRootPart.Position - self.hrp.Position))
				self:geste("roar")
			end
		end
		self.etat = "chasse"
		self.derniereVue = t
		self.dernierePosition = cible.HumanoidRootPart.Position
		if dist <= CONFIG.PORTEE_ATTAQUE and maintenant() > self.reposJusqua then
			self:miseAMort(cible, self:choisirMiseAMort())
			return
		end
		self:allerVers(cible.HumanoidRootPart.Position, CONFIG.VITESSE.course)
		return
	end
	if self.etat == "chasse" then
		if t - self.derniereVue < CONFIG.DETECTION.oubli and self.dernierePosition then
			self:allerVers(self.dernierePosition, CONFIG.VITESSE.course)
			if plat(self.dernierePosition - self.hrp.Position).Magnitude < 4 then
				self.etat = "recherche"
			end
			return
		end
		self.etat = "recherche"
	end
	if self.etat == "recherche" then
		self.cible = nil
		self:arret()
		self:geste("sniff")
		self.etat = "patrouille"
		self.but = nil
		return
	end
	-- patrouille
	if not self.but or plat(self.but - self.hrp.Position).Magnitude < 4 or t > (self.butLimite or 0) then
		if self.but then
			self:arret()
			if math.random() < CONFIG.PATROUILLE.flairer then
				self:geste("sniff")
			else
				task.wait(CONFIG.PATROUILLE.pause_min + math.random() * (CONFIG.PATROUILLE.pause_max - CONFIG.PATROUILLE.pause_min))
			end
		end
		self.but = self:pointPatrouille()
		self.butLimite = t + 25
	end
	self:allerVers(self.but, CONFIG.VITESSE.marche)
end

function Monstre:boucle()
	while self.modele.Parent do
		if not self.occupe and not self.enPause then
			local ok, err = pcall(self.penser, self)
			if not ok then
				warn("[Monstre] " .. tostring(err))
				task.wait(1)
			end
		end
		task.wait(0.15)
	end
end

------------------------------------------------------------------------------------------------------------
-- mises à mort
------------------------------------------------------------------------------------------------------------

-- place le monstre face à la victime, la victime exactement sur l'ancre (position de repos de VictimeAncre)
function Monstre:placer(victime)
	local vroot = victime.HumanoidRootPart
	local d = plat(vroot.Position - self.hrp.Position)
	if d.Magnitude < 0.1 then
		d = plat(self.hrp.CFrame.LookVector)
	end
	d = d.Unit
	local rel = self.ancreMoteur.C0 * self.ancreMoteur.C1:Inverse() -- ancre au repos, repère du HumanoidRootPart
	local cible = CFrame.lookAt(Vector3.zero, d)
	local P = vroot.Position - cible:VectorToWorldSpace(rel.Position)
	local cf = CFrame.lookAt(P, P + d)
	self.hrp.Anchored = true
	local depart = self.hrp.CFrame
	for i = 1, 6 do
		self.hrp.CFrame = depart:Lerp(cf, i / 6)
		task.wait()
	end
	self.hrp.CFrame = cf
	return cf * rel
end

local function sauverEtat(victime)
	local st = { parties = {}, hum = {} }
	local h = victime:FindFirstChildOfClass("Humanoid")
	st.hum = { PlatformStand = h.PlatformStand, AutoRotate = h.AutoRotate, BreakJointsOnDeath = h.BreakJointsOnDeath }
	for _, p in ipairs(victime:GetDescendants()) do
		if p:IsA("BasePart") then
			st.parties[p] = { CanCollide = p.CanCollide, Massless = p.Massless, Anchored = p.Anchored }
			p.CanCollide = false
			p.Massless = true
			p.Anchored = false
		end
	end
	h.PlatformStand = true
	h.AutoRotate = false
	h.BreakJointsOnDeath = false
	return st
end

local function restaurerEtat(victime, st)
	if not st then
		return
	end
	for p, v in pairs(st.parties) do
		if p.Parent then
			p.CanCollide = v.CanCollide
			p.Massless = v.Massless
			p.Anchored = v.Anchored
		end
	end
	local h = victime:FindFirstChildOfClass("Humanoid")
	if h then
		h.PlatformStand = st.hum.PlatformStand
		h.AutoRotate = st.hum.AutoRotate
		h.BreakJointsOnDeath = st.hum.BreakJointsOnDeath
	end
end

local function joueurDe(victime)
	return Players:GetPlayerFromCharacter(victime)
end

-- destination d'une traînée : partie étiquetée la plus proche, sinon loin des autres joueurs
function Monstre:destination(etiquette, victime)
	local pos = self.hrp.Position
	local best, dmin = nil, CONFIG.TRAINER.distance_max
	for _, p in ipairs(CollectionService:GetTagged(etiquette)) do
		if p:IsA("BasePart") then
			local d = (p.Position - pos).Magnitude
			if d < dmin and d > 6 then
				best, dmin = p.Position, d
			end
		end
	end
	if best then
		return best
	end
	local fuite = Vector3.zero
	for _, pl in ipairs(Players:GetPlayers()) do
		local c = pl.Character
		if c and c ~= victime and c:FindFirstChild("HumanoidRootPart") then
			local d = plat(pos - c.HumanoidRootPart.Position)
			if d.Magnitude > 0.1 then
				fuite += d.Unit / math.max(d.Magnitude, 4)
			end
		end
	end
	if fuite.Magnitude < 1e-3 then
		fuite = -plat(self.hrp.CFrame.LookVector) -- dans le dos du monstre (son corps regarde par là en traînant)
	end
	return pos + fuite.Unit * CONFIG.TRAINER.distance_sans_cible
end

-- traîne la victime (le HumanoidRootPart, ancré, recule : le corps est tourné de 180 degrés dans le clip)
function Monstre:trainer(victime, but, vitesse, distanceMax)
	local pos = self.hrp.Position
	local points = { but }
	local path = PathfindingService:CreatePath({ AgentRadius = 2.4, AgentHeight = 8, AgentCanJump = false, WaypointSpacing = 4 })
	local ok = pcall(function()
		path:ComputeAsync(pos, but)
	end)
	if ok and path.Status == Enum.PathStatus.Success then
		points = {}
		for i, wp in ipairs(path:GetWaypoints()) do
			if i > 1 then
				table.insert(points, wp.Position)
			end
		end
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { self.modele, victime }
	local dir = -plat(self.hrp.CFrame.LookVector).Unit
	local parcouru, i = 0, 1
	while parcouru < distanceMax and points[i] and victime.Parent do
		local dt = math.min(task.wait(), 0.1)
		local cur = self.hrp.Position
		local vise = plat(points[i] - cur)
		if vise.Magnitude < 1.5 then
			i += 1
			continue
		end
		-- tourne progressivement vers la direction du chemin (au plus 120 degrés par seconde)
		local want = vise.Unit
		local ang = math.acos(math.clamp(dir:Dot(want), -1, 1))
		local maxA = math.rad(120) * dt
		if ang > maxA then
			local axe = dir:Cross(want).Y >= 0 and 1 or -1
			dir = (CFrame.Angles(0, axe * maxA, 0) * CFrame.new(dir)).Position.Unit
		else
			dir = want
		end
		local pas = math.min(vitesse * dt, vise.Magnitude)
		local np = cur + dir * pas
		local sol = workspace:Raycast(np + Vector3.new(0, 4, 0), Vector3.new(0, -HRP_Y - 10, 0), params)
		if sol then
			np = Vector3.new(np.X, sol.Position.Y + HRP_Y, np.Z)
		end
		local mur = workspace:Raycast(cur + Vector3.new(0, -HRP_Y + 1.5, 0), dir * 3, params)
		if mur and mur.Instance.CanCollide then
			break
		end
		self.hrp.CFrame = CFrame.lookAt(np, np - dir)
		parcouru += pas
	end
	return parcouru
end

-- cadavre posé : copies ancrées des parties visibles de la victime, à la pose finale de la mise à mort
local function creerCadavre(monstre, victime, cle, t)
	local ancreCF = MA.ancre(monstre.modele, cle, t)
	if not ancreCF then
		return nil
	end
	local pose = MA.pose("victime", cle, t)
	local cfs = MA.cinematique(victime, "victime", pose, ancreCF)
	-- parties soudées (tenue, anatomie) : même décalage que sur le serveur par rapport à leur pièce du rig
	local voisins = {}
	local function lier(a, b)
		if a and b then
			voisins[a] = voisins[a] or {}
			voisins[b] = voisins[b] or {}
			table.insert(voisins[a], b)
			table.insert(voisins[b], a)
		end
	end
	for _, d in ipairs(victime:GetDescendants()) do
		if d:IsA("WeldConstraint") or (d:IsA("JointInstance") and not d:IsA("Motor6D")) then
			lier(d.Part0, d.Part1)
		end
	end
	local rigParts = {} -- pièces reliées par des Motor6D (cinématique directe) et la racine
	for _, d in ipairs(victime:GetDescendants()) do
		if d:IsA("Motor6D") then
			for _, x in ipairs({ d.Part0, d.Part1 }) do
				if x and cfs[x] then
					rigParts[x] = true
				end
			end
		elseif d.Name == "HumanoidRootPart" and d:IsA("BasePart") and cfs[d] then
			rigParts[d] = true
		end
	end
	local finale = {}
	for p, _ in pairs(rigParts) do
		finale[p] = cfs[p]
	end
	-- parcours en largeur depuis les pièces du rig à travers les soudures
	local file = {}
	for p, _ in pairs(rigParts) do
		table.insert(file, p)
	end
	local k = 1
	while file[k] do
		local a = file[k]
		k += 1
		for _, b in ipairs(voisins[a] or {}) do
			if not finale[b] then
				finale[b] = finale[a] * a.CFrame:ToObjectSpace(b.CFrame)
				table.insert(file, b)
			end
		end
	end
	victime.Archivable = true
	local corps = Instance.new("Model")
	corps.Name = "Cadavre_" .. victime.Name
	for p, cf in pairs(finale) do
		local anatomie = p:FindFirstAncestor("Anatomie")
		if p.Name ~= "HumanoidRootPart" and p.Transparency < 1 and not anatomie then
			p.Archivable = true
			local ok, c = pcall(function()
				return p:Clone()
			end)
			if ok and c then
				for _, d in ipairs(c:GetDescendants()) do
					if d:IsA("JointInstance") or d:IsA("WeldConstraint") or d:IsA("BaseScript") or d:IsA("Attachment") then
						d:Destroy()
					end
				end
				c.Anchored = true
				c.CanCollide = false
				c.CanTouch = false
				c.CFrame = cf
				c.Parent = corps
			end
		end
	end
	corps:SetAttribute("MA_Cadavre", true)
	corps.Parent = workspace
	if CONFIG.SANG.duree_cadavre and CONFIG.SANG.duree_cadavre > 0 then
		task.delay(CONFIG.SANG.duree_cadavre, function()
			if corps.Parent then
				corps:Destroy()
			end
		end)
	end
	return corps
end

local function cacherEtTuer(victime)
	for _, d in ipairs(victime:GetDescendants()) do
		if d:IsA("BasePart") or d:IsA("Decal") then
			d.Transparency = 1
		end
	end
	local h = victime:FindFirstChildOfClass("Humanoid")
	if h then
		h.Health = 0
	end
	if not joueurDe(victime) then
		-- victime d'essai : retirée (les outils de test peuvent en recréer une)
		task.delay(2, function()
			if victime.Parent then
				victime:Destroy()
			end
		end)
	end
end

-- infection : la victime est relâchée vivante, symptômes après CONFIG.INFECTION.delai
local function infecter(victime)
	local debut = maintenant() + CONFIG.INFECTION.delai
	victime:SetAttribute("MA_Infection", debut)
	local h = victime:FindFirstChildOfClass("Humanoid")
	local couleurs = {}
	for _, p in ipairs(victime:GetDescendants()) do
		if p:IsA("MeshPart") and p.Transparency < 1 and not p:FindFirstAncestor("Anatomie") then
			couleurs[p] = p.Color
		end
	end
	task.spawn(function()
		attendreJusqua(debut)
		local I = CONFIG.INFECTION
		while victime.Parent and h and h.Health > 0 and victime:GetAttribute("MA_Infection") == debut do
			local k = math.clamp((maintenant() - debut) / I.duree, 0, 1)
			for p, c0 in pairs(couleurs) do
				if p.Parent then
					p.Color = c0:Lerp(Color3.new(c0.R * I.teinte_peau.R, c0.G * I.teinte_peau.G, c0.B * I.teinte_peau.B), k)
				end
			end
			if I.degats_par_seconde > 0 then
				h:TakeDamage(I.degats_par_seconde * 0.5)
			end
			if k >= 1 and I.issue == "mort" then
				h.Health = 0
				break
			end
			task.wait(0.5)
		end
	end)
end

function Monstre:liberer(victime, st, cle, t)
	local w = self.ancrePart:FindFirstChild("MA_Soudure")
	if w then
		w:Destroy()
	end
	if victime and victime.Parent then
		local vroot = victime:FindFirstChild("HumanoidRootPart")
		if vroot and cle then
			local cf = MA.ancre(self.modele, cle, t)
			if cf then
				local look = plat(cf.LookVector)
				look = look.Magnitude > 0.1 and look.Unit or Vector3.new(0, 0, -1)
				vroot.CFrame = CFrame.lookAt(cf.Position, cf.Position + look)
			end
		end
		restaurerEtat(victime, st)
		victime:SetAttribute("MA_EnMiseAMort", nil)
		local pl = joueurDe(victime)
		if pl and vroot then
			pcall(function()
				vroot:SetNetworkOwner(pl)
			end)
		end
	end
end

function Monstre:finirSequence()
	self.modele:SetAttribute("MA_Sequence", "")
	self.modele:SetAttribute("MA_Phase", "")
	self.victimeVal.Value = nil
	self.hrp.Anchored = false
	self.hum.AutoRotate = true
	self.hum.WalkSpeed = CONFIG.VITESSE.marche
	pcall(function()
		self.hrp:SetNetworkOwner(nil)
	end)
end

function Monstre:miseAMort(victime, cle)
	local seq = SEQ[cle]
	if not seq or self.occupe then
		return false
	end
	self.occupe = true
	self.derniereMiseAMort = cle
	log("mise à mort", cle, victime.Name)
	local st
	local ok, err = pcall(function()
		self:arret()
		self.hum.AutoRotate = false
		self.modele:SetAttribute("MA_Action", "")
		local ancreCF = self:placer(victime)
		victime:SetAttribute("MA_EnMiseAMort", true)
		st = sauverEtat(victime)
		local vroot = victime.HumanoidRootPart
		pcall(function()
			vroot:SetNetworkOwner(nil)
		end)
		vroot.CFrame = ancreCF
		local w = Instance.new("Weld")
		w.Name = "MA_Soudure"
		w.Part0 = self.ancrePart
		w.Part1 = vroot
		w.C0 = CFrame.identity
		w.C1 = CFrame.identity
		w.Parent = self.ancrePart
		self.victimeVal.Value = victime
		self.modele:SetAttribute("MA_Graine", math.random(1, 1000000))
		self.modele:SetAttribute("MA_Sequence", cle)
		local derniere, tFin = nil, 0
		for _, ph in ipairs(seq.phases) do
			local c = DATA.monstre[ph.clip]
			local debut = maintenant() + AVANCE
			self.modele:SetAttribute("MA_PhaseDebut", debut)
			self.modele:SetAttribute("MA_Phase", ph.clip)
			derniere = ph.clip
			if ph.trainer then
				local trn = seq.trainer or {}
				local etiquette = trn.vers == "sortie" and CONFIG.TRAINER.etiquette_sortie or CONFIG.TRAINER.etiquette_taniere
				local vitesse = trn.vitesse or CONFIG.VITESSE.trainer
				local but = self:destination(etiquette, victime)
				attendreJusqua(debut)
				self:trainer(victime, but, vitesse, math.min(trn.distance or CONFIG.TRAINER.distance_max, CONFIG.TRAINER.distance_max))
				tFin = (maintenant() - debut)
			else
				local duree = c.length
				if ph.repas then
					duree = CONFIG.TRAINER.duree_repas
				end
				attendreJusqua(debut + duree)
				tFin = duree
			end
			if not victime.Parent then
				break
			end
		end
		if victime.Parent then
			if seq.fin == "infection" then
				self:liberer(victime, st, derniere, tFin)
				st = nil
				victime:SetAttribute("MA_Releve", maintenant() + 0.05) -- les clients jouent « se relever »
				infecter(victime)
			else
				local tPose = DATA.monstre[derniere].loop and MA.clipTime(MA.clip("monstre", derniere), tFin) or tFin
				local corps = creerCadavre(self, victime, derniere, tPose)
				-- le personnage (invisible, mort) reste sur place ; le cadavre posé le remplace
				local w = self.ancrePart:FindFirstChild("MA_Soudure")
				if w then
					w:Destroy()
				end
				local vroot = victime:FindFirstChild("HumanoidRootPart")
				if vroot then
					vroot.Anchored = true
				end
				st = nil
				if corps then
					victime:SetAttribute("MA_Cadavre", corps.Name)
				end
				cacherEtTuer(victime)
			end
		end
	end)
	if not ok then
		warn("[Monstre] mise à mort interrompue : " .. tostring(err))
		pcall(function()
			self:liberer(victime, st, nil, nil)
		end)
	end
	self:finirSequence()
	self.reposJusqua = maintenant() + CONFIG.REPOS_APRES_MISE_A_MORT
	self.cible = nil
	self.etat = "patrouille"
	self.but = nil
	if ok and self.modele.Parent then
		pcall(self.geste, self, "roar") -- hurlement de victoire avant de reprendre la patrouille
	end
	self.occupe = false
	return ok
end

------------------------------------------------------------------------------------------------------------
-- démarrage
------------------------------------------------------------------------------------------------------------
local function ajouter(modele)
	if MONSTRES[modele] or not modele:IsA("Model") then
		return
	end
	local ok, m = pcall(Monstre.new, modele)
	if not ok then
		warn("[Monstre] " .. tostring(m))
		return
	end
	MONSTRES[modele] = m
	task.spawn(function()
		m:boucle()
	end)
end

for _, modele in ipairs(CollectionService:GetTagged("Monstre")) do
	ajouter(modele)
end
CollectionService:GetInstanceAddedSignal("Monstre"):Connect(ajouter)
CollectionService:GetInstanceRemovedSignal("Monstre"):Connect(function(modele)
	MONSTRES[modele] = nil
end)

-- accès pour MonstreOutils (essais depuis la barre de commande pendant le test)
local api = Instance.new("BindableFunction")
api.Name = "MonstreAPI"
api.OnInvoke = function(action, ...)
	local args = { ... }
	local modele = args[1]
	local m = modele and MONSTRES[modele]
	if not m then
		for _, x in pairs(MONSTRES) do
			m = x
			break
		end
	end
	if not m then
		return false, "aucun monstre"
	end
	if action == "miseAMort" then
		return m:miseAMort(args[2], args[3])
	elseif action == "geste" then
		task.spawn(m.geste, m, args[2])
		return true
	elseif action == "etat" then
		return { etat = m.etat, occupe = m.occupe, cible = m.cible and m.cible.Name or "" }
	elseif action == "pause" then
		m.enPause = args[2] and true or false
		if m.enPause and not m.occupe then
			m:arret()
		end
		return true
	end
	return false, "action inconnue"
end
api.Parent = script

log("prêt :", #CollectionService:GetTagged("Monstre"), "monstre(s)")
