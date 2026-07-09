"""Model and weapon id databases for GTA San Andreas."""

# Vehicle model ids 400..611, in game order.
_VEHICLE_NAMES = [
    "landstal", "bravura", "buffalo", "linerun", "peren", "sentinel", "dumper",
    "firetruk", "trash", "stretch", "manana", "infernus", "voodoo", "pony",
    "mule", "cheetah", "ambulan", "leviathn", "moonbeam", "esperant", "taxi",
    "washing", "bobcat", "mrwhoop", "bfinject", "hunter", "premier", "enforcer",
    "securica", "banshee", "predator", "bus", "rhino", "barracks", "hotknife",
    "artict1", "previon", "coach", "cabbie", "stallion", "rumpo", "rcbandit",
    "romero", "packer", "monster", "admiral", "squalo", "seaspar", "pizzaboy",
    "tram", "artict2", "turismo", "speeder", "reefer", "tropic", "flatbed",
    "yankee", "caddy", "solair", "topfun", "skimmer", "pcj600", "faggio",
    "freeway", "rcbaron", "rcraider", "glendale", "oceanic", "sanchez",
    "sparrow", "patriot", "quad", "coastg", "dinghy", "hermes", "sabre",
    "rustler", "zr350", "walton", "regina", "comet", "bmx", "burrito",
    "camper", "marquis", "baggage", "dozer", "maverick", "vcnmav", "rancher",
    "fbiranch", "virgo", "greenwoo", "jetmax", "hotring", "sandking",
    "blistac", "polmav", "boxville", "benson", "mesa", "rcgoblin", "hotrina",
    "hotrinb", "bloodra", "rnchlure", "supergt", "elegant", "journey", "bike",
    "mtbike", "beagle", "cropdust", "stunt", "petro", "rdtrain", "nebula",
    "majestic", "buccanee", "shamal", "hydra", "fcr900", "nrg500", "copbike",
    "cement", "towtruck", "fortune", "cadrona", "fbitruck", "willard",
    "forklift", "tractor", "combine", "feltzer", "remingtn", "slamvan",
    "blade", "freight", "streak", "vortex", "vincent", "bullet", "clover",
    "sadler", "firela", "hustler", "intruder", "primo", "cargobob", "tampa",
    "sunrise", "merit", "utility", "nevada", "yosemite", "windsor",
    "monstera", "monsterb", "uranus", "jester", "sultan", "stratum", "elegy",
    "raindanc", "rctiger", "flash", "tahoma", "savanna", "bandito",
    "freiflat", "streakc", "kart", "mower", "duneride", "sweeper", "broadway",
    "tornado", "at400", "dft30", "huntley", "stafford", "bf400", "newsvan",
    "tug", "petrotr", "emperor", "wayfarer", "euros", "hotdog", "club",
    "freibox", "artict3", "androm", "dodo", "rccam", "launch", "copcarla",
    "copcarsf", "copcarvg", "copcarru", "picador", "swatvan", "alpha",
    "phoenix", "glenshit", "sadlshit", "bagboxa", "bagboxb", "tugstair",
    "boxburg", "farmtr1", "utiltr1",
]

#: Vehicle name (lowercase) -> model id.
VEHICLES = {name: 400 + i for i, name in enumerate(_VEHICLE_NAMES)}

#: Model id -> vehicle name.
VEHICLE_NAMES = {v: k for k, v in VEHICLES.items()}


def vehicle_id(name_or_id) -> int:
    """Resolve a vehicle model: accepts an id (400-611) or a name like 'infernus'."""
    if isinstance(name_or_id, int):
        return name_or_id
    key = str(name_or_id).lower()
    if key not in VEHICLES:
        raise ValueError(f"unknown vehicle {name_or_id!r}")
    return VEHICLES[key]


class WEAPON:
    """Weapon ids for GIVE_WEAPON_TO_CHAR and friends."""

    FIST = 0
    BRASS_KNUCKLES = 1
    GOLF_CLUB = 2
    NIGHTSTICK = 3
    KNIFE = 4
    BAT = 5
    SHOVEL = 6
    POOL_CUE = 7
    KATANA = 8
    CHAINSAW = 9
    GRENADE = 16
    TEARGAS = 17
    MOLOTOV = 18
    PISTOL = 22
    SILENCED_PISTOL = 23
    DESERT_EAGLE = 24
    SHOTGUN = 25
    SAWNOFF = 26
    COMBAT_SHOTGUN = 27
    UZI = 28
    MP5 = 29
    AK47 = 30
    M4 = 31
    TEC9 = 32
    RIFLE = 33
    SNIPER = 34
    RPG = 35
    HEAT_SEEKER = 36
    FLAMETHROWER = 37
    MINIGUN = 38
    SATCHEL = 39
    DETONATOR = 40
    SPRAYCAN = 41
    EXTINGUISHER = 42
    CAMERA = 43
    NIGHT_VISION = 44
    THERMAL_VISION = 45
    PARACHUTE = 46


class PED_TYPE:
    """Ped types for CREATE_CHAR."""

    CIVMALE = 4
    CIVFEMALE = 5
    COP = 6
    GANG1 = 7
    GANG2 = 8
    GANG3 = 9
    GANG4 = 10
    GANG5 = 11
    GANG6 = 12
    GANG7 = 13
    GANG8 = 14
