--[[
	Installateur du monstre (ModuleScript du kit Monstre_Kit). Dans Roblox Studio, en mode édition :
		1. Importer 3D : monstre/export/Monstre.fbx (ou .glb) ;
		2. insérer monstre/roblox/Monstre_Kit.rbxmx (clic droit sur Workspace > Insérer depuis un fichier) ;
		3. barre de commande :  require(workspace.Monstre_Kit.Installateur)()
	Options : require(...)({ position = Vector3, garderConfig = true, victimeTest = false })

	Ce que fait l'installation (annulable avec Ctrl+Z) :
	- retrouve l'import (maillages MON_*, marqueurs REF_A..REF_D), en déduit échelle et orientation, remet le modèle à
	  l'échelle 1 (1 unité = 1 stud), debout, face à sa direction d'origine ;
	- monte le rig : HumanoidRootPart, un Motor6D par pièce (37) au pivot de son articulation (C0/C1 alignés sur les
	  axes du modèle), pièce VictimeAncre (la victime y est soudée pendant une mise à mort), Humanoid (R15, HipHeight),
	  lueur de la gueule (pièce Neon + PointLight à GLOW_MOUTH) ;
	- range les gabarits de sang SANG_* (ReplicatedStorage.Monstre.Effets, transparence par l'alpha) ;
	- installe les scripts : ReplicatedStorage.Monstre (MonstreAnim, MonstreConfig, MonstreDonnees, Effets),
	  ServerScriptService.MonstreServeur, StarterPlayerScripts.MonstreClient, ServerStorage.MonstreOutils.
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")
local ServerStorage = game:GetService("ServerStorage")
local StarterPlayer = game:GetService("StarterPlayer")
local CollectionService = game:GetService("CollectionService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

local KIT = script.Parent

local function v3(t)
	return Vector3.new(t[1], t[2], t[3])
end

local function trouverImports()
	local out = {}
	local vus = {}
	for _, d in ipairs(workspace:GetDescendants()) do
		if d.Name == "REF_A" and d:IsA("BasePart") then
			local m = d.Parent
			while m and m.Parent ~= workspace and not (m:IsA("Model") and m:FindFirstChild("REF_B", true) and m:FindFirstChild("REF_C", true)) do
				m = m.Parent
			end
			if m and m:IsA("Model") and not vus[m] and not m:GetAttribute("MA_Installe") then
				vus[m] = true
				table.insert(out, m)
			end
		end
	end
	return out
end

local function choisirImport()
	local liste = trouverImports()
	if #liste <= 1 then
		return liste[1]
	end
	for _, s in ipairs(Selection:Get()) do
		for _, m in ipairs(liste) do
			if s == m or s:IsDescendantOf(m) then
				return m
			end
		end
	end
	return nil, "plusieurs imports du monstre : sélectionnez celui à installer"
end

-- repère du modèle d'après les marqueurs : M (axes unitaires), échelle s (studs par unité du modèle)
local function repere(modele, data)
	local function pos(nom)
		local p = modele:FindFirstChild(nom, true)
		return p and p:IsA("BasePart") and p.Position or nil
	end
	local A, B, C, D = pos("REF_A"), pos("REF_B"), pos("REF_C"), pos("REF_D")
	if not (A and B and C) then
		return nil, "marqueurs REF_A, REF_B ou REF_C introuvables"
	end
	local mk = data.rig.markers
	local dAB = (v3(mk.REF_B) - v3(mk.REF_A)).Magnitude
	local s = (B - A).Magnitude / dAB
	if s < 1e-4 then
		return nil, "marqueurs confondus"
	end
	local up = (B - A).Unit
	local ac = C - A
	local right = (ac - up * ac:Dot(up))
	if right.Magnitude < 1e-6 then
		return nil, "marqueurs alignés"
	end
	right = right.Unit
	local back = right:Cross(up)
	if D then
		local attendu = v3(mk.REF_D) - v3(mk.REF_A) -- (0, 0, -1) dans le modèle
		local mesure = (D - A) / s
		local z = mesure:Dot(back)
		if attendu.Z ~= 0 and z * attendu.Z < 0 then
			return nil, "import en miroir (REF_D du mauvais côté) : réimportez sans inverser d'axe"
		end
	end
	local origine = A - up * (v3(mk.REF_A).Y * s) - right * (v3(mk.REF_A).X * s) - back * (v3(mk.REF_A).Z * s)
	return CFrame.fromMatrix(origine, right, up, back), s
end

local function nomPiece(nom)
	local piece, n = string.match(nom, "^MON_(.+)_(%d+)$")
	return piece, tonumber(n)
end

local function installerScripts(opts, rapport)
	local data = KIT:FindFirstChild("MonstreDonnees")
	local dossier = ReplicatedStorage:FindFirstChild("Monstre")
	if not dossier then
		dossier = Instance.new("Folder")
		dossier.Name = "Monstre"
		dossier.Parent = ReplicatedStorage
	end
	for _, nom in ipairs({ "MonstreAnim", "MonstreDonnees", "MonstreConfig" }) do
		local src = KIT:FindFirstChild(nom)
		local ancien = dossier:FindFirstChild(nom)
		if nom == "MonstreConfig" and ancien and opts.garderConfig ~= false then
			table.insert(rapport, "MonstreConfig existant conservé (garderConfig = false pour le remplacer)")
		elseif src then
			if ancien then
				ancien:Destroy()
			end
			src:Clone().Parent = dossier
		end
	end
	if not dossier:FindFirstChild("Effets") then
		local e = Instance.new("Folder")
		e.Name = "Effets"
		e.Parent = dossier
	end
	local function placer(nom, parent)
		local src = KIT:FindFirstChild(nom)
		if not src then
			table.insert(rapport, "ATTENTION : " .. nom .. " absent du kit")
			return
		end
		local ancien = parent:FindFirstChild(nom)
		if ancien then
			ancien:Destroy()
		end
		local c = src:Clone()
		if c:IsA("Script") then -- désactivé dans le kit (le kit peut être dans le Workspace)
			pcall(function()
				c.Enabled = true
			end)
			pcall(function()
				c.Disabled = false
			end)
		end
		c.Parent = parent
	end
	placer("MonstreServeur", ServerScriptService)
	local sps = StarterPlayer:FindFirstChildOfClass("StarterPlayerScripts")
	if not sps then
		sps = Instance.new("StarterPlayerScripts")
		sps.Parent = StarterPlayer
	end
	placer("MonstreClient", sps)
	placer("MonstreOutils", ServerStorage)
	return dossier, data
end

local function preparerEffets(modele, dossier, rapport)
	local effets = dossier:FindFirstChild("Effets")
	local n = 0
	for _, d in ipairs(modele:GetDescendants()) do
		if d:IsA("BasePart") and string.sub(d.Name, 1, 5) == "SANG_" then
			local ancien = effets:FindFirstChild(d.Name)
			if ancien then
				ancien:Destroy()
			end
			d.Anchored = true
			d.CanCollide = false
			d.CanTouch = false
			d.CanQuery = false
			d.CastShadow = false
			d.Massless = true
			local sa = d:FindFirstChildOfClass("SurfaceAppearance")
			if sa then
				pcall(function()
					sa.AlphaMode = Enum.AlphaMode.Transparency
				end)
				if d.Name == "SANG_Goutte" then
					local ok, id = pcall(function()
						return sa.ColorMap
					end)
					if ok and type(id) == "string" and id ~= "" then
						effets:SetAttribute("ImageGoutte", id)
					end
				end
			elseif d:IsA("MeshPart") and d.Name == "SANG_Goutte" and d.TextureID ~= "" then
				effets:SetAttribute("ImageGoutte", d.TextureID)
			end
			d.Parent = effets
			n += 1
		end
	end
	table.insert(rapport, string.format("%d gabarit(s) de sang rangé(s) dans ReplicatedStorage.Monstre.Effets", n))
end

return function(opts)
	opts = opts or {}
	local rapport = {}
	local enreg = nil
	pcall(function()
		enreg = ChangeHistoryService:TryBeginRecording("InstallerMonstre", "Installer le monstre")
	end)
	local ok, res = pcall(function()
		local modele, err = choisirImport()
		local dossier, dataModule = installerScripts(opts, rapport)
		local data = require(dataModule)
		if not modele then
			local deja = nil
			for _, m in ipairs(CollectionService:GetTagged("Monstre")) do
				deja = m
			end
			if deja then
				table.insert(rapport, "monstre déjà installé (" .. deja:GetFullName() .. ") : scripts et données mis à jour")
				return deja
			end
			error(err or "aucun import du monstre trouvé (Importer 3D : monstre/export/Monstre.fbx)")
		end
		local M, s = repere(modele, data)
		if not M then
			error(s)
		end
		table.insert(rapport, string.format("import trouvé : %s (échelle %.4g, remis à 1 stud par unité)", modele:GetFullName(), s))
		-- placement debout, face à la direction d'origine (horizontale)
		local avant = -M.ZVector
		avant = Vector3.new(avant.X, 0, avant.Z)
		avant = avant.Magnitude > 1e-3 and avant.Unit or Vector3.new(0, 0, -1)
		local o = opts.position or M.Position
		local M2 = CFrame.lookAt(o, o + avant)
		-- remise à l'échelle et à plat de toutes les pièces
		local parties = {}
		for _, d in ipairs(modele:GetDescendants()) do
			if d:IsA("BasePart") then
				table.insert(parties, d)
			end
		end
		for _, p in ipairs(parties) do
			local lp = M:PointToObjectSpace(p.Position) / s
			local lr = M.Rotation:Inverse() * p.CFrame.Rotation
			p.Anchored = true
			p.Size = p.Size / s
			p.CFrame = M2 * CFrame.new(lp) * lr
		end
		-- pièces du rig
		local principal, extras = {}, {}
		for _, p in ipairs(parties) do
			local piece, n = nomPiece(p.Name)
			if piece then
				if n == 1 or not principal[piece] then
					if principal[piece] then
						table.insert(extras, { piece, principal[piece] })
					end
					principal[piece] = p
				else
					table.insert(extras, { piece, p })
				end
			end
		end
		local manquantes = {}
		for _, def in ipairs(data.rig.parts) do
			if def.name ~= "VictimeAncre" and not principal[def.name] then
				table.insert(manquantes, def.name)
			end
		end
		if #manquantes > 0 then
			error("pièces absentes de l'import : " .. table.concat(manquantes, ", "))
		end
		local hrp = modele:FindFirstChild("HumanoidRootPart")
		if hrp then
			hrp:Destroy()
		end
		hrp = Instance.new("Part")
		hrp.Name = "HumanoidRootPart"
		hrp.Size = v3(data.rig.hrp.size)
		hrp.Transparency = 1
		hrp.CanCollide = true
		hrp.Anchored = true
		hrp.CFrame = M2 * CFrame.new(v3(data.rig.hrp.center))
		hrp.Parent = modele
		modele.PrimaryPart = hrp
		local nbMoteurs = 0
		for _, def in ipairs(data.rig.parts) do
			local pivotCF = M2 * CFrame.new(v3(def.pivot))
			local p0 = def.parent == "HumanoidRootPart" and hrp or principal[def.parent]
			local p1
			if def.name == "VictimeAncre" then
				p1 = modele:FindFirstChild("VictimeAncrePart") or Instance.new("Part")
				p1.Name = "VictimeAncrePart"
				p1.Size = Vector3.new(1, 1, 1)
				p1.Transparency = 1
				p1.CanCollide = false
				p1.CanTouch = false
				p1.CanQuery = false
				p1.Massless = true
				p1.Anchored = false
				p1.CFrame = pivotCF * CFrame.Angles(0, math.pi, 0)
				p1.Parent = modele
			else
				p1 = principal[def.name]
			end
			for _, x in ipairs(p1:GetChildren()) do
				if x:IsA("Motor6D") then
					x:Destroy()
				end
			end
			local m = Instance.new("Motor6D")
			m.Name = def.name
			m.Part0 = p0
			m.Part1 = p1
			m.C0 = p0.CFrame:ToObjectSpace(pivotCF)
			m.C1 = p1.CFrame:ToObjectSpace(pivotCF)
			m.Parent = p1
			nbMoteurs += 1
		end
		for _, e in ipairs(extras) do
			local w = Instance.new("WeldConstraint")
			w.Part0 = principal[e[1]]
			w.Part1 = e[2]
			w.Parent = e[2]
		end
		-- lueur de la gueule
		local glowMarker = modele:FindFirstChild("GLOW_MOUTH", true)
		local glowPos = M2 * v3(data.rig.glow)
		if glowMarker then
			glowMarker:Destroy()
		end
		local lueur = Instance.new("Part")
		lueur.Name = "Lueur"
		lueur.Shape = Enum.PartType.Ball
		lueur.Size = Vector3.new(0.22, 0.22, 0.22)
		lueur.Material = Enum.Material.Neon
		lueur.Color = Color3.fromRGB(255, 96, 36)
		lueur.Transparency = 0.15
		lueur.CanCollide = false
		lueur.CanTouch = false
		lueur.CanQuery = false
		lueur.Massless = true
		lueur.CastShadow = false
		lueur.CFrame = CFrame.new(glowPos)
		lueur.Parent = modele
		local light = Instance.new("PointLight")
		light.Range = 7
		light.Brightness = 1.6
		light.Color = Color3.fromRGB(255, 110, 50)
		light.Shadows = false
		light.Parent = lueur
		local wl = Instance.new("WeldConstraint")
		wl.Part0 = principal.Head
		wl.Part1 = lueur
		wl.Parent = lueur
		-- marqueurs et gabarits de sang
		for _, nom in ipairs({ "REF_A", "REF_B", "REF_C", "REF_D" }) do
			local mk = modele:FindFirstChild(nom, true)
			if mk then
				mk:Destroy()
			end
		end
		preparerEffets(modele, dossier, rapport)
		-- propriétés physiques
		for _, d in ipairs(modele:GetDescendants()) do
			if d:IsA("BasePart") and d ~= hrp then
				d.CanCollide = false
				d.CanTouch = false
				d.Massless = true
				d.Anchored = false
				if d:IsA("MeshPart") then
					pcall(function()
						d.CollisionFidelity = Enum.CollisionFidelity.Box
					end)
				end
			end
		end
		local hum = modele:FindFirstChildOfClass("Humanoid") or Instance.new("Humanoid")
		hum.RigType = Enum.HumanoidRigType.R15
		hum.AutomaticScalingEnabled = false
		hum.RequiresNeck = false
		hum.BreakJointsOnDeath = false
		hum.HipHeight = data.rig.hrp.hipHeight
		hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
		hum.WalkSpeed = 5.5
		hum.Parent = modele
		hrp.Anchored = false
		pcall(function() -- avec StreamingEnabled, tout le modèle arrive d'un coup chez les clients
			modele.ModelStreamingMode = Enum.ModelStreamingMode.Atomic
		end)
		modele.Name = "Monstre"
		modele:SetAttribute("MA_Installe", true)
		CollectionService:AddTag(modele, "Monstre")
		if modele.Parent ~= workspace then
			modele.Parent = workspace
		end
		table.insert(rapport, string.format("rig monté : %d Motor6D (37 pièces + VictimeAncre), %d maillage(s) soudé(s) en plus",
			nbMoteurs, #extras))
		return modele
	end)
	if enreg then
		pcall(function()
			ChangeHistoryService:FinishRecording(enreg, ok and Enum.FinishRecordingOperation.Commit or Enum.FinishRecordingOperation.Cancel)
		end)
	end
	if not ok then
		warn("[Monstre] installation impossible : " .. tostring(res))
		return false, tostring(res)
	end
	-- le kit est rangé dans ServerStorage (réinstallation possible)
	if KIT.Parent ~= ServerStorage then
		local ancien = ServerStorage:FindFirstChild(KIT.Name)
		if ancien and ancien ~= KIT then
			ancien:Destroy()
		end
		KIT.Parent = ServerStorage
	end
	table.insert(rapport, "scripts installés : ReplicatedStorage.Monstre, ServerScriptService.MonstreServeur, StarterPlayerScripts.MonstreClient, ServerStorage.MonstreOutils")
	table.insert(rapport, "lancez le test (F5) ; essais : require(game.ServerStorage.MonstreOutils).miseAMort(\"frenesie\") (barre de commande, côté serveur)")
	print("[Monstre] installation terminée :\n  - " .. table.concat(rapport, "\n  - "))
	return true, res, rapport
end
