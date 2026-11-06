"""
db_service.py

Turns a canonical dict into an upsert against Build_Info, using the registry
for the field-name mapping instead of hand-listing columns per route.
"""

from app.services import field_registry as fr
from app.db.database import db_session
from app.db.models import Build_Info, Build_Parts, Notes, IV_Info, Polarity, Note_Type, Yellow_Flags
from app.db import queries
from sqlalchemy import Integer, case, cast, func, select, or_, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, date, timedelta
import logging

def get_block_and_build_info(canonical: dict):
    block_id = fr.build_block_id(canonical)
    filters = {"block_id": block_id}
    block = queries.get_table_entries(db_session, Build_Info, **filters)[0] if queries.get_table_entries(db_session, Build_Info, **filters) else None
    parts = queries.get_table_entries(db_session, Build_Parts, **filters)
    notes = queries.get_table_entries(db_session, Notes, **filters)
    return block, parts, notes


def get_all_block_revisions(canonical: dict):
    block_engraving = canonical.get("block_engraving")
    block_serial_number = canonical.get("block_serial_number")
    kwargs = {"block_engraving": block_engraving, "block_serial_number": block_serial_number}

    block_revision_entries = queries.get_table_entries(db_session, Build_Info, **kwargs)
    revision_letters = []
    for entry in block_revision_entries:
        revision_letters.append(entry.block_revision)
    revision_letters.sort()
    return revision_letters


def get_all_block_revisions_from_partial_block_id(partial_block_id):
    kwargs = {"block_id": partial_block_id}

    block_revision_entries = queries.get_table_entries_like(db_session, Build_Info, **kwargs)
    revision_letters = []
    for entry in block_revision_entries:
        revision_letters.append(entry.block_revision)
    revision_letters.sort()
    return revision_letters


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
    kwargs["from_file"] = False
    kwargs["last_save_date"] = datetime.now()
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
        queries.delete_table_entry(db_session, Notes, entry.note_id)

    new_entries = []
    for part in parts_list:
        entry = queries.add_table_entry(db_session, Build_Parts, block_id=block_id, **part)
        new_entries.append(entry)
    for index, note in enumerate(notes_list):
        note_type = None
        if 	note["type"].lower() ==  "generic":
            note_type = Note_Type.GENERIC
        elif note["type"].lower() ==  "current_test":
            note_type = Note_Type.CURRENT_TEST
        elif note["type"].lower() ==  "rework_summary":
            note_type = Note_Type.REWORK_SUMMARY
        elif note["type"].lower() ==  "fast_cart_number":
            note_type = Note_Type.FAST_CART_NUMBER
        elif note["type"].lower() ==  "capa_number":
            note_type = Note_Type.CAPA_NUMBER
        elif note["type"].lower() ==  "job_number":
            note_type = Note_Type.JOB_NUMBER
        note_with_proper_type = note.copy()
        note_with_proper_type["type"] = note_type
        entry = queries.add_table_entry(db_session, Notes, block_id=block_id, **note_with_proper_type)
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
    kwargs["from_file"] = False
    return queries.add_table_entry(db_session, IV_Info, **kwargs)


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
    kwargs["from_file"] = False

    if existing:
        entry = existing[0]
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


def get_iv_info_by_id(iv_id):
    """Direct PK lookup -- IV_Info.iv_id IS the primary key, so this is the
    one thing that should ever be used to name a specific IV row. Replaces
    the old query-by-build_id-then-scan-for-matching-path-stem pattern."""
    return db_session.get(IV_Info, iv_id)


def stage_upsert_yellow_flags(canonical: dict) -> object:
    block_id = fr.build_block_id(canonical)
    kwargs = fr.canonical_to_db_kwargs(canonical, "Yellow_Flags")
    kwargs["block_id"] = block_id

    existing = queries.get_table_entries(db_session, Yellow_Flags, block_id=block_id)

    if existing:
        entry = existing[0]
        entry = queries.update_table_entry(db_session, Yellow_Flags, entry.block_id, **kwargs)
    else:
        entry = queries.add_table_entry(db_session, Yellow_Flags, **kwargs)
    return entry


def stage_delete_yellow_flags(canonical: dict) -> object:
    block_id = fr.build_block_id(canonical)

    existing = queries.get_table_entries(db_session, Yellow_Flags, block_id=block_id)
    
    if existing:
        entry = existing[0]
        return db_session.delete(entry)
    else:
        return


