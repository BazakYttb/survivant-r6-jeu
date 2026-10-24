--[[
	rbx_mock.lua - émulation minimale de l'API Roblox (Studio, mode édition) pour tester hors ligne
	les scripts AnatomieR6_*.lua avec un interpréteur Luau autonome.

	Couvre : Vector3, CFrame (dont Lerp), Color3, Enum (listes fermées : une faute de frappe lève une
	erreur), Instance (arbre, propriétés typées et vérifiées par classe, attributs, Clone, Destroy),
	workspace:Raycast (boîtes orientées), RaycastParams, services Selection, ChangeHistoryService,
	StarterPlayer, ServerStorage, ScriptEditorService, require des ModuleScript, Animator (pistes,
	StepAnimations qui applique les poses des KeyframeSequences aux Motor6D). Écrire ou lire une
	propriété inconnue lève une erreur comme dans Roblox (« X is not a valid member of Part »).

	Copie étendue pour le monstre (monstre/roblox/test) : ordonnanceur task à coroutines et horloge simulée
	(task.wait / spawn / delay / defer, Signal:Wait), RunService.PreSimulation et BindToRenderStep, attributs avec
	GetAttributeChangedSignal, CollectionService, PathfindingService (ligne droite), Debris, sons, particules, lumières,
	SurfaceAppearance, interface (Frame, UIGradient...), effets de Lighting, caméra, Players (joueurs simulés),
	BindableFunction, types Vector2 / UDim / NumberRange / NumberSequence / ColorSequence / Random, CFrame.lookAt,
	Color3:Lerp, et un solveur de joints (MOCK.solveJoints : Motor6D avec Transform, Weld, WeldConstraint).
]]

local MOCK = {}

------------------------------------------------------------------------------------------
-- Vector3
------------------------------------------------------------------------------------------
local V3mt = {}
local function isV3(v)
	return type(v) == "table" and getmetatable(v) == V3mt
end
local function v3(x, y, z)
	return setmetatable({ X = x, Y = y, Z = z }, V3mt)
end
V3mt.__index = function(t, k)
	if k == "Magnitude" then
		return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z)
	elseif k == "Unit" then
		local m = math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z)
		if m == 0 then
			return v3(0 / 0, 0 / 0, 0 / 0)
		end
		return v3(t.X / m, t.Y / m, t.Z / m)
	elseif k == "Dot" then
		return function(a, b)
			assert(isV3(a) and isV3(b), "Vector3:Dot expects Vector3")
			return a.X * b.X + a.Y * b.Y + a.Z * b.Z
		end
	elseif k == "Cross" then
		return function(a, b)
			assert(isV3(a) and isV3(b), "Vector3:Cross expects Vector3")
			return v3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X)
		end
	elseif k == "Lerp" then
		return function(a, b, t2)
			return v3(a.X + (b.X - a.X) * t2, a.Y + (b.Y - a.Y) * t2, a.Z + (b.Z - a.Z) * t2)
		end
	elseif k == "Abs" then
		return function(a)
			return v3(math.abs(a.X), math.abs(a.Y), math.abs(a.Z))
		end
	end
	error(tostring(k) .. " is not a valid member of Vector3", 2)
end
V3mt.__newindex = function(_, k)
	error(tostring(k) .. " cannot be assigned to (Vector3 is immutable)", 2)
end
V3mt.__add = function(a, b)
	assert(isV3(a) and isV3(b), "attempt to perform arithmetic (add) on Vector3 and " .. type(b))
	return v3(a.X + b.X, a.Y + b.Y, a.Z + b.Z)
end
V3mt.__sub = function(a, b)
	assert(isV3(a) and isV3(b), "attempt to perform arithmetic (sub) on Vector3 and non-Vector3")
	return v3(a.X - b.X, a.Y - b.Y, a.Z - b.Z)
end
V3mt.__mul = function(a, b)
	if type(a) == "number" then
		return v3(a * b.X, a * b.Y, a * b.Z)
	elseif type(b) == "number" then
		return v3(a.X * b, a.Y * b, a.Z * b)
	elseif isV3(a) and isV3(b) then
		return v3(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
	end
	error("invalid Vector3 multiplication", 2)
end
V3mt.__div = function(a, b)
	if type(b) == "number" then
		return v3(a.X / b, a.Y / b, a.Z / b)
	elseif isV3(a) and isV3(b) then
		return v3(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
	end
	error("invalid Vector3 division", 2)
end
V3mt.__unm = function(a)
	return v3(-a.X, -a.Y, -a.Z)
end
V3mt.__eq = function(a, b)
	return a.X == b.X and a.Y == b.Y and a.Z == b.Z
end
V3mt.__tostring = function(a)
	return string.format("%g, %g, %g", a.X, a.Y, a.Z)
end
local Vector3 = {
	new = function(x, y, z)
		return v3(x or 0, y or 0, z or 0)
	end,
}
Vector3.zero = v3(0, 0, 0)
Vector3.one = v3(1, 1, 1)
Vector3.xAxis = v3(1, 0, 0)
Vector3.yAxis = v3(0, 1, 0)
Vector3.zAxis = v3(0, 0, 1)

------------------------------------------------------------------------------------------
-- CFrame (position + matrice 3x3 ligne par ligne, mêmes conventions que Roblox)
------------------------------------------------------------------------------------------
local CFmt = {}
local function isCF(v)
	return type(v) == "table" and getmetatable(v) == CFmt
end
local function cf(px, py, pz, m)
	return setmetatable({ _x = px, _y = py, _z = pz, _m = m }, CFmt)
end
local IDM = { 1, 0, 0, 0, 1, 0, 0, 0, 1 }
local function mmul(a, b)
	local r = {}
	for i = 0, 2 do
		for j = 0, 2 do
			r[i * 3 + j + 1] = a[i * 3 + 1] * b[j + 1] + a[i * 3 + 2] * b[3 + j + 1] + a[i * 3 + 3] * b[6 + j + 1]
		end
	end
	return r
end
local function mvec(m, x, y, z)
	return m[1] * x + m[2] * y + m[3] * z, m[4] * x + m[5] * y + m[6] * z, m[7] * x + m[8] * y + m[9] * z
end
local function mT(m)
	return { m[1], m[4], m[7], m[2], m[5], m[8], m[3], m[6], m[9] }
end
local CFrame = {}
-- matrice <-> quaternion {x, y, z, w}
local function quatToMat(q)
	local n = math.sqrt(q[1] * q[1] + q[2] * q[2] + q[3] * q[3] + q[4] * q[4])
	local qx, qy, qz, qw = q[1] / n, q[2] / n, q[3] / n, q[4] / n
	return {
		1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw),
		2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw),
		2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy),
	}
end
local function matToQuat(m)
	local tr = m[1] + m[5] + m[9]
	if tr > 0 then
		local s = math.sqrt(tr + 1) * 2
		return { (m[8] - m[6]) / s, (m[3] - m[7]) / s, (m[4] - m[2]) / s, 0.25 * s }
	elseif m[1] > m[5] and m[1] > m[9] then
		local s = math.sqrt(1 + m[1] - m[5] - m[9]) * 2
		return { 0.25 * s, (m[2] + m[4]) / s, (m[3] + m[7]) / s, (m[8] - m[6]) / s }
	elseif m[5] > m[9] then
		local s = math.sqrt(1 + m[5] - m[1] - m[9]) * 2
		return { (m[2] + m[4]) / s, 0.25 * s, (m[6] + m[8]) / s, (m[3] - m[7]) / s }
	end
	local s = math.sqrt(1 + m[9] - m[1] - m[5]) * 2
	return { (m[3] + m[7]) / s, (m[6] + m[8]) / s, 0.25 * s, (m[4] - m[2]) / s }
end
local function cfInverse(c)
	local t = mT(c._m)
	local x, y, z = mvec(t, -c._x, -c._y, -c._z)
	return cf(x, y, z, t)
end
CFmt.__index = function(c, k)
	local m = c._m
	if k == "Position" or k == "p" then
		return v3(c._x, c._y, c._z)
	elseif k == "X" then
		return c._x
	elseif k == "Y" then
		return c._y
	elseif k == "Z" then
		return c._z
	elseif k == "Rotation" then
		return cf(0, 0, 0, m)
	elseif k == "XVector" then
		return v3(m[1], m[4], m[7])
	elseif k == "YVector" then
		return v3(m[2], m[5], m[8])
	elseif k == "ZVector" then
		return v3(m[3], m[6], m[9])
	elseif k == "RightVector" then
		return v3(m[1], m[4], m[7])
	elseif k == "UpVector" then
		return v3(m[2], m[5], m[8])
	elseif k == "LookVector" then
		return v3(-m[3], -m[6], -m[9])
	elseif k == "Inverse" then
		return cfInverse
	elseif k == "GetComponents" or k == "components" then
		return function(s)
			local q = s._m
			return s._x, s._y, s._z, q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9]
		end
	elseif k == "ToEulerAnglesXYZ" then
		return function(s)
			local q = s._m
			local b = math.asin(math.clamp(q[3], -1, 1))
			local a = math.atan2(-q[6], q[9])
			local cc = math.atan2(-q[2], q[1])
			return a, b, cc
		end
	elseif k == "VectorToWorldSpace" then
		return function(s, v)
			return v3(mvec(s._m, v.X, v.Y, v.Z))
		end
	elseif k == "VectorToObjectSpace" then
		return function(s, v)
			return v3(mvec(mT(s._m), v.X, v.Y, v.Z))
		end
	elseif k == "PointToWorldSpace" then
		return function(s, v)
			return s * v
		end
	elseif k == "PointToObjectSpace" then
		return function(s, v)
			return cfInverse(s) * v
		end
	elseif k == "ToWorldSpace" then
		return function(s, o)
			return s * o
		end
	elseif k == "ToObjectSpace" then
		return function(s, o)
			return cfInverse(s) * o
		end
	elseif k == "Lerp" then
		-- position linéaire, rotation slerp (comme Roblox)
		return function(a, b, alpha)
			assert(isCF(a) and isCF(b) and type(alpha) == "number", "CFrame:Lerp(CFrame, number) expected")
			local qa, qb = matToQuat(a._m), matToQuat(b._m)
			local d = qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3] + qa[4] * qb[4]
			if d < 0 then
				qb = { -qb[1], -qb[2], -qb[3], -qb[4] }
				d = -d
			end
			local q = {}
			if d > 0.99995 then
				for i = 1, 4 do
					q[i] = qa[i] + (qb[i] - qa[i]) * alpha
				end
			else
				local th = math.acos(math.min(d, 1))
				local sa, sb = math.sin((1 - alpha) * th) / math.sin(th), math.sin(alpha * th) / math.sin(th)
				for i = 1, 4 do
					q[i] = qa[i] * sa + qb[i] * sb
				end
			end
			return cf(a._x + (b._x - a._x) * alpha, a._y + (b._y - a._y) * alpha, a._z + (b._z - a._z) * alpha,
				quatToMat(q))
		end
	end
	error(tostring(k) .. " is not a valid member of CFrame", 2)
end
CFmt.__newindex = function(_, k)
	error(tostring(k) .. " cannot be assigned to (CFrame is immutable)", 2)
end
CFmt.__mul = function(a, b)
	assert(isCF(a), "CFrame multiplication: left operand must be a CFrame")
	if isCF(b) then
		local x, y, z = mvec(a._m, b._x, b._y, b._z)
		return cf(a._x + x, a._y + y, a._z + z, mmul(a._m, b._m))
	elseif isV3(b) then
		local x, y, z = mvec(a._m, b.X, b.Y, b.Z)
		return v3(a._x + x, a._y + y, a._z + z)
	end
	error("invalid CFrame multiplication with " .. type(b), 2)
