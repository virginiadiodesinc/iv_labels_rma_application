"""
save_orchestrator.py

The only place that decides "DB then file" and handles the failure of
either. Routes never call file_service or db_service directly.

DB goes first because it's now stage-then-commit (see queries.py /
db_service.py): staging is cheap and fully reversible via
roll_back_db_changes, since nothing is committed yet. The file write goes
second because disk writes aren't reversible the same way. block_file_path
is only known *after* the file write succeeds, so it gets attached to the
already-staged entry right before the single commit at the end -- there's
no need to stage the DB row twice.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from app.services import field_registry as fr
from app.services import file_service
from app.services import db_service
from app import config
import traceback


@dataclass
class SaveResult:
    success: bool
    failure_cause: Optional[str] = None   # "file" or "db"
    error: Optional[Exception] = None


def _save_block_file_and_info(canonical: dict, write_file: Callable[[dict, str], str], write_db: Callable[[dict], object]) -> SaveResult:
    """write_file(canonical, block_file_directory) -> path written. Bind the
    section (or full-overwrite) choice at the call site below, so every
    block-file save variant shares this one implementation."""
    try:
        entry = write_db(canonical)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    try:
        file_path = write_file(canonical, config.block_file_directory)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="file", error=e)

    entry.block_file_path = file_path
    db_service.commit_db_changes()
    return SaveResult(success=True)


def save_inspection_info(canonical: dict) -> SaveResult:
    return _save_block_file_and_info(
        canonical,
        lambda c, d: file_service.save_block_file_section(c, fr.Section.INSPECTION, d),
        lambda c: db_service.stage_upsert_build_info_sections(c, [fr.Section.INSPECTION, fr.Section.IDENTITY])
    )


def save_pb1_info(canonical: dict) -> SaveResult:
    return _save_block_file_and_info(
        canonical,
        lambda c, d: file_service.save_block_file_section(c, fr.Section.PB1, d),
        lambda c: db_service.stage_upsert_build_info_sections(c, [fr.Section.PB1, fr.Section.IDENTITY])
    )


def save_pb2_info(canonical: dict) -> SaveResult:
    return _save_block_file_and_info(
        canonical,
        lambda c, d: file_service.save_block_file_section(c, fr.Section.PB2, d),
        lambda c: db_service.stage_upsert_build_info_sections(c, [fr.Section.PB2, fr.Section.IDENTITY])
    )


def save_all_block_info(canonical: dict) -> SaveResult:
    """The deliberate full-overwrite path -- canonical here needs to be
    complete (all sections' fields present), since save_full_block_file
    blanks anything canonical doesn't have. Make sure whatever route calls
    this gathers the full form (hx-include covering #block-info,
    #inspection-info, #pb1-info, #pb2-info), not just one section's."""
    return _save_block_file_and_info(
        canonical, 
        file_service.save_full_block_file,
        db_service.stage_upsert_build_info
        )
