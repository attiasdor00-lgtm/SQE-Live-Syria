"""Author the 32-sector Lebanon/Syria campaign profile.

The JSON file retains the small stable Israel profile.  This module expands the
red theatre before export so the packaged content remains data-only for Lua.
Unit names are limited to types shipped by DCS/pydcs.
"""
from __future__ import annotations

from copy import deepcopy


BLUE_GRID = {
    "negev": (0, 8),
    "central": (0, 7),
    "sharon": (0, 6),
    "haifa": (0, 5),
    "galilee": (1, 5),
    "upper_galilee": (1, 4),
    "golan": (2, 4),
}


# id, label, name, airport anchor, dx, dy, grid column, grid row, tier,
# force profile, SAM profile, strategic kind, historically grounded formation.
RED_ZONES = [
    ("naqoura", "NAQ", "Naqoura / South Lebanon", "Naqoura", 0, 0, 3, 5, 1, "militia", "sa8", "FUEL", "South Litani border group"),
    ("tyre", "TYR", "Tyre", "HL05", 0, 0, 3, 4, 1, "laf_light", "sa8", "C2", "Lebanese 5th Intervention Regiment detachment"),
    ("bint_jbeil", "BJL", "Bint Jbeil", "HL12", 0, 0, 4, 4, 1, "militia", "sa8", "C2", "South Lebanon local defence group"),
    ("nabatieh", "NAB", "Nabatieh", "HL08", 0, 0, 3, 3, 1, "laf_light", "sa3", "FUEL", "Lebanese 5th Intervention Regiment detachment"),
    ("sidon", "SID", "Sidon", "HL04", 0, 0, 2, 3, 1, "laf_light", "sa3", "C2", "Lebanese 1st Intervention Regiment detachment"),
    ("beirut", "BEY", "Beirut", "Beirut-Rafic Hariri", 0, 0, 2, 2, 2, "laf_heavy", "sa6", "DEPOT", "Lebanese 1st Armoured Regiment detachment"),
    ("tripoli", "TRI", "Tripoli", "Rene Mouawad", 0, 0, 2, 1, 2, "laf_light", "sa3", "C2", "Lebanese 2nd Intervention Regiment detachment"),
    ("akkar", "AKK", "Akkar", "Rene Mouawad", 8000, 18000, 2, 0, 2, "laf_light", "sa8", "FUEL", "Lebanese 1st Land Border Regiment detachment"),
    ("zahle", "ZAH", "Zahle / Rayak", "Rayak", 0, 0, 3, 2, 2, "laf_heavy", "sa6", "FUEL", "Lebanese 6th Brigade detachment"),
    ("baalbek", "BAA", "Baalbek", "Rayak", 18000, 26000, 3, 1, 2, "laf_heavy", "sa6", "DEPOT", "Lebanese 6th Brigade reserve"),
    ("hermel", "HER", "Hermel", "Rayak", 36000, 43000, 3, 0, 2, "militia", "sa8", "C2", "Lebanese 2nd Land Border Regiment detachment"),
    ("arsal", "ARS", "Arsal / Qalamoun border", "Rayak", -12000, 33000, 4, 1, 2, "militia", "sa8", "FUEL", "Lebanese 2nd Land Border Regiment detachment"),
    ("south", "QUN", "Quneitra line", "Khalkhalah", -15000, -20000, 4, 5, 1, "syrian_mech", "sa6", "C2", "Syrian 1st Armoured Division battlegroup"),
    ("daraa", "DAR", "Daraa", "Khalkhalah", -30000, -12000, 4, 6, 1, "syrian_light", "sa8", "FUEL", "Syrian 5th Division battlegroup"),
    ("suwayda", "SUW", "As-Suwayda / Tha'lah", "Tha'lah", 0, 0, 5, 6, 1, "syrian_light", "sa3", "C2", "Syrian 15th Special Forces Division detachment"),
    ("khalkhalah", "KHA", "Khalkhalah", "Khalkhalah", 0, 0, 5, 5, 2, "syrian_mech", "sa6", "FUEL", "Syrian 1st Armoured Division reserve"),
    ("marj", "MAR", "Marj Ruhayyil", "Marj Ruhayyil", 4000, -6000, 5, 4, 2, "syrian_mech", "sa3", "FUEL", "Syrian 7th Mechanised Division reserve"),
    ("damascus", "DAM", "Damascus", "Damascus", 10000, 8000, 5, 3, 3, "syrian_elite", "sa11", "DEPOT", "Syrian Republican Guard detachment"),
    ("mezzeh", "MEZ", "Mezzeh", "Mezzeh", 0, 0, 4, 3, 3, "syrian_elite", "sa11", "C2", "Syrian 4th Armoured Division detachment"),
    ("dumayr", "DUM", "Al-Dumayr", "Al-Dumayr", 0, 0, 6, 4, 2, "syrian_mech", "sa6", "FUEL", "Syrian 3rd Armoured Division detachment"),
    ("nasiriyah", "NAS", "An Nasiriyah", "An Nasiriyah", 0, 0, 6, 3, 2, "syrian_mech", "sa6", "C2", "Syrian 3rd Armoured Division reserve"),
    ("sayqal", "SAY", "Sayqal", "Sayqal", 0, 0, 7, 3, 3, "syrian_elite", "sa11", "FUEL", "Syrian Air Defence Command mobile group"),
    ("homs", "HOM", "Homs", "Al Qusayr", 15000, 20000, 5, 2, 2, "syrian_mech", "sa6", "DEPOT", "Syrian 11th Tank Division battlegroup"),
    ("shayrat", "SHA", "Shayrat", "Shayrat", -6000, -6000, 6, 2, 2, "syrian_mech", "sa6", "DEPOT", "Syrian 11th Tank Division reserve"),
    ("tiyas", "TIY", "Tiyas / T-4", "Tiyas", 0, 0, 7, 2, 3, "syrian_mech", "sa11", "FUEL", "Syrian 18th Tank Division detachment"),
    ("palmyra", "PAL", "Palmyra / Tadmur", "Palmyra", 0, 0, 8, 2, 3, "syrian_light", "sa8", "DEPOT", "Syrian 18th Tank Division desert group"),
    ("hama", "HAM", "Hama", "Hama", 0, 0, 5, 1, 2, "syrian_mech", "sa6", "FUEL", "Syrian 25th Special Mission Forces detachment"),
    ("tartus", "TAR", "Tartus", "Bassel Al-Assad", -30000, 25000, 4, 2, 2, "syrian_light", "sa3", "C2", "Syrian Coastal Defence brigade detachment"),
    ("latakia", "LAT", "Latakia / Bassel Al-Assad", "Bassel Al-Assad", 0, 0, 4, 0, 3, "syrian_mech", "sa11", "DEPOT", "Syrian 4th Corps coastal group"),
    ("idlib", "IDL", "Idlib / Taftanaz", "Taftanaz", -10000, 10000, 6, 1, 3, "syrian_light", "sa8", "FUEL", "Syrian 25th Special Mission Forces detachment"),
    ("aleppo", "ALP", "Aleppo", "Aleppo", 0, 0, 7, 0, 3, "syrian_elite", "sa11", "DEPOT", "Syrian 30th Republican Guard Division detachment"),
    ("kuweires", "KUW", "Kuweires", "Kuweires", 0, 0, 8, 0, 3, "syrian_mech", "sa6", "FUEL", "Syrian 17th Reserve Division detachment"),
]