end
CFmt.__add = function(a, b)
	assert(isCF(a) and isV3(b), "CFrame + expects Vector3")
	return cf(a._x + b.X, a._y + b.Y, a._z + b.Z, a._m)
end
CFmt.__sub = function(a, b)
	assert(isCF(a) and isV3(b), "CFrame - expects Vector3")
	return cf(a._x - b.X, a._y - b.Y, a._z - b.Z, a._m)
end
CFmt.__tostring = function(c)
	local q = c._m
	return string.format("%g, %g, %g, %g, %g, %g, %g, %g, %g, %g, %g, %g", c._x, c._y, c._z, q[1], q[2], q[3],
		q[4], q[5], q[6], q[7], q[8], q[9])
end
CFmt.__eq = function(a, b)
	for i = 1, 9 do
		if a._m[i] ~= b._m[i] then
			return false
		end
	end
	return a._x == b._x and a._y == b._y and a._z == b._z
end

function CFrame.new(...)
	local n = select("#", ...)
	local a = { ... }
	if n == 0 then
		return cf(0, 0, 0, IDM)
	elseif n == 1 then
		assert(isV3(a[1]), "CFrame.new(Vector3) expected")
		return cf(a[1].X, a[1].Y, a[1].Z, IDM)
	elseif n == 2 and isV3(a[1]) and isV3(a[2]) then
		local look = (a[2] - a[1]).Unit
		local right = look:Cross(v3(0, 1, 0)).Unit
		local up = right:Cross(look)
		return CFrame.fromMatrix(a[1], right, up, -look)
	elseif n == 3 then
		return cf(a[1], a[2], a[3], IDM)
	elseif n == 7 then
		-- quaternion (qx, qy, qz, qw), normalisé comme le fait Roblox
		return cf(a[1], a[2], a[3], quatToMat({ a[4], a[5], a[6], a[7] }))
	elseif n == 12 then
		for i = 1, 12 do
			assert(type(a[i]) == "number", "CFrame.new: number expected")
		end
		return cf(a[1], a[2], a[3], { a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11], a[12] })
	end
	error("CFrame.new: invalid arguments (" .. n .. ")", 2)
end
function CFrame.lookAt(at, target, up)
	up = up or v3(0, 1, 0)
	local look = (target - at).Unit
	local right = look:Cross(up)
	if right.Magnitude < 1e-6 then
		right = look:Cross(v3(0, 0, 1))
	end
	right = right.Unit
	local upv = right:Cross(look)
	return CFrame.fromMatrix(at, right, upv, -look)
end
function CFrame.fromMatrix(pos, vx, vy, vz)
	assert(isV3(pos) and isV3(vx) and isV3(vy), "CFrame.fromMatrix: Vector3 expected")
	vz = vz or vx:Cross(vy).Unit
	return cf(pos.X, pos.Y, pos.Z, { vx.X, vy.X, vz.X, vx.Y, vy.Y, vz.Y, vx.Z, vy.Z, vz.Z })
end
function CFrame.Angles(rx, ry, rz)
	local ca, sa, cb, sb, cc, sc = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
	local mx = { 1, 0, 0, 0, ca, -sa, 0, sa, ca }
	local my = { cb, 0, sb, 0, 1, 0, -sb, 0, cb }
	local mz = { cc, -sc, 0, sc, cc, 0, 0, 0, 1 }
	return cf(0, 0, 0, mmul(mmul(mx, my), mz))
end
CFrame.fromEulerAnglesXYZ = CFrame.Angles
function CFrame.fromAxisAngle(axis, angle)
	local u = axis.Unit
	local c, s = math.cos(angle), math.sin(angle)
	local t = 1 - c
	local x, y, z = u.X, u.Y, u.Z
	return cf(0, 0, 0, {
		t * x * x + c, t * x * y - s * z, t * x * z + s * y,
		t * x * y + s * z, t * y * y + c, t * y * z - s * x,
		t * x * z - s * y, t * y * z + s * x, t * z * z + c,
	})
end
CFrame.identity = cf(0, 0, 0, IDM)

------------------------------------------------------------------------------------------
-- Color3
------------------------------------------------------------------------------------------
local C3mt = {}
C3mt.__index = function(_, k)
	if k == "Lerp" then
		return function(a, b, t)
			return setmetatable({ R = a.R + (b.R - a.R) * t, G = a.G + (b.G - a.G) * t, B = a.B + (b.B - a.B) * t }, C3mt)
		end
	end
	error(tostring(k) .. " is not a valid member of Color3", 2)
end
C3mt.__newindex = function(_, k)
	error(tostring(k) .. " cannot be assigned to", 2)
end
C3mt.__eq = function(a, b)
	return a.R == b.R and a.G == b.G and a.B == b.B
end
C3mt.__tostring = function(c)
	return string.format("%g, %g, %g", c.R, c.G, c.B)
end
local function isC3(v)
	return type(v) == "table" and getmetatable(v) == C3mt
end
local Color3 = {
	new = function(r, g, b)
		return setmetatable({ R = r or 0, G = g or 0, B = b or 0 }, C3mt)
	end,
	fromRGB = function(r, g, b)
		return setmetatable({ R = (r or 0) / 255, G = (g or 0) / 255, B = (b or 0) / 255 }, C3mt)
	end,
}

------------------------------------------------------------------------------------------
-- UDim2
------------------------------------------------------------------------------------------
local U2mt = { __index = function(_, k)
	error(tostring(k) .. " is not a valid member of UDim2", 2)
end }
local function isU2(v)
	return type(v) == "table" and getmetatable(v) == U2mt
end
local UDim2 = {
	new = function(xs, xo, ys, yo)
		return setmetatable({ XScale = xs or 0, XOffset = xo or 0, YScale = ys or 0, YOffset = yo or 0 }, U2mt)
	end,
}
UDim2.fromScale = function(x, y)
	return UDim2.new(x, 0, y, 0)
end
UDim2.fromOffset = function(x, y)
	return UDim2.new(0, x, 0, y)
end

------------------------------------------------------------------------------------------
-- Enum (listes fermées)
------------------------------------------------------------------------------------------
local ENUMS = {
	Material = { "Plastic", "SmoothPlastic", "Neon", "Wood", "WoodPlanks", "Marble", "Slate", "Concrete",
		"Granite", "Brick", "Pebble", "Cobblestone", "Rock", "Sandstone", "Basalt", "CrackedLava", "Limestone",
		"Pavement", "CorrodedMetal", "DiamondPlate", "Foil", "Metal", "Grass", "LeafyGrass", "Sand", "Fabric",
		"Snow", "Mud", "Ground", "Asphalt", "Salt", "Ice", "Glacier", "Glass", "ForceField", "Air", "Water",
		"Cardboard", "Carpet", "CeramicTiles", "ClayRoofTiles", "RoofShingles", "Leather", "Plaster", "Rubber" },
	RaycastFilterType = { "Exclude", "Include", "Blacklist", "Whitelist" },
	MeshType = { "Head", "Torso", "Wedge", "Prism", "Pyramid", "ParallelRamp", "RightAngleRamp", "CornerWedge",
		"Brick", "Sphere", "Cylinder", "FileMesh" },
	HumanoidRigType = { "R6", "R15" },
	RenderFidelity = { "Automatic", "Precise", "Performance" },
	CollisionFidelity = { "Default", "Hull", "Box", "PreciseConvexDecomposition" },
	SurfaceType = { "Smooth", "Glue", "Weld", "Studs", "Inlet", "Universal", "Hinge", "Motor", "SteppingMotor",
		"SmoothNoOutlines" },
	NormalId = { "Right", "Top", "Back", "Left", "Bottom", "Front" },
	FinishRecordingOperation = { "Cancel", "Commit", "Append" },
	HumanoidDisplayDistanceType = { "Viewer", "Subject", "None" },
	PartType = { "Ball", "Block", "Cylinder", "Wedge", "CornerWedge" },
	AnimationPriority = { "Idle", "Movement", "Action", "Action2", "Action3", "Action4", "Core" },
	PoseEasingStyle = { "Linear", "Constant", "Elastic", "Cubic", "Bounce", "CubicV2" },
	PoseEasingDirection = { "In", "Out", "InOut" },
	KeyCode = { "LeftShift", "RightShift", "LeftControl", "C", "X", "R", "Z", "Q", "S", "D", "W", "A", "E", "Space",
		"ButtonA", "ButtonB", "ButtonX", "ButtonY", "ButtonL3", "Unknown" },
	UserInputType = { "Keyboard", "Touch", "MouseButton1", "MouseButton2", "Gamepad1", "None" },
	UserInputState = { "Begin", "Change", "End", "Cancel", "None" },
	HumanoidStateType = { "FallingDown", "Running", "RunningNoPhysics", "Climbing", "StrafingNoPhysics", "Ragdoll",
		"GettingUp", "Jumping", "Landed", "Flying", "Freefall", "Seated", "PlatformStanding", "Dead", "Swimming",
		"Physics", "None" },
	ContextActionResult = { "Pass", "Sink" },
	Font = { "Legacy", "SourceSans", "Gotham", "GothamMedium", "GothamBold", "Arial" },
	AlphaMode = { "Overlay", "Transparency", "TintMask" },
	PathStatus = { "Success", "ClosestNoPath", "ClosestOutOfRange", "FailStartNotEmpty", "FailFinishNotEmpty", "NoPath" },
	PathWaypointAction = { "Walk", "Jump", "Custom" },
	CameraType = { "Fixed", "Attach", "Watch", "Track", "Follow", "Custom", "Scriptable", "Orbital" },
	RenderPriority = { "First", "Input", "Camera", "Character", "Last" },
}
local EImt = {
	__tostring = function(e)
		return "Enum." .. e.EnumType .. "." .. e.Name
	end,
}
local Enum = {}
for typeName, items in pairs(ENUMS) do
	local et = {}
	for i, name in ipairs(items) do
		et[name] = setmetatable({ Name = name, Value = i - 1, EnumType = typeName }, EImt)
	end
	setmetatable(et, {
		__index = function(_, k)
			error(tostring(k) .. " is not a valid member of \"Enum." .. typeName .. "\"", 2)
		end,
	})
	Enum[typeName] = et
end
setmetatable(Enum, {
	__index = function(_, k)
		error(tostring(k) .. " is not a valid member of \"Enum\" (non émulé)", 2)
	end,
})
local function isEnumItem(v, typeName)
	return type(v) == "table" and getmetatable(v) == EImt and (typeName == nil or v.EnumType == typeName)
end

