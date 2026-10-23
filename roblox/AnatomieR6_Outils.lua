--[[
	AnatomieR6_Outils.lua  --  petits utilitaires pour la BARRE DE COMMANDE de Roblox Studio
	=========================================================================================

	À utiliser après AnatomieR6_Setup.lua. Chaque outil est un bloc « do ... end » autonome :
	copiez UN bloc (de « do » à « end » inclus), modifiez les réglages en tête du bloc si besoin,
	collez-le dans la barre de commande (Affichage > Barre de commande) puis Entrée.

	Les pièces masquées ne sont pas supprimées : Transparency passe à 1 et l'ancienne valeur est
	mémorisée dans l'attribut « Anat_T0 » (l'attribut « Anat_Masque » indique l'état masqué),
	ce qui permet de les réafficher exactement comme avant. Ctrl+Z fonctionne aussi.

	Rig : R6 articulé (bras et jambes coupés au coude et au genou), 10 pièces : Head, Torso,
	RightUpperArm, RightLowerArm, LeftUpperArm, LeftLowerArm, RightUpperLeg, RightLowerLeg,
	LeftUpperLeg, LeftLowerLeg. Chaque pièce anatomique est rangée dans Anatomie.<pièce>.

	Tenue (« peau ») : les éléments visibles du survivant portent l'attribut « Anat_Peau » (les
	pièces Survivor_* du dossier Peau en mode "maillage", ou les blocs Roblox du rig en mode
	"blocs") et leur transparence normale est dans « Anat_TransparencePeau ». Le bonnet et le
	sac à dos portent en plus « Anat_Accessoire ».

	Catégories disponibles (attribut « Anat_Categorie » posé par le script d'installation) :
	bone, tooth, cartilage, disc, ligament, organ, brain, eye, vessel, nerve, muscle, gland.

	Outils :
	  [1] Tenue : afficher / masquer
	  [2] Radiographie : transparence de la tenue (0 = opaque, 0.7 = anatomie visible)
	  [3] Calvaria (calotte du crâne) : masquer / afficher -> voir le cerveau
	  [4] Catégorie(s) : masquer / afficher (ex. tous les organes, tous les vaisseaux)
	  [5] Isoler le squelette
	  [6] Tout réafficher
	  [7] Compter les pièces par catégorie et par pièce du rig
	  [8] Convertir le rig en StarterCharacter jouable
	  [9] Tenue : changer de mode (tenue importée <-> blocs Roblox)
]]

-- >>> OUTIL 1 : Tenue - afficher / masquer
do
	local RIG_NAME = "Anatomie_R6"
	local VISIBLE = false -- false = masquer la tenue, true = la réafficher

	local rig = workspace:FindFirstChild(RIG_NAME)
	if not rig then
		warn("Rig « " .. RIG_NAME .. " » introuvable dans le Workspace")
	else
		local n = 0
		for _, p in ipairs(rig:GetDescendants()) do
			if p:IsA("BasePart") and p:GetAttribute("Anat_Peau") then
				if VISIBLE then
					p.Transparency = p:GetAttribute("Anat_TransparencePeau") or 0
				else
					p.Transparency = 1
				end
				p:SetAttribute("Anat_Masque", (not VISIBLE) or nil)
				for _, c in ipairs(p:GetChildren()) do
					if c:IsA("Decal") then
						c.Transparency = p.Transparency
					end
				end
				n = n + 1
			end
		end
		print(string.format("Tenue %s (%d pièce(s))", VISIBLE and "affichée" or "masquée", n))
	end
end

-- >>> OUTIL 2 : Radiographie - transparence de la tenue
do
	local RIG_NAME = "Anatomie_R6"
	local TRANSPARENCE = 0.7 -- 0 = opaque (survivant), 0.7 = radiographie, 1 = invisible
	local MASQUER_ACCESSOIRES = true -- bonnet et sac à dos masqués dès que la tenue est transparente

	local rig = workspace:FindFirstChild(RIG_NAME)
	if not rig then
		warn("Rig « " .. RIG_NAME .. " » introuvable dans le Workspace")
	else
		local n = 0
		for _, p in ipairs(rig:GetDescendants()) do
			if p:IsA("BasePart") and p:GetAttribute("Anat_Peau") then
				local t = TRANSPARENCE
				if MASQUER_ACCESSOIRES and TRANSPARENCE > 0 and p:GetAttribute("Anat_Accessoire") then
					t = 1
				end
				p.Transparency = t
				p:SetAttribute("Anat_TransparencePeau", t)
				p:SetAttribute("Anat_Masque", nil)
				for _, c in ipairs(p:GetChildren()) do
					if c:IsA("Decal") then
						c.Transparency = t
					end
				end
				n = n + 1
			end
		end
		rig:SetAttribute("Anat_TransparencePeau", TRANSPARENCE)
		print(string.format("Transparence de la tenue : %s (%d pièce(s))", tostring(TRANSPARENCE), n))
	end
