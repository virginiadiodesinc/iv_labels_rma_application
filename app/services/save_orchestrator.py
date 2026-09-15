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
from app.services import postprocess
from app.services import string_utilities
from app import config
import traceback
import os


@dataclass
class SaveResult:
    success: bool
    failure_cause: Optional[str] = None   # "file" or "db"
    error: Optional[Exception] = None


def _save_block_file_and_info(canonical: dict, write_file: Callable[[dict, str], str]) -> SaveResult:
    """write_file(canonical, block_file_directory) -> path written. Bind the
    section (or full-overwrite) choice at the call site below, so every
    block-file save variant shares this one implementation."""
    try:
        entry = db_service.stage_upsert_build_info(canonical)
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

def _save_build_file_and_info(canonical: dict, write_file: Callable[[dict, str], str], parts_list: list[dict], notes_list: list[dict]) -> SaveResult:
    """write_file(canonical, build_file_directory) -> path written. Bind the
    section (or full-overwrite) choice at the call site below, so every
    block-file save variant shares this one implementation."""
    try:
        entry = db_service.stage_upsert_build_info(canonical)
        build_parts_list = db_service.stage_replace_build_parts_and_notes(canonical, parts_list, notes_list)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    try:
        file_path = write_file(canonical, config.build_file_directory)
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
        lambda c, d: file_service.save_block_file_section(c, fr.Section.INSPECTION, d)
    )


def save_pb1_info(canonical: dict) -> SaveResult:
    return _save_block_file_and_info(
        canonical,
        lambda c, d: file_service.save_block_file_section(c, fr.Section.PB1, d)
    )


def save_pb2_info(canonical: dict) -> SaveResult:
    return _save_block_file_and_info(
        canonical,
        lambda c, d: file_service.save_block_file_section(c, fr.Section.PB2, d)
    )


def save_block_info(canonical: dict) -> SaveResult:
    """The deliberate full-overwrite path -- canonical here needs to be
    complete (all sections' fields present), since save_block_file
    blanks anything canonical doesn't have. Make sure whatever route calls
    this gathers the full form (hx-include covering #block-info,
    #inspection-info, #pb1-info, #pb2-info), not just one section's."""
    return _save_block_file_and_info(
        canonical, 
        file_service.save_block_file
        )


def save_build_info(canonical: dict, parts_list: list[dict], notes_list: list[dict]) -> SaveResult:
    return _save_build_file_and_info(
        canonical,
        file_service.save_build_file,
        parts_list,
        notes_list
        )


def save_iv_info(canonical: dict, vup_list: list, vdown_list: list, isource_list: list,
                  heat_current_list: list = None, heat_voltage_list: list = None) -> SaveResult:
    canonical = fr.stamp_iv_datetime(canonical)
    # Enriched ONCE here -- get_iv_file_path, stage_upsert_iv_info, and
    # save_iv_file all assume this already happened, so they don't each
    # redo the CSV lookup.
    canonical = fr.enrich_with_build_suffix(
        canonical, string_utilities.get_build_name_with_suffix,
        build_name_key="iv_build_name", block_engraving_key="iv_block_engraving",
        output_key="iv_full_build_name_with_suffix",
    )

    block_identity = fr.iv_identity_as_block_identity(canonical)
    try:
        db_service.stage_upsert_build_info(block_identity)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db build info", error=e)

    iv_file_path = file_service.choose_iv_file_path(canonical, config.iv_file_directory)

    try:
        iv_entry = db_service.stage_upsert_iv_info(canonical, iv_file_path)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db iv info", error=e)

    canonical = dict(canonical)
    canonical["iv_id"] = iv_entry.iv_id

    try:
        file_service.save_iv_file(canonical, vup_list, vdown_list, isource_list, iv_file_path)
        iv_entry.iv_file_path = str(iv_file_path)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="iv file", error=e)

    heat_test_taken = bool(heat_current_list) and bool(heat_voltage_list) and any(heat_current_list) and any(heat_voltage_list)
    if heat_test_taken:
        try:
            temperature_list = postprocess.calculate_heat_parameters(
                heat_current_list, heat_voltage_list, canonical.get("ideality")
            )
            heat_file_name = os.path.basename(iv_file_path)
            heat_path = file_service.save_heat_test_file(
                canonical, heat_file_name, temperature_list, heat_voltage_list, config.heat_data_directory
            )
            iv_entry.heat_file_path = heat_path
        except Exception as e:
            traceback.print_exc()
            db_service.roll_back_db_changes()
            return SaveResult(success=False, failure_cause="heat file", error=e)

    db_service.commit_db_changes()
    return SaveResult(success=True)