------------------------------------------------------------------------------------------
-- Instances
------------------------------------------------------------------------------------------
local CLASSES = {
	Instance = { props = { Name = "string", Parent = "Instance?", Archivable = "boolean" }, abstract = true },
	PVInstance = { super = "Instance", abstract = true },
	BasePart = {
		super = "PVInstance",
		abstract = true,
		props = {
			Anchored = "boolean", CanCollide = "boolean", CanTouch = "boolean", CanQuery = "boolean",
			Massless = "boolean", CastShadow = "boolean", Locked = "boolean", Color = "Color3",
			Material = "Enum.Material", Reflectance = "number", Transparency = "number", Size = "Vector3",
			CFrame = "CFrame", Position = "Vector3", TopSurface = "Enum.SurfaceType",
			BottomSurface = "Enum.SurfaceType", LeftSurface = "Enum.SurfaceType",
			RightSurface = "Enum.SurfaceType", FrontSurface = "Enum.SurfaceType",
			BackSurface = "Enum.SurfaceType", AssemblyLinearVelocity = "Vector3", CollisionGroup = "string",
			LocalTransparencyModifier = "number",
		},
	},
	Part = { super = "BasePart", props = { Shape = "Enum.PartType" } },
	TriangleMeshPart = { super = "BasePart", abstract = true, props = { CollisionFidelity = "Enum.CollisionFidelity" } },
	MeshPart = {
		super = "TriangleMeshPart",
		props = { RenderFidelity = "Enum.RenderFidelity", MeshId = "string", TextureID = "string" },
	},
	Model = { super = "PVInstance", props = { PrimaryPart = "BasePart?" } },
	Workspace = { super = "Model", abstract = true, props = { Gravity = "number", CurrentCamera = "Instance?" } },
	Folder = { super = "Instance" },
	Humanoid = {
		super = "Instance",
		props = {
			RigType = "Enum.HumanoidRigType", DisplayDistanceType = "Enum.HumanoidDisplayDistanceType",
			HipHeight = "number", Health = "number", MaxHealth = "number", WalkSpeed = "number",
			JumpPower = "number", UseJumpPower = "boolean", CameraOffset = "Vector3", MoveDirection = "Vector3",
			AutoRotate = "boolean", AutomaticScalingEnabled = "boolean", RequiresNeck = "boolean",
			BreakJointsOnDeath = "boolean", PlatformStand = "boolean", Jump = "boolean",
		},
	},
	JointInstance = {
		super = "Instance",
		abstract = true,
		props = { Part0 = "BasePart?", Part1 = "BasePart?", C0 = "CFrame", C1 = "CFrame", Enabled = "boolean" },
	},
	Motor = { super = "JointInstance", props = { MaxVelocity = "number", DesiredAngle = "number" } },
	Motor6D = { super = "Motor", props = { Transform = "CFrame" } },
	Weld = { super = "JointInstance" },
	WeldConstraint = { super = "Instance", props = { Part0 = "BasePart?", Part1 = "BasePart?", Enabled = "boolean" } },
	Attachment = { super = "Instance", props = { CFrame = "CFrame", Visible = "boolean", WorldPosition = "any",
		WorldCFrame = "any" } },
	DataModelMesh = { super = "Instance", abstract = true, props = { Scale = "Vector3", Offset = "Vector3" } },
	FileMesh = { super = "DataModelMesh", abstract = true, props = { MeshId = "string", TextureId = "string" } },
	SpecialMesh = { super = "FileMesh", props = { MeshType = "Enum.MeshType" } },
	Decal = { super = "Instance", props = { Texture = "string", Face = "Enum.NormalId", Transparency = "number" } },
	StringValue = { super = "Instance", props = { Value = "string" } },
	Script = { super = "Instance", props = { Source = "string", Disabled = "boolean" } },
	DataModel = { super = "Instance", abstract = true },
	Selection = { super = "Instance", abstract = true },
	ChangeHistoryService = { super = "Instance", abstract = true },
	StarterPlayer = { super = "Instance", abstract = true },
	StarterCharacterScripts = { super = "Instance", abstract = true },
	ReplicatedStorage = { super = "Instance", abstract = true },
	ServerScriptService = { super = "Instance", abstract = true },
	UserInputService = { super = "Instance", abstract = true },
	ContextActionService = { super = "Instance", abstract = true },
	RunService = { super = "Instance", abstract = true },
	KeyframeSequenceProvider = { super = "Instance", abstract = true },
	ScriptEditorService = { super = "Instance", abstract = true },
	PhysicsService = { super = "Instance", abstract = true },
	Player = { super = "Instance", abstract = true, props = { Character = "Instance?", UserId = "number" } },
	PlayerGui = { super = "Instance", abstract = true },
	KeyframeSequence = { super = "Instance", props = { Loop = "boolean", Priority = "Enum.AnimationPriority" } },
	Keyframe = { super = "Instance", props = { Time = "number" } },
	Pose = { super = "Instance", props = { CFrame = "CFrame", Weight = "number", EasingStyle = "Enum.PoseEasingStyle",
		EasingDirection = "Enum.PoseEasingDirection" } },
	Animation = { super = "Instance", props = { AnimationId = "string" } },
	Animator = { super = "Instance" },
	LocalScript = { super = "Instance", props = { Source = "string", Disabled = "boolean" } },
	ModuleScript = { super = "Instance", props = { Source = "string" } },
	ObjectValue = { super = "Instance", props = { Value = "Instance?" } },
	Configuration = { super = "Instance" },
	Tool = { super = "Instance" },
	ScreenGui = { super = "Instance", props = { ResetOnSpawn = "boolean", Enabled = "boolean", IgnoreGuiInset = "boolean",
		DisplayOrder = "number" } },
	TextLabel = { super = "Instance", props = { Size = "UDim2", Position = "UDim2", BackgroundTransparency = "number",
		BackgroundColor3 = "Color3", TextColor3 = "Color3", Font = "Enum.Font", TextSize = "number", Text = "string" } },
	Players = { super = "Instance", abstract = true, props = { LoadCharacterAppearance = "boolean",
		CharacterAutoLoads = "boolean", LocalPlayer = "Instance?" } },
	ServerStorage = { super = "Instance", abstract = true },
	-- ajouts pour le monstre
	Terrain = { super = "BasePart", abstract = true },
	Sound = { super = "Instance", props = { SoundId = "string", Volume = "number", PlaybackSpeed = "number",
		RollOffMinDistance = "number", RollOffMaxDistance = "number", Looped = "boolean", IsPlaying = "boolean" } },
	ParticleEmitter = { super = "Instance", props = { Texture = "string", Color = "any", LightEmission = "number",
		LightInfluence = "number", Size = "any", Transparency = "any", Lifetime = "any", Speed = "any", SpreadAngle = "any",
		Acceleration = "Vector3", Drag = "number", Rate = "number", EmissionDirection = "Enum.NormalId", Enabled = "boolean" } },
	PointLight = { super = "Instance", props = { Range = "number", Brightness = "number", Color = "Color3", Shadows = "boolean" } },
	SurfaceAppearance = { super = "Instance", props = { AlphaMode = "Enum.AlphaMode", ColorMap = "string" } },
	GuiObject = { super = "Instance", abstract = true, props = { Size = "UDim2", Position = "UDim2",
		BackgroundColor3 = "Color3", BackgroundTransparency = "number", BorderSizePixel = "number", ZIndex = "number",
		Visible = "boolean" } },
	Frame = { super = "GuiObject" },
	UIGradient = { super = "Instance", props = { Rotation = "number", Transparency = "any", Color = "any" } },
	UICorner = { super = "Instance", props = { CornerRadius = "any" } },
	ColorCorrectionEffect = { super = "Instance", props = { Enabled = "boolean", TintColor = "Color3", Saturation = "number",
		Contrast = "number", Brightness = "number" } },
	BlurEffect = { super = "Instance", props = { Enabled = "boolean", Size = "number" } },
	BindableFunction = { super = "Instance", props = { OnInvoke = "any" } },
	Camera = { super = "Instance", props = { CFrame = "CFrame", FieldOfView = "number", CameraType = "Enum.CameraType",
		CameraSubject = "Instance?", ViewportSize = "any" } },
	StarterPlayerScripts = { super = "Instance" },
	PlayerScripts = { super = "Instance", abstract = true },
	Lighting = { super = "Instance", abstract = true },
	SoundService = { super = "Instance", abstract = true },
	Debris = { super = "Instance", abstract = true },
	CollectionService = { super = "Instance", abstract = true },
	PathfindingService = { super = "Instance", abstract = true },
}

local DEFAULTS = {
	BasePart = function(s)
		s.Anchored = false
		s.CanCollide = true
		s.CanTouch = true
		s.CanQuery = true
		s.Massless = false
		s.CastShadow = true
		s.Locked = false
		s.Color = Color3.new(0.64, 0.64, 0.64)
		s.Material = Enum.Material.Plastic
		s.Reflectance = 0
		s.Transparency = 0
		s.Size = v3(4, 1, 2)
		s.CFrame = CFrame.new()
		s.AssemblyLinearVelocity = v3(0, 0, 0)
		s.CollisionGroup = "Default"
		s.LocalTransparencyModifier = 0
		for _, f in ipairs({ "TopSurface", "BottomSurface", "LeftSurface", "RightSurface", "FrontSurface",
			"BackSurface" }) do
			s[f] = Enum.SurfaceType.Smooth
		end
	end,
	Part = function(s)
		s.Shape = Enum.PartType.Block
	end,
	TriangleMeshPart = function(s)
		s.CollisionFidelity = Enum.CollisionFidelity.Default
	end,
	MeshPart = function(s)
		s.RenderFidelity = Enum.RenderFidelity.Automatic
		s.MeshId = ""
		s.TextureID = ""
	end,
	Humanoid = function(s)
		s.RigType = Enum.HumanoidRigType.R15
		s.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.Viewer
		s.HipHeight = 0
		s.Health = 100
		s.MaxHealth = 100
		s.WalkSpeed = 16
		s.JumpPower = 50
		s.UseJumpPower = true
		s.CameraOffset = v3(0, 0, 0)
		s.MoveDirection = v3(0, 0, 0)
		s.AutoRotate = true
		s.AutomaticScalingEnabled = true
		s.RequiresNeck = true
		s.BreakJointsOnDeath = true
		s.PlatformStand = false
		s.Jump = false
	end,
	Attachment = function(s)
		s.CFrame = CFrame.new()
		s.Visible = false
	end,
	JointInstance = function(s)
		s.C0 = CFrame.new()
		s.C1 = CFrame.new()
		s.Enabled = true
	end,
	Motor = function(s)
		s.MaxVelocity = 0
		s.DesiredAngle = 0
	end,
	Motor6D = function(s)
		s.Transform = CFrame.new()
	end,
	WeldConstraint = function(s)
		s.Enabled = true
	end,
	DataModelMesh = function(s)
		s.Scale = v3(1, 1, 1)
		s.Offset = v3(0, 0, 0)
	end,
	FileMesh = function(s)
		s.MeshId = ""
		s.TextureId = ""
	end,
	SpecialMesh = function(s)
		s.MeshType = Enum.MeshType.Brick
	end,
	Decal = function(s)
		s.Texture = ""
		s.Face = Enum.NormalId.Front
		s.Transparency = 0
	end,
	StringValue = function(s)
		s.Value = ""
	end,
	KeyframeSequence = function(s)
		s.Loop = true
		s.Priority = Enum.AnimationPriority.Action
	end,
	Keyframe = function(s)
		s.Time = 0
	end,
	Pose = function(s)
		s.CFrame = CFrame.new()
		s.Weight = 1
		s.EasingStyle = Enum.PoseEasingStyle.Linear
		s.EasingDirection = Enum.PoseEasingDirection.In
	end,
	Animation = function(s)
		s.AnimationId = ""
	end,
	LocalScript = function(s)
		s.Source = ""
		s.Disabled = false
	end,
	ModuleScript = function(s)
		s.Source = ""
	end,
	ScreenGui = function(s)
		s.ResetOnSpawn = true
		s.Enabled = true
	end,
	Sound = function(s)
		s.SoundId = ""
		s.Volume = 0.5
		s.PlaybackSpeed = 1
		s.RollOffMinDistance = 10
		s.RollOffMaxDistance = 10000
		s.Looped = false
		s.IsPlaying = false
	end,
	ParticleEmitter = function(s)
		s.Texture = "rbxasset://textures/particles/sparkles_main.dds"
		s.LightEmission = 0
		s.LightInfluence = 0
		s.Acceleration = v3(0, 0, 0)
		s.Drag = 0
		s.Rate = 20
		s.EmissionDirection = Enum.NormalId.Top
		s.Enabled = true
	end,
	PointLight = function(s)
		s.Range = 8
		s.Brightness = 1
		s.Color = Color3.new(1, 1, 1)
		s.Shadows = false
	end,
	SurfaceAppearance = function(s)
		s.AlphaMode = Enum.AlphaMode.Overlay
		s.ColorMap = ""
	end,
	GuiObject = function(s)
		s.Size = UDim2.new(0, 100, 0, 100)
		s.Position = UDim2.new(0, 0, 0, 0)
		s.BackgroundColor3 = Color3.new(1, 1, 1)
		s.BackgroundTransparency = 0
		s.BorderSizePixel = 1
		s.ZIndex = 1
		s.Visible = true
	end,
	UIGradient = function(s)
		s.Rotation = 0
	end,
	ColorCorrectionEffect = function(s)
		s.Enabled = true
		s.TintColor = Color3.new(1, 1, 1)
		s.Saturation = 0
		s.Contrast = 0
		s.Brightness = 0
	end,
	BlurEffect = function(s)
		s.Enabled = true
		s.Size = 24
	end,
	Camera = function(s)
		s.CFrame = CFrame.new()
		s.FieldOfView = 70
		s.CameraType = Enum.CameraType.Custom
	end,
	TextLabel = function(s)
		s.Text = ""
		s.TextSize = 14
		s.BackgroundTransparency = 0
	end,
}