NEIGHBORS = {
    "galilee": ["golan", "haifa", "upper_galilee", "sharon"],
    "golan": ["galilee", "upper_galilee", "south"],
    "haifa": ["galilee", "upper_galilee", "sharon", "naqoura"],
    "upper_galilee": ["galilee", "haifa", "golan", "naqoura", "bint_jbeil"],
    "sharon": ["haifa", "galilee", "central"],
    "central": ["sharon", "negev"],
    "negev": ["central"],
    "naqoura": ["haifa", "upper_galilee", "tyre"],
    "tyre": ["naqoura", "bint_jbeil", "nabatieh", "sidon"],
    "bint_jbeil": ["upper_galilee", "tyre", "nabatieh"],
    "nabatieh": ["tyre", "bint_jbeil", "sidon", "zahle"],
    "sidon": ["tyre", "nabatieh", "beirut", "zahle"],
    "beirut": ["sidon", "zahle", "tripoli"],
    "tripoli": ["beirut", "akkar", "baalbek"],
    "akkar": ["tripoli", "hermel"],
    "zahle": ["nabatieh", "sidon", "beirut", "baalbek", "damascus", "mezzeh"],
    "baalbek": ["zahle", "tripoli", "hermel", "arsal", "homs"],
    "hermel": ["akkar", "baalbek", "arsal", "homs"],
    "arsal": ["hermel", "baalbek", "homs", "nasiriyah"],
    "south": ["golan", "daraa", "khalkhalah", "marj"],
    "daraa": ["south", "suwayda", "khalkhalah"],
    "suwayda": ["daraa", "khalkhalah"],
    "khalkhalah": ["south", "daraa", "suwayda", "marj"],
    "marj": ["south", "khalkhalah", "damascus"],
    "damascus": ["marj", "mezzeh", "zahle", "dumayr", "nasiriyah"],
    "mezzeh": ["damascus", "zahle"],
    "dumayr": ["damascus", "nasiriyah", "sayqal"],
    "nasiriyah": ["damascus", "dumayr", "sayqal", "arsal", "homs"],
    "sayqal": ["dumayr", "nasiriyah", "homs", "tiyas"],
    "homs": ["baalbek", "hermel", "arsal", "nasiriyah", "sayqal", "shayrat", "hama", "tartus"],
    "shayrat": ["homs", "tiyas", "hama"],
    "tiyas": ["shayrat", "sayqal", "palmyra"],
    "palmyra": ["tiyas"],
    "hama": ["homs", "shayrat", "tartus", "latakia", "idlib"],
    "tartus": ["homs", "hama", "latakia"],
    "latakia": ["tartus", "hama", "idlib"],
    "idlib": ["latakia", "hama", "aleppo"],
    "aleppo": ["idlib", "kuweires"],
    "kuweires": ["aleppo"],
}


