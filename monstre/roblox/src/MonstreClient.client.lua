--[[
	MonstreClient (LocalScript, StarterPlayer.StarterPlayerScripts) : tout ce qui se voit et s'entend.

	- Anime chaque monstre (étiquette « Monstre ») et sa victime à partir des attributs posés par MonstreServeur :
	  déplacement (repos / marche / course selon la vitesse, saut, chute, atterrissage), gestes, phases de mise à mort
	  (synchronisées sur l'horloge du serveur). Les Motor6D.Transform sont écrits après l'Animator.
	- Marqueurs des clips : sons, sang (giclées, éclaboussures et flaques au sol, traînée), tremblements, silence.
	- Pour la victime : caméra scénarisée (plans, coupures au noir, sang sur l'écran), commandes coupées.
	- Infection (mise à mort « contamination ») : symptômes progressifs sur le joueur infecté.
]]

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Lighting = game:GetService("Lighting")
local SoundService = game:GetService("SoundService")
local Debris = game:GetService("Debris")

local joueur = Players.LocalPlayer
local dossier = ReplicatedStorage:WaitForChild("Monstre")
local CONFIG = require(dossier:WaitForChild("MonstreConfig"))
local DATA = require(dossier:WaitForChild("MonstreDonnees"))
local MA = require(dossier:WaitForChild("MonstreAnim")).init(DATA)
local EFFETS = dossier:FindFirstChild("Effets")

local function maintenant()
	return workspace:GetServerTimeNow()
end

local function plat(v)
	return Vector3.new(v.X, 0, v.Z)
end

local locaux = Instance.new("Folder")
locaux.Name = "MonstreEffetsLocaux"
locaux.Parent = workspace

------------------------------------------------------------------------------------------------------------
-- sons
------------------------------------------------------------------------------------------------------------
local function jouerSon(nom, parent, volume, vitesse)
	local id = CONFIG.SONS[nom]
	if type(id) ~= "string" or id == "" then
		return nil
	end
	local s = Instance.new("Sound")
	s.Name = "MA_" .. nom
	s.SoundId = id
	s.Volume = (volume or 1) * (CONFIG.SONS.volume or 1)
	s.PlaybackSpeed = vitesse or 1
	s.RollOffMinDistance = 10
	s.RollOffMaxDistance = 150
	s.Parent = parent or SoundService
	s:Play()
	s.Ended:Connect(function()
		s:Destroy()
	end)
	Debris:AddItem(s, 20)
	return s
end

-- silence : tous les sons coupés pendant `duree` secondes
local silenceJusqua = 0
local function silence(duree)
	local fin = os.clock() + duree
	if fin <= silenceJusqua then
		return
	end
	silenceJusqua = fin
	local coupes = {}
	for _, racine in ipairs({ workspace, SoundService }) do
		for _, s in ipairs(racine:GetDescendants()) do
			if s:IsA("Sound") and s.Volume > 0 then
				coupes[s] = s.Volume
				s.Volume = 0
			end
		end
	end
	task.delay(duree, function()
		if os.clock() + 0.05 < silenceJusqua then
			return
		end
		for s, v in pairs(coupes) do
			if s.Parent then
				s.Volume = v
			end
		end
	end)
end

------------------------------------------------------------------------------------------------------------
-- sang
------------------------------------------------------------------------------------------------------------
local exclusRayon = { locaux }

local function sousLePoint(pos, exclus)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = exclus
	return workspace:Raycast(pos + Vector3.new(0, 1.5, 0), Vector3.new(0, -40, 0), params)
end

-- MeshPart plat (gabarit importé, normale +Y) ou disque de repli, posé sur une surface
local function decalque(nom, pos, normale, taille, angle, allonge)
	if not (CONFIG.SANG.actif and CONFIG.SANG.decalques) then
		return nil
	end
	local g = EFFETS and EFFETS:FindFirstChild(nom)
	local p
	normale = normale or Vector3.yAxis
	local ref = math.abs(normale.Y) < 0.9 and Vector3.yAxis or Vector3.xAxis
	local u = normale:Cross(ref).Unit
	local v = u:Cross(normale).Unit
	local c, s = math.cos(angle), math.sin(angle)
	local ax = u * c + v * s -- axe X du décalque (allongement) ; sur un sol plat, angle = atan2(dx, -dz)
	if g then
		p = g:Clone()
		p.Size = Vector3.new(taille * (allonge or 1), 0.02, taille)
		p.CFrame = CFrame.fromMatrix(pos + normale * 0.03, ax, normale)
	else
		p = Instance.new("Part")
		p.Shape = Enum.PartType.Cylinder
		p.Material = Enum.Material.SmoothPlastic
		p.Color = Color3.fromRGB(62, 4, 4)
		p.Size = Vector3.new(0.04, taille, taille * (allonge or 1))
		p.CFrame = CFrame.fromMatrix(pos + normale * 0.03, normale, ax)
	end
	p.Anchored = true
	p.CanCollide = false
	p.CanTouch = false
	p.CanQuery = false
	p.CastShadow = false
	p.Parent = locaux
	Debris:AddItem(p, CONFIG.SANG.duree_decalques or 90)
	return p
end

local IMAGE_GOUTTE = EFFETS and EFFETS:GetAttribute("ImageGoutte") or "rbxasset://textures/particles/smoke_main.dds"

local function giclee(pos, dir, n)
	if not (CONFIG.SANG.actif and CONFIG.SANG.particules) then
		return
	end
	local a = Instance.new("Attachment")
	a.WorldPosition = pos
	a.Parent = workspace.Terrain
	local e = Instance.new("ParticleEmitter")
	e.Texture = IMAGE_GOUTTE
	e.Color = ColorSequence.new(Color3.fromRGB(110, 6, 6), Color3.fromRGB(45, 2, 2))
	e.LightEmission = 0
	e.LightInfluence = 1
	e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.18), NumberSequenceKeypoint.new(1, 0.08) })
	e.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(0.8, 0.1),
		NumberSequenceKeypoint.new(1, 1) })
	e.Lifetime = NumberRange.new(0.35, 0.8)
	e.Speed = NumberRange.new(6, 16)
	e.SpreadAngle = Vector2.new(35, 35)
	e.Acceleration = Vector3.new(0, -workspace.Gravity * 0.35, 0)
	e.Drag = 1.5
	e.Rate = 0
	e.EmissionDirection = Enum.NormalId.Top
	if dir and dir.Magnitude > 1e-3 then
		a.WorldCFrame = CFrame.lookAt(pos, pos + dir) * CFrame.Angles(-math.pi / 2, 0, 0)
	end
	e.Parent = a
	e:Emit(math.floor((n or 24) * (CONFIG.SANG.quantite or 1)))
	Debris:AddItem(a, 2)
