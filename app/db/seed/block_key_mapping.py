"""
Editable configuration for mapping raw block_converter output keys onto your
DB-ready field names.

This is the file you touch whenever a template changes field names, or you
decide to rename something for the DB schema. It does NOT require re-parsing
any files -- rerun transform_block_records.py and it re-reads
raw_block_records.jsonl from disk.

FIELD_NAME_MAP:
    Maps raw_fields key -> db-ready key. Any raw key not listed here is
    dropped during transform (see DROP_UNMAPPED_KEYS below) -- this is
    intentional, so that unexpected/legacy keys don't silently leak into the
    DB-ready output without you having decided what to call them.

REQUIRED_DB_KEYS:
    Keys that MUST be present (and non-blank) in the transformed record for
    it to be considered "clean." Records missing these are still written to
    db_ready_block_records.jsonl, but are also flagged in
    block_transform_warnings.jsonl so you can spot-check them.

BLANK_EQUIVALENTS:
    Values that should be treated as "blank" for the purposes of required-
    field checking (case-insensitive, whitespace-stripped comparison).
"""

FIELD_NAME_MAP = {
    # example:
    # "insp_result": "inspection_result",
    # "pb1_val": "pb1_value",
    # "pb2_val": "pb2_value",
    'block_engraving': 'block_engraving', 
    'block_revision': 'block_revision', 
    'block_serial_number': 'block_serial_number', 
    'inspection_date': 'inspection_date', 
    'inspection_initials': 'inspection_initials',
    'pb1_build_name': 'pb1_build_name',
    'pb1_date': 'pb1_date', 
    'pb1_initials': 'pb1_initials', 
    'pb2_build_name': 'pb2_build_name', 
    'pb2_date': 'pb2_date', 
    'pb2_initials': 'pb2_initials', 
    'pb2_inspection_initials': 'pb2_inspection_initials'

}

# If True, any raw_fields key with no entry in FIELD_NAME_MAP is silently
# dropped from the transformed record. If False, unmapped keys pass through
# unchanged (useful early on, before you've filled out the full mapping).
DROP_UNMAPPED_KEYS = True

REQUIRED_DB_KEYS = [
    'block_engraving',
    'block_serial_number',
]

BLANK_EQUIVALENTS = {"", "na", "n/a", "none", "null"}

BLANK_DEFAULTS = {
    'block_revision': 'A',
    'inspection_initials': 'UNK',
    'inspection_date': '01/01/0001'
    }

# Keyed by POST-mapping (db-ready) field name. Any field listed here has its
# raw value parsed as a date during transform and normalized to an ISO
# (YYYY-MM-DD) string for JSONL storage -- JSON has no native date type, so
# the actual conversion to a real datetime.date object happens later, in
# the seed script, right before insert.
DATE_FIELDS = [
    "inspection_date",
    "cleanout_date",
    "pb1_date",
    "pb2_date",
    "full_build_date",
]

# Formats tried IN ORDER against each DATE_FIELDS raw value. Ground truth
# from labview_date_to_iso(): LabView dates are "%m/%d/%Y" (no leading
# zeros -- strptime handles that fine) with ALL whitespace stripped first,
# not just leading/trailing.
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",
]

# What to do when a DATE_FIELDS value fails to parse against every format
# above:
#   "warn_and_drop" (default) -- field is dropped from the record, reported
#       as a warning in block_transform_warnings.jsonl. Nothing is
#       fabricated. Recommended for this bulk historical seed, since a
#       silently-wrong date is worse than a missing one across 25k records.
#   "file_mtime" -- matches the live app's
#       labview_date_to_iso_with_modified_date_fallback() behavior: falls
#       back to the source file's mtime (already captured as source_mtime
#       during parse, no extra filesystem access needed). Still logged as a
#       warning (fallback_used, not silent) so you can review how often it
#       fired.
DATE_PARSE_FALLBACK = "file_mtime"


def is_blank(value):
    if value is None:
        return True
    return str(value).strip().lower() in BLANK_EQUIVALENTS

# {
#     'block_engraving': 'WR6.5QWR4', 
#     'block_revision': 'A', 
#     'block_serial_number': '8-12', 
#     'inspection_date': '2023-10-05', 
#     'inspection_initials': 'JBS', 
#     'pb1_date': '2023-10-05', 
#     'pb1_initials': '', 
#     'pb2_build_name': '', 
#     'pb2_date': '', 
#     'pb2_initials': '', 
#     'pb2_pass_fail': '', 
#     'pb2_bond_pads_count': '', 
#     'pb2_components_count': '', 
#     'pb2_inspection_initials': ''
# }
