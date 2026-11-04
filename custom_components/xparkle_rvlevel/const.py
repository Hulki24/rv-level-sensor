"""Constants and built-in profiles for RV Level Sensor."""
DOMAIN = "xparkle_rvlevel"
PLATFORMS = ["sensor"]
SERVICE_FFF0 = "0000fff0-0000-1000-8000-00805f9b34fb"
CHAR_FFF1 = "0000fff1-0000-1000-8000-00805f9b34fb"
CHAR_FFF2 = "0000fff2-0000-1000-8000-00805f9b34fb"
CHAR_FFF3 = "0000fff3-0000-1000-8000-00805f9b34fb"
CHAR_FFF4 = "0000fff4-0000-1000-8000-00805f9b34fb"
CHAR_FFF6 = "0000fff6-0000-1000-8000-00805f9b34fb"
CHAR_FFF8 = "0000fff8-0000-1000-8000-00805f9b34fb"
CONF_ADDRESS = "address"
CONF_NAME = "name"
CONF_LONGITUDINAL_LENGTH = "longitudinal_length"
CONF_TRANSVERSE_WIDTH = "transverse_width"
CONF_VEHICLE_PROFILE = "vehicle_profile"
CONF_VEHICLE_MANUFACTURER = "vehicle_manufacturer"
CONF_VEHICLE_MODEL = "vehicle_model"
CONF_VEHICLE_YEAR = "vehicle_year"
CONF_WEDGE_PROFILE = "wedge_profile"
CONF_SENSOR_ORIENTATION = "sensor_orientation"
SENSOR_ORIENTATION_NORMAL = "normal"
SENSOR_WALL_RIGHT = "wall_right"
SENSOR_WALL_LEFT = "wall_left"
SENSOR_WALL_FRONT = "wall_front"
SENSOR_WALL_REAR = "wall_rear"
SENSOR_ORIENTATION_ROTATED_180 = "rotated_180"
# Kept only for backwards compatibility with existing config entries.
CONF_WEDGE_COUNT = "wedge_count"
DEFAULT_LONGITUDINAL_LENGTH = 4.332
DEFAULT_TRANSVERSE_WIDTH = 1.74
DEFAULT_VEHICLE_PROFILE = "ahorn_canada_ad_2019"
DEFAULT_WEDGE_PROFILE = "milenco_triple_3"
DEFAULT_SENSOR_ORIENTATION = SENSOR_ORIENTATION_NORMAL
DEFAULT_WEDGE_COUNT = 2

# track is the effective transverse calculation width. For Master III profiles
# it follows the existing 1.74 m setup (between Renault's 1.75/1.73 m tracks).
# 2026 Master IV uses the mean of 1.77/1.73 m = 1.75 m.
VEHICLE_PROFILES = {}

def _vehicle(key, model, year, wheelbase, track, body, length=None):
    VEHICLE_PROFILES[key] = {
        "label": f"Ahorn Camp · {model} · {year}", "manufacturer": "Ahorn Camp",
        "model": model, "year": year, "wheelbase": wheelbase, "track": track,
        "body": body, "length": length,
    }

# Canada generation on Renault Master III. Separate model-year entries are
# intentional so later corrections/changes can be made without migrations.
for _year in range(2019, 2026):
    _vehicle(f"ahorn_canada_ad_{_year}", "Canada AD", _year, 4.332, 1.74, "alcove", 7.32)

# Canada range: 2022 and 2024 are covered by Ahorn technical catalogues; 2023 is
# explicitly listed by Ahorn model pages, and 2025 vehicles retain the same 4332 mm
# Master-III wheelbase (also documented by ADAC for AD/TF).
for _year in (2022, 2023, 2024, 2025):
    for _model, _body, _length in (
        ("Canada AE", "alcove", 7.48), ("Canada AS", "alcove", 7.48),
        ("Canada TE", "semi-integrated", 7.48), ("Canada TQ", "semi-integrated", 7.48),
        ("Canada TF", "semi-integrated", 7.48), ("Canada TU", "semi-integrated", 6.97),
    ):
        _slug = _model.lower().replace(" ", "_")
        _vehicle(f"ahorn_{_slug}_{_year}", _model, _year, 4.332, 1.74, _body, _length)

# New 2026 generation on Renault Master IV. Ahorn technical data gives 3583 mm
# for CV560, 3585 mm for T590/A595 and 4213 mm for the long models.
for _model, _wb, _body, _length in (
    ("CV 560", 3.583, "campervan", 5.68), ("CV 630", 4.213, "campervan", 6.31),
    ("T 590", 3.585, "semi-integrated", 5.99), ("T 640", 4.213, "semi-integrated", 6.49),
    ("T 680", 4.213, "semi-integrated", 6.99), ("T 690", 4.213, "semi-integrated", 6.99),
    ("TE 740", 4.213, "semi-integrated", 7.48), ("TQ 740", 4.213, "semi-integrated", 7.48),
    ("A 595", 3.585, "alcove", 5.99), ("A 690", 4.213, "alcove", 6.99),
    ("A 720", 4.213, "alcove", 7.20),
):
    _slug = _model.lower().replace(" ", "_")
    _vehicle(f"ahorn_{_slug}_2026", _model, 2026, _wb, 1.75, _body, _length)

VEHICLE_PROFILES["custom"] = {"label": "Benutzerdefiniertes Fahrzeug", "manufacturer": "Benutzerdefiniert", "model": "Benutzerdefiniert"}

WEDGE_PROFILES = {
    "milenco_triple_3": {"label": "Milenco · Triple Level / Triple 3", "manufacturer": "Milenco", "model": "Triple Level", "stages_cm": [4.0, 8.0, 12.0]},
    "milenco_trident": {"label": "Milenco · Trident", "manufacturer": "Milenco", "model": "Trident", "stages_cm": [4.0, 11.0, 17.0]},
    "milenco_quattro_2": {"label": "Milenco · Quattro 2", "manufacturer": "Milenco", "model": "Quattro 2", "stages_cm": [4.0, 8.0, 12.0, 18.0]},
    "thule_levelers": {"label": "Thule · Levelers 307617", "manufacturer": "Thule", "model": "Levelers 307617", "stages_cm": [4.4, 7.8, 11.2]},
    "froli_stufenkeil": {"label": "Froli · Stufenkeil", "manufacturer": "Froli", "model": "Stufenkeil", "stages_cm": [4.5, 7.5, 10.5]},
    "froli_stufenkeil_xl": {"label": "Froli · Stufenkeil XL", "manufacturer": "Froli", "model": "Stufenkeil XL", "stages_cm": [6.5, 11.5]},
    "fiamma_level_up": {"label": "Fiamma · Level Up", "manufacturer": "Fiamma", "model": "Level Up", "stages_cm": [4.0, 7.0, 13.0]},
    "fiamma_level_up_premium_s": {"label": "Fiamma · Level Up Premium S", "manufacturer": "Fiamma", "model": "Level Up Premium S", "stages_cm": [4.0, 8.0, 13.0]},
}