end

local function pointVictime(victime, nom)
	local def = DATA.points[nom]
	if not (victime and def) then
		return nil
	end
	local part = victime:FindFirstChild(def[1])
	if not part then
		return nil
	end
	return part.CFrame * Vector3.new(def[2][1], def[2][2], def[2][3]), part
end

-- éclaboussure : giclée + taches au sol autour du point
local function eclaboussure(ctrl, quoi, rng)
	local victime = ctrl.victime
	if quoi == "frenesie" then
		quoi = ({ "cou", "poitrine", "ventre" })[rng:NextInteger(1, 3)]
	elseif quoi == "bras" then
		quoi = "brasG"
	elseif quoi == "trainee" or quoi == "sol" then
		quoi = "dos"
	end
	local pos, part = pointVictime(victime, quoi)
	if not pos then
		local head = ctrl.tete
		if not head then
			return
		end
		pos = head.Position
	end
	local dir = part and (pos - part.Position) or Vector3.yAxis
	giclee(pos, dir + Vector3.new(rng:NextNumber(-0.3, 0.3), 0.6, rng:NextNumber(-0.3, 0.3)), 26)
	local exclus = { locaux, ctrl.modele, victime }
	local nb = math.max(1, math.floor(rng:NextInteger(1, 3) * (CONFIG.SANG.quantite or 1)))
	for _ = 1, nb do
		local off = Vector3.new(rng:NextNumber(-1.6, 1.6), 0, rng:NextNumber(-1.6, 1.6))
		local r = sousLePoint(pos + off, exclus)
		if r then
			local nom = "SANG_Eclaboussure_" .. rng:NextInteger(1, 3)
			decalque(nom, r.Position, r.Normal, rng:NextNumber(1.2, 2.8), rng:NextNumber(0, math.pi * 2))
		end
	end
end

-- flaque qui s'étend sous le corps
local function flaque(ctrl, quoi, rng)
	local pos = pointVictime(ctrl.victime, quoi == "cou" and "cou" or "dos") or (ctrl.hrp and ctrl.hrp.Position)
	if not pos then
		return
	end
	local r = sousLePoint(pos, { locaux, ctrl.modele, ctrl.victime })
	if not r then
		return
	end
	local p = decalque("SANG_Flaque", r.Position, r.Normal, 0.6, rng:NextNumber(0, math.pi * 2))
	if not p then
		return
	end
	local cf = p.CFrame
	local fin = rng:NextNumber(4.5, 6.5)
	task.spawn(function()
		local t0 = os.clock()
		while p.Parent and os.clock() - t0 < 6 do
			local k = (os.clock() - t0) / 6
			local tl = 0.6 + (fin - 0.6) * (1 - (1 - k) ^ 2)
			if p:IsA("MeshPart") then
				p.Size = Vector3.new(tl, 0.02, tl)
			else
				p.Size = Vector3.new(0.04, tl, tl)
			end
			p.CFrame = cf
			task.wait(0.05)
		end
	end)
