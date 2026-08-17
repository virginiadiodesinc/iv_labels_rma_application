"""
db_service.py

Turns a canonical dict into an upsert against Build_Info, using the registry
for the field-name mapping instead of hand-listing columns per route.
"""

from app.services import field_registry as fr
from app.db.database import db_session
from app.db.models import Build_Info, Build_Parts, Notes, IV_Info, IV_Points, Polarity
from app.db import queries


def stage_upsert_build_info(canonical: dict, **extra_columns):
    """extra_columns is for things that aren't part of the form-sourced
    registry at all -- e.g. block_file_path, which is only known after
    file_service has actually written the file. Only flushes (via
    queries.upsert_table_entry) -- does NOT commit. See save_orchestrator.py
    for why that's the caller's job."""
    block_id = fr.build_block_id(canonical)
    kwargs = fr.canonical_to_db_kwargs(canonical, "Build_Info")
    kwargs["block_id"] = block_id
    kwargs.update(extra_columns)
    return queries.upsert_table_entry(db_session, Build_Info, block_id, **kwargs)


def stage_replace_build_parts_and_notes(canonical: dict, parts_list: list, notes_list: list) -> list:
    """Full-build saves replace ALL parts for this block wholesale --
    Build_Parts has no meaningful single row to upsert (its real PK,
    instance_id, is an unrelated autoincrement int; block_id is just a
    repeated FK column on every row), so delete-then-reinsert is the
    correct operation here, not a per-row upsert like Build_Info gets.
    Only flushes -- does not commit, same as everything else in here."""
    block_id = fr.build_block_id(canonical)
 
    existing_parts = queries.get_table_entries(db_session, Build_Parts, block_id=block_id)
    for entry in existing_parts:
        queries.delete_table_entry(db_session, Build_Parts, entry.instance_id)

    existing_notes = queries.get_table_entries(db_session, Notes, block_id=block_id)
    for entry in existing_notes:
        queries.delete_table_entry(db_session, Notes, entry.instance_id)
 
    new_entries = []
    for part in parts_list:
        entry = queries.add_table_entry(db_session, Build_Parts, block_id=block_id, **part)
        new_entries.append(entry)
    for note in notes_list:
        entry = queries.add_table_entry(db_session, Notes, block_id=block_id, **note)
        new_entries.append(entry)
    return new_entries


def stage_add_iv_info(canonical: dict) -> object:
    """Every IV save is a NEW row -- unlike Build_Info (single upsertable
    row) or Build_Parts (delete-and-replace-all), there's a genuine 0-to-n
    relationship between a build and its IVs, so this is always a plain
    insert, never an upsert or replace."""
    kwargs = fr.canonical_to_db_kwargs(canonical, "IV_Info")
    kwargs["build_id"] = fr.build_block_id_from_iv(canonical)
    kwargs["polarity"] = Polarity.POSITIVE if canonical.get("polarity") == "+" else Polarity.NEGATIVE
    return queries.add_table_entry(db_session, IV_Info, **kwargs)


def stage_add_iv_points(canonical: dict) -> object:
    """canonical must already have 'iv_id' merged in -- the orchestrator
    sets this right after stage_add_iv_info runs, since add_table_entry's
    flush() assigns the PK before this is called."""
    kwargs = fr.canonical_to_db_kwargs(canonical, "IV_Points")
    kwargs["iv_id"] = canonical["iv_id"]
    return queries.add_table_entry(db_session, IV_Points, **kwargs)


def commit_db_changes():
    queries.commit_db_changes(db_session)


def roll_back_db_changes():
    queries.roll_back_db_changes(db_session)