end

-- >>> OUTIL 3 : Calvaria - masquer / afficher (pour voir le cerveau)
do
	local RIG_NAME = "Anatomie_R6"
	local VISIBLE = false -- false = retirer la calotte crânienne, true = la remettre
	local NOMS = { "Head_Skull_Calvaria" } -- ajoutez d'autres noms de pièces si besoin

	local function setVisible(p, visible)
		if visible then
			if p:GetAttribute("Anat_Masque") then
				p.Transparency = p:GetAttribute("Anat_T0") or 0
				p:SetAttribute("Anat_Masque", nil)
			end
		else
			if not p:GetAttribute("Anat_Masque") then
				p:SetAttribute("Anat_T0", p.Transparency)
				p:SetAttribute("Anat_Masque", true)
			end
			p.Transparency = 1
		end
	end

	local rig = workspace:FindFirstChild(RIG_NAME)
	if not rig then
		warn("Rig « " .. RIG_NAME .. " » introuvable dans le Workspace")
	else
		for _, nom in ipairs(NOMS) do
			local p = rig:FindFirstChild(nom, true)
			if p and p:IsA("BasePart") then
				setVisible(p, VISIBLE)
				print(nom .. (VISIBLE and " affichée" or " masquée"))
			else
				warn(nom .. " introuvable dans le rig")
			end
		end
	end
end

-- >>> OUTIL 4 : Catégorie(s) - masquer / afficher
do
	local RIG_NAME = "Anatomie_R6"
	local CATEGORIES = { "organ" } -- ex. { "organ" }, { "vessel", "nerve" }, { "muscle" }
	local VISIBLE = false -- false = masquer, true = réafficher

	local function setVisible(p, visible)
		if visible then
			if p:GetAttribute("Anat_Masque") then
				p.Transparency = p:GetAttribute("Anat_T0") or 0
				p:SetAttribute("Anat_Masque", nil)
			end
		else
			if not p:GetAttribute("Anat_Masque") then
				p:SetAttribute("Anat_T0", p.Transparency)
				p:SetAttribute("Anat_Masque", true)
			end
			p.Transparency = 1
		end
	end

	local rig = workspace:FindFirstChild(RIG_NAME)
	local anat = rig and rig:FindFirstChild("Anatomie")
	if not anat then
		warn("Rig « " .. RIG_NAME .. " » (ou son dossier Anatomie) introuvable")
	else
		local wanted = {}
		for _, c in ipairs(CATEGORIES) do
			wanted[c] = true
		end
		local n = 0
		for _, p in ipairs(anat:GetDescendants()) do
			if p:IsA("BasePart") and wanted[p:GetAttribute("Anat_Categorie") or ""] then
				setVisible(p, VISIBLE)
				n = n + 1
			end
		end
		print(string.format("%d pièce(s) %s (%s)", n, VISIBLE and "affichée(s)" or "masquée(s)",
			table.concat(CATEGORIES, ", ")))
	end
end

-- >>> OUTIL 5 : Isoler le squelette
do
	local RIG_NAME = "Anatomie_R6"
	local INCLURE_ARTICULATIONS = false -- true : garde aussi cartilages, disques, ligaments
	local MASQUER_PEAU = true

	local function setVisible(p, visible)
		if visible then
			if p:GetAttribute("Anat_Masque") then
				p.Transparency = p:GetAttribute("Anat_T0") or 0
				p:SetAttribute("Anat_Masque", nil)
			end
		else
			if not p:GetAttribute("Anat_Masque") then
				p:SetAttribute("Anat_T0", p.Transparency)
				p:SetAttribute("Anat_Masque", true)
			end
			p.Transparency = 1
		end
	end

	local rig = workspace:FindFirstChild(RIG_NAME)
	local anat = rig and rig:FindFirstChild("Anatomie")
	if not anat then
		warn("Rig « " .. RIG_NAME .. " » (ou son dossier Anatomie) introuvable")
	else
		local keep = { bone = true, tooth = true }
		if INCLURE_ARTICULATIONS then
			keep.cartilage, keep.disc, keep.ligament = true, true, true
		end
		local shown, hidden = 0, 0
		for _, p in ipairs(anat:GetDescendants()) do
			if p:IsA("BasePart") then
				local k = keep[p:GetAttribute("Anat_Categorie") or ""] == true
				setVisible(p, k)
				if k then
					shown = shown + 1
				else
					hidden = hidden + 1
				end
			end
		end
		if MASQUER_PEAU then
			for _, p in ipairs(rig:GetDescendants()) do
				if p:IsA("BasePart") and p:GetAttribute("Anat_Peau") then
					p.Transparency = 1
					p:SetAttribute("Anat_Masque", true)
					for _, c in ipairs(p:GetChildren()) do
						if c:IsA("Decal") then
							c.Transparency = 1
						end
					end
				end
			end
		end
		print(string.format("Squelette isolé : %d pièce(s) visibles, %d masquée(s)", shown, hidden))
	end