end

------------------------------------------------------------------------------------------------------------
-- écran (victime) : noir, sang, vignette
------------------------------------------------------------------------------------------------------------
local ecran = Instance.new("ScreenGui")
ecran.Name = "MonstreEcran"
ecran.IgnoreGuiInset = true
ecran.ResetOnSpawn = false
ecran.DisplayOrder = 50
ecran.Parent = joueur:WaitForChild("PlayerGui")

local noir = Instance.new("Frame")
noir.Name = "Noir"
noir.Size = UDim2.fromScale(1, 1)
noir.BackgroundColor3 = Color3.new(0, 0, 0)
noir.BackgroundTransparency = 1
noir.BorderSizePixel = 0
noir.ZIndex = 20
noir.Parent = ecran

local rouge = Instance.new("Frame")
rouge.Name = "Rouge"
rouge.Size = UDim2.fromScale(1, 1)
rouge.BackgroundColor3 = Color3.fromRGB(120, 0, 0)
rouge.BackgroundTransparency = 1
rouge.BorderSizePixel = 0
rouge.ZIndex = 10
rouge.Parent = ecran

-- vignette : quatre bords en dégradé (aucune image à importer)
local vignette = {}
for i, def in ipairs({ { UDim2.fromScale(1, 0.35), UDim2.fromScale(0, 0), 90 }, { UDim2.fromScale(1, 0.35), UDim2.fromScale(0, 0.65), -90 },
	{ UDim2.fromScale(0.3, 1), UDim2.fromScale(0, 0), 0 }, { UDim2.fromScale(0.3, 1), UDim2.fromScale(0.7, 0), 180 } }) do
	local f = Instance.new("Frame")
	f.Name = "Vignette" .. i
	f.Size = def[1]
	f.Position = def[2]
	f.BackgroundColor3 = Color3.fromRGB(20, 0, 0)
	f.BorderSizePixel = 0
	f.BackgroundTransparency = 0
	f.ZIndex = 5
	local g = Instance.new("UIGradient")
	g.Rotation = def[3]
	g.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(1, 1) })
	g.Parent = f
	f.Visible = false
	f.Parent = ecran
	vignette[i] = f
end

local function vignetteForce(k, couleur)
	for _, f in ipairs(vignette) do
		f.Visible = k > 0.01
		f.BackgroundTransparency = 1 - math.clamp(k, 0, 1)
		if couleur then
			f.BackgroundColor3 = couleur
		end
	end
end

local function fondu(frame, de, a, duree)
	task.spawn(function()
		local t0 = os.clock()
		while os.clock() - t0 < duree do
			frame.BackgroundTransparency = de + (a - de) * ((os.clock() - t0) / duree)
			RunService.RenderStepped:Wait()
		end
		frame.BackgroundTransparency = a
	end)
end

local function coupure(duree)
	noir.BackgroundTransparency = 0
	task.delay(duree, function()
		fondu(noir, 0, 1, 0.3)
	end)
end

local function flashRouge(force)
	rouge.BackgroundTransparency = 1 - force
	fondu(rouge, 1 - force, 1, 0.5)
end

-- sang sur l'écran : gabarit SANG_Ecran (plan importé) devant la caméra, sinon taches d'interface
local sangEcran = nil
local sangEcranDebut = 0
local function sangSurEcran()
	if not (CONFIG.SANG.actif and CONFIG.SANG.ecran) then
		return
	end
	sangEcranDebut = os.clock()
	local g = EFFETS and EFFETS:FindFirstChild("SANG_Ecran")
	if g then
		if not sangEcran then
			sangEcran = g:Clone()
			sangEcran.Anchored = true
			sangEcran.CanCollide = false
			sangEcran.CanQuery = false
			sangEcran.CanTouch = false
			sangEcran.CastShadow = false
			sangEcran.Parent = workspace.CurrentCamera
		end
	else
		local rng = Random.new()
		for _ = 1, 7 do
			local f = Instance.new("Frame")
			local s = rng:NextNumber(0.08, 0.25)
			f.Size = UDim2.fromScale(s, s * 1.6)
			f.Position = UDim2.fromScale(rng:NextNumber(0, 0.9), rng:NextNumber(0, 0.85))
			f.BackgroundColor3 = Color3.fromRGB(rng:NextInteger(70, 120), 0, 0)
			f.BorderSizePixel = 0
			f.BackgroundTransparency = 0.15
			f.ZIndex = 8
			local cc = Instance.new("UICorner")
			cc.CornerRadius = UDim.new(0.5, 0)
			cc.Parent = f
			f.Parent = ecran
			fondu(f, 0.15, 1, 4)
			Debris:AddItem(f, 4.2)
		end
	end
