"""
db_service.py

Turns a canonical dict into an upsert against Build_Info, using the registry
for the field-name mapping instead of hand-listing columns per route.
"""

from app.services import field_registry as fr
from app.db.database import db_session
from app.db.models import Build_Info
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


def stage_upsert_build_info_sections(canonical: dict, section_list: list[fr.Section], **extra_columns):
    section_canonical = {}
    for canonical_key, canonical_value in canonical.items():
        for field in fr.FIELDS:
            for section in section_list:
                if canonical_key == field.canonical and field.section == section:
                    section_canonical[canonical_key] = canonical_value

    return stage_upsert_build_info(section_canonical, **extra_columns)


def commit_db_changes():
    queries.commit_db_changes(db_session)


def roll_back_db_changes():
    queries.roll_back_db_changes(db_session)

