--[[
	Animate  --  animations et déplacements du survivant R6 articulé (LocalScript du personnage)
	=====================================================================================

	Remplace le script « Animate » par défaut de Roblox (il porte le même nom, donc Roblox
	n'ajoute pas le sien). Installé par SurvivantR6_Animations.lua dans le rig Anatomie_R6 (copie de
	référence) et dans StarterPlayer.StarterCharacterScripts : c'est cette copie qui tourne en jeu (un
	« Animate » rangé dans le StarterCharacter serait remplacé au lancement par celui de Roblox).
	Rig : R6 articulé (coudes et genoux, 10 pièces).

	Commandes (clavier AZERTY ou QWERTY) :
	  Maj gauche  : courir (maintenir)            C : s'accroupir / se relever
	  X           : s'allonger / se relever        R : radiographie (voir l'anatomie)
	Sur mobile, des boutons apparaissent (Courir, Accroupi, Allongé, Radio).
	Automatique : saut, chute, atterrissage, grimper (échelles, treillis), assis (sièges), outil
	tenu en main (le bras droit se lève, le reste du corps continue de s'animer).

	Animations : celles du dossier ReplicatedStorage.SurvivantAnimations.
	  - Une fois publiées (clic droit sur la KeyframeSequence > « Save to Roblox »), collez leur
	    identifiant dans ReplicatedStorage.SurvivantAnimations.AnimationIds.<clé>.
	  - Tant qu'un identifiant est vide, le jeu lancé depuis Studio joue directement la
	    KeyframeSequence (KeyframeSequenceProvider) ; dans un jeu publié, l'animation est ignorée
	    et un avertissement unique liste celles à publier.
]]