SAM = {
    "sa3": {
        "types": ["snr s-125 tr", "p-19 s-125 sr", "5p73 s-125 ln", "5p73 s-125 ln", "Ural-375"],
        "radars": [1, 2],
        "title": "SA-3 battery",
    },
    "sa6": {
        "types": ["Kub 1S91 str", "Kub 2P25 ln", "Kub 2P25 ln", "Kub 2P25 ln", "Ural-375"],
        "radars": [1],
        "title": "SA-6 battery",
    },
    "sa8": {
        "types": ["Osa 9A33 ln", "Osa 9A33 ln", "Ural-375", "Ural-375 ZU-23"],
        "radars": [1, 2],
        "title": "SA-8 mobile section",
    },
    "sa11": {
        "types": ["SA-11 Buk SR 9S18M1", "SA-11 Buk CC 9S470M1", "SA-11 Buk LN 9A310M1", "SA-11 Buk LN 9A310M1"],
        "radars": [1, 3, 4],
        "title": "SA-11 battery",
    },
}


FORCES = {
    "laf_light": ["Hummer", "Hummer", "Cobra", "M-2 Bradley", "Vulcan"],
    "laf_heavy": ["M-60", "M-2 Bradley", "M-2 Bradley", "Hummer", "Vulcan"],
    "militia": ["T-55", "BRDM-2", "Ural-375 ZU-23 Insurgent", "tt_DSHK", "Grad-URAL"],
    "syrian_light": ["T-55", "BMP-1", "BTR-80", "BRDM-2", "ZSU-23-4 Shilka"],
    "syrian_mech": ["T-72B", "BMP-2", "BMP-2", "BTR-80", "ZSU-23-4 Shilka"],
    "syrian_elite": ["T-72B", "T-72B", "BMP-2", "BTR-80", "ZSU-23-4 Shilka"],
}


STRATEGIC = {
    "DEPOT": ["Ural-375", "Ural-375", "ATZ-10", "ZIL-131 KUNG"],
    "FUEL": ["ATZ-10", "ATZ-10", "ATZ-10", "Ural-375"],
    "C2": ["SKP-11", "ZIL-131 KUNG", "BRDM-2", "Ural-375"],
}


