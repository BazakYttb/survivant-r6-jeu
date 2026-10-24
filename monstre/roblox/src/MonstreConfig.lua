--[[
	MonstreConfig (ModuleScript, ReplicatedStorage.Monstre) : réglages du monstre. Modifiez librement les valeurs ;
	le serveur et les clients relisent ce module au lancement du jeu.
]]

return {
	-- déplacement (studs/s). Les animations de marche et de course sont accélérées ou ralenties dans la même
	-- proportion (pieds plantés : marche 5,5 et course 20 sont les vitesses des clips)
	VITESSE = {
		marche = 5.5,
		course = 20,
		trainer = 4.2, -- traîner une victime (clip calé sur 4,2)
		trainer_vite = 8, -- la tirer hors de la pièce (clip calé sur 8)
	},

	-- perception
	DETECTION = {
		vue = 70, -- distance de vue (studs), avec ligne de vue dégagée
		angle_vue = 140, -- champ de vision (degrés) ; derrière lui il n'entend que les joueurs qui courent
		ouie = 26, -- entend un joueur qui court (vitesse > 10) à cette distance, même sans le voir
		oubli = 8, -- secondes sans voir sa cible avant d'abandonner la poursuite
		hurle_a_la_vue = true, -- hurle quand il repère une nouvelle cible
	},

	-- attaque : distance à laquelle une mise à mort se déclenche, temps entre deux mises à mort
	PORTEE_ATTAQUE = 5.5,
	REPOS_APRES_MISE_A_MORT = 6,

	-- mises à mort disponibles et poids du tirage (0 = désactivée)
	MISES_A_MORT = {
		morsure_cou = 1,
		morsure_repetee = 1,
		devoration = 1,
		attaque_ventre = 1,
		trainee = 1,
		extraction = 1,
		frenesie = 1,
		contamination = 1,
	},

	-- traînées : où aller (parties étiquetées dans la place avec CollectionService), distance sinon
	TRAINER = {
		etiquette_taniere = "MonstreTaniere", -- dévoration : un coin sombre
		etiquette_sortie = "MonstreSortie", -- traînée : une porte, la sortie de la pièce
		distance_max = 45, -- studs parcourus au plus
		distance_sans_cible = 26, -- sans partie étiquetée : distance parcourue (en s'éloignant des joueurs)
		duree_repas = 7, -- secondes de dévoration
	},

	-- patrouille : parties étiquetées « MonstrePatrouille », sinon des points au hasard autour du départ
	PATROUILLE = {
		etiquette = "MonstrePatrouille",
		rayon = 60,
		pause_min = 2,
		pause_max = 6,
		flairer = 0.35, -- probabilité de flairer à chaque pause
	},

	-- victimes possibles : les personnages des joueurs, et les modèles étiquetés « Survivant » (essais dans Studio)
	ETIQUETTE_VICTIME = "Survivant",

	-- sang et gore
	SANG = {
		actif = true,
		decalques = true, -- flaques, éclaboussures et traînées au sol
		particules = true,
		ecran = true, -- sang sur l'écran de la victime
		duree_decalques = 90, -- secondes avant disparition
		duree_cadavre = 60, -- secondes avant de retirer le cadavre (0 = jamais)
		quantite = 1, -- multiplie le nombre d'éclaboussures
	},

	-- caméra de la victime pendant sa mise à mort
	CAMERA = {
		active = true,
		tremblement = 1, -- force des tremblements
		champ = 60, -- champ de vision (degrés) des plans cinématiques
	},

	-- infection (mise à mort « contamination ») : la victime survit, les symptômes commencent après « delai »
	INFECTION = {
		delai = 4,
		duree = 60, -- montée des symptômes (secondes)
		vitesse_min = 0.6, -- vitesse de marche au plus fort (fraction)
		degats_par_seconde = 0, -- 0 : elle reste en vie
		issue = "rien", -- "rien" (symptômes jusqu'à la mort du personnage) ou "mort" (meurt à la fin de « duree »)
		teinte_peau = Color3.fromRGB(150, 165, 140), -- multiplie la couleur de la tenue et de la peau
	},

	-- sons : remplissez les identifiants (rbxassetid://...) après avoir importé les fichiers de monstre/roblox/sons
	-- dans le Gestionnaire de ressources ; un son sans identifiant est ignoré
	SONS = {
		volume = 1,
		grognement = "",
		hurlement = "",
		hurlement_court = "",
		reniflement = "",
		souffle = "",
		pas_lourd = "",
		saisie = "",
		morsure = "",
		dechirure = "",
		craquement = "",
		mastication = "",
		impact = "",
		chute_corps = "",
		trainer = "",
		cri_victime = "",
		eclaboussure = "",
		battement = "",
		toux = "",
		acouphene = "",
	},

	-- vie du monstre (il ne meurt pas par défaut)
	VIE = math.huge,
	-- affiche des informations dans la sortie (Output)
	DEBUG = false,
}
