"""
Shared helpers used by seed_block_info.py, seed_build_info.py, and
seed_iv_info.py.

The reason this exists as its own module rather than being duplicated in
each script: build_block_id() MUST return identical output for the block
seed and the build seed given the same engraving/serial/revision, or the
build-file upsert will never find the row the block-file seed created --
it'll silently create a duplicate row instead of updating the right one.

(This already happened once: the block seed's local copy used "_" as a
delimiter, then got hand-edited to " " -- if the build seed had its own
copy, it would be trivial for the two to disagree without anyone noticing
until duplicate rows showed up.)

>>> PLACEHOLDER -- build_block_id() MUST be replaced with the real
>>> field_registry.build_block_id() logic before either seed script is run
>>> for real.
"""

import datetime

# Mirrors how the data is produced in practice: the latest stage wins.
# Block files never contain full_build_date, so for them this naturally
# starts at pb2_date.
LAST_SAVE_DATE_PRIORITY = ["full_build_date", "pb2_date", "pb1_date", "inspection_date"]


def build_block_id(fields):
    return f"{fields['block_engraving']} {fields['block_serial_number']} {fields['block_revision']}"


def valid_columns(model):
    return {c.name for c in model.__table__.columns}


def find_invalid_columns(fields, valid_column_names):
    return [key for key in fields if key not in valid_column_names]


def find_missing_required(fields, required_fields):
    """Presence check, NOT truthiness -- transform already drops any field
    that's genuinely blank (see apply_blank_handling), so by the time a
    record reaches seed, "key absent" is the only valid signal for
    "missing." A key that IS present should be trusted as-is, whatever its
    value -- `not fields.get(key)` would incorrectly flag legitimate 0 /
    0.0 / False values (e.g. reverse_breakdown_current == 0.0) as missing,
    since those are falsy in Python but perfectly valid data."""
    return [key for key in required_fields if key not in fields]


def is_protected(existing_from_file):
    """True if an EXISTING row must not be overwritten by a file seed.
    `is not True` (rather than `== False`) deliberately treats NULL as
    protected too -- a row whose provenance is unknown shows up in the
    protected log for review instead of being silently clobbered.
    Shared by build + IV seeding so the rule can't drift between them."""
    return existing_from_file is not True


def compute_last_save_date(fields, source_mtime=None):
    """Full build > PB2 > PB1 > Inspection (values must already be
    datetime.date objects, i.e. AFTER coerce_dates). If none exist, falls
    back to the source file's mtime, and only then to now(). One shared
    copy so block + build seeding can't drift apart."""
    for key in LAST_SAVE_DATE_PRIORITY:
        value = fields.get(key)
        if value:
            return datetime.datetime.combine(value, datetime.time.min)
    if source_mtime is not None:
        try:
            return datetime.datetime.fromtimestamp(float(source_mtime))
        except (TypeError, ValueError, OSError, OverflowError):
            pass
        try:
            return datetime.datetime.fromisoformat(str(source_mtime))
        except ValueError:
            pass
    return datetime.datetime.now()


def is_stub_row(from_file, block_file_path, build_file_path):
    """True if an existing Build_Info row is a PLACEHOLDER created by the IV
    seed (an IV exists for a block/build that has no info yet -- typically
    an uprev). A stub is from_file=True with NO block or build file path.
    File seeds may fill a stub in; anything the app has saved
    (from_file != True) is never a stub and stays protected."""
    return from_file is True and block_file_path is None and build_file_path is None