end

-- >>> OUTIL 6 : Tout réafficher (anatomie + peau)
do
	local RIG_NAME = "Anatomie_R6"

	local rig = workspace:FindFirstChild(RIG_NAME)
	if not rig then
		warn("Rig « " .. RIG_NAME .. " » introuvable dans le Workspace")
	else
		local n = 0
		local anat = rig:FindFirstChild("Anatomie")
		if anat then
			for _, p in ipairs(anat:GetDescendants()) do
				if p:IsA("BasePart") and p:GetAttribute("Anat_Masque") then
					p.Transparency = p:GetAttribute("Anat_T0") or 0
					p:SetAttribute("Anat_Masque", nil)
					n = n + 1
				end
			end
		end
		for _, p in ipairs(rig:GetDescendants()) do
			if p:IsA("BasePart") and p:GetAttribute("Anat_Peau") then
				p.Transparency = p:GetAttribute("Anat_TransparencePeau") or 0
				p:SetAttribute("Anat_Masque", nil)
				for _, c in ipairs(p:GetChildren()) do
					if c:IsA("Decal") then
						c.Transparency = p.Transparency
					end
				end
			end
		end
		print(string.format("Tout est réaffiché (%d pièce(s) anatomiques rétablies)", n))
	end
end

-- >>> OUTIL 7 : Compter les pièces par catégorie et par pièce du rig
do
	local RIG_NAME = "Anatomie_R6"

	local rig = workspace:FindFirstChild(RIG_NAME)
	local anat = rig and rig:FindFirstChild("Anatomie")
	if not anat then
		warn("Rig « " .. RIG_NAME .. " » (ou son dossier Anatomie) introuvable")
	else
		local parCat, parMembre, total = {}, {}, 0
		for _, p in ipairs(anat:GetDescendants()) do
			if p:IsA("BasePart") then
				local c = p:GetAttribute("Anat_Categorie") or "?"
				local m = p.Parent and p.Parent.Name or "?"
				parCat[c] = (parCat[c] or 0) + 1
				parMembre[m] = (parMembre[m] or 0) + 1
				total = total + 1
			end
		end
		local function dump(t)
			local keys = {}
			for k in pairs(t) do
				table.insert(keys, k)
			end
			table.sort(keys)
			local out = {}
			for _, k in ipairs(keys) do
				table.insert(out, k .. " " .. tostring(t[k]))
			end
			return table.concat(out, ", ")
		end
		local peau = rig:FindFirstChild("Peau")
		local nPeau = 0
		if peau then
			for _, p in ipairs(peau:GetDescendants()) do
				if p:IsA("BasePart") then
					nPeau = nPeau + 1
				end
			end
		end
		print("Pièces anatomiques : " .. tostring(total))
		print("  par catégorie : " .. dump(parCat))
		print("  par pièce     : " .. dump(parMembre))
		print("Tenue : mode « " .. tostring(rig:GetAttribute("Anat_ModePeau") or "?") .. " », "
			.. tostring(nPeau) .. " pièce(s) Survivor_* dans le dossier Peau")
	end
end

