--[[
	MonstreOutils (ModuleScript, ServerStorage) : essais depuis la barre de commande (ou par Claude via le serveur MCP de
	Studio). Pendant un test (F5), la barre de commande s'exécute côté serveur :
		local O = require(game.ServerStorage.MonstreOutils)
		O.victimeTest()                 -- un survivant d'essai (copie du StarterCharacter) devant le monstre
		O.miseAMort("frenesie")         -- mise à mort sur la victime la plus proche (ou O.miseAMort("trainee", victime))
		O.geste("roar")                 -- hurlement ; "sniff" : flairer ; "attack" : attaque
		O.pause(true)                   -- arrête l'IA (false : la relance)
		print(O.liste())                -- mises à mort et clips disponibles
		print(O.verifier())             -- contrôle de l'installation (fonctionne aussi en mode édition)
]]

local Players = game:GetService("Players")
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")
local StarterPlayer = game:GetService("StarterPlayer")

local O = {}

local function monstre()
	for _, m in ipairs(CollectionService:GetTagged("Monstre")) do
		return m
	end
	return nil
end

local function api()
	local s = ServerScriptService:FindFirstChild("MonstreServeur")
	return s and s:FindFirstChild("MonstreAPI")
end

local function plusProche(m)
	local hrp = m and m:FindFirstChild("HumanoidRootPart")
	if not hrp then
		return nil
	end
	local best, dmin = nil, math.huge
	local cands = {}
	for _, p in ipairs(Players:GetPlayers()) do
		if p.Character then
			table.insert(cands, p.Character)
		end
	end
	for _, v in ipairs(CollectionService:GetTagged("Survivant")) do
		table.insert(cands, v)
	end
	for _, c in ipairs(cands) do
		local h = c:FindFirstChildOfClass("Humanoid")
		local r = c:FindFirstChild("HumanoidRootPart")
		if h and r and h.Health > 0 and not c:GetAttribute("MA_EnMiseAMort") then
			local d = (r.Position - hrp.Position).Magnitude
			if d < dmin then
				best, dmin = c, d
			end
		end
	end
	return best
end

-- survivant d'essai : copie du StarterCharacter, étiquetée « Survivant », 6 studs devant le monstre
function O.victimeTest(position)
	local modeleSrc = StarterPlayer:FindFirstChild("StarterCharacter")
	if not modeleSrc then
		return nil, "pas de StarterPlayer.StarterCharacter (installez d'abord le survivant)"
	end
	local m = monstre()
	local c = modeleSrc:Clone()
	c.Name = "Victime_Essai"
	for _, d in ipairs(c:GetDescendants()) do
		if d:IsA("BaseScript") then
			d:Destroy()
		end
	end
	local pos, regard = position, Vector3.new(0, 0, 1)
	if not pos and m and m:FindFirstChild("HumanoidRootPart") then
		local cf = m.HumanoidRootPart.CFrame
		local avant = Vector3.new(cf.LookVector.X, 0, cf.LookVector.Z).Unit
		pos = cf.Position + avant * 6 - Vector3.new(0, 4.128, 0) -- HumanoidRootPart du survivant 3 studs au-dessus du sol
		regard = -avant
	end
	pos = pos or Vector3.new(0, 3, 0)
	c:PivotTo(CFrame.lookAt(pos, pos + regard))
	CollectionService:AddTag(c, "Survivant")
	c.Parent = workspace
	return c
end

function O.miseAMort(cle, victime)
	local a = api()
	if not a then
		return false, "MonstreServeur ne tourne pas (lancez le test avec F5)"
	end
	local m = monstre()
	victime = victime or plusProche(m)
	if not victime then
		return false, "aucune victime : O.victimeTest() en crée une"
	end
	task.spawn(function()
		a:Invoke("miseAMort", m, victime, cle)
	end)
	return true
end

function O.geste(cle)
	local a = api()
	if not a then
		return false, "MonstreServeur ne tourne pas"
	end
	return a:Invoke("geste", monstre(), cle)
