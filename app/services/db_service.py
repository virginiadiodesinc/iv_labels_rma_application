"""
db_service.py

Turns a canonical dict into an upsert against Build_Info, using the registry
for the field-name mapping instead of hand-listing columns per route.
"""

from app.services import field_registry as fr
from app.services import parts_service
from app.db.database import db_session
from app.db.models import Build_Info, Build_Parts, Notes, IV_Info, Polarity, Note_Type, Yellow_Flags
from app.db import queries
from sqlalchemy import Integer, case, cast, func, select, or_, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, date, timedelta
from collections import Counter
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


def _note_type(value: str) -> Note_Type:
    try:
        return Note_Type[value.upper()]
    except (KeyError, AttributeError):
        raise ValueError(f"Unknown note type '{value}'")


# ---------- STAGING ----------

def stage_replace_build_parts(block_id: str, parts_list: list) -> list:
    """Delete-then-reinsert every Build_Parts row for this block. Insert order
    = list order, so instance_id preserves the order slot assignment uses.
    Only flushes."""
    for entry in queries.get_table_entries(db_session, Build_Parts, block_id=block_id):
        queries.delete_table_entry(db_session, Build_Parts, entry.instance_id)
    return [queries.add_table_entry(db_session, Build_Parts, block_id=block_id, **part)
            for part in parts_list]


def stage_replace_notes(block_id: str, notes_list: list) -> list:
    """Same as above for Notes. Only flushes."""
    for entry in queries.get_table_entries(db_session, Notes, block_id=block_id):
        queries.delete_table_entry(db_session, Notes, entry.note_id)
    return [queries.add_table_entry(db_session, Notes, block_id=block_id,
                                    type=_note_type(note["type"]), note=note["note"])
            for note in notes_list]


def stage_replace_build_parts_and_notes(canonical: dict, parts_list: list, notes_list: list) -> list:
    """Regular saves: replace both lists at once. Unchanged signature."""
    block_id = fr.build_block_id(canonical)
    return stage_replace_build_parts(block_id, parts_list) + stage_replace_notes(block_id, notes_list)


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


def search_builds(filter_groups, sorts, page, page_size):
    conditions = queries.build_grouped_filter_conditions(filter_groups, FILTER_REGISTRY)
    base = queries.apply_filters(select(Build_Info), conditions)

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


# Which sections write files (go through save_edited_section). Everything
# else in EDIT_SECTIONS is DB-only.
FILE_SECTIONS = {"inspection", "pb1", "pb2", "full_build"}


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
    "meta": {
        "title": "Audit / Meta",
        "fields": {
            "audit_info": _text("Audit info"),
        },
        "readonly": [
            {"column": "flagged",         "label": "Flagged"},
            {"column": "from_file",       "label": "From file"},
            {"column": "last_save_date",  "label": "Last saved", "fmt": "%m/%d/%Y %H:%M"},
            {"column": "block_file_path", "label": "Block file"},
            {"column": "build_file_path", "label": "Build file"},
        ],
    }
}

# Read off the model, so a flag added to Yellow_Flags later shows up here
# (and in the template, via the yellow_flag_columns() global) automatically.
YELLOW_FLAG_COLUMNS = [c.name for c in Yellow_Flags.__table__.columns if c.name != "block_id"]


def active_yellow_flags(build):
    row = build.yellow_flags
    return [c for c in YELLOW_FLAG_COLUMNS if row is not None and getattr(row, c)]


def _check_editor_and_freshness(build, form):
    """Same two checks validate_section_edit does inline (you can swap those
    for a call to this). Returns the editor's initials."""
    initials = form.get("editor_initials", "").strip().upper()
    if len(initials) != 3:
        raise ValueError("Enter your 3-letter initials.")
    current = build.last_save_date.isoformat() if build.last_save_date else ""
    if form.get("loaded_save_date", "") != current:
        raise ValueError("This build was changed since you opened it. Cancel and reopen to see the latest.")
    return initials