local function classChain(className)
	local chain = {}
	local c = className
	while c do
		table.insert(chain, 1, c)
		local def = CLASSES[c]
		assert(def, "unknown class " .. c)
		c = def.super
	end
	return chain
end

local function findPropType(className, prop)
	local c = className
	while c do
		local def = CLASSES[c]
		if def.props and def.props[prop] then
			return def.props[prop]
		end
		c = def.super
	end
	return nil
end

local INSTmt = {}
local STATE = setmetatable({}, { __mode = "k" }) -- proxy -> internal state
local function isInstance(v)
	return type(v) == "table" and getmetatable(v) == INSTmt
end
MOCK.isInstance = isInstance

local function classIsA(className, other)
	local c = className
	while c do
		if c == other then
			return true
		end
		c = CLASSES[c].super
	end
	return false
end

local function checkType(className, prop, t, value)
	local optional = string.sub(t, -1) == "?"
	if optional then
		t = string.sub(t, 1, -2)
	end
	if value == nil then
		if optional then
			return
		end
		error("Unable to assign nil to property " .. prop .. " of " .. className, 3)
	end
	local ok
	if t == "any" then
		ok = true
	elseif t == "string" then
		ok = type(value) == "string"
	elseif t == "number" then
		ok = type(value) == "number"
	elseif t == "boolean" then
		ok = type(value) == "boolean"
	elseif t == "Vector3" then
		ok = isV3(value)
	elseif t == "CFrame" then
		ok = isCF(value)
	elseif t == "Color3" then
		ok = isC3(value)
	elseif t == "UDim2" then
		ok = isU2(value)
	elseif string.sub(t, 1, 5) == "Enum." then
		ok = isEnumItem(value, string.sub(t, 6))
	else -- classe d'instance
		ok = isInstance(value) and classIsA(STATE[value].ClassName, t)
	end
	if not ok then
		error("Invalid value for " .. className .. "." .. prop .. " (expected " .. t .. ", got " .. tostring(value) .. ")", 3)
	end
end

local METHODS = {}

local function newInstance(className, isService)
	local def = CLASSES[className]
	if not def then
		error("Unable to create an Instance of type \"" .. tostring(className) .. "\"", 3)
	end
	if def.abstract and not isService then
		error("Unable to create an Instance of type \"" .. className .. "\"", 3)
	end
	local st = { ClassName = className, props = {}, children = {}, attributes = {}, parentLocked = false }
	local proxy = setmetatable({}, INSTmt)
	STATE[proxy] = st
	st.props.Name = className
	st.props.Archivable = true
	for _, c in ipairs(classChain(className)) do
		if DEFAULTS[c] then
			DEFAULTS[c](st.props)
		end
	end
	return proxy
end

local function removeChild(parent, child)
	local ch = STATE[parent].children
	for i = #ch, 1, -1 do
		if ch[i] == child then
			table.remove(ch, i)
			return
		end
	end
end

local EVENTS = {
	Instance = { ChildAdded = true, ChildRemoved = true, Destroying = true, DescendantAdded = true, DescendantRemoving = true },
	Humanoid = { StateChanged = true, Running = true, Died = true, Climbing = true, Seated = true, Jumping = true },
	RunService = { Heartbeat = true, RenderStepped = true, Stepped = true, PreSimulation = true, PostSimulation = true },
	UserInputService = { InputBegan = true, InputEnded = true, InputChanged = true },
	Player = { CharacterAdded = true, CharacterRemoving = true },
	Players = { PlayerAdded = true, PlayerRemoving = true },
	Sound = { Ended = true },
}
local function newSignal()
	local sig = { handlers = {} }
	function sig:Connect(fn)
		assert(type(fn) == "function", "Connect: function expected")
		local h = { fn = fn, connected = true }
		table.insert(self.handlers, h)
		return { Connected = true, Disconnect = function(c)
			h.connected = false
			c.Connected = false
		end }
	end
	function sig:Once(fn)
		local c
		c = self:Connect(function(...)
			c:Disconnect()
			fn(...)
		end)
		return c
	end
	function sig:Fire(...)
		local ws = self.waiters
		self.waiters = nil
		for _, h in ipairs(self.handlers) do
			if h.connected then
				if MOCK.resume then
					MOCK.resume(coroutine.create(h.fn), ...)
				else
					h.fn(...)
				end
			end
		end
		if ws then
			for _, co in ipairs(ws) do
				MOCK.resume(co, ...)
			end
		end
	end
	function sig:Wait()
		local co = coroutine.running()
		assert(co and coroutine.isyieldable(), "Signal:Wait hors d'une coroutine (émulation)")
		self.waiters = self.waiters or {}
		table.insert(self.waiters, co)
		return coroutine.yield()
	end
	return sig
end
MOCK.newSignal = newSignal
local function eventFor(st, k)
	local c = st.ClassName
	while c do
		local ev = EVENTS[c]
		if ev and ev[k] then
			st.signals = st.signals or {}
			st.signals[k] = st.signals[k] or newSignal()
			return st.signals[k]
		end
		c = CLASSES[c].super
	end
	return nil
end
local function fireEvent(inst, name, ...)
	local st = STATE[inst]
	if st and st.signals and st.signals[name] then
		st.signals[name]:Fire(...)
	end
end
MOCK.fire = fireEvent

INSTmt.__index = function(self, k)
	local st = STATE[self]
	if k == "ClassName" then
		return st.ClassName
	elseif k == "Parent" then
		return st.parent
	end
	if METHODS[k] then
		return METHODS[k]
	end
	local sig = eventFor(st, k)
	if sig then
		return sig
	end
	if classIsA(st.ClassName, "BasePart") and k == "Position" then
		return st.props.CFrame.Position
	end
	local t = findPropType(st.ClassName, k)
	if t then
		return st.props[k]
	end
	-- enfant de ce nom (comme Roblox : inst.ChildName)
	for _, c in ipairs(st.children) do
		if STATE[c].props.Name == k then
			return c
		end
	end
	error(tostring(k) .. " is not a valid member of " .. st.ClassName .. " \"" .. tostring(st.props.Name) .. "\"", 2)
end

INSTmt.__newindex = function(self, k, v)
	local st = STATE[self]
	if k == "Parent" then
		if st.parentLocked then
			error("The Parent property of " .. tostring(st.props.Name) .. " is locked", 2)
		end
		if v ~= nil and not isInstance(v) then
			error("Invalid Parent value", 2)
		end
		if v == self then
			error("Attempt to set " .. st.props.Name .. " as its own parent", 2)
		end
		if v ~= nil then
			local a = v
			while a do
				if a == self then
					error("Attempt to set parent of " .. st.props.Name .. " to a descendant", 2)
				end
				a = STATE[a].parent
			end
		end
		local oldParent = st.parent
		if oldParent then
			removeChild(oldParent, self)
		end
		st.parent = v
		if v then
			table.insert(STATE[v].children, self)
		end
		if oldParent and oldParent ~= v then
			fireEvent(oldParent, "ChildRemoved", self)
		end
		if v and oldParent ~= v then
			fireEvent(v, "ChildAdded", self)
			local a = v
			while a do
				if STATE[a].signals and STATE[a].signals.DescendantAdded then
					fireEvent(a, "DescendantAdded", self)
					for _, dd in ipairs(METHODS.GetDescendants(self)) do
						fireEvent(a, "DescendantAdded", dd)
					end
				end
				a = STATE[a].parent
			end
		end
		return
	end
	if k == "ClassName" then
		error("ClassName is read-only", 2)
	end
	if classIsA(st.ClassName, "BasePart") and k == "Position" then
		checkType(st.ClassName, k, "Vector3", v)
		st.props.CFrame = CFrame.new(v) * st.props.CFrame.Rotation
		return
	end
	local t = findPropType(st.ClassName, k)
	if not t then
		error(tostring(k) .. " is not a valid member of " .. st.ClassName .. " \"" .. tostring(st.props.Name) .. "\"", 2)
	end
	checkType(st.ClassName, k, t, v)
	if k == "Size" and isV3(v) then
		v = v3(math.max(v.X, 0.001), math.max(v.Y, 0.001), math.max(v.Z, 0.001))
	end
	st.props[k] = v
	if MOCK.onSet then
		MOCK.onSet(self, k, v)
	end
end

INSTmt.__tostring = function(self)
	return STATE[self].props.Name
end

function METHODS.IsA(self, className)
	return classIsA(STATE[self].ClassName, className)
end
function METHODS.GetChildren(self)
	local out = {}
	for i, c in ipairs(STATE[self].children) do
		out[i] = c
	end
	return out
end
function METHODS.GetDescendants(self)
	local out = {}
	local function rec(i)
		for _, c in ipairs(STATE[i].children) do
			table.insert(out, c)
			rec(c)
		end
	end
	rec(self)
	return out
end
function METHODS.FindFirstChild(self, name, recursive)
	assert(type(name) == "string", "FindFirstChild: string expected")
	local list = recursive and METHODS.GetDescendants(self) or STATE[self].children
	for _, c in ipairs(list) do
		if STATE[c].props.Name == name then
			return c
		end
	end
	return nil
end
function METHODS.WaitForChild(self, name)
	local c = METHODS.FindFirstChild(self, name)
	if not c then
		error("Infinite yield possible on WaitForChild(\"" .. tostring(name) .. "\") (émulation)", 2)
	end
	return c
end
function METHODS.FindFirstChildOfClass(self, className)
	for _, c in ipairs(STATE[self].children) do
		if STATE[c].ClassName == className then
			return c
		end
	end
	return nil
end
function METHODS.FindFirstChildWhichIsA(self, className, recursive)
	local list = recursive and METHODS.GetDescendants(self) or STATE[self].children
	for _, c in ipairs(list) do
		if classIsA(STATE[c].ClassName, className) then
			return c
		end
	end
	return nil