end

function O.pause(actif)
	local a = api()
	if not a then
		return false, "MonstreServeur ne tourne pas"
	end
	return a:Invoke("pause", monstre(), actif)
end

function O.etat()
	local a = api()
	if not a then
		return nil
	end
	return a:Invoke("etat", monstre())
end

function O.liste()
	local dossier = ReplicatedStorage:FindFirstChild("Monstre")
	local d = dossier and require(dossier.MonstreDonnees)
	if not d then
		return "MonstreDonnees introuvable"
	end
	local lignes = { "Mises à mort :" }
	for _, s in ipairs(d.sequences) do
		local ph = {}
		for _, p in ipairs(s.phases) do
			table.insert(ph, p.clip)
		end
		table.insert(lignes, string.format("  %-16s %s (%s) -> %s", s.key, s.label, table.concat(ph, ", "), s.fin))
	end
	local cl = {}
	for k, _ in pairs(d.monstre) do
		table.insert(cl, k)
	end
	table.sort(cl)
	table.insert(lignes, "Clips du monstre : " .. table.concat(cl, ", "))
	return table.concat(lignes, "\n")
end

function O.verifier()
	local lignes = {}
	local okTout = true
	local function ligne(ok, texte)
		okTout = okTout and ok
		table.insert(lignes, (ok and "OK   " or "ERR  ") .. texte)
	end
	local m = monstre()
	ligne(m ~= nil, "modèle étiqueté « Monstre » : " .. (m and m:GetFullName() or "absent"))
	if m then
		local n = 0
		for _, d in ipairs(m:GetDescendants()) do
			if d:IsA("Motor6D") then
				n += 1
			end
		end
		ligne(n == 38, string.format("%d Motor6D (38 attendus)", n))
		local h = m:FindFirstChildOfClass("Humanoid")
		ligne(h ~= nil and math.abs(h.HipHeight - 5.928) < 0.01, "Humanoid, HipHeight " .. (h and string.format("%.3f", h.HipHeight) or "?"))
		ligne(m:FindFirstChild("VictimeAncrePart") ~= nil, "pièce VictimeAncrePart")
		ligne(m:FindFirstChild("Lueur") ~= nil, "lueur de la gueule")
	end
	local dossier = ReplicatedStorage:FindFirstChild("Monstre")
	ligne(dossier ~= nil, "ReplicatedStorage.Monstre")
	if dossier then
		for _, nom in ipairs({ "MonstreAnim", "MonstreConfig", "MonstreDonnees" }) do
			ligne(dossier:FindFirstChild(nom) ~= nil, nom)
		end
		local e = dossier:FindFirstChild("Effets")
		local n = e and #e:GetChildren() or 0
		ligne(n >= 6, string.format("gabarits de sang : %d (SANG_Flaque, SANG_Eclaboussure_1..3, SANG_Trainee, SANG_Ecran, SANG_Goutte)", n))
	end
	ligne(ServerScriptService:FindFirstChild("MonstreServeur") ~= nil, "ServerScriptService.MonstreServeur")
	local sps = StarterPlayer:FindFirstChildOfClass("StarterPlayerScripts")
	ligne(sps ~= nil and sps:FindFirstChild("MonstreClient") ~= nil, "StarterPlayerScripts.MonstreClient")
	table.insert(lignes, (StarterPlayer:FindFirstChild("StarterCharacter") and "OK   " or "info ")
		.. "StarterCharacter (survivant) : les victimes ne sont animées que si elles ont son rig")
	local cfg = dossier and dossier:FindFirstChild("MonstreConfig") and require(dossier.MonstreConfig)
	if cfg then
		local manquants = 0
		for k, v in pairs(cfg.SONS) do
			if k ~= "volume" and v == "" then
				manquants += 1
			end
		end
		table.insert(lignes, string.format("info sons sans identifiant : %d (voir monstre/roblox/sons/LISEZMOI.md)", manquants))
	end
	return table.concat(lignes, "\n"), okTout
end

return O
