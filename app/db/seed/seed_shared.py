"""
Shared helpers used by BOTH seed_block_info.py and seed_build_info.py.

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


def build_block_id(fields):
    return f"{fields['block_engraving']} {fields['block_serial_number']} {fields['block_revision']}"


def valid_columns(model):
    return {c.name for c in model.__table__.columns}


def find_invalid_columns(fields, valid_column_names):
    return [key for key in fields if key not in valid_column_names]


def find_missing_required(fields, required_fields):
    return [key for key in required_fields if not fields.get(key)]