local CONFIG = {
	-- Vitesses (studs/s) par posture. Chaque animation de déplacement est faite pour une vitesse
	-- (CLIPS.<clé>.speed ci-dessous) et accélère ou ralentit avec le personnage (x0,45 à x1,8) :
	-- les bottes restent plantées au sol ; au-delà de x1,8 les pieds glissent.
	VITESSE = { marche = 6, course = 16, accroupi = 3, allonge = 1.5 },
	-- Touches.
	TOUCHE_COURSE = { Enum.KeyCode.LeftShift },
	-- true : la touche de course est réservée à la course (Maj gauche ne bascule plus le « Shift Lock » des
	-- joueurs qui l'ont activé ; il reste sur Maj droite). false : Maj gauche fait les deux.
	COURSE_PRIORITAIRE = true,
	TOUCHE_ACCROUPI = { Enum.KeyCode.C },
	TOUCHE_ALLONGE = { Enum.KeyCode.X },
	TOUCHE_RADIO = { Enum.KeyCode.R },
	BOUTONS_TACTILES = true,
	-- Radiographie : transparence de la peau, accessoires (bonnet, sac) masqués.
	TRANSPARENCE_RADIO = 0.72,
	-- Caméra (CameraOffset, repère du personnage : Y vers le haut, Z vers l'arrière).
	CAMERA = {
		debout = Vector3.new(0, 0, 0),
		accroupi = Vector3.new(0, -1.15, 0),
		allonge = Vector3.new(0, -2.3, -1.1),
	},
	-- Groupe de collision du torse et de la tête quand le personnage est allongé (créé par
	-- SurvivantR6_Animations.lua) : le corps au sol ne soulève pas le personnage.
	GROUPE_COLLISION = "SurvivantPosture",
	FONDU = 0.2,
	AIDE_A_L_ECRAN = true, -- rappel des touches pendant quelques secondes
}

--@@CLIPS@@

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ContextActionService = game:GetService("ContextActionService")

local character = script.Parent
local humanoid = character:WaitForChild("Humanoid")
local rootPart = character:WaitForChild("HumanoidRootPart")
local animator = humanoid:FindFirstChildOfClass("Animator")
if not animator then
	animator = Instance.new("Animator")
	animator.Parent = humanoid
end

------------------------------------------------------------------------------------------
-- Chargement des animations
------------------------------------------------------------------------------------------
local folder = ReplicatedStorage:FindFirstChild("SurvivantAnimations")
local idsFolder = folder and folder:FindFirstChild("AnimationIds")
local tracks, sources, missing = {}, {}, {}

local function normalizeId(id)
	id = tostring(id or "")
	id = string.gsub(id, "^%s+", "")
	id = string.gsub(id, "%s+$", "")
	if id == "" then
		return nil
	end
	if tonumber(id) then
		return "rbxassetid://" .. id
	end
	return id
end

-- Identifiant publié, sinon (Studio seulement) identifiant temporaire de la KeyframeSequence.
local function animationIdFor(key, clip)
	local v = idsFolder and idsFolder:FindFirstChild(key)
	local id = v and v:IsA("StringValue") and normalizeId(v.Value)
	if id then
		return id, "publiée"
	end
	local kfs = folder and folder:FindFirstChild(clip.name)
	if kfs and RunService:IsStudio() then
		local ok, tempId = pcall(function()
			return game:GetService("KeyframeSequenceProvider"):RegisterKeyframeSequence(kfs)
		end)
		if ok and tempId then
			return tempId, "studio"
		end
	end
	return nil, "absente"
end

local function loadTrack(key, id, looped, priority)
	local anim = Instance.new("Animation")
	anim.Name = key
	anim.AnimationId = id
	local ok, track = pcall(function()
		return animator:LoadAnimation(anim)
	end)
	if not ok or not track then
		return nil
	end
	pcall(function()
		track.Looped = looped
		track.Priority = priority
	end)
	return track
end

-- Animations dont la dernière pose est tenue jusqu'à ce que le contrôleur les arrête : chargées en boucle
-- (une animation non bouclée qui se termine s'efface d'elle-même en 0,3 s, Stop() n'y change plus rien).
local HOLD_AT_END = { jump = true }

for key, clip in pairs(CLIPS) do
	local id, source = animationIdFor(key, clip)
	sources[key] = source
	if id then
		tracks[key] = loadTrack(key, id, clip.loop or HOLD_AT_END[key] == true, Enum.AnimationPriority[clip.priority])
	end
	if not tracks[key] then
		table.insert(missing, clip.name)
	end
end
if #missing > 0 then
	table.sort(missing)
	if RunService:IsStudio() then
		warn("[Survivant] Animations introuvables : " .. table.concat(missing, ", ")
			.. ". Relancez SurvivantR6_Animations.lua dans la barre de commande de Studio.")
	else
		warn("[Survivant] Animations non publiées, ignorées dans ce jeu publié : " .. table.concat(missing, ", ")
			.. ". Dans Studio : clic droit sur chaque KeyframeSequence de ReplicatedStorage.SurvivantAnimations > "
			.. "« Save to Roblox… », puis collez l'identifiant dans SurvivantAnimations.AnimationIds.<clé>.")
	end
end

------------------------------------------------------------------------------------------
-- État
------------------------------------------------------------------------------------------
local stance = "debout" -- "debout" | "accroupi" | "allonge"
local sprintHeld, sprintToggled = false, false
local now = 0
local transitionEnd = -1 -- pendant une transition (s'allonger / se relever), le personnage ne bouge pas
local pendingStance = nil
local base = nil -- animation de fond en cours (repos, marche, ...)
local air = nil -- animation aérienne en cours (saut, chute)
local special = nil -- "climb" (grimper) ou "sit" (assis) : remplace l'animation de fond
local equippedTool = nil -- outil tenu en main (animation « tool » sur le bras droit)
local moving = false
local xray = false
local dead = false
local savedTransparency = {}
local airTime = 0
local jumpStart = 0
local jumpEnabled = nil
local collisionGroup = nil

local function play(key, fade, speed)
	local tr = tracks[key]
	if tr then
		tr:Play(fade or CONFIG.FONDU, 1, speed or 1)
	end
	return tr
end

local function stop(key, fade)
	local tr = key and tracks[key]
	if tr and tr.IsPlaying then
		if HOLD_AT_END[key] then
			tr:AdjustSpeed(0) -- pose figée pendant le fondu (la piste bouclée repartirait au début)
		end
		tr:Stop(fade or CONFIG.FONDU)
	end
end

local function setBase(key, speed)
	if base ~= key then
		stop(base)
		base = key
		if key then
			play(key, CONFIG.FONDU, speed)
		end
	elseif key and speed and tracks[key] then
		tracks[key]:AdjustSpeed(speed)
	end
end

local function setCollision(lying)
	local group = "Default"
	if collisionGroup == (lying and "lying" or "standing") then
		return
	end
	collisionGroup = lying and "lying" or "standing"
	if lying then
		local ok, registered = pcall(function()
			return game:GetService("PhysicsService"):IsCollisionGroupRegistered(CONFIG.GROUPE_COLLISION)
		end)
		if ok and registered then
			group = CONFIG.GROUPE_COLLISION
		end
	end
	for _, name in ipairs({ "Torso", "Head" }) do
		local p = character:FindFirstChild(name)
		if p and p:IsA("BasePart") then
			pcall(function()
				p.CollisionGroup = group
			end)
		end
	end
end

local function applySpeed()
	if now < transitionEnd then
		humanoid.WalkSpeed = 0
	elseif stance == "allonge" then
		humanoid.WalkSpeed = CONFIG.VITESSE.allonge
	elseif stance == "accroupi" then
		humanoid.WalkSpeed = CONFIG.VITESSE.accroupi
	elseif sprintHeld or sprintToggled then
		humanoid.WalkSpeed = CONFIG.VITESSE.course
	else
		humanoid.WalkSpeed = CONFIG.VITESSE.marche
	end
	local canJump = stance ~= "allonge" and now >= transitionEnd
	if canJump ~= jumpEnabled then
		jumpEnabled = canJump
		pcall(function()
			humanoid:SetStateEnabled(Enum.HumanoidStateType.Jumping, canJump)
		end)
	end
end

-- Outil en main : le bras droit le tient, sauf allongé, en transition ou en grimpant.
local function updateTool()
	local tr = tracks.tool
	if not tr then
		return
	end
	local want = equippedTool ~= nil and not dead and stance ~= "allonge" and now >= transitionEnd
		and special ~= "climb"
	if want and not tr.IsPlaying then
		play("tool", 0.15)
	elseif not want and tr.IsPlaying then
		stop("tool", 0.15)
	end
end

local function transition(key, nextStance)
	local clip = CLIPS[key]
	local tr = tracks[key]
	if tr and clip then
		tr:Play(0.12, 1, 1)
		transitionEnd = now + clip.length
	else
		transitionEnd = now
	end
	pendingStance = nextStance
end

local function setStance(target)
	if target == stance and not pendingStance then
		return
	end
	if now < transitionEnd then
		return
	end
	local from = stance
	if target == "allonge" then
		stance = "allonge"
		setCollision(true)
		transition("liedown", nil)
	elseif from == "allonge" then
		stance = target
		transition("getup", target)
	else
		stance = target
	end
	if stance ~= "debout" then
		sprintToggled = false
	end
	applySpeed()
	updateTool()
end

-- Grimper ou s'asseoir depuis une posture basse : le personnage se redresse aussitôt.
local function forceStanding()
	if stance ~= "debout" or pendingStance then
		stance = "debout"
		pendingStance = nil
		transitionEnd = now
		stop("liedown", 0.1)
		stop("getup", 0.1)
		setCollision(false)
		applySpeed()
	end
end

------------------------------------------------------------------------------------------
-- Radiographie (locale : seul ce joueur voit l'anatomie)
------------------------------------------------------------------------------------------
local function setXray(on)
	xray = on
	for _, d in ipairs(character:GetDescendants()) do
		local isSkin = d:IsA("BasePart") and d:GetAttribute("Anat_Peau") == true
		local isGear = d:IsA("BasePart") and d:GetAttribute("Anat_Accessoire") == true
		local isDecal = d:IsA("Decal") and d.Parent and d.Parent:IsA("BasePart") and d.Parent:GetAttribute("Anat_Peau") == true
		if isSkin or isGear or isDecal then
			if on then
				if savedTransparency[d] == nil then
					savedTransparency[d] = d.Transparency
				end
				d.Transparency = isGear and 1 or math.max(d.Transparency, CONFIG.TRANSPARENCE_RADIO)
			elseif savedTransparency[d] ~= nil then
				d.Transparency = savedTransparency[d]
				savedTransparency[d] = nil
			end
		end
	end
end

------------------------------------------------------------------------------------------
-- Commandes
------------------------------------------------------------------------------------------
local function isTouch(input)
	return input and input.UserInputType == Enum.UserInputType.Touch
end

local function onSprint(_, state, input)
	if isTouch(input) then
		if state == Enum.UserInputState.Begin then
			sprintToggled = not sprintToggled
			if sprintToggled and stance == "accroupi" then
				setStance("debout")
			end
		end
	else
		sprintHeld = state == Enum.UserInputState.Begin
		if sprintHeld and stance == "accroupi" then
			setStance("debout")
		end
	end
	applySpeed()
	return CONFIG.COURSE_PRIORITAIRE and Enum.ContextActionResult.Sink or Enum.ContextActionResult.Pass
end

local function onCrouch(_, state)
	if state == Enum.UserInputState.Begin then
		setStance(stance == "accroupi" and "debout" or "accroupi")
	end
	return Enum.ContextActionResult.Sink
end

local function onProne(_, state)
	if state == Enum.UserInputState.Begin then
		setStance(stance == "allonge" and "debout" or "allonge")
	end
	return Enum.ContextActionResult.Sink
end

local function onXray(_, state)
	if state == Enum.UserInputState.Begin then
		setXray(not xray)
	end
	return Enum.ContextActionResult.Sink
end

local ACTIONS = {
	{ "SurvivantCourse", onSprint, CONFIG.TOUCHE_COURSE, "Courir" },
	{ "SurvivantAccroupi", onCrouch, CONFIG.TOUCHE_ACCROUPI, "Accroupi" },
	{ "SurvivantAllonge", onProne, CONFIG.TOUCHE_ALLONGE, "Allongé" },
	{ "SurvivantRadio", onXray, CONFIG.TOUCHE_RADIO, "Radio" },
}
for _, a in ipairs(ACTIONS) do
	if a[2] == onSprint and CONFIG.COURSE_PRIORITAIRE then
		-- avant le Shift Lock de Roblox (priorité moyenne), qui ne reçoit plus la touche de course
		ContextActionService:BindActionAtPriority(a[1], a[2], CONFIG.BOUTONS_TACTILES,
			Enum.ContextActionPriority.High.Value, table.unpack(a[3]))
	else
		ContextActionService:BindAction(a[1], a[2], CONFIG.BOUTONS_TACTILES, table.unpack(a[3]))
	end
	pcall(function()
		ContextActionService:SetTitle(a[1], a[4])
	end)
end

------------------------------------------------------------------------------------------
-- États du Humanoid
------------------------------------------------------------------------------------------
local function stopAir(fade)
	if air then
		stop(air, fade)
		air = nil
	end
end

local function stopSpecial()
	if special then
		stop(special, 0.15)
		special = nil
		updateTool()
	end
end

local function climbRate(speed)
	local ref = CLIPS.climb and CLIPS.climb.speed or 5
	return math.clamp((speed or 0) / ref, -1.8, 1.8)
end

humanoid.StateChanged:Connect(function(_, new)
	if dead then
		return
	end
	local S = Enum.HumanoidStateType
	if new == S.Jumping then
		if stance == "accroupi" then
			setStance("debout")
		end
		stopSpecial()
		stop("land", 0.1)
		stopAir(0.1)
		air = "jump"
		jumpStart = now
		play("jump", 0.1)
	elseif new == S.Freefall then
		stopSpecial()
		stop("land", 0.1) -- reparti en l'air pendant l'atterrissage
		if air ~= "jump" then -- tombé d'un rebord ; après un saut, la chute prend le relais dans Heartbeat
			stopAir(0.1)
			air = "fall"
			play("fall", 0.3)
		end
	elseif new == S.Landed then
		stopAir(0.12)
		if stance == "debout" and airTime > 0.35 then
			play("land", 0.05)
		end
		airTime = 0
	elseif new == S.Climbing then
		forceStanding()
		stopAir(0.1)
		stopSpecial()
		special = "climb"
		setBase(nil)
		play("climb", 0.1)
		updateTool()
	elseif new == S.Seated then
		forceStanding()
		stopAir(0.1)
		stopSpecial()
		special = "sit"
		setBase(nil)
		play("sit", 0.3)
		updateTool()
	elseif new == S.Running or new == S.RunningNoPhysics or new == S.Swimming then
		stopSpecial()
		if air then
			stopAir(0.15)
		end
	elseif new == S.Dead then
		dead = true
		for _, tr in pairs(tracks) do
			pcall(function()
				tr:Stop(0.2)
			end)
		end
	end
end)

-- Vitesse de l'escalade (studs/s, négative en descendant) : l'animation suit, à l'envers en
-- descendant, figée à l'arrêt.
humanoid.Climbing:Connect(function(speed)
	if special == "climb" and tracks.climb then
		tracks.climb:AdjustSpeed(climbRate(speed))
	end
end)

character.ChildAdded:Connect(function(child)
	if child:IsA("Tool") then
		equippedTool = child
		updateTool()
	end
end)
character.ChildRemoved:Connect(function(child)
	if child:IsA("Tool") and child == equippedTool then
		equippedTool = character:FindFirstChildOfClass("Tool")
		updateTool()
	end
end)
equippedTool = character:FindFirstChildOfClass("Tool")

------------------------------------------------------------------------------------------
-- Boucle
------------------------------------------------------------------------------------------
local function horizontalSpeed()
	local v = rootPart.AssemblyLinearVelocity
	return Vector3.new(v.X, 0, v.Z).Magnitude
end

RunService.Heartbeat:Connect(function(dt)
	if dead then
		return
	end
	now = now + dt
	if pendingStance ~= nil and now >= transitionEnd then
		if pendingStance ~= "allonge" then
			setCollision(false)
		end
		pendingStance = nil
	end
	if pendingStance == nil and stance ~= "allonge" and now >= transitionEnd then
		setCollision(false)
	end
	applySpeed()
	updateTool()
	-- la chute prend le relais du saut
	if air then
		airTime = airTime + dt
	end
	if air == "jump" then
		local jt = tracks.jump
		local t = now - jumpStart
		-- au bout du saut, sa dernière pose est tenue : un saut normal (0,55 s en l'air) atterrit dessus
		if jt and jt.IsPlaying and jt.Speed ~= 0 and t >= CLIPS.jump.length - 0.06 then
			jt:AdjustSpeed(0)
			jt.TimePosition = math.max(0, CLIPS.jump.length - 0.001)
		end
		-- toujours en l'air peu après : la chute prend le relais
		if not jt or not jt.IsPlaying or t >= CLIPS.jump.length + 0.15 then
			air = "fall"
			play("fall", 0.25)
			stop("jump", 0.25)
		end
	end

	local speed = horizontalSpeed()
	moving = speed > (moving and 0.35 or 0.7)
	if special then
		setBase(nil) -- grimper / assis remplacent l'animation de fond
	else
		local key
		if stance == "allonge" then
			key = moving and "crawl" or "prone"
		elseif stance == "accroupi" then
			key = moving and "crouchwalk" or "crouch"
		elseif moving and (sprintHeld or sprintToggled) and speed > CONFIG.VITESSE.marche * 0.8 then
			key = "run"
		else
			key = moving and "walk" or "idle"
		end
		local ref = CLIPS[key].speed
		setBase(key, ref and math.clamp(speed / ref, 0.45, 1.8) or 1)
	end

	local target = CONFIG.CAMERA[stance] or Vector3.new()
	humanoid.CameraOffset = humanoid.CameraOffset:Lerp(target, 1 - math.exp(-dt * 8))
end)

humanoid.Died:Connect(function()
	dead = true
	for _, a in ipairs(ACTIONS) do
		pcall(function()
			ContextActionService:UnbindAction(a[1])
		end)
	end
end)

------------------------------------------------------------------------------------------
-- Rappel des commandes
------------------------------------------------------------------------------------------
if CONFIG.AIDE_A_L_ECRAN then
	local player = Players.LocalPlayer
	local gui = player and player:FindFirstChildOfClass("PlayerGui")
	if gui then
		local sg = Instance.new("ScreenGui")
		sg.Name = "SurvivantAide"
		sg.ResetOnSpawn = true
		local label = Instance.new("TextLabel")
		label.Name = "Texte"
		label.Size = UDim2.new(0, 520, 0, 34)
		label.Position = UDim2.new(0.5, -260, 1, -120)
		label.BackgroundTransparency = 0.35
		label.BackgroundColor3 = Color3.fromRGB(20, 22, 18)
		label.TextColor3 = Color3.fromRGB(235, 230, 214)
		label.Font = Enum.Font.GothamMedium
		label.TextSize = 15
		label.Text = "Maj : courir   ·   C : s'accroupir   ·   X : s'allonger   ·   R : radiographie"
		label.Parent = sg
		sg.Parent = gui
		task.delay(12, function()
			if sg.Parent then
				sg:Destroy()
			end
		end)
	end
end

setBase("idle", 1)
applySpeed()
updateTool()
