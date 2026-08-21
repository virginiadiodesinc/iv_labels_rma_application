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


def stage_upsert_iv_info(canonical: dict, iv_file_path: str) -> object:
    """Keyed by the computed file path, not a business identity like
    Build_Info's upsert or a bare delete-and-reinsert like Build_Parts --
    "same path" IS the identity rule for an IV file in this app. If a row
    already exists at this path, its old IV_Points get cleared here (fresh
    ones get staged right after by the caller, using the returned entry's
    iv_id) rather than accumulating alongside stale ones from the previous
    save at this same path.

    NOTE: expects canonical to already be enriched
    (fr.enrich_with_build_suffix) -- the orchestrator does that once, up
    top, not this function."""
    existing = queries.get_table_entries(db_session, IV_Info, iv_file_path=iv_file_path)

    kwargs = fr.canonical_to_db_kwargs(canonical, "IV_Info")
    kwargs["build_id"] = fr.build_block_id_from_iv(canonical)
    kwargs["polarity"] = Polarity.POSITIVE if canonical.get("polarity") == "+" else Polarity.NEGATIVE
    kwargs["iv_file_path"] = iv_file_path

    if existing:
        entry = existing[0]
        stage_delete_iv_points(entry.iv_id)  # same-file call, unqualified
        entry = queries.update_table_entry(db_session, IV_Info, entry.iv_id, **kwargs)
    else:
        entry = queries.add_table_entry(db_session, IV_Info, **kwargs)
    return entry


def stage_delete_block_info(canonical: dict) -> object:
    return


def stage_delete_build_info(canonical: dict) -> object:
    return


def stage_delete_iv_info(iv_id):
    """Returns the entry that was deleted -- fetched and kept as a
    reference BEFORE the delete happens, since delete_table_entry itself
    only returns True/False, not the row. Reading entry.iv_file_path /
    entry.heat_file_path after this still works within the same
    transaction (the object isn't invalidated until commit)."""
    entry = db_session.get(IV_Info, iv_id)
    if entry:
        queries.delete_table_entry(db_session, IV_Info, iv_id)
    return entry


def stage_delete_iv_points(iv_id) -> list:
    points = queries.get_table_entries(db_session, IV_Points, iv_id=iv_id)
    for point in points:
        queries.delete_table_entry(db_session, IV_Points, point.point_id)
    return points


def get_iv_info_by_id(iv_id):
    """Direct PK lookup -- IV_Info.iv_id IS the primary key, so this is the
    one thing that should ever be used to name a specific IV row. Replaces
    the old query-by-build_id-then-scan-for-matching-path-stem pattern."""
    return db_session.get(IV_Info, iv_id)


def commit_db_changes():
    queries.commit_db_changes(db_session)


def roll_back_db_changes():
    queries.roll_back_db_changes(db_session)