end

local function majSangEcran()
	if not sangEcran then
		return
	end
	local cam = workspace.CurrentCamera
	local k = (os.clock() - sangEcranDebut) / 4.5
	if k >= 1 then
		sangEcran:Destroy()
		sangEcran = nil
		return
	end
	local d = 0.6
	local h = 2 * d * math.tan(math.rad(cam.FieldOfView) / 2)
	local w = h * cam.ViewportSize.X / math.max(cam.ViewportSize.Y, 1)
	sangEcran.Size = Vector3.new(w * 1.05, 0.01, h * 1.05)
	sangEcran.CFrame = cam.CFrame * CFrame.new(0, 0, -d) * CFrame.Angles(math.rad(90), 0, 0)
	sangEcran.Transparency = k ^ 2
end

------------------------------------------------------------------------------------------------------------
-- commandes et caméra de la victime
------------------------------------------------------------------------------------------------------------
local controles = nil
local function commandes(actif)
	if not controles then
		local ok, pm = pcall(function()
			return require(joueur:WaitForChild("PlayerScripts"):WaitForChild("PlayerModule", 5))
		end)
		if ok and pm then
			controles = pm:GetControls()
		end
	end
	if controles then
		if actif then
			controles:Enable()
		else
			controles:Disable()
		end
	end
end

local CAM = { actif = false, mode = nil, tremble = 0, cf = nil, coupe = false, fixe = nil, ctrl = nil }

local function partie(modele, ...)
	if not modele then
		return nil
	end
	for _, nom in ipairs({ ... }) do
		local p = modele:FindFirstChild(nom, true)
		if p and p:IsA("BasePart") then
			return p
		end
	end
	return modele.PrimaryPart
end

local function cameraMode(mode)
	if not CONFIG.CAMERA.active then
		return
	end
	if mode == "retour" then
		CAM.actif = false
		local cam = workspace.CurrentCamera
		cam.CameraType = Enum.CameraType.Custom
		local h = joueur.Character and joueur.Character:FindFirstChildOfClass("Humanoid")
		if h then
			cam.CameraSubject = h
		end
		return
	end
	if mode == "tremble" then
		CAM.tremble = math.max(CAM.tremble, 0.7)
		return
	end
	CAM.actif = true
	CAM.mode = mode
	CAM.fixe = nil
	CAM.depuis = os.clock()
end

local function cibleCamera(ctrl)
	if CAM.mode == "cadavre" then -- au-dessus du corps (cadavre posé, sinon dernière position du torse)
		local corps = ctrl.cadavre
		local p = corps and corps.Parent and (corps:FindFirstChild("Torso") or corps:FindFirstChildWhichIsA("BasePart"))
		local centre = p and p.Position or ctrl.dernierCentre
		if not centre then
			return nil
		end
		local a = (os.clock() - CAM.depuis) * 0.15
		return CFrame.lookAt(centre + Vector3.new(math.cos(a) * 5, 9, math.sin(a) * 5), centre)
	end
	local m, v = ctrl.modele, ctrl.victime
	local teteM = partie(m, "MON_Head_1", "HumanoidRootPart")
	local hautM = partie(m, "MON_UpperChest_1", "HumanoidRootPart")
	local teteV = partie(v, "Head")
	local torseV = partie(v, "Torso", "UpperTorso", "HumanoidRootPart")
	local mode = CAM.mode
	if not (teteM and torseV) then
		return nil
	end
	if mode == "victime" and teteV then
		local o = teteV.CFrame * Vector3.new(0, 0.15, -0.55)
		return CFrame.lookAt(o, teteM.Position)
	elseif mode == "epaule_victime" then
		local o = torseV.CFrame * Vector3.new(1.8, 1.6, 4.2)
		return CFrame.lookAt(o, teteM.Position:Lerp(torseV.Position, 0.35))
	elseif mode == "face" or mode == "suivre" then
		local mid = teteM.Position:Lerp(torseV.Position, 0.55)
		local axe = plat(torseV.Position - ctrl.hrp.Position)
		axe = axe.Magnitude > 0.1 and axe.Unit or Vector3.zAxis
		local cote = axe:Cross(Vector3.yAxis)
		if not CAM.fixe then
			CAM.fixe = { cote = cote }
		end
		local o = mid + CAM.fixe.cote * 11 + Vector3.new(0, 1.5, 0) + axe * 2
		return CFrame.lookAt(o, mid)
	elseif mode == "epaule_monstre" and hautM then
		local o = hautM.CFrame * Vector3.new(2.6, 3.2, 5.5)
		return CFrame.lookAt(o, torseV.Position)
	elseif mode == "distance" then
		-- caméra posée à l'écart ; elle ne suit le monstre que s'il s'éloigne de plus de 26 studs
		if not CAM.fixe then
			local axe = plat(torseV.Position - ctrl.hrp.Position)
			axe = axe.Magnitude > 0.1 and axe.Unit or Vector3.zAxis
			CAM.fixe = { pos = torseV.Position + axe * 14 + axe:Cross(Vector3.yAxis) * 9 + Vector3.new(0, 6, 0) }
		end
		local vers = plat(ctrl.hrp.Position - CAM.fixe.pos)
		if vers.Magnitude > 26 then
			CAM.fixe.pos += vers.Unit * (vers.Magnitude - 26)
		end
		return CFrame.lookAt(CAM.fixe.pos, ctrl.hrp.Position)
	elseif mode == "trainee" and teteV then
		local loin = plat(teteV.Position - ctrl.hrp.Position)
		loin = loin.Magnitude > 0.1 and loin.Unit or Vector3.zAxis
		local o = teteV.Position + loin * 1.6 + Vector3.new(0, 1.6, 0)
		return CFrame.lookAt(o, hautM and hautM.Position or ctrl.hrp.Position)
	elseif mode == "fige" then
		return CAM.cf
	end
	return nil