def commit_db_changes():
    queries.commit_db_changes(db_session)


def roll_back_db_changes():
    queries.roll_back_db_changes(db_session)



# AUDITING

def serial_sort_keys(col):
    dash = func.instr(col, "-")
    major = case(
        (dash == 0, 0),                                   # no hyphen: no major half
        else_=cast(func.substr(col, 1, dash - 1), Integer),
    )
    minor = case(
        (dash == 0, cast(col, Integer)),                  # no hyphen: whole thing is the minor
        else_=cast(func.substr(col, dash + 1), Integer),
    )
    return [major, minor]


def string_to_bool(value):
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"expected True or False, got '{value}'")


def string_to_datetime(value):
    return datetime.fromisoformat(value.strip())


def string_to_date(value):          # for <input type="date"> and Date columns
    return date.fromisoformat(value.strip())


def string_to_next_day(value):
      return date.fromisoformat(value.strip()) + timedelta(days=1)


FILTER_REGISTRY = {
    "engraving": {"column": Build_Info.block_engraving, "ops": {"eq", "in", "contains"}, "coerce": str},
    "serial":    {"column": Build_Info.block_serial_number, "ops": {"eq", "in", "starts_with"}, "coerce": str},
    "build_name": {
        "ops": {"eq", "contains"},
        "builder": lambda op, v: or_(*[queries.translate_filter(c, op, v) for c in
            (Build_Info.pb1_build_name, Build_Info.pb2_build_name, Build_Info.full_build_name)]),
    },
    "full_build_name": {"column": Build_Info.full_build_name, "ops": {"eq", "in", "contains"}, "coerce": str},
    "pb2_build_name": {"column": Build_Info.pb2_build_name, "ops": {"eq", "in", "contains"}, "coerce": str},
    "has_part": {
        "ops": {"eq"},
        "builder": lambda op, v: Build_Info.parts.any(Build_Parts.part_name == v),
    },
    "has_lot": {
            "ops": {"eq"},
            "builder": lambda op, v: Build_Info.parts.any(Build_Parts.part_lot == v),
        },
    "has_part_and_lot": {
            "ops": {"eq"},
            "builder": lambda op, v: Build_Info.parts.any(and_(Build_Parts.part_name == v[0], Build_Parts.part_lot == v[1])),
    },
    "yellow_flag_status": {"column": Build_Info.flagged, "ops": {"eq"}, "coerce": string_to_bool},
    "audit_info": {"column": Build_Info.audit_info, "ops": {"eq"}},
    "last_save_datetime": {"column": Build_Info.last_save_date, "ops": {"gte", "lte", "lt"}, "coerce": string_to_datetime},
    "full_build_date": {"column": Build_Info.full_build_date, "ops": {"gte", "lte", "lt"}, "coerce": string_to_date},
    "from_file": {"column": Build_Info.from_file, "ops": {"eq"}, "coerce": string_to_bool},
    "revision": {"column": Build_Info.block_revision, "ops": {"eq"}},
}


SORT_REGISTRY = {
    "full_build_date": [Build_Info.full_build_date],
    "save_date": [Build_Info.last_save_date],
    "serial":    serial_sort_keys(Build_Info.block_serial_number),
}


def search_builds(filters, sorts, page, page_size):
    conditions = queries.build_filter_conditions(filters, FILTER_REGISTRY)
    base  = queries.apply_filters(select(Build_Info), conditions)

    total = queries.count_query(db_session, base)                  # count BEFORE sorting

    orderings = queries.build_sort_orderings(sorts, SORT_REGISTRY)
    paged = queries.paginate(queries.apply_sort(base, Build_Info, orderings), page, page_size)
    paged = paged.options(selectinload(Build_Info.parts), selectinload(Build_Info.notes),
                        selectinload(Build_Info.yellow_flags))
    return total, db_session.execute(paged).scalars().all()


def get_filter_menu():
    return {key: sorted(entry["ops"]) for key, entry in FILTER_REGISTRY.items()}


def get_sort_menu():
    return list(SORT_REGISTRY)


def row_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def build_to_dict(build):
    data = row_to_dict(build)
    data["parts"] = [row_to_dict(p) for p in build.parts]
    data["notes"] = [row_to_dict(n) for n in build.notes]
    data["yellow_flags"] = row_to_dict(build.yellow_flags) if build.yellow_flags else None
    return data


# ---------- EDIT COERCION ----------
# For editing, a BLANK means "clear this field" (None), whereas a blank
# filter is skipped entirely -- hence separate from the filter coercions.

