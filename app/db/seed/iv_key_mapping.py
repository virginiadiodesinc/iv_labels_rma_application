"""
Editable configuration for mapping raw iv_file_converter output keys onto
DB-ready field names, driving transform_iv_records.py.

Same philosophy as block_key_mapping.py / build_key_mapping.py: this is the
file you touch when a template changes, not the transform script.

Fields intentionally NOT mapped (left out of FIELD_NAME_MAP entirely, so
DROP_UNMAPPED_KEYS drops them silently -- kept here as a comment, not a
None entry, so the reason isn't lost without cluttering the real mapping):
  - build_name       -- must not overwrite the build name from the build file
  - full_build_sn    -- includes the revision, which needs to stay separate
  - block_sn         -- unreliable: not guaranteed to carry the right revision
  - time             -- only relevant to the source filename, not the DB
"""

FIELD_NAME_MAP = {
    "build_sn": "block_serial_number",
    "build_revision": "block_revision",
    "diode": "diode",
    "circuit": "circuit",
    "assembly_number": "assembly_number",
    "polarity": "polarity",
    "block_name": "block_engraving",
    "additional_info": "additional_information",
    "date": "iv_date",
    "points_per_decade": "points_per_decade",
    "ideality": "ideality",
    "is": "saturation_current",
    "rs": "series_resistance",
    "mean_squared_error": "mean_squared_error",
    "r_squared_error": "r_squared_error",
    "hysteresis_std": "hysteresis_standard_deviation",
    "hysteresis_mean": "hysteresis_mean",
    "hysteresis_max": "hysteresis_maximum",
    "hysteresis_min": "hysteresis_minimum",  # was "hysteresis_miniumum" -- typo, doesn't match the model column
    "reverse_current": "reverse_breakdown_current",
    "reverse_voltage": "reverse_breakdown_voltage",
    "voltage_up": "voltage_up_mv",
    "voltage_down": "voltage_down_mv",
    "current": "current_ua",
}

DROP_UNMAPPED_KEYS = True

# >>> VERIFY against the current IV_Info model (post IV_Points fold-in) --
# >>> this is my best guess at everything nullable=False, but I'm going on
# >>> the pre-fold schema for voltage/current/points_per_decade.
REQUIRED_DB_KEYS = [
    "block_engraving",
    "block_serial_number",
    "diode",
    "diode_lot",
    "iv_date",
    "points_per_decade",
    "ideality",
    "saturation_current",
    "series_resistance",
    "mean_squared_error",
    "r_squared_error",
    "polarity",
    "hysteresis_standard_deviation",
    "hysteresis_mean",
    "hysteresis_maximum",
    "hysteresis_minimum",
    "reverse_breakdown_current",
    "reverse_breakdown_voltage",
    "voltage_up_mv",
    "voltage_down_mv",
    "current_ua",
]

BLANK_EQUIVALENTS = {"", "na", "n/a", "none", "null"}

# Only block_revision needs a default here -- inspection_initials/
# inspection_date from the block/build configs don't apply to IV_Info at
# all (no such columns), so they're not copied over.
BLANK_DEFAULTS = {
    "block_revision": "A",
}

DATE_FIELDS = [
    "iv_date",
]

DATE_INPUT_FORMATS = [
    "%m/%d/%Y",
]

DATE_PARSE_FALLBACK = "file_mtime"


def is_blank(value):
    if value is None:
        return True
    return str(value).strip().lower() in BLANK_EQUIVALENTS


# ---------------------------------------------------------------------------
# Diode / circuit lot splitting (IV-specific: two flat fields, not a parts
# list like build files -- IV_Info has dedicated diode/diode_lot and
# circuit/circuit_lot columns).
# ---------------------------------------------------------------------------

# Each entry: raw combined "name_lot" field -> (name db key, lot db key).
# Same su.separate_part_and_lot() helper as build's parts extraction.
NAME_LOT_SPLITS = {
    "diode": ("diode", "diode_lot"),
    "circuit": ("circuit", "circuit_lot"),
}

# ---------------------------------------------------------------------------
# Voltage/current point lists -> comma-joined strings (post IV_Points fold)
# ---------------------------------------------------------------------------

# Post-mapping (db-ready) field names whose raw value is a Python list that
# needs to become ",".join(...)'d into a single string column. Runs BEFORE
# blank-handling, so an empty list becomes "" and flows through the normal
# blank/required-field logic rather than needing a separate check.
LIST_JOIN_FIELDS = [
    "voltage_up_mv",
    "voltage_down_mv",
    "current_ua",
]

# ---------------------------------------------------------------------------
# Numeric coercion -- JSON can hold real numbers, so (unlike dates) this
# happens in TRANSFORM, not deferred to seed. float() parses E-notation
# natively, so scientific-notation raw values aren't a special case.
# ---------------------------------------------------------------------------

FLOAT_FIELDS = [
    "ideality",
    "saturation_current",
    "series_resistance",
    "mean_squared_error",
    "r_squared_error",
    "hysteresis_standard_deviation",
    "hysteresis_mean",
    "hysteresis_maximum",
    "hysteresis_minimum",
    "reverse_breakdown_current",
    "reverse_breakdown_voltage",
    "temperature",
]

INT_FIELDS = [
    "points_per_decade",
]

# ---------------------------------------------------------------------------
# Polarity -- stored as the Enum's VALUE STRING during transform (JSON can't
# hold a Python Enum), coerced back to Polarity(...) at seed time, same
# pattern as Note_Type on the build side.
# ---------------------------------------------------------------------------

# Raw value -> Polarity enum value string. Add more raw spellings here if
# the converter or older files use something other than "+"/"-".
POLARITY_MAP = {
    "+": "positive",
    "-": "negative",
}