end

local bruit = Random.new()
RunService:BindToRenderStep("MonstreCamera", Enum.RenderPriority.Camera.Value + 5, function(dt)
	majSangEcran()
	if not (CAM.actif and CAM.ctrl) then
		return
	end
	local cam = workspace.CurrentCamera
	local cible = cibleCamera(CAM.ctrl)
	if not cible then
		return
	end
	cam.CameraType = Enum.CameraType.Scriptable
	cam.FieldOfView = CONFIG.CAMERA.champ or 60
	if not CAM.cf or CAM.coupe then
		CAM.cf = cible
		CAM.coupe = false
	else
		CAM.cf = CAM.cf:Lerp(cible, 1 - math.exp(-dt * 7))
	end
	local cf = CAM.cf
	if CAM.tremble > 0.01 then
		local a = CAM.tremble * (CONFIG.CAMERA.tremblement or 1)
		cf = cf * CFrame.Angles(bruit:NextNumber(-1, 1) * 0.03 * a, bruit:NextNumber(-1, 1) * 0.03 * a, bruit:NextNumber(-1, 1) * 0.02 * a)
		CAM.tremble = CAM.tremble * math.exp(-dt * 3.5)
	end
	cam.CFrame = cf
end)

------------------------------------------------------------------------------------------------------------
-- monstres
------------------------------------------------------------------------------------------------------------
local CTRL = {}

local function victimeAnim(ctrl, victime)
	if ctrl.victime == victime and ctrl.vlec then
		return ctrl.vlec
	end
	ctrl.victime = victime
	ctrl.vlec = nil
	if victime then
		local moteurs = MA.moteurs(victime, "victime")
		if moteurs.Torso or moteurs.Head then
			ctrl.vlec = MA.lecteur("victime", moteurs)
		end
	end
	return ctrl.vlec
end

local function estVictimeLocale(ctrl)
	return ctrl.victime ~= nil and ctrl.victime == joueur.Character
end

local function effetMarqueur(ctrl, m)
	local nom, val = m[2], m[3]
	if m[4] - m[1] > 0.6 then
		return -- client arrivé en retard : on ne rejoue pas les vieux effets
	end
	ctrl.compteur = (ctrl.compteur or 0) + 1
	local rng = Random.new((ctrl.graine or 0) * 131 + ctrl.compteur)
	local moi = estVictimeLocale(ctrl)
	local distance = (workspace.CurrentCamera.CFrame.Position - ctrl.hrp.Position).Magnitude
	if nom == "Son" then
		jouerSon(val, ctrl.tete or ctrl.hrp, 1, rng:NextNumber(0.94, 1.06))
	elseif nom == "Eclaboussure" then
		eclaboussure(ctrl, val, rng)
	elseif nom == "Flaque" then
		flaque(ctrl, val, rng)
	elseif nom == "Trace" then
		ctrl.trace = { derniere = nil }
	elseif nom == "Morsure" or nom == "Coup" or nom == "Impact" or nom == "Retrait" then
		if moi then
			CAM.tremble = math.max(CAM.tremble, nom == "Impact" and 1.2 or 0.8)
			flashRouge(nom == "Morsure" and 0.35 or 0.25)
		elseif distance < 25 then
			CAM.tremble = math.max(CAM.tremble, 0.15)
		end
	elseif nom == "Tremble" then
		if moi then
			CAM.tremble = math.max(CAM.tremble, tonumber(val) or 0.6)
		end
	elseif nom == "Camera" then
		if moi then
			cameraMode(val)
		end
	elseif nom == "Coupure" then
		if moi then
			coupure(tonumber(val) or 0.4)
			CAM.coupe = true
		end
	elseif nom == "Ecran" then
		if moi then
			sangSurEcran()
		end
	elseif nom == "Silence" then
		if moi or distance < 60 then
			silence(tonumber(val) or 2.5)
		end
	elseif nom == "Infection" then
		if moi then
			flashRouge(0.5)
			vignetteForce(0.6, Color3.fromRGB(10, 30, 5))
			task.delay(0.8, function()
				vignetteForce(0)
			end)
		end
	end