def edit_text(value):
    value = (value or "").strip()
    return value or None


def edit_date(value):
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None   # ValueError if malformed


def _text(label):
    return {"label": label, "input": "text", "coerce": edit_text}


def _date(label):
    return {"label": label, "input": "date", "coerce": edit_date}


# ---------- EDIT REGISTRY ----------
# Keys are the section names, which are exactly the fr.Section values
# ("inspection", "pb1", "pb2", "full_build"), and the field keys are
# canonical names == Build_Info column names. block_id and last_save_date
# are deliberately absent.

EDIT_SECTIONS = {
    "inspection": {"title": "Inspection", "fields": {
        "inspection_date":     _date("Inspection date"),
        "inspection_initials": _text("Inspection initials"),
        "cleanout_date":       _date("Cleanout date"),
        "cleanout_initials":   _text("Cleanout initials"),
    }},
    "pb1": {"title": "PB1", "fields": {
        "pb1_build_name": _text("Build name"),
        "pb1_date":       _date("Date"),
        "pb1_initials":   _text("Initials"),
    }},
    "pb2": {"title": "PB2", "fields": {
        "pb2_build_name":          _text("Build name"),
        "pb2_date":                _date("Date"),
        "pb2_initials":            _text("Initials"),
        "pb2_inspection_initials": _text("Inspector"),
    }},
    "full_build": {"title": "Full Build", "fields": {
        "full_build_name":     _text("Build name"),
        "full_build_date":     _date("Date"),
        "full_build_initials": _text("Initials"),
    }},
}


def get_build(block_id):
    return db_session.get(Build_Info, block_id)


def record_audit(block_id, section_name, changes, initials, reason):
    """PLACEHOLDER. The orchestrator calls this in the same transaction as
    the edit, right after staging and before any file is written. Later:
    insert one audit-table row per change here. For now it just logs."""
    logging.getLogger(__name__).info(
        "EDIT %s [%s] by %s reason=%r changes=%r",
        block_id, section_name, initials, reason, changes,
    )


def validate_section_edit(block_id, section_name, form):
    """PURE validation -- touches nothing. Returns
    (new_values, changes, initials, reason):
      new_values  {canonical/column name: coerced value} for every field in the section
      changes     [(column, old, new)] for fields that actually differ
      initials    the editor's initials, uppercased
      reason      free text, may be ''
    Raises ValueError with a user-readable message on any problem."""
    section = EDIT_SECTIONS.get(section_name)
    if section is None:
        raise ValueError("Unknown section.")

    build = db_session.get(Build_Info, block_id)
    if build is None:
        raise ValueError("Build not found.")

    initials = form.get("editor_initials", "").strip().upper()
    if len(initials) != 3:
        raise ValueError("Enter your 3-letter initials.")

    # stale-edit check: reject if someone saved this build since the form loaded
    current = build.last_save_date.isoformat() if build.last_save_date else ""
    if form.get("loaded_save_date", "") != current:
        raise ValueError("This build was changed since you opened it. Cancel and reopen to see the latest.")

    new_values = {}
    for column, field in section["fields"].items():
        try:
            new_values[column] = field["coerce"](form.get(column, ""))
        except ValueError:
            raise ValueError(f"{field['label']}: invalid value.")

    # (old or None) so a legacy '' in the DB doesn't show up as a change to None
    changes = [(column, getattr(build, column), new)
               for column, new in new_values.items()
               if (getattr(build, column) or None) != new]

    return new_values, changes, initials, form.get("edit_reason", "").strip()


def get_parts_and_notes_as_dicts(block_id):
    """The same dict shapes parts_from_form / notes_from_form produce (keys
    are Build_Parts / Notes column names, note type as its lowercase string),
    so parts_service.assign_parts_and_notes_to_build_slots can consume them
    unchanged. Sorted by primary key because slot assignment is order
    dependent ('first DIODE goes to diode1') and relationships have no
    guaranteed order; the ids preserve the original form order."""
    build = db_session.get(Build_Info, block_id)
    parts = [
        {c.name: getattr(p, c.name) for c in p.__table__.columns
         if c.name not in ("instance_id", "block_id")}
        for p in sorted(build.parts, key=lambda p: p.instance_id)
    ]
    notes = [
        {"type": n.type.value, "note": n.note}
        for n in sorted(build.notes, key=lambda n: n.note_id)
    ]
    return parts, notes