FARPS = [
    ("golan_farp", "Golan forward arming point", "golan", "blue"),
    ("upper_galilee_farp", "Upper Galilee forward arming point", "upper_galilee", "blue"),
    ("naqoura_farp", "Naqoura FARP", "naqoura", "red"),
    ("rayak_farp", "Rayak FARP", "zahle", "red"),
    ("arsal_farp", "Arsal FARP", "arsal", "red"),
    ("khalkhalah_farp", "Khalkhalah FARP", "khalkhalah", "red"),
    ("damascus_farp", "Damascus FARP", "damascus", "red"),
    ("homs_farp", "Homs FARP", "homs", "red"),
    ("tadmur_farp", "Tadmur FARP", "palmyra", "red"),
    ("hama_farp", "Hama FARP", "hama", "red"),
    ("taftanaz_farp", "Taftanaz FARP", "idlib", "red"),
    ("kuweires_farp", "Kuweires FARP", "kuweires", "red"),
]


RED_BASES = [
    ("khalkhalah", "Khalkhalah", "Khalkhalah", "khalkhalah", 3, 2),
    ("marj_ab", "Marj Ruhayyil", "Marj Ruhayyil", "marj", 2, 2),
    ("damascus", "Damascus", "Damascus", "damascus", 6, 6),
    ("dumayr", "Al-Dumayr", "Al-Dumayr", "dumayr", 4, 3),
    ("nasiriyah", "An Nasiriyah", "An Nasiriyah", "nasiriyah", 3, 3),
    ("sayqal", "Sayqal", "Sayqal", "sayqal", 3, 3),
    ("shayrat", "Shayrat", "Shayrat", "shayrat", 5, 5),
    ("tiyas", "Tiyas", "Tiyas", "tiyas", 3, 3),
    ("palmyra", "Palmyra", "Palmyra", "palmyra", 2, 2),
    ("hama", "Hama", "Hama", "hama", 3, 3),
    ("bassel", "Bassel Al-Assad", "Bassel Al-Assad", "latakia", 4, 3),
    ("taftanaz", "Taftanaz", "Taftanaz", "idlib", 2, 2),
    ("aleppo", "Aleppo", "Aleppo", "aleppo", 4, 4),
    ("kuweires", "Kuweires", "Kuweires", "kuweires", 2, 2),
]


def _target_ids(zone_id: str) -> tuple[str, str, str]:
    preserved = {
        "south": ("south_sam", "south_c2", "south_armor"),
        "marj": ("marj_sam", "marj_fuel", "marj_armor"),
        "damascus": ("damascus_sam", "damascus_depot", "damascus_armor"),
        "shayrat": ("shayrat_sam", "shayrat_depot", "shayrat_armor"),
    }
    return preserved.get(zone_id, (f"{zone_id}_sam", f"{zone_id}_strike", f"{zone_id}_armor"))


