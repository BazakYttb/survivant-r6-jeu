--[[
	MonstreAnim (ModuleScript, ReplicatedStorage.Monstre) : lecteur d'animations du monstre et de ses victimes.

	Les animations ne passent pas par des AnimationTrack : chaque client calcule la pose (pistes par articulation de
	MonstreDonnees) et écrit Motor6D.Transform à chaque image (RunService.PreSimulation, après l'Animator, donc par-dessus
	les animations du survivant). Rien n'est à publier sur Roblox, et la pose de chaque phase de mise à mort ne dépend que
	de (clip, heure de début sur l'horloge du serveur) : tous les clients voient la même chose au même moment.

	Format d'une piste (MonstreDonnees) : chaîne base64 d'enregistrements little-endian
		u16 temps (ms) ; i16 qx, qy, qz, qw (x 32767) ; puis i16 x, y, z (mm) si la piste a une translation.
	Interpolation : linéaire pour la translation, quaternion normalisé (nlerp) pour la rotation (comme le calcul de la
	réduction des clés, faite hors ligne avec une tolérance de 0,5 degré).
]]

local MonstreAnim = {}

local DONNEES -- table de MonstreDonnees (définie par MonstreAnim.init)
local CLIPS = { monstre = {}, victime = {} } -- clips décodés à la demande

------------------------------------------------------------------------------------------------------------
-- décodage
------------------------------------------------------------------------------------------------------------
local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local DEC = {}
for i = 1, 64 do
	DEC[string.byte(B64, i)] = i - 1
end

local function b64decode(s)
	local len = #s
	local pad = 0
	if string.sub(s, -2) == "==" then
		pad = 2
	elseif string.sub(s, -1) == "=" then
		pad = 1
	end
	local nbytes = (len // 4) * 3 - pad
	local buf = buffer.create(math.max(nbytes, 0))
	local o = 0
	for i = 1, len, 4 do
		local a, b, c, d = string.byte(s, i, i + 3)
		local x = DEC[a] * 262144 + DEC[b] * 4096 + (DEC[c] or 0) * 64 + (DEC[d] or 0)
		local b1, b2, b3 = x // 65536, (x // 256) % 256, x % 256
		if o < nbytes then
			buffer.writeu8(buf, o, b1)
		end
		if o + 1 < nbytes then
			buffer.writeu8(buf, o + 1, b2)
		end
		if o + 2 < nbytes then
			buffer.writeu8(buf, o + 2, b3)
		end
		o += 3
	end
	return buf, nbytes
end
MonstreAnim._b64decode = b64decode

local function decodeTrack(s, hasT)
	local buf, nbytes = b64decode(s)
	local rec = hasT and 16 or 10
	local n = nbytes // rec
	local T, Q = table.create(n), table.create(n * 4)
	local P = hasT and table.create(n * 3) or nil
	for i = 0, n - 1 do
		local o = i * rec
		T[i + 1] = buffer.readu16(buf, o) / 1000
		local qx, qy = buffer.readi16(buf, o + 2), buffer.readi16(buf, o + 4)
		local qz, qw = buffer.readi16(buf, o + 6), buffer.readi16(buf, o + 8)
		local m = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) -- quaternion quantifié : renormalisé
		Q[i * 4 + 1], Q[i * 4 + 2], Q[i * 4 + 3], Q[i * 4 + 4] = qx / m, qy / m, qz / m, qw / m
		if hasT then
			P[i * 3 + 1] = buffer.readi16(buf, o + 10) / 1000
			P[i * 3 + 2] = buffer.readi16(buf, o + 12) / 1000
			P[i * 3 + 3] = buffer.readi16(buf, o + 14) / 1000
		end
	end
	return { T = T, Q = Q, P = P, n = n }
end

function MonstreAnim.init(donnees)
	DONNEES = donnees
	CLIPS = { monstre = {}, victime = {} }
	return MonstreAnim
end

function MonstreAnim.donnees()
	return DONNEES
end

-- clip décodé : {key, name, length, loop, speed, markers, tracks = {nom = piste}}
function MonstreAnim.clip(rig, key)
	local cache = CLIPS[rig]
	local c = cache[key]
	if c then
		return c
	end
	local src = DONNEES[rig][key]
	if not src then
		return nil
	end
	c = {
		key = key,
		name = src.name,
		label = src.label,
		length = src.length,
		loop = src.loop,
		speed = src.speed,
		markers = src.markers or {},
		tracks = {},
	}
	for nom, s in pairs(src.tracks) do
		c.tracks[nom] = decodeTrack(s, src.trans and src.trans[nom] or false)
	end
	cache[key] = c
	return c
end

------------------------------------------------------------------------------------------------------------
-- échantillonnage
------------------------------------------------------------------------------------------------------------
local function findSeg(T, n, t)
	if t <= T[1] then
		return 1, 0
	end
	if t >= T[n] then
		return n, 0
	end
	local lo, hi = 1, n
	while hi - lo > 1 do
		local mid = (lo + hi) // 2
		if T[mid] <= t then
			lo = mid
		else
			hi = mid
		end
	end
	return lo, (t - T[lo]) / (T[lo + 1] - T[lo])
end

-- renvoie qx, qy, qz, qw, x, y, z
local function sampleTrack(tr, t)
	local i, u = findSeg(tr.T, tr.n, t)
	local Q = tr.Q
	local a = (i - 1) * 4
	local qx, qy, qz, qw = Q[a + 1], Q[a + 2], Q[a + 3], Q[a + 4]
	local x, y, z = 0, 0, 0
	local P = tr.P
	if P then
		local b = (i - 1) * 3
		x, y, z = P[b + 1], P[b + 2], P[b + 3]
	end
	if u > 0 then
		local c = a + 4
		local rx, ry, rz, rw = Q[c + 1], Q[c + 2], Q[c + 3], Q[c + 4]
		if qx * rx + qy * ry + qz * rz + qw * rw < 0 then
			rx, ry, rz, rw = -rx, -ry, -rz, -rw
		end
		qx, qy, qz, qw = qx + (rx - qx) * u, qy + (ry - qy) * u, qz + (rz - qz) * u, qw + (rw - qw) * u
		local m = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
		qx, qy, qz, qw = qx / m, qy / m, qz / m, qw / m
		if P then
			local b = i * 3
			x, y, z = x + (P[b + 1] - x) * u, y + (P[b + 2] - y) * u, z + (P[b + 3] - z) * u
		end
	end
	return qx, qy, qz, qw, x, y, z
end
MonstreAnim.sampleTrack = sampleTrack

-- temps local du clip (boucle ou maintien de la dernière pose)
local function clipTime(c, t)
	if c.loop then
		local L = c.length
		return t - math.floor(t / L) * L
	end
	return math.clamp(t, 0, c.length)
end
MonstreAnim.clipTime = clipTime

-- pose d'un clip : {nom = {qx, qy, qz, qw, x, y, z}}
function MonstreAnim.pose(rig, key, t)
	local c = MonstreAnim.clip(rig, key)
	local out = {}
	if not c then
		return out
	end
	local tt = clipTime(c, t)
	for nom, tr in pairs(c.tracks) do
		local qx, qy, qz, qw, x, y, z = sampleTrack(tr, tt)
		out[nom] = { qx, qy, qz, qw, x, y, z }
	end
	return out
end

local function toCFrame(p)
	return CFrame.new(p[5], p[6], p[7], p[1], p[2], p[3], p[4])
end
MonstreAnim.toCFrame = toCFrame

local IDENT = { 0, 0, 0, 1, 0, 0, 0 }

local function blend(a, b, w)
	a = a or IDENT
	b = b or IDENT
	if w >= 1 then
		return b
	elseif w <= 0 then
		return a
	end
	local bx, by, bz, bw = b[1], b[2], b[3], b[4]
	if a[1] * bx + a[2] * by + a[3] * bz + a[4] * bw < 0 then
		bx, by, bz, bw = -bx, -by, -bz, -bw
	end
	local qx, qy, qz, qw = a[1] + (bx - a[1]) * w, a[2] + (by - a[2]) * w, a[3] + (bz - a[3]) * w, a[4] + (bw - a[4]) * w
	local m = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
	return { qx / m, qy / m, qz / m, qw / m, a[5] + (b[5] - a[5]) * w, a[6] + (b[6] - a[6]) * w, a[7] + (b[7] - a[7]) * w }
end
MonstreAnim.blend = blend

------------------------------------------------------------------------------------------------------------
-- lecteur : deux couches (base = déplacement, action = gestes et mises à mort), fondus enchaînés
------------------------------------------------------------------------------------------------------------
local Lecteur = {}
Lecteur.__index = Lecteur

-- moteurs : {nom de piste = Motor6D}
function MonstreAnim.lecteur(rig, moteurs)
	return setmetatable({
		rig = rig,
		moteurs = moteurs,
		couches = { base = {}, action = {} },
		poidsAction = 0,
		cibleAction = 0,
		fonduAction = 0.2,
	}, Lecteur)
end

-- moteurs d'un modèle : monstre = Motor6D nommés comme les pièces ; victime = clé = nom de la Part1
function MonstreAnim.moteurs(modele, rig)
	local out = {}
	for _, d in ipairs(modele:GetDescendants()) do
		if d:IsA("Motor6D") then
			if rig == "monstre" then
				out[d.Name] = d
			elseif d.Part1 then
				out[d.Part1.Name] = d
			end
		end
	end
	return out
end

-- joue un clip sur une couche. opts : debut (horloge de référence), horloge (fonction), vitesse, fondu, decalage
function Lecteur:jouer(couche, key, opts)
	opts = opts or {}
	local c = MonstreAnim.clip(self.rig, key)
	if not c then
		return nil
	end
	local L = self.couches[couche]
	local cur = L.cur
	if cur and cur.key == key and not opts.relancer then
		cur.vitesse = opts.vitesse or cur.vitesse
		return cur
	end
	local horloge = opts.horloge or os.clock
	local now = horloge()
	local lec = {
		key = key,
		clip = c,
		horloge = horloge,
		debut = opts.debut or now,
		vitesse = opts.vitesse or 1,
		tAcc = opts.decalage or 0, -- temps accumulé (vitesse variable) pour la couche de base
		dernier = now,
		tPrec = nil,
	}
	if cur then
		L.prev = cur
		L.fonduDebut = now
		L.fondu = opts.fondu or 0.2
		L.horlogeFondu = horloge
	end
	L.cur = lec
	if couche == "action" then
		self.cibleAction = 1
		self.fonduAction = opts.fondu or 0.2
	end
	return lec
end

function Lecteur:arreterAction(fondu)
	self.cibleAction = 0
	self.fonduAction = fondu or 0.25
end

-- temps courant d'une lecture (avec vitesse) ; la couche de base accumule (vitesse qui change sans saut)
local function tempsLecture(lec, accumule)
	local now = lec.horloge()
	if accumule then
		lec.tAcc += (now - lec.dernier) * lec.vitesse
		lec.dernier = now
		return lec.tAcc
	end
	return (now - lec.debut) * lec.vitesse
end
MonstreAnim._tempsLecture = tempsLecture

local function evalLecture(self, lec, t)
	return MonstreAnim.pose(self.rig, lec.key, t)
end

-- marqueurs franchis entre deux instants (boucles comprises) : {instant du marqueur, nom, valeur, instant courant}
local function marqueursEntre(c, t0, t1, out)
	if not c.markers or #c.markers == 0 or t1 <= t0 then
		return
	end
	if not c.loop then
		for _, m in ipairs(c.markers) do
			if m[1] > t0 and m[1] <= t1 then
				table.insert(out, { m[1], m[2], m[3], t1 })
			end
		end
		return
	end
	local L = c.length
	local k0 = math.floor(t0 / L)
	local k1 = math.floor(t1 / L)
	for k = math.max(k0, k1 - 3), k1 do
		for _, m in ipairs(c.markers) do
			local tm = k * L + m[1]
			if tm > t0 and tm <= t1 then
				table.insert(out, { tm, m[2], m[3], t1 })
			end
		end
	end
end
MonstreAnim.marqueursEntre = marqueursEntre

-- calcule la pose, écrit les Transform ; renvoie les marqueurs franchis (déplacement et action courante)
function Lecteur:etape(dt)
	local poses = {}
	local base = self.couches.base
	local evts = {}
	if base.cur then
		local t = tempsLecture(base.cur, true)
		local p = evalLecture(self, base.cur, t)
		if base.cur.tPrec ~= nil then
			marqueursEntre(base.cur.clip, base.cur.tPrec, t, evts)
		end
		base.cur.tPrec = t
		if base.prev then
			local w = math.clamp((base.horlogeFondu() - base.fonduDebut) / math.max(base.fondu, 1e-3), 0, 1)
			if w >= 1 then
				base.prev = nil
			else
				local tp = tempsLecture(base.prev, true)
				local pp = evalLecture(self, base.prev, tp)
				for nom, _ in pairs(self.moteurs) do
					p[nom] = blend(pp[nom], p[nom], w)
				end
			end
		end
		poses = p
	end
	-- couche d'action
	local A = self.couches.action
	local step = (dt or 1 / 60) / math.max(self.fonduAction, 1e-3)
	if self.cibleAction > self.poidsAction then
		self.poidsAction = math.min(self.cibleAction, self.poidsAction + step)
	elseif self.cibleAction < self.poidsAction then
		self.poidsAction = math.max(self.cibleAction, self.poidsAction - step)
	end
	if A.cur and self.poidsAction > 0 then
		local lec = A.cur
		local t = tempsLecture(lec, false)
		local pa = evalLecture(self, lec, t)
		if A.prev then
			local w = math.clamp((A.horlogeFondu() - A.fonduDebut) / math.max(A.fondu, 1e-3), 0, 1)
			if w >= 1 then
				A.prev = nil
			else
				local tp = tempsLecture(A.prev, false)
				local pp = evalLecture(self, A.prev, tp)
				for nom, _ in pairs(self.moteurs) do
					pa[nom] = blend(pp[nom], pa[nom], w)
				end
			end
		end
		for nom, _ in pairs(self.moteurs) do
			poses[nom] = blend(poses[nom], pa[nom], self.poidsAction)
		end
		if lec.tPrec ~= nil then
			marqueursEntre(lec.clip, lec.tPrec, t, evts)
		elseif t >= 0 then
			marqueursEntre(lec.clip, -1e-6, t, evts)
		end
		lec.tPrec = t
		lec.fini = (not lec.clip.loop) and t >= lec.clip.length
	elseif A.cur and self.cibleAction == 0 and self.poidsAction <= 0 then
		A.cur = nil
		A.prev = nil
	end
	for nom, m in pairs(self.moteurs) do
		local p = poses[nom]
		m.Transform = p and toCFrame(p) or CFrame.identity
	end
	return evts
end

function Lecteur:action()
	return self.couches.action.cur
end

------------------------------------------------------------------------------------------------------------
-- cinématique directe (serveur : cadavre posé, points du corps pour le sang)
------------------------------------------------------------------------------------------------------------

-- CFrame monde de chaque pièce d'un modèle pour une pose donnée (racine : la pièce sans Motor6D parent).
-- pose : {nom de piste = {qx, qy, qz, qw, x, y, z}} ; cle : "monstre" (nom du Motor6D) ou "victime" (nom de la Part1)
function MonstreAnim.cinematique(modele, rig, pose, racineCF)
	local moteurs = MonstreAnim.moteurs(modele, rig)
	local parPart1 = {}
	for nom, m in pairs(moteurs) do
		if m.Part0 and m.Part1 then
			parPart1[m.Part1] = { m = m, nom = nom }
		end
	end
	local racine = modele:FindFirstChild("HumanoidRootPart")
	local out = {}
	if racine then
		out[racine] = racineCF or racine.CFrame
	end
	local function cfDe(part)
		if out[part] then
			return out[part]
		end
		local e = parPart1[part]
		if not e then
			out[part] = part.CFrame
			return out[part]
		end
		local p0 = cfDe(e.m.Part0)
		local p = pose[e.nom]
		local tr = p and toCFrame(p) or CFrame.identity
		out[part] = p0 * e.m.C0 * tr * e.m.C1:Inverse()
		return out[part]
	end
	for _, d in ipairs(modele:GetDescendants()) do
		if d:IsA("BasePart") then
			cfDe(d)
		end
	end
	return out
end

-- CFrame monde de la pièce VictimeAncre (où est soudé le HumanoidRootPart de la victime) au temps t d'un clip
function MonstreAnim.ancre(monstre, key, t)
	local hrp = monstre:FindFirstChild("HumanoidRootPart")
	local m = monstre:FindFirstChild("VictimeAncre", true)
	if not (hrp and m and m:IsA("Motor6D")) then
		return nil
	end
	local p = MonstreAnim.pose("monstre", key, t).VictimeAncre
	local tr = p and toCFrame(p) or CFrame.identity
	return hrp.CFrame * m.C0 * tr * m.C1:Inverse()
end

return MonstreAnim