end

-- traînée de sang derrière la victime
local function majTrace(ctrl)
	local tr = ctrl.trace
	if not tr or not ctrl.victime then
		return
	end
	local pos = pointVictime(ctrl.victime, "dos")
	if not pos then
		return
	end
	if not tr.derniere then
		tr.derniere = pos
		return
	end
	local d = plat(pos - tr.derniere)
	if d.Magnitude < 1.3 then
		return
	end
	local mid = tr.derniere:Lerp(pos, 0.5)
	local r = sousLePoint(mid, { locaux, ctrl.modele, ctrl.victime })
	if r then
		decalque("SANG_Trainee", r.Position, r.Normal, 1.6, math.atan2(d.X, -d.Z), d.Magnitude / 1.6 + 0.25)
	end
	tr.derniere = pos
end

local function nouveauMonstre(modele)
	if CTRL[modele] then
		return
	end
	local hrp = modele:WaitForChild("HumanoidRootPart", 10)
	if not hrp then
		return
	end
	local ctrl = {
		modele = modele,
		hrp = hrp,
		tete = partie(modele, "MON_Head_1"),
		lec = MA.lecteur("monstre", MA.moteurs(modele, "monstre")),
		air = 0,
		vy = 0,
		saut = nil,
	}
	ctrl.lec:jouer("base", "idle", { horloge = os.clock })
	CTRL[modele] = ctrl
	modele.DescendantAdded:Connect(function(d) -- pièces arrivées en retard (StreamingEnabled) : on reprend les Motor6D
		if d:IsA("Motor6D") then
			ctrl.lec.moteurs = MA.moteurs(modele, "monstre")
		end
	end)
end

local function finSequence(ctrl)
	local victime = ctrl.victime
	local moi = estVictimeLocale(ctrl)
	if ctrl.vlec then
		ctrl.vlec:arreterAction(0.15)
		ctrl.vlec:etape(1)
		for _, mo in pairs(ctrl.vlec.moteurs) do
			mo.Transform = CFrame.identity
		end
	end
	ctrl.vlec = nil
	ctrl.trace = nil
	ctrl.sequence = nil
	ctrl.victime = nil
	ctrl.phaseKey = nil
	if moi then
		local corpsNom = victime and victime:GetAttribute("MA_Cadavre")
		if corpsNom and victime:GetAttribute("MA_Infection") == nil then
			ctrl.cadavre = workspace:FindFirstChild(corpsNom)
			CAM.ctrl = ctrl
			cameraMode("cadavre")
		else
			cameraMode("retour")
			CAM.ctrl = nil
			if not (victime and victime:GetAttribute("MA_Infection")) then
				commandes(true) -- sinon après « se relever »
			end
		end
	end
end

-- relevé de la victime contaminée (tous les clients jouent « se relever » sur son personnage)
local releves = {}
local function majReleves(dt)
	for perso, r in pairs(releves) do
		if not perso.Parent or os.clock() - r.t0 > 1.4 then
			if r.lec then
				for _, mo in pairs(r.lec.moteurs) do
					mo.Transform = CFrame.identity
				end
			end
			releves[perso] = nil
			if perso == joueur.Character then
				commandes(true)
			end
		elseif r.lec then
			r.lec:etape(dt)
		end
	end
end

local function surveillerReleve(perso)
	perso:GetAttributeChangedSignal("MA_Releve"):Connect(function()
		local t = perso:GetAttribute("MA_Releve")
		if t and DATA.victime.getup then
			local lec = MA.lecteur("victime", MA.moteurs(perso, "victime"))
			lec:jouer("action", "getup", { horloge = maintenant, debut = t, fondu = 0.2 })
			releves[perso] = { lec = lec, t0 = os.clock() }
		end
	end)