def validate_yellow_flags_edit(block_id, form):
    """PURE validation. The form only contains a checkbox for each flag that
    is currently active, so an unchecked (absent) box means 'clear it'.
    Flags can only be cleared here, never raised: raising is the regular
    save's job. Returns (flags_to_clear, changes, initials, reason)."""
    build = db_session.get(Build_Info, block_id)
    if build is None:
        raise ValueError("Build not found.")
    initials = _check_editor_and_freshness(build, form)

    before = active_yellow_flags(build)
    keep = [c for c in before if c in form]
    flags_to_clear = [c for c in before if c not in keep]

    changes = [(c, True, False) for c in flags_to_clear]
    still_flagged = bool(keep)
    if bool(build.flagged) != still_flagged:      # also repairs 'flagged' with no flag rows
        changes.append(("flagged", bool(build.flagged), still_flagged))

    return flags_to_clear, changes, initials, form.get("edit_reason", "").strip()


def stage_update_build_info_columns(block_id, **updates):
    """Direct column update for DB-only edits (no canonical involved, so it
    works for columns that aren't in the field registry, like audit_info).
    Same bookkeeping as every other edit: from_file False, save date now."""
    updates["from_file"] = False
    updates["last_save_date"] = datetime.now()
    entry = queries.update_table_entry(db_session, Build_Info, block_id, **updates)
    if entry is False:
        raise ValueError("Build not found.")
    return entry


def stage_clear_yellow_flags(block_id, flags_to_clear):
    """Clears the given flags, then keeps the two representations in sync in
    the SAME transaction: if nothing is left raised, the Yellow_Flags row is
    deleted (no row == no flags) and Build_Info.flagged becomes False;
    otherwise flagged stays True. Only flushes -- the orchestrator commits."""
    row = db_session.get(Yellow_Flags, block_id)     # block_id is the PK now
    still_active = False
    if row is not None:
        for name in flags_to_clear:
            if name in YELLOW_FLAG_COLUMNS:
                setattr(row, name, False)
        db_session.flush()
        still_active = any(getattr(row, c) for c in YELLOW_FLAG_COLUMNS)
        if not still_active:
            queries.delete_table_entry(db_session, Yellow_Flags, block_id)
    return stage_update_build_info_columns(block_id, flagged=still_active)


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


# ---------- VALIDATION ----------

LIST_SECTIONS = {"parts", "notes"}


def _part_key(row: dict) -> tuple:
    display = parts_service.part_row_for_display(row)
    return tuple(display[c] for c in parts_service.PART_EDIT_COLUMNS)


def _note_key(row: dict) -> tuple:
    display = parts_service.note_row_for_display(row)
    return (display["type"], display["note"].strip())


def _diff_rows(label, old_rows, new_rows, key_fn, columns) -> list:
    """Rows have no stable identity (they're deleted and reinserted), so this
    compares the lists as multisets: each row only in the old list is
    'removed', each row only in the new one is 'added', and an edited row
    shows up as one of each. Change tuples keep the (column, old, new) shape
    record_audit already gets:
        ("part", {row}, None)   removed
        ("part", None, {row})   added
    If nothing was added or removed but the order changed (which matters for
    build-file slots), one ("part_order", old_keys, new_keys) entry is
    recorded instead."""
    old_keys = [key_fn(r) for r in old_rows]
    new_keys = [key_fn(r) for r in new_rows]
    removed = Counter(old_keys) - Counter(new_keys)
    added = Counter(new_keys) - Counter(old_keys)

    changes = [(label, dict(zip(columns, k)), None) for k in removed.elements()]
    changes += [(label, None, dict(zip(columns, k))) for k in added.elements()]
    if not changes and old_keys != new_keys:
        changes.append((f"{label}_order", old_keys, new_keys))
    return changes


def validate_parts_or_notes_edit(block_id: str, section_name: str, form):
    """PURE validation for the whole-list Parts / Notes edits.
    Returns (new_rows, changes, initials, reason); raises ValueError with a
    user-readable message."""
    if section_name not in LIST_SECTIONS:
        raise ValueError("Unknown section.")
    build = db_session.get(Build_Info, block_id)
    if build is None:
        raise ValueError("Build not found.")
    initials = _check_editor_and_freshness(build, form)

    old_parts, old_notes = get_parts_and_notes_as_dicts(block_id)
    if section_name == "parts":
        new_rows = parts_service.parts_from_edit_form(form)
        changes = _diff_rows("part", old_parts, new_rows, _part_key, parts_service.PART_EDIT_COLUMNS)
    else:
        new_rows = parts_service.notes_from_edit_form(form)
        changes = _diff_rows("note", old_notes, new_rows, _note_key, ("type", "note"))

    return new_rows, changes, initials, form.get("edit_reason", "").strip()