-- >>> OUTIL 8 : Convertir le rig en StarterCharacter jouable
-- Copie le rig dans StarterPlayer sous le nom « StarterCharacter » (remplace l'ancien), désancre
-- toutes les pièces et remet les articulations au repos. Humanoid de type R15 (HipHeight 2) : c'est
-- ce type qui donne au rig articulé sa hauteur au-dessus du sol et la prise des outils (RightHand).
-- Les animations du survivant viennent du script « Animate » installé par SurvivantR6_Animations.lua :
-- celui du rig est copié dans StarterPlayer.StarterCharacterScripts (rangé dans le StarterCharacter, il
-- serait remplacé au lancement par l'« Animate » R15 par défaut de Roblox, qui tord les pièces du survivant).
-- Les pièces masquées avec les outils ci-dessus restent masquées dans le personnage jouable.
do
	local RIG_NAME = "Anatomie_R6"
	-- true : StarterPlayer.LoadCharacterAppearance = false, pour que Roblox n'ajoute pas les vêtements,
	-- accessoires et le visage de l'avatar du joueur par-dessus la tenue du survivant.
	local GARDER_TENUE = true

	local rig = workspace:FindFirstChild(RIG_NAME)
	local starterPlayer = game:GetService("StarterPlayer")
	if not rig then
		warn("Rig « " .. RIG_NAME .. " » introuvable dans le Workspace")
	else
		local old = starterPlayer:FindFirstChild("StarterCharacter")
		if old then
			old:Destroy()
		end
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
			hum.RigType = Enum.HumanoidRigType.R15
			if hum.HipHeight <= 0 then
				hum.HipHeight = 2
			end
			pcall(function()
				hum.AutomaticScalingEnabled = false
			end)
			pcall(function()
				hum.RequiresNeck = false
			end)
		end
		local animate = char:FindFirstChild("Animate")
		local scs = starterPlayer:FindFirstChildOfClass("StarterCharacterScripts")
		if animate and scs then
			local current = scs:FindFirstChild("Animate")
			if current then
				current:Destroy()
			end
			animate.Parent = scs
		end
		char.Parent = starterPlayer
		if GARDER_TENUE then
			starterPlayer.LoadCharacterAppearance = false
		end
		print(string.format("StarterCharacter créé dans StarterPlayer (%d pièces, toutes désancrées). "
			.. "Lancez Play pour jouer avec le personnage anatomique.", n))
		if not (scs and scs:FindFirstChild("Animate")) then
			warn("Pas de script « Animate » dans le rig : lancez SurvivantR6_Animations.lua pour les animations "
				.. "du survivant (les animations R15 par défaut ne conviennent pas à ce rig).")
		end
	end
end

-- >>> OUTIL 9 : Tenue - changer de mode (tenue importée <-> blocs Roblox)
do
	local RIG_NAME = "Anatomie_R6"
	local MODE = "blocs" -- "maillage" = tenue importée (Survivor_*), "blocs" = blocs Roblox du rig
	local VISAGE = true -- mode "blocs" : visage Roblox classique (decal « face ») sur la tête

	local rig = workspace:FindFirstChild(RIG_NAME)
	if not rig then
		warn("Rig « " .. RIG_NAME .. " » introuvable dans le Workspace")
	else
		local T = rig:GetAttribute("Anat_TransparencePeau") or 0
		local meshes = {}
		local peau = rig:FindFirstChild("Peau")
		if peau then
			for _, d in ipairs(peau:GetDescendants()) do
				local m = d:IsA("BasePart") and d:GetAttribute("Anat_Membre")
				if m then
					meshes[m] = meshes[m] or {}
					table.insert(meshes[m], d)
				end
			end
		end
		local nMesh, nBlock = 0, 0
		for _, name in ipairs({ "Head", "Torso", "RightUpperArm", "RightLowerArm", "LeftUpperArm", "LeftLowerArm",
			"RightUpperLeg", "RightLowerLeg", "LeftUpperLeg", "LeftLowerLeg" }) do
			local block = rig:FindFirstChild(name)
			if block and block:IsA("BasePart") then
				local list = meshes[name]
				local covered = false -- au moins une pièce de tenue (hors bonnet et sac) sur cette pièce
				for _, m in ipairs(list or {}) do
					if not m:GetAttribute("Anat_Accessoire") then
						covered = true
					end
				end
				local useMesh = MODE == "maillage" and covered
				block.Transparency = useMesh and 1 or T
				block:SetAttribute("Anat_Peau", (not useMesh) or nil)
				block:SetAttribute("Anat_TransparencePeau", T)
				block:SetAttribute("Anat_Masque", nil)
				for _, m in ipairs(list or {}) do
					local show = MODE == "maillage" -- bonnet et sac : visibles avec la tenue importée
					m.Transparency = show and T or 1
					m:SetAttribute("Anat_Peau", show or nil)
					m:SetAttribute("Anat_TransparencePeau", T)
					m:SetAttribute("Anat_Masque", nil)
				end
				if useMesh then
					nMesh = nMesh + 1
				else
					nBlock = nBlock + 1
				end
				if name == "Head" then
					local face = block:FindFirstChild("face")
					if not useMesh and VISAGE then
						if not (face and face:IsA("Decal")) then
							face = Instance.new("Decal")
							face.Name = "face"
							face.Parent = block
						end
						face.Texture = "rbxasset://textures/face.png"
						face.Face = Enum.NormalId.Front
						face.Transparency = T
					elseif face and face:IsA("Decal") then
						face:Destroy()
					end
				end
			end
		end
		local mode = (nBlock == 0 and "maillage") or (nMesh == 0 and "blocs") or "mixte"
		rig:SetAttribute("Anat_ModePeau", mode)
		if MODE == "maillage" and nMesh == 0 then
			warn("Aucune pièce Survivor_* dans le dossier Peau : importez le modèle avec sa tenue.")
		end
		print(string.format("Tenue en mode « %s » (%d pièce(s) en tenue importée, %d en blocs Roblox)", mode,
			nMesh, nBlock))
	end
end