end

local function majMonstre(ctrl, dt)
	local m = ctrl.modele
	local lec = ctrl.lec
	local seq = m:GetAttribute("MA_Sequence") or ""
	local phase = m:GetAttribute("MA_Phase") or ""
	local action = m:GetAttribute("MA_Action") or ""
	-- déplacement
	local v = ctrl.hrp.AssemblyLinearVelocity
	local hv = plat(v).Magnitude
	if hv < 0.6 then
		lec:jouer("base", "idle", { horloge = os.clock, fondu = 0.3 })
	elseif hv < (CONFIG.VITESSE.marche + CONFIG.VITESSE.course) / 2 then
		local l = lec:jouer("base", "walk", { horloge = os.clock, fondu = 0.3 })
		if l then
			l.vitesse = math.clamp(hv / DATA.monstre.walk.speed, 0.4, 2)
		end
	else
		local l = lec:jouer("base", "run", { horloge = os.clock, fondu = 0.25 })
		if l then
			l.vitesse = math.clamp(hv / DATA.monstre.run.speed, 0.5, 1.6)
		end
	end
	-- en l'air ?
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { m, locaux }
	local auSol = ctrl.hrp.Anchored or workspace:Raycast(ctrl.hrp.Position, Vector3.new(0, -(DATA.rig.hrp.center[2] + 1.2), 0), params) ~= nil
	if auSol then
		if ctrl.air > 0.3 and ctrl.vy < -12 then
			ctrl.atterrit = os.clock()
		end
		ctrl.air = 0
	else
		ctrl.air += dt
	end
	ctrl.vy = v.Y
	-- couche d'action
	if seq ~= "" and phase ~= "" then
		local debut = m:GetAttribute("MA_PhaseDebut") or 0
		if ctrl.sequence ~= seq then
			ctrl.sequence = seq
			ctrl.graine = m:GetAttribute("MA_Graine") or 0
			ctrl.compteur = 0
			ctrl.cadavre = nil
		end
		local vv = m:FindFirstChild("MA_Victime")
		local victime = vv and vv.Value
		if ctrl.phaseKey ~= phase or ctrl.phaseDebut ~= debut then
			local premier = ctrl.phaseKey == nil
			lec:jouer("action", phase, { horloge = maintenant, debut = debut, fondu = premier and 0.15 or 0.3, relancer = true })
			local vl = victimeAnim(ctrl, victime)
			if vl and DATA.victime[phase] then
				vl:jouer("action", phase, { horloge = maintenant, debut = debut, fondu = premier and 0.12 or 0.3, relancer = true })
			end
			ctrl.phaseKey, ctrl.phaseDebut = phase, debut
			ctrl.trace = nil
			if premier and estVictimeLocale(ctrl) then
				CAM.ctrl = ctrl
				CAM.cf = nil
				commandes(false)
			end
		end
	elseif ctrl.sequence then
		finSequence(ctrl)
		lec:arreterAction(0.4)
	elseif action ~= "" then
		local debut = m:GetAttribute("MA_ActionDebut") or 0
		local c = DATA.monstre[action]
		if c and maintenant() < debut + c.length then
			if not lec:action() or lec:action().key ~= action or ctrl.actionDebut ~= debut then
				lec:jouer("action", action, { horloge = maintenant, debut = debut, fondu = 0.2, relancer = true })
				ctrl.actionDebut = debut
			end
		else
			lec:arreterAction(0.3)
		end
	elseif ctrl.air > 0.25 or (not auSol and v.Y > 6) then
		if v.Y > 2 then
			if not lec:action() or lec:action().key ~= "jump" then
				lec:jouer("action", "jump", { horloge = os.clock, fondu = 0.1 })
			end
		elseif not lec:action() or lec:action().key ~= "fall" then
			lec:jouer("action", "fall", { horloge = os.clock, fondu = 0.3 })
		end
	elseif ctrl.atterrit and os.clock() - ctrl.atterrit < DATA.monstre.land.length then
		if not lec:action() or lec:action().key ~= "land" then
			lec:jouer("action", "land", { horloge = os.clock, fondu = 0.08, relancer = true })
		end
	else
		lec:arreterAction(0.3)
	end
	local evts = lec:etape(dt)
	if ctrl.vlec then
		ctrl.vlec:etape(dt)
		local torse = ctrl.victime and ctrl.victime:FindFirstChild("Torso")
		if torse then
			ctrl.dernierCentre = torse.Position
		end
	end
	for _, e in ipairs(evts) do
		if ctrl.sequence or e[2] == "Son" then
			effetMarqueur(ctrl, e)
		end
	end
end