end
function METHODS.FindFirstAncestorOfClass(self, className)
	local a = STATE[self].parent
	while a do
		if STATE[a].ClassName == className then
			return a
		end
		a = STATE[a].parent
	end
	return nil
end
function METHODS.FindFirstAncestorWhichIsA(self, className)
	local a = STATE[self].parent
	while a do
		if classIsA(STATE[a].ClassName, className) then
			return a
		end
		a = STATE[a].parent
	end
	return nil
end
function METHODS.IsDescendantOf(self, other)
	assert(other == nil or isInstance(other), "IsDescendantOf: Instance expected")
	local a = STATE[self].parent
	while a do
		if a == other then
			return true
		end
		a = STATE[a].parent
	end
	return false
end
function METHODS.IsAncestorOf(self, other)
	return METHODS.IsDescendantOf(other, self)
end
function METHODS.GetFullName(self)
	local names = {}
	local a = self
	while a and STATE[a].ClassName ~= "DataModel" do
		table.insert(names, 1, STATE[a].props.Name)
		a = STATE[a].parent
	end
	return table.concat(names, ".")
end
function METHODS.Destroy(self)
	local st = STATE[self]
	for _, c in ipairs(METHODS.GetChildren(self)) do
		METHODS.Destroy(c)
	end
	if st.parent then
		removeChild(st.parent, self)
	end
	st.parent = nil
	st.parentLocked = true
	st.destroyed = true
	MOCK.destroyedCount = (MOCK.destroyedCount or 0) + 1
end
function METHODS.ClearAllChildren(self)
	for _, c in ipairs(METHODS.GetChildren(self)) do
		METHODS.Destroy(c)
	end
end
function METHODS.SetAttribute(self, name, value)
	assert(type(name) == "string" and #name <= 100 and string.match(name, "^[%w_]+$"),
		"SetAttribute: invalid attribute name " .. tostring(name))
	assert(string.sub(name, 1, 3) ~= "RBX", "SetAttribute: reserved name")
	local tv = type(value)
	assert(value == nil or tv == "string" or tv == "number" or tv == "boolean" or isV3(value) or isC3(value)
		or isCF(value), "SetAttribute: unsupported type " .. tv)
	local old = STATE[self].attributes[name]
	STATE[self].attributes[name] = value
	if old ~= value then
		local st = STATE[self]
		if st.attrSignals and st.attrSignals[name] then
			st.attrSignals[name]:Fire()
		end
	end
end
function METHODS.GetAttributeChangedSignal(self, name)
	local st = STATE[self]
	st.attrSignals = st.attrSignals or {}
	st.attrSignals[name] = st.attrSignals[name] or MOCK.newSignal()
	return st.attrSignals[name]
end
function METHODS.FindFirstAncestor(self, name)
	local a = STATE[self].parent
	while a do
		if STATE[a].props.Name == name then
			return a
		end
		a = STATE[a].parent
	end
	return nil
end
function METHODS.GetAttribute(self, name)
	return STATE[self].attributes[name]
end
function METHODS.GetAttributes(self)
	local out = {}
	for k, v in pairs(STATE[self].attributes) do
		out[k] = v
	end
	return out
end
function METHODS.GetPivot(self)
	local st = STATE[self]
	if classIsA(st.ClassName, "BasePart") then
		return st.props.CFrame
	end
	if st.props.PrimaryPart then
		return STATE[st.props.PrimaryPart].props.CFrame
	end
	local cfB = METHODS.GetBoundingBox(self)
	return cfB
end
function METHODS.GetBoundingBox(self)
	assert(classIsA(STATE[self].ClassName, "Model"), "GetBoundingBox: Model expected")
	local minV, maxV
	for _, d in ipairs(METHODS.GetDescendants(self)) do
		if classIsA(STATE[d].ClassName, "BasePart") then
			local c = STATE[d].props.CFrame
			local s = STATE[d].props.Size / 2
			for _, sx in ipairs({ -1, 1 }) do
				for _, sy in ipairs({ -1, 1 }) do
					for _, sz in ipairs({ -1, 1 }) do
						local p = c * v3(sx * s.X, sy * s.Y, sz * s.Z)
						if not minV then
							minV, maxV = p, p
						else
							minV = v3(math.min(minV.X, p.X), math.min(minV.Y, p.Y), math.min(minV.Z, p.Z))
							maxV = v3(math.max(maxV.X, p.X), math.max(maxV.Y, p.Y), math.max(maxV.Z, p.Z))
						end
					end
				end
			end
		end
	end
	if not minV then
		return CFrame.new(), v3(0, 0, 0)
	end
	return CFrame.new((minV + maxV) / 2), maxV - minV
end
function METHODS.Clone(self)
	local map = {}
	local function copy(i)
		local st = STATE[i]
		if not st.props.Archivable then
			return nil
		end
		local c = newInstance(st.ClassName, true)
		map[i] = c
		local cs = STATE[c]
		for k, v in pairs(st.props) do
			cs.props[k] = v
		end
		for k, v in pairs(st.attributes) do
			cs.attributes[k] = v
		end
		if st.tags then
			cs.tags = {}
			for k, v in pairs(st.tags) do
				cs.tags[k] = v
			end
		end
		for _, ch in ipairs(st.children) do
			local cc = copy(ch)
			if cc then
				STATE[cc].parent = c
				table.insert(cs.children, cc)
			end
		end
		return c
	end
	local root = copy(self)
	-- Remappe les références internes (Part0, Part1, PrimaryPart...).
	for orig, c in pairs(map) do
		local cs = STATE[c]
		for k, v in pairs(cs.props) do
			if isInstance(v) and map[v] then
				cs.props[k] = map[v]
			end
		end
	end
	return root
end

local Instance = {
	new = function(className, parent)
		local inst = newInstance(className, false)
		if parent then
			inst.Parent = parent
		end
		return inst
	end,
}

------------------------------------------------------------------------------------------
-- DataModel, services, Raycast
------------------------------------------------------------------------------------------
local game = newInstance("DataModel", true)
STATE[game].props.Name = "Game"
local workspaceInst = newInstance("Workspace", true)
STATE[workspaceInst].props.Name = "Workspace"
workspaceInst.Parent = game

local services = { Workspace = workspaceInst }
local function makeService(className)
	local s = newInstance(className, true)
	STATE[s].props.Name = className
	s.Parent = game
	services[className] = s
	return s
end
local selectionService = makeService("Selection")
local chsService = makeService("ChangeHistoryService")
makeService("StarterPlayer")
local playersService
do
	local pl = makeService("Players")
	pl.LoadCharacterAppearance = true
	pl.CharacterAutoLoads = true
	playersService = pl
end
for _, name in ipairs({ "Lighting", "SoundService", "Debris", "CollectionService", "PathfindingService" }) do
	makeService(name)
end
for _, name in ipairs({ "ReplicatedStorage", "ServerScriptService", "UserInputService", "ContextActionService",
	"RunService", "KeyframeSequenceProvider", "PhysicsService", "ScriptEditorService" }) do
	makeService(name)
end
do
	local scs = newInstance("StarterCharacterScripts", true)
	STATE[scs].props.Name = "StarterCharacterScripts"
	scs.Parent = services.StarterPlayer
	local lp = newInstance("Player", true)
	STATE[lp].props.Name = "Testeur"
	lp.Parent = playersService
	local gui = newInstance("PlayerGui", true)
	STATE[gui].props.Name = "PlayerGui"
	gui.Parent = lp
	playersService.LocalPlayer = lp
	MOCK.localPlayer = lp
end

-- Exécution (jeu) : horloge, animations, actions, groupes de collision
MOCK.isStudio = true
MOCK.clock = 0
MOCK.tracks = {}
MOCK.tempKfs = {}
MOCK.actions = {}
MOCK.delays = {}
MOCK.collision = { groups = { Default = true }, collidable = {} }
local tempCounter = 0

function METHODS.IsStudio(self)
	assert(self == services.RunService, "IsStudio is not a valid member")
	return MOCK.isStudio
end
function METHODS.IsRunning(self)
	assert(self == services.RunService, "IsRunning is not a valid member")
	return true
end
function METHODS.RegisterKeyframeSequence(self, kfs)
	assert(self == services.KeyframeSequenceProvider, "RegisterKeyframeSequence is not a valid member")
	assert(isInstance(kfs) and STATE[kfs].ClassName == "KeyframeSequence", "RegisterKeyframeSequence: KeyframeSequence expected")
	if not MOCK.isStudio then
		error("RegisterKeyframeSequence only works in Studio (émulation)", 2)
	end
	tempCounter = tempCounter + 1
	local id = "rbxtemp://" .. tempCounter
	MOCK.tempKfs[id] = kfs
	return id
