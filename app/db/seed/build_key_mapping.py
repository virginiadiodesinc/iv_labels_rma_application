"""
Editable configuration for build-file transform. Same philosophy as
block_key_mapping.py: this is the file you touch when a template changes,
not the transform script itself.

Split into two kinds of config:
  - FIELD_NAME_MAP / REQUIRED_DB_KEYS / BLANK_DEFAULTS / DATE_* / is_blank:
    identical in spirit to block_key_mapping.py -- flat, one-to-one fields
    that end up as Build_Info columns.
  - PART_SLOTS_* / NOTES_LIST_KEY / EXTRA_NOTE_KEYS: build-specific, since
    build files fan out into Build_Parts and Notes rows too, which block
    files never needed.
"""

# ---------------------------------------------------------------------------
# Flat Build_Info fields (same shape/purpose as block_key_mapping.py)
# ---------------------------------------------------------------------------

FIELD_NAME_MAP = {
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
    'pb2_inspection_initials': 'pb2_inspection_initials',
    'full_build_name': 'full_build_name',
    'full_build_date': 'full_build_date',
    'full_build_initials': 'full_build_initials',
    # NOTE: full_build_initials_again / full_build_date_again are the
    # form's confirmation fields -- intentionally left unmapped and
    # dropped (DROP_UNMAPPED_KEYS below), same as block.
}

DROP_UNMAPPED_KEYS = True

REQUIRED_DB_KEYS = [
    'block_engraving',
    'block_serial_number',
]

BLANK_EQUIVALENTS = {"", "na", "n/a", "none", "null"}

# Front half of a build file is the same form data as a block file, so
# these mirror block_key_mapping.py's defaults -- including the
# intentionally-wrong inspection_date, which exists specifically to fail
# date parsing and trigger the file_mtime fallback (confirmed intentional).
BLANK_DEFAULTS = {
    'block_revision': 'A',
    'inspection_initials': 'UNK',
    'inspection_date': '01/01/0001',
}

DATE_FIELDS = [
    "inspection_date",
    "cleanout_date",
    "pb1_date",
    "pb2_date",
    "full_build_date",
]

# Build raw dates already arrive as ISO strings (per your sample data),
# same as block.
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",
]

DATE_PARSE_FALLBACK = "file_mtime"


def is_blank(value):
    if value is None:
        return True
    return str(value).strip().lower() in BLANK_EQUIVALENTS


# ---------------------------------------------------------------------------
# Parts extraction (build-specific -- block files have no parts)
# ---------------------------------------------------------------------------
#
# Each slot describes one Build_Parts row. "name_lot_key" points at a
# combined "NAME_LOT" raw string, split via
# app.services.string_utilities.separate_part_and_lot() -- same helper the
# original seed_build_files_post_template_change.py used. MMIC is the
# exception: its name and lot already arrive as two separate raw keys.

PART_SLOTS_NEW_STYLE = [
    {"part_type": "DIODE",   "name_lot_key": "diode_1",   "quantity_key": "diode_1_chip_count"},
    {"part_type": "CIRCUIT", "name_lot_key": "circuit_1", "quantity": 1},
    {"part_type": "FILTER",  "name_lot_key": "filter_1",  "quantity": 1},
    {"part_type": "DIODE",   "name_lot_key": "diode_2",   "quantity_key": "diode_2_chip_count"},
    {"part_type": "CIRCUIT", "name_lot_key": "circuit_2", "quantity": 1},
    {"part_type": "FILTER",  "name_lot_key": "filter_2",  "quantity": 1},
    {"part_type": "PCB",     "name_lot_key": "pcb_info",  "quantity": 1},
    {"part_type": "MMIC",    "name_key": "mmic_name", "lot_key": "mmic_lot", "quantity": 1},
]

# CONFIRMED (per conversation): old-style forms have fewer dedicated
# fields, so people sometimes used a spare field (e.g. filter_2) to record
# whatever didn't have its own slot -- known behavior, part of why the
# template was updated. Rather than guessing an exact part_type for that
# slot, it's marked "ambiguous": True below -- transform only treats it as
# a part if the text actually looks like a real part/lot pair (a non-blank
# lot comes back from separate_part_and_lot). If it doesn't, the raw text
# becomes a Note instead of a mislabeled part, per "doesn't matter which
# exact type, otherwise call it a note -- someone can clean it up later."
PART_SLOTS_OLD_STYLE = [
    {"part_type": "DIODE",   "name_lot_key": "diode_1",   "quantity_key": "diode_1_chip_count"},
    {"part_type": "CIRCUIT", "name_lot_key": "circuit_1", "quantity": 1},
    {"part_type": "FILTER",  "name_lot_key": "filter_1",  "quantity": 1},
    {"part_type": "DIODE",   "name_lot_key": "diode_2",   "quantity_key": "diode_2_chip_count"},
    {"part_type": "CIRCUIT", "name_lot_key": "circuit_2", "quantity": 1},
    {"part_type": "PCB",     "name_lot_key": "filter_2",  "quantity": 1, "ambiguous": True},
]

# ---------------------------------------------------------------------------
# Notes extraction
# ---------------------------------------------------------------------------

NOTES_LIST_KEY = "notes"
EXTRA_NOTE_KEYS = ["vbr", "indium_info"]