RunService.PreSimulation:Connect(function(dt)
	for modele, ctrl in pairs(CTRL) do
		if not modele.Parent then
			CTRL[modele] = nil
		else
			local ok, err = pcall(majMonstre, ctrl, dt)
			if not ok then
				warn("[MonstreClient] " .. tostring(err))
			end
		end
	end
	majReleves(dt)
end)

RunService.Heartbeat:Connect(function()
	for _, ctrl in pairs(CTRL) do
		if ctrl.trace then
			majTrace(ctrl)
		end
	end
end)

for _, m in ipairs(CollectionService:GetTagged("Monstre")) do
	task.spawn(nouveauMonstre, m)
end
CollectionService:GetInstanceAddedSignal("Monstre"):Connect(function(m)
	task.spawn(nouveauMonstre, m)
end)

------------------------------------------------------------------------------------------------------------
-- infection du joueur local
------------------------------------------------------------------------------------------------------------
local cc = Instance.new("ColorCorrectionEffect")
cc.Name = "MonstreInfection"
cc.Enabled = false
cc.Parent = Lighting
local flou = Instance.new("BlurEffect")
flou.Name = "MonstreInfectionFlou"
flou.Size = 0
flou.Enabled = false
flou.Parent = Lighting
local INF = { prochainCoeur = 0, prochaineToux = 0, balance = 0 }

local function finInfection()
	cc.Enabled = false
	flou.Enabled = false
	vignetteForce(0)
end

RunService:BindToRenderStep("MonstreInfection", Enum.RenderPriority.Camera.Value + 6, function(dt)
	local perso = joueur.Character
	local debut = perso and perso:GetAttribute("MA_Infection")
	local h = perso and perso:FindFirstChildOfClass("Humanoid")
	if not (debut and h and h.Health > 0) then
		if cc.Enabled then
			finInfection()
		end
		return
	end
	local t = maintenant()
	if t < debut then
		return
	end
	local I = CONFIG.INFECTION
	local k = math.clamp((t - debut) / I.duree, 0, 1)
	local s = 0.25 + 0.75 * k -- les symptômes commencent faibles
	cc.Enabled = true
	cc.TintColor = Color3.new(1, 1, 1):Lerp(Color3.fromRGB(205, 235, 190), s)
	cc.Saturation = -0.55 * s
	cc.Contrast = 0.2 * s
	local pouls = (0.5 + 0.5 * math.sin(os.clock() * (2.2 + 2 * s))) ^ 6
	flou.Enabled = true
	flou.Size = (2 + 10 * s) * pouls
	vignetteForce((0.25 + 0.5 * s) * (0.75 + 0.25 * pouls), Color3.fromRGB(14, 24, 8))
	if os.clock() > INF.prochainCoeur then
		INF.prochainCoeur = os.clock() + (1.25 - 0.55 * s)
		jouerSon("battement", nil, 0.5 + 0.5 * s)
	end
	if os.clock() > INF.prochaineToux then
		INF.prochaineToux = os.clock() + 6 + math.random() * (14 - 8 * s)
		if INF.dejaToux then
			jouerSon("toux", nil, 0.8)
			CAM.tremble = math.max(CAM.tremble, 0.25)
		end
		INF.dejaToux = true
	end
	-- vitesse plafonnée, caméra qui tangue
	local f = 1 + (I.vitesse_min - 1) * s
	if h.WalkSpeed > 16 * f then
		h.WalkSpeed = 16 * f
	end
	if not CAM.actif then
		local cam = workspace.CurrentCamera
		INF.balance += dt
		cam.CFrame = cam.CFrame * CFrame.Angles(math.sin(INF.balance * 0.9) * 0.012 * s, 0, math.sin(INF.balance * 0.6) * 0.03 * s)
	end
end)

local function nouveauPerso(perso)
	finInfection()
	CAM.actif = false
	CAM.ctrl = nil
	noir.BackgroundTransparency = 1
	if controles then
		commandes(true) -- coupées pendant une mise à mort : rendues au nouveau personnage
	end
	local cam = workspace.CurrentCamera
	cam.CameraType = Enum.CameraType.Custom
	surveillerReleve(perso)
end
joueur.CharacterAdded:Connect(nouveauPerso)
if joueur.Character then
	nouveauPerso(joueur.Character)
end
for _, p in ipairs(Players:GetPlayers()) do
	if p ~= joueur then
		if p.Character then
			surveillerReleve(p.Character)
		end
		p.CharacterAdded:Connect(surveillerReleve)
	end
end
Players.PlayerAdded:Connect(function(p)
	p.CharacterAdded:Connect(surveillerReleve)
end)
for _, m in ipairs(CollectionService:GetTagged(CONFIG.ETIQUETTE_VICTIME)) do
	surveillerReleve(m)
end