end
function METHODS.RegisterCollisionGroup(self, name)
	assert(self == services.PhysicsService, "RegisterCollisionGroup is not a valid member")
	assert(type(name) == "string" and #name > 0, "RegisterCollisionGroup: name expected")
	MOCK.collision.groups[name] = true
end
function METHODS.IsCollisionGroupRegistered(self, name)
	assert(self == services.PhysicsService, "IsCollisionGroupRegistered is not a valid member")
	return MOCK.collision.groups[name] == true
end
function METHODS.CollisionGroupSetCollidable(self, a, b, collidable)
	assert(self == services.PhysicsService, "CollisionGroupSetCollidable is not a valid member")
	assert(MOCK.collision.groups[a] and MOCK.collision.groups[b], "CollisionGroupSetCollidable: unknown group")
	assert(type(collidable) == "boolean", "CollisionGroupSetCollidable: boolean expected")
	MOCK.collision.collidable[a .. "|" .. b] = collidable
	MOCK.collision.collidable[b .. "|" .. a] = collidable
end
function METHODS.BindAction(self, name, fn, touch, ...)
	assert(self == services.ContextActionService, "BindAction is not a valid member")
	assert(type(name) == "string" and type(fn) == "function" and type(touch) == "boolean", "BindAction: bad arguments")
	local keys = { ... }
	for _, k in ipairs(keys) do
		assert(isEnumItem(k), "BindAction: Enum inputs expected")
	end
	MOCK.actions[name] = { fn = fn, touch = touch, keys = keys }
end
function METHODS.UnbindAction(self, name)
	assert(self == services.ContextActionService, "UnbindAction is not a valid member")
	MOCK.actions[name] = nil
end
function METHODS.SetTitle(self, name, title)
	assert(self == services.ContextActionService, "SetTitle is not a valid member")
	assert(type(title) == "string", "SetTitle: string expected")
	if MOCK.actions[name] then
		MOCK.actions[name].title = title
	end
end
function METHODS.SetPosition(self, name, pos)
	assert(self == services.ContextActionService, "SetPosition is not a valid member")
	assert(isU2(pos), "SetPosition: UDim2 expected")
end
function METHODS.SetStateEnabled(self, state, enabled)
	assert(STATE[self].ClassName == "Humanoid", "SetStateEnabled is not a valid member")
	assert(isEnumItem(state, "HumanoidStateType") and type(enabled) == "boolean", "SetStateEnabled: bad arguments")
	local st = STATE[self]
	st.stateEnabled = st.stateEnabled or {}
	st.stateEnabled[state.Name] = enabled
end
function METHODS.GetStateEnabled(self, state)
	local st = STATE[self]
	return not (st.stateEnabled and st.stateEnabled[state.Name] == false)
end
function METHODS.GetState(self)
	return STATE[self].state or Enum.HumanoidStateType.Running
end
function METHODS.ChangeState(self, state)
	local st = STATE[self]
	local old = st.state or Enum.HumanoidStateType.Running
	st.state = state
	fireEvent(self, "StateChanged", old, state)
end
local function newTrack(anim)
	local id = STATE[anim].props.AnimationId
	local kfs = MOCK.tempKfs[id]
	local length = 1
	if kfs then
		length = 0
		for _, kf in ipairs(METHODS.GetChildren(kfs)) do
			length = math.max(length, STATE[kf].props.Time)
		end
	end
	local tr = { Animation = anim, AnimationId = id, Length = length, IsPlaying = false, Looped = false,
		Priority = Enum.AnimationPriority.Core, Speed = 1, TimePosition = 0, WeightTarget = 1, plays = 0, stops = 0,
		kfs = kfs }
	function tr:Play(fade, weight, speed)
		self.IsPlaying = true
		self.TimePosition = 0
		self.Speed = speed or 1
		self.plays = self.plays + 1
		self.lastFade = fade
	end
	function tr:Stop(fade)
		self.IsPlaying = false
		self.stops = self.stops + 1
	end
	function tr:AdjustSpeed(sp)
		self.Speed = sp
	end
	function tr:AdjustWeight(w)
		self.WeightTarget = w
	end
	table.insert(MOCK.tracks, tr)
	return tr
end
function METHODS.LoadAnimation(self, anim)
	local cls = STATE[self].ClassName
	assert(cls == "Animator" or cls == "Humanoid", "LoadAnimation is not a valid member")
	assert(isInstance(anim) and STATE[anim].ClassName == "Animation", "LoadAnimation: Animation expected")
	assert(STATE[anim].props.AnimationId ~= "", "LoadAnimation: empty AnimationId")
	local tr = newTrack(anim)
	tr.animator = self
	return tr
end
function METHODS.GetPlayingAnimationTracks(self)
	assert(STATE[self].ClassName == "Animator", "GetPlayingAnimationTracks is not a valid member")
	local out = {}
	for _, tr in ipairs(MOCK.tracks) do
		if tr.animator == self and tr.IsPlaying then
			table.insert(out, tr)
		end
	end
	return out
end
-- Pose (Pose.CFrame) d'une pièce dans une KeyframeSequence à l'instant t : interpolation linéaire entre les
-- images clés où elle a un poids > 0.
local function kfsPoseAt(kfs, name, t)
	local list = {}
	for _, kf in ipairs(METHODS.GetChildren(kfs)) do
		if STATE[kf].ClassName == "Keyframe" then
			for _, p in ipairs(METHODS.GetDescendants(kf)) do
				local ps = STATE[p]
				if ps.ClassName == "Pose" and ps.props.Name == name and ps.props.Weight > 0 then
					table.insert(list, { t = STATE[kf].props.Time, cf = ps.props.CFrame })
				end
			end
		end
	end
	table.sort(list, function(a, b)
		return a.t < b.t
	end)
	if #list == 0 then
		return nil
	end
	if t <= list[1].t then
		return list[1].cf
	end
	for i = 2, #list do
		if t <= list[i].t then
			local a, b = list[i - 1], list[i]
			return a.cf:Lerp(b.cf, (t - a.t) / (b.t - a.t))
		end
	end
	return list[#list].cf
end
MOCK.kfsPoseAt = kfsPoseAt
-- Mode édition (plugins, barre de commande) : avance les pistes de cet Animator et applique leurs poses.
function METHODS.StepAnimations(self, dt)
	assert(STATE[self].ClassName == "Animator", "StepAnimations is not a valid member")
	assert(type(dt) == "number", "StepAnimations: number expected")
	if MOCK.stepAnimationsDisabled then
		error("StepAnimations indisponible (simulé)", 2)
	end
	local hum = STATE[self].parent
	local model = hum and STATE[hum].parent
	MOCK.stepCalls = (MOCK.stepCalls or 0) + 1
	for _, tr in ipairs(MOCK.tracks) do
		if tr.animator == self and tr.IsPlaying and tr.kfs then
			tr.TimePosition = tr.TimePosition + dt * tr.Speed
			for _, d in ipairs(model and METHODS.GetDescendants(model) or {}) do
				local ds = STATE[d]
				if ds.ClassName == "Motor6D" and ds.props.Part1 then
					local cfp = kfsPoseAt(tr.kfs, STATE[ds.props.Part1].props.Name, tr.TimePosition)
					if cfp then
						ds.props.Transform = cfp
					end
				end
			end
		end
	end
end
function METHODS.UpdateSourceAsync(self, scr, fn)
	assert(self == services.ScriptEditorService, "UpdateSourceAsync is not a valid member")
	local cls = isInstance(scr) and STATE[scr].ClassName
	assert(cls == "Script" or cls == "LocalScript" or cls == "ModuleScript", "UpdateSourceAsync: script expected")
	assert(type(fn) == "function", "UpdateSourceAsync: callback expected")
	if MOCK.scriptEditorDisabled then
		error("UpdateSourceAsync indisponible (simulé)", 2)
	end
	local src = fn(STATE[scr].props.Source)
	assert(type(src) == "string", "UpdateSourceAsync: callback must return a string")
	STATE[scr].props.Source = src
	MOCK.sourceUpdates = (MOCK.sourceUpdates or 0) + 1
end

-- avance l'horloge du jeu : pistes d'animation, task.delay, puis RunService.Heartbeat
function MOCK.step(dt, n)
	for _ = 1, (n or 1) do
		MOCK.clock = MOCK.clock + dt
		for _, tr in ipairs(MOCK.tracks) do
			if tr.IsPlaying then
				tr.TimePosition = tr.TimePosition + dt * tr.Speed
				if not tr.Looped and tr.TimePosition >= tr.Length then
					tr.IsPlaying = false
				end
			end
		end
		local due = {}
		for i = #MOCK.delays, 1, -1 do
			if MOCK.delays[i].t <= MOCK.clock then
				table.insert(due, table.remove(MOCK.delays, i))
			end
		end
		for _, d in ipairs(due) do
			d.fn()
		end
		fireEvent(services.RunService, "Heartbeat", dt)
	end
end
MOCK.services = services
makeService("ServerStorage")

MOCK.selection = {}
MOCK.chsLog = {}
MOCK.recordingActive = nil
MOCK.allowRecording = true

function METHODS.GetService(self, name)
	assert(self == game, "GetService must be called on game")
	local s = services[name]
	if not s then
		error("'" .. tostring(name) .. "' is not a valid Service name (non émulé)", 2)
	end
	return s
end

local baseGet = METHODS.GetChildren
METHODS.Get = function(self)
	assert(self == selectionService, "Get is not a valid member")
	local out = {}
	for i, v in ipairs(MOCK.selection) do
		out[i] = v
	end
	return out
end
METHODS.Set = function(self, list)
	assert(self == selectionService, "Set is not a valid member")
	MOCK.selection = {}
	for i, v in ipairs(list) do
		MOCK.selection[i] = v
	end
end
METHODS.TryBeginRecording = function(self, name, displayName)
	assert(self == chsService, "TryBeginRecording is not a valid member")
	assert(type(name) == "string", "TryBeginRecording: name must be a string")
	table.insert(MOCK.chsLog, "begin:" .. name)
	if not MOCK.allowRecording then
		error("TryBeginRecording non disponible (simulé)", 2)
	end
	if MOCK.recordingActive then
		return nil
	end
	MOCK.recordingActive = "rec-" .. name
	return MOCK.recordingActive
end
METHODS.FinishRecording = function(self, id, op, opts)
	assert(self == chsService, "FinishRecording is not a valid member")
	assert(id == MOCK.recordingActive, "FinishRecording: unknown identifier")
	assert(isEnumItem(op, "FinishRecordingOperation"), "FinishRecording: operation must be an EnumItem")
	table.insert(MOCK.chsLog, "finish:" .. op.Name)
	MOCK.recordingActive = nil
end
METHODS.SetWaypoint = function(self, name)
	assert(self == chsService, "SetWaypoint is not a valid member")
	table.insert(MOCK.chsLog, "waypoint:" .. tostring(name))
end

-- RaycastParams
local RPmt = {}
local RP_PROPS = { FilterType = true, FilterDescendantsInstances = true, IgnoreWater = true,
	RespectCanCollide = true, CollisionGroup = true, BruteForceAllSlow = true }
RPmt.__index = function(t, k)
	if RP_PROPS[k] then
		return rawget(t, "_" .. k)
	end
	error(tostring(k) .. " is not a valid member of RaycastParams", 2)
end
RPmt.__newindex = function(t, k, v)
	if not RP_PROPS[k] then
		error(tostring(k) .. " is not a valid member of RaycastParams", 2)
	end
	if k == "FilterType" then
		assert(isEnumItem(v, "RaycastFilterType"), "FilterType must be Enum.RaycastFilterType")
	elseif k == "FilterDescendantsInstances" then
		assert(type(v) == "table", "FilterDescendantsInstances must be an array")
		for _, x in ipairs(v) do
			assert(isInstance(x), "FilterDescendantsInstances: Instance expected")
		end
	end
	rawset(t, "_" .. k, v)
end
local RaycastParams = {
	new = function()
		local p = setmetatable({}, RPmt)
		p.FilterType = Enum.RaycastFilterType.Exclude
		p.FilterDescendantsInstances = {}
		p.IgnoreWater = false
		p.RespectCanCollide = false
		return p
	end,
}

local function rayBox(origin, dir, c, size)
	-- intersection rayon / boîte orientée (méthode des dalles dans le repère de la pièce)
	local inv = c:Inverse()
	local o = inv * origin
	local d = inv:VectorToWorldSpace(dir)
	local h = size / 2
	local tmin, tmax = 0, 1
	for _, ax in ipairs({ "X", "Y", "Z" }) do
		local oa, da, ha = o[ax], d[ax], h[ax]
		if math.abs(da) < 1e-12 then
			if oa < -ha or oa > ha then
				return nil
			end
		else
			local t1, t2 = (-ha - oa) / da, (ha - oa) / da
			if t1 > t2 then
				t1, t2 = t2, t1
			end
			tmin = math.max(tmin, t1)
			tmax = math.min(tmax, t2)
			if tmin > tmax then
				return nil
			end
		end
	end
	return tmin
end

function METHODS.Raycast(self, origin, direction, params)
	assert(self == workspaceInst, "Raycast is not a valid member")
	assert(isV3(origin) and isV3(direction), "Raycast: Vector3 expected")
	params = params or RaycastParams.new()
	local filter = params.FilterDescendantsInstances or {}
	local exclude = params.FilterType == Enum.RaycastFilterType.Exclude
		or params.FilterType == Enum.RaycastFilterType.Blacklist
	local function filtered(part)
		local inList = false
		for _, f in ipairs(filter) do
			if part == f or part:IsDescendantOf(f) then
				inList = true
				break
			end
		end
		if exclude then
			return inList
		end
		return not inList
	end
	local best, bestT = nil, math.huge
	for _, d in ipairs(METHODS.GetDescendants(workspaceInst)) do
		local st = STATE[d]
		if classIsA(st.ClassName, "BasePart") and st.props.CanQuery and not filtered(d)
			and (not params.RespectCanCollide or st.props.CanCollide) then
			local t = rayBox(origin, direction, st.props.CFrame, st.props.Size)
			if t and t < bestT then
				best, bestT = d, t
			end
		end
	end
	if not best then
		return nil
	end
	return { Instance = best, Position = origin + direction * bestT, Distance = direction.Magnitude * bestT,
		Normal = v3(0, 1, 0), Material = STATE[best].props.Material }
end

------------------------------------------------------------------------------------------
-- Globals
------------------------------------------------------------------------------------------
MOCK.warnings = {}
MOCK.printed = {}
local rawPrint = print
MOCK.quiet = false
local function mprint(...)
	local parts = {}
	for i = 1, select("#", ...) do
		parts[i] = tostring((select(i, ...)))
	end
	local s = table.concat(parts, " ")
	table.insert(MOCK.printed, s)
	if not MOCK.quiet then
		rawPrint(s)
	end
end
local function mwarn(...)
	local parts = {}
	for i = 1, select("#", ...) do
		parts[i] = tostring((select(i, ...)))
	end
	local s = table.concat(parts, " ")
	table.insert(MOCK.warnings, s)
	if not MOCK.quiet then
		rawPrint("WARN: " .. s)
	end
end

function MOCK.reset()
	for _, c in ipairs(METHODS.GetChildren(workspaceInst)) do
		local cls = STATE[c].ClassName
		if cls ~= "Camera" and cls ~= "Terrain" then
			METHODS.Destroy(c)
		end
	end
	if MOCK.resetExtensions then
		MOCK.resetExtensions()
	end
	for _, c in ipairs(METHODS.GetChildren(services.StarterPlayer)) do
		local cls = STATE[c].ClassName
		if cls ~= "StarterCharacterScripts" and cls ~= "StarterPlayerScripts" then
			METHODS.Destroy(c)
		end
	end
	MOCK.selection = {}
	MOCK.chsLog = {}
	MOCK.recordingActive = nil
	MOCK.allowRecording = true
	MOCK.warnings = {}
	MOCK.printed = {}
	services.Players.LoadCharacterAppearance = true
	for _, svc in ipairs({ "ReplicatedStorage", "ServerStorage", "ServerScriptService" }) do
		for _, c in ipairs(METHODS.GetChildren(services[svc])) do
			METHODS.Destroy(c)
		end
	end
	local scs = METHODS.FindFirstChild(services.StarterPlayer, "StarterCharacterScripts")
	for _, c in ipairs(METHODS.GetChildren(scs)) do
		METHODS.Destroy(c)
	end
	for _, c in ipairs(METHODS.GetChildren(METHODS.FindFirstChild(MOCK.localPlayer, "PlayerGui"))) do
		METHODS.Destroy(c)
	end
	MOCK.isStudio = true
	MOCK.tracks = {}
	MOCK.tempKfs = {}
	MOCK.actions = {}
	MOCK.delays = {}
	MOCK.collision = { groups = { Default = true }, collidable = {} }
	MOCK.requireCache = {}
	MOCK.stepAnimationsDisabled = false
	MOCK.scriptEditorDisabled = false
	MOCK.sourceUpdates = 0
	MOCK.stepCalls = 0
	MOCK.threads = {}
	MOCK.errors = {}
	MOCK.debris = {}
	MOCK.renderBindings = {}
	MOCK.sons = {}
	MOCK.particules = 0
end


------------------------------------------------------------------------------------------
-- Extensions pour le monstre : ordonnanceur, services, types, joints
------------------------------------------------------------------------------------------
MOCK.threads = {}
MOCK.errors = {}
MOCK.debris = {}
MOCK.renderBindings = {}
MOCK.sons = {}
MOCK.particules = 0
MOCK.serverOffset = 1000

function MOCK.resume(co, ...)
	local ok, err = coroutine.resume(co, ...)
	if not ok then
		local tb = debug.traceback(co)
		table.insert(MOCK.errors, tostring(err) .. "\n" .. tb)
		if not MOCK.quiet then
			rawPrint("ERREUR (coroutine) : " .. tostring(err) .. "\n" .. tb)
		end
	end
	return ok
end

local function schedule(co, wake, args)
	table.insert(MOCK.threads, { co = co, wake = wake, args = args })
end

function MOCK.step(dt, n)
	local rs = services.RunService
	for _ = 1, (n or 1) do
		MOCK.clock = MOCK.clock + dt
		for _, tr in ipairs(MOCK.tracks) do
			if tr.IsPlaying then
				tr.TimePosition = tr.TimePosition + dt * tr.Speed
				if not tr.Looped and tr.TimePosition >= tr.Length then
					tr.IsPlaying = false
				end
			end
		end
		local dueD = {}
		for i = #MOCK.delays, 1, -1 do
			if MOCK.delays[i].t <= MOCK.clock then
				table.insert(dueD, table.remove(MOCK.delays, i))
			end
		end
		for _, d in ipairs(dueD) do
			d.fn()
		end
		local due = {}
		for i = #MOCK.threads, 1, -1 do
			if MOCK.threads[i].wake <= MOCK.clock + 1e-9 then
				table.insert(due, table.remove(MOCK.threads, i))
			end
		end
		table.sort(due, function(a, b)
			return a.wake < b.wake
		end)
		for _, th in ipairs(due) do
			if coroutine.status(th.co) == "suspended" then
				if th.args then
					MOCK.resume(th.co, table.unpack(th.args, 1, th.args.n))
				else
					MOCK.resume(th.co)
				end
			end
		end
		for i = #MOCK.debris, 1, -1 do
			local e = MOCK.debris[i]
			if e.t <= MOCK.clock then
				table.remove(MOCK.debris, i)
				if STATE[e.inst] and not STATE[e.inst].destroyed then
					METHODS.Destroy(e.inst)
				end
			end
		end
		fireEvent(rs, "Stepped", MOCK.clock, dt)
		fireEvent(rs, "PreSimulation", dt)
		if MOCK.autoSolve then
			MOCK.solveJoints()
		end
		fireEvent(rs, "PostSimulation", dt)
		fireEvent(rs, "Heartbeat", dt)
		local binds = {}
		for _, b in pairs(MOCK.renderBindings) do
			table.insert(binds, b)
		end
		table.sort(binds, function(a, b)
			return a.prio < b.prio
		end)
		for _, b in ipairs(binds) do
			MOCK.resume(coroutine.create(b.fn), dt)
		end
		fireEvent(rs, "RenderStepped", dt)
	end
end

-- exécute un Script / LocalScript (script = l'instance), dans sa propre coroutine
function MOCK.runScript(inst)
	local src = STATE[inst].props.Source
	local f, e = loadstring("local script = ...\n" .. src, "@" .. METHODS.GetFullName(inst))
	assert(f, e)
	local co = coroutine.create(f)
	MOCK.resume(co, inst)
	return co
end

-- services et méthodes
function METHODS.GetServerTimeNow(self)
	assert(self == workspaceInst, "GetServerTimeNow is not a valid member")
	return MOCK.clock + MOCK.serverOffset
end
function METHODS.BindToRenderStep(self, name, prio, fn)
	assert(self == services.RunService, "BindToRenderStep is not a valid member")
	assert(type(name) == "string" and type(prio) == "number" and type(fn) == "function", "BindToRenderStep: bad arguments")
	MOCK.renderBindings[name] = { prio = prio, fn = fn }
end
function METHODS.UnbindFromRenderStep(self, name)
	MOCK.renderBindings[name] = nil
end
function METHODS.SetNetworkOwner(self, owner)
	assert(classIsA(STATE[self].ClassName, "BasePart"), "SetNetworkOwner is not a valid member")
	if STATE[self].props.Anchored then
		error("Network Ownership API cannot be called on Anchored parts or parts welded to Anchored parts (émulation)", 2)
	end
	STATE[self].networkOwner = owner
end
function METHODS.PivotTo(self, target)
	local cur = METHODS.GetPivot(self)
	local delta = target * cur:Inverse()
	if classIsA(STATE[self].ClassName, "BasePart") then
		STATE[self].props.CFrame = target
		return
	end
	for _, d in ipairs(METHODS.GetDescendants(self)) do
		if classIsA(STATE[d].ClassName, "BasePart") then
			STATE[d].props.CFrame = delta * STATE[d].props.CFrame
		end
	end
end
function METHODS.MoveTo(self, pos)
	assert(STATE[self].ClassName == "Humanoid", "MoveTo is not a valid member")
	STATE[self].moveTo = pos
	MOCK.lastMoveTo = pos
end
function METHODS.TakeDamage(self, n)
	assert(STATE[self].ClassName == "Humanoid", "TakeDamage is not a valid member")
	local st = STATE[self]
	st.props.Health = math.max(0, st.props.Health - n)
end
function METHODS.Play(self)
	assert(STATE[self].ClassName == "Sound", "Play is not a valid member")
	STATE[self].props.IsPlaying = true
	local nom = STATE[self].props.Name
	MOCK.sons[nom] = (MOCK.sons[nom] or 0) + 1
end
function METHODS.Stop(self)
	STATE[self].props.IsPlaying = false
end
function METHODS.Emit(self, n)
	assert(STATE[self].ClassName == "ParticleEmitter", "Emit is not a valid member")
	MOCK.particules = MOCK.particules + (n or 1)
end
function METHODS.Invoke(self, ...)
	assert(STATE[self].ClassName == "BindableFunction", "Invoke is not a valid member")
	local f = STATE[self].props.OnInvoke
	assert(type(f) == "function", "BindableFunction sans OnInvoke")
	return f(...)
end
function METHODS.AddItem(self, inst, t)
	assert(self == services.Debris, "AddItem is not a valid member")
	table.insert(MOCK.debris, { inst = inst, t = MOCK.clock + (t or 10) })
end
-- CollectionService (et Instance:AddTag / HasTag)
local tagAdded, tagRemoved = {}, {}
local function inGame(inst)
	return METHODS.IsDescendantOf(inst, game)
end
function METHODS.AddTag(self, a, b)
	local inst, tag = a, b
	if self ~= services.CollectionService then
		inst, tag = self, a
	end
	local st = STATE[inst]
	st.tags = st.tags or {}
	if not st.tags[tag] then
		st.tags[tag] = true
		if tagAdded[tag] and inGame(inst) then
			tagAdded[tag]:Fire(inst)
		end
	end
end
function METHODS.RemoveTag(self, a, b)
	local inst, tag = a, b
	if self ~= services.CollectionService then
		inst, tag = self, a
	end
	local st = STATE[inst]
	if st.tags and st.tags[tag] then
		st.tags[tag] = nil
		if tagRemoved[tag] then
			tagRemoved[tag]:Fire(inst)
		end
	end
end
function METHODS.HasTag(self, a, b)
	local inst, tag = a, b
	if self ~= services.CollectionService then
		inst, tag = self, a
	end
	local st = STATE[inst]
	return st.tags ~= nil and st.tags[tag] == true
end
function METHODS.GetTagged(self, tag)
	assert(self == services.CollectionService, "GetTagged is not a valid member")
	local out = {}
	for _, d in ipairs(METHODS.GetDescendants(game)) do
		local st = STATE[d]
		if st.tags and st.tags[tag] then
			table.insert(out, d)
		end
	end
	return out
end
function METHODS.GetInstanceAddedSignal(self, tag)
	tagAdded[tag] = tagAdded[tag] or MOCK.newSignal()
	return tagAdded[tag]
end
function METHODS.GetInstanceRemovedSignal(self, tag)
	tagRemoved[tag] = tagRemoved[tag] or MOCK.newSignal()
	return tagRemoved[tag]
end
-- PathfindingService : chemin en ligne droite (points tous les 4 studs)
function METHODS.CreatePath(self, params)
	assert(self == services.PathfindingService, "CreatePath is not a valid member")
	local path = { Status = Enum.PathStatus.NoPath, wps = {} }
	function path:ComputeAsync(a, b)
		self.Status = MOCK.pathFails and Enum.PathStatus.NoPath or Enum.PathStatus.Success
		self.wps = {}
		local d = b - a
		local n = math.max(1, math.ceil(d.Magnitude / 4))
		for i = 0, n do
			table.insert(self.wps, { Position = a + d * (i / n), Action = Enum.PathWaypointAction.Walk })
		end
		MOCK.pathComputes = (MOCK.pathComputes or 0) + 1
	end
	function path:GetWaypoints()
		return self.wps
	end
	return path
end
-- Players
function METHODS.GetPlayers(self)
	assert(self == services.Players, "GetPlayers is not a valid member")
	local out = {}
	for _, c in ipairs(STATE[self].children) do
		if STATE[c].ClassName == "Player" then
			table.insert(out, c)
		end
	end
	return out
end
function METHODS.GetPlayerFromCharacter(self, c)
	for _, p in ipairs(METHODS.GetPlayers(services.Players)) do
		if STATE[p].props.Character == c and c ~= nil then
			return p
		end
	end
	return nil
end
function MOCK.addPlayer(name)
	local pl = newInstance("Player", true)
	STATE[pl].props.Name = name
	STATE[pl].props.UserId = 1000 + #METHODS.GetPlayers(services.Players)
	pl.Parent = services.Players
	for _, cls in ipairs({ "PlayerGui", "PlayerScripts" }) do
		local g = newInstance(cls, true)
		STATE[g].props.Name = cls
		g.Parent = pl
	end
	fireEvent(services.Players, "PlayerAdded", pl)
	return pl
end
function MOCK.setCharacter(pl, model)
	STATE[pl].props.Character = model
	if model then
		fireEvent(pl, "CharacterAdded", model)
	end
end

-- caméra, terrain, gravité
do
	local cam = newInstance("Camera", true)
	STATE[cam].props.Name = "Camera"
	STATE[cam].props.ViewportSize = { X = 1280, Y = 720 }
	cam.Parent = workspaceInst
	STATE[workspaceInst].props.CurrentCamera = cam
	STATE[workspaceInst].props.Gravity = 196.2
	local terr = newInstance("Terrain", true)
	STATE[terr].props.Name = "Terrain"
	STATE[terr].props.Anchored = true
	STATE[terr].props.CanQuery = false
	STATE[terr].props.CanCollide = false
	STATE[terr].props.Size = v3(0.001, 0.001, 0.001)
	terr.Parent = workspaceInst
	local ps = newInstance("PlayerScripts", true)
	STATE[ps].props.Name = "PlayerScripts"
	ps.Parent = MOCK.localPlayer
	local sps = newInstance("StarterPlayerScripts", true)
	STATE[sps].props.Name = "StarterPlayerScripts"
	sps.Parent = services.StarterPlayer
end

-- solveur de joints : Part1 = Part0 * C0 * Transform * C1:Inverse() (Motor6D), C0 * C1:Inverse() (Weld), décalage
-- mémorisé à la première résolution (WeldConstraint). Les pièces ancrées ne sont pas déplacées.
function MOCK.solveJoints(root)
	root = root or workspaceInst
	local drive, parts = {}, {}
	for _, d in ipairs(METHODS.GetDescendants(root)) do
		local st = STATE[d]
		local cls = st.ClassName
		if classIsA(cls, "BasePart") then
			table.insert(parts, d)
		elseif (cls == "Motor6D" or cls == "Weld" or cls == "WeldConstraint") and st.props.Enabled ~= false then
			local p0, p1 = st.props.Part0, st.props.Part1
			if p0 and p1 then
				if cls == "WeldConstraint" and not st.offset then
					st.offset = cfInverse(STATE[p0].props.CFrame) * STATE[p1].props.CFrame
				end
				drive[p1] = drive[p1] or d
			end
		end
	end
	local done = {}
	local function solve(p)
		if done[p] then
			return
		end
		done[p] = true
		local j = drive[p]
		if not j or STATE[p].props.Anchored then
			return
		end
		local js = STATE[j]
		local p0 = js.props.Part0
		solve(p0)
		local c0 = STATE[p0].props.CFrame
		if js.ClassName == "Motor6D" then
			STATE[p].props.CFrame = c0 * js.props.C0 * js.props.Transform * cfInverse(js.props.C1)
		elseif js.ClassName == "Weld" then
			STATE[p].props.CFrame = c0 * js.props.C0 * cfInverse(js.props.C1)
		else
			STATE[p].props.CFrame = c0 * js.offset
		end
	end
	for _, p in ipairs(parts) do
		solve(p)
	end
end

-- types de valeurs
local V2mt = { __index = function(t, k)
	if k == "Magnitude" then
		return math.sqrt(t.X * t.X + t.Y * t.Y)
	end
	error(tostring(k) .. " is not a valid member of Vector2", 2)
end }
local Vector2 = { new = function(x, y)
	return setmetatable({ X = x or 0, Y = y or 0 }, V2mt)
end }
local UDim = { new = function(sc, off)
	return { Scale = sc or 0, Offset = off or 0 }
end }
local NumberRange = { new = function(a, b)
	return { Min = a, Max = b or a }
end }
local NumberSequenceKeypoint = { new = function(t, v, e)
	assert(type(t) == "number" and type(v) == "number", "NumberSequenceKeypoint.new: numbers expected")
	return { Time = t, Value = v, Envelope = e or 0 }
end }
local NumberSequence = { new = function(a, b)
	if type(a) == "table" then
		assert(a[1] and a[1].Time == 0 and a[#a].Time == 1, "NumberSequence: keypoints must start at 0 and end at 1")
		return { Keypoints = a }
	end
	return { Keypoints = { NumberSequenceKeypoint.new(0, a), NumberSequenceKeypoint.new(1, b or a) } }
end }
local ColorSequence = { new = function(a, b)
	if type(a) == "table" and not isC3(a) then
		return { Keypoints = a }
	end
	assert(isC3(a), "ColorSequence.new: Color3 expected")
	return { Keypoints = { { Time = 0, Value = a }, { Time = 1, Value = b or a } } }
end }
local Random = { new = function(seed)
	local st = { s = math.floor(math.abs(seed or os.clock() * 1e6)) % 2147483647 + 1 }
	local function nxt()
		st.s = (st.s * 48271) % 2147483647
		return st.s / 2147483647
	end
	return {
		NextNumber = function(_, a, b)
			a, b = a or 0, b or 1
			return a + (b - a) * nxt()
		end,
		NextInteger = function(_, a, b)
			return a + math.floor(nxt() * (b - a + 1))
		end,
	}
end }
function MOCK.resetExtensions()
	for k in pairs(tagAdded) do
		tagAdded[k] = nil
	end
	for k in pairs(tagRemoved) do
		tagRemoved[k] = nil
	end
	for _, inst in ipairs({ services.RunService, services.Players, MOCK.localPlayer, services.Lighting, services.SoundService }) do
		STATE[inst].signals = nil
		STATE[inst].attrSignals = nil
	end
	for _, svc in ipairs({ services.Lighting, services.SoundService, services.Debris }) do
		for _, c in ipairs(METHODS.GetChildren(svc)) do
			METHODS.Destroy(c)
		end
	end
	for _, c in ipairs(METHODS.GetChildren(STATE[workspaceInst].props.CurrentCamera)) do
		METHODS.Destroy(c)
	end
	local cam = STATE[workspaceInst].props.CurrentCamera
	STATE[cam].props.CameraType = Enum.CameraType.Custom
	STATE[cam].props.CFrame = CFrame.new()
	for _, c in ipairs(METHODS.GetChildren(services.StarterPlayer)) do
		if STATE[c].ClassName == "StarterPlayerScripts" then
			for _, x in ipairs(METHODS.GetChildren(c)) do
				METHODS.Destroy(x)
			end
		end
	end
	STATE[MOCK.localPlayer].props.Character = nil
	MOCK.autoSolve = false
	MOCK.pathFails = false
end
MOCK.types = { Vector2 = Vector2, UDim = UDim, NumberRange = NumberRange, NumberSequence = NumberSequence,
	NumberSequenceKeypoint = NumberSequenceKeypoint, ColorSequence = ColorSequence, Random = Random }

MOCK.STATE = STATE
MOCK.rawPrint = rawPrint
MOCK.isV3, MOCK.isCF, MOCK.isC3 = isV3, isCF, isC3

-- Installe l'environnement global.
_G.Vector3 = Vector3
_G.CFrame = CFrame
_G.Color3 = Color3
_G.Enum = Enum
_G.Instance = Instance
_G.RaycastParams = RaycastParams
_G.game = game
_G.workspace = workspaceInst
_G.warn = mwarn
_G.print = mprint
_G.MOCK = MOCK
_G.UDim2 = UDim2
_G.task = {
	spawn = function(fn, ...)
		local co = type(fn) == "thread" and fn or coroutine.create(fn)
		MOCK.resume(co, ...)
		return co
	end,
	defer = function(fn, ...)
		local co = coroutine.create(fn)
		schedule(co, MOCK.clock, table.pack(...))
		return co
	end,
	delay = function(t, fn, ...)
		local co = coroutine.create(fn)
		schedule(co, MOCK.clock + (t or 0), table.pack(...))
		return co
	end,
	wait = function(t)
		t = t or 0
		local start = MOCK.clock
		local co = coroutine.running()
		if co and coroutine.isyieldable() then
			schedule(co, MOCK.clock + math.max(t, 1 / 60), nil)
			coroutine.yield()
			return MOCK.clock - start
		end
		local target = MOCK.clock + math.max(t, 1 / 60)
		while MOCK.clock < target - 1e-9 do
			MOCK.step(1 / 60)
		end
		return MOCK.clock - start
	end,
	cancel = function(co)
		for i = #MOCK.threads, 1, -1 do
			if MOCK.threads[i].co == co then
				table.remove(MOCK.threads, i)
			end
		end
	end,
}
for k, v in pairs(MOCK.types) do
	_G[k] = v
end
-- os.clock suit l'horloge simulée (les scripts mesurent leurs durées avec)
local osReel = os
_G.os = setmetatable({ clock = function()
	return MOCK.clock
end }, { __index = osReel })
-- require(ModuleScript) : exécute la source une fois (script = le module), résultat mis en cache.
MOCK.requireCache = {}
_G.require = function(m)
	assert(isInstance(m) and STATE[m].ClassName == "ModuleScript", "require: ModuleScript expected, got " .. tostring(m))
	local cached = MOCK.requireCache[m]
	if cached ~= nil then
		return cached
	end
	local f, e = loadstring("local script = ...\n" .. STATE[m].props.Source, "@" .. METHODS.GetFullName(m))
	if not f then
		error("Requested module experienced an error while loading: " .. tostring(e), 2)
	end
	local res = table.pack(pcall(f, m))
	if not res[1] then
		error("Requested module experienced an error while loading: " .. tostring(res[2]), 2)
	end
	if res.n ~= 2 or res[2] == nil then
		error("Module code did not return exactly one value", 2)
	end
	MOCK.requireCache[m] = res[2]
	return res[2]
end
_G.typeof = function(v)
	if isV3(v) then
		return "Vector3"
	elseif isCF(v) then
		return "CFrame"
	elseif isC3(v) then
		return "Color3"
	elseif isEnumItem(v) then
		return "EnumItem"
	elseif STATE[v] then
		return "Instance"
	end
	return type(v)
end