def apply(spec: dict) -> dict:
    """Replace the old four-zone red corridor with the 32-zone campaign."""
    blue_zones = [deepcopy(z) for z in spec["zones"] if z["owner"] == "blue"]
    for zone in blue_zones:
        zone["neighbors"] = list(NEIGHBORS[zone["id"]])
        zone["ui_col"], zone["ui_row"] = BLUE_GRID[zone["id"]]

    red_zones = []
    by_zone = {}
    for red_index, row in enumerate(RED_ZONES):
        (zone_id, label, name, airport, dx, dy, col, grid_row, tier,
         force, sam, strategic, formation) = row
        sam_id, strike_id, armor_id = _target_ids(zone_id)
        zone = {
            "id": zone_id,
            "map_label": label,
            "name": name,
            "airport": airport,
            "dx": dx,
            "dy": dy,
            "owner": "red",
            "neighbors": list(NEIGHBORS[zone_id]),
            "ui_col": col,
            "ui_row": grid_row,
            "tier": tier,
            "nation": "Lebanon" if red_index < 12 else "Syria",
            "formation": formation,
            "mission_chain": ["SEAD", "DEAD", "STRIKE", "CAS"],
            "objectives": {"sam": sam_id, "strike": strike_id, "armor": armor_id},
        }
        red_zones.append(zone)
        by_zone[zone_id] = {"force": force, "sam": sam, "strategic": strategic, "tier": tier,
                            "formation": formation, "name": name, "ids": (sam_id, strike_id, armor_id)}

    blue_targets = [deepcopy(t) for t in spec["targets"] if t["side"] == "blue"]
    farp_for_zone = {zone: (fid, name) for fid, name, zone, _ in FARPS}
    red_targets = []
    for zone_id, data in by_zone.items():
        sam_id, strike_id, armor_id = data["ids"]
        sam = SAM[data["sam"]]
        priority = 20 + data["tier"] * 5
        red_targets.append({
            "id": sam_id,
            "name": f"{data['name']} {sam['title']}",
            "kind": "SAM",
            "side": "red",
            "zone": zone_id,
            "dx": 1800,
            "dy": 2200,
            "types": list(sam["types"]),
            "radars": list(sam["radars"]),
            "priority": priority + 3,
            "chain_objective": "SAM",
            "formation": data["formation"],
            "threat": f"{sam['title']}; local guns and fighters may protect the sector",
        })
        farp = farp_for_zone.get(zone_id)
        strategic_kind = data["strategic"]
        strategic_name = f"{data['name']} {strategic_kind.lower()} site"
        strategic_types = list(STRATEGIC[strategic_kind])
        target = {
            "id": strike_id,
            "name": strategic_name,
            "kind": strategic_kind,
            "side": "red",
            "zone": zone_id,
            "dx": -2200,
            "dy": 1200,
            "types": strategic_types,
            "priority": priority + 1,
            "chain_objective": "STRIKE",
            "formation": data["formation"],
        }
        if farp:
            target.update(name=f"{farp[1]} logistics", kind="FUEL", types=list(STRATEGIC["FUEL"]),
                          farp=farp[0], dx=-2600, dy=-1200)
        red_targets.append(target)
        red_targets.append({
            "id": armor_id,
            "name": f"{data['name']} garrison — {data['formation']}",
            "kind": "ARMOR",
            "side": "red",
            "zone": zone_id,
            "dx": 400,
            "dy": -900,
            "types": list(FORCES[data["force"]]),
            "priority": priority + 2,
            "chain_objective": "CAS",
            "formation": data["formation"],
            "threat": "Armoured/mechanised garrison with organic short-range air defence",
        })

    blue_bases = [deepcopy(b) for b in spec["bases"] if b["side"] == "blue"]
    red_bases = []
    for base_id, name, airport, zone, fighters, strikers in RED_BASES:
        red_bases.append({
            "id": base_id,
            "name": name,
            "airport": airport,
            "zone": zone,
            "side": "red",
            "aircraft": {"MiG-29S": fighters, "Su-24M": strikers},
            "resources": {"fuel": 80 if fighters <= 3 else 100,
                          "ammo": 80 if fighters <= 3 else 100,
                          "supply": 80 if fighters <= 3 else 100},
        })

    existing_fields = [deepcopy(f) for f in spec.get("airfields", []) if f["zone"] in {z["id"] for z in blue_zones}]
    red_fields = [
        {"airport": "Naqoura", "zone": "naqoura"},
        {"airport": "Beirut-Rafic Hariri", "zone": "beirut"},
        {"airport": "Rayak", "zone": "zahle"},
        {"airport": "Rene Mouawad", "zone": "tripoli"},
    ]

    spec["zones"] = blue_zones + red_zones
    spec["targets"] = blue_targets + red_targets
    spec["bases"] = blue_bases + red_bases
    spec["airfields"] = existing_fields + red_fields
    spec["farps"] = [
        {"id": fid, "name": name, "airport": name, "zone": zone, "owner": owner,
         "dx": -900, "dy": -900, "physical": True}
        for fid, name, zone, owner in FARPS
    ]
    spec["red_zone_count"] = len(red_zones)
    spec["zone_mission_stages"] = 4
    spec["supply_hops"] = 4
    # Keep enough of the global 180-unit budget free for flights and convoys
    # even when captures and counterattacks fragment the front. Player/AI-bound
    # objectives rank first; waiting sectors retain their exact progress.
    spec["active_front_unit_limit"] = 60
    spec["added_bases"] = [b[0] for b in RED_BASES if b[0] not in {"khalkhalah", "marj_ab", "damascus", "shayrat", "tiyas"}]
    return spec
