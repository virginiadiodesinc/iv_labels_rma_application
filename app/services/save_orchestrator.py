"""
save_orchestrator.py

The only place that decides "DB then file(s)" and handles the failure of
either. Routes never call file_service or db_service directly.

DB goes first because it's stage-then-commit (see queries.py / db_service.py):
staging is cheap and fully reversible via roll_back_db_changes, since nothing
is committed yet. File writes go second because disk writes aren't reversible
the same way. The written paths are only known AFTER the writes succeed, so
they get attached to the already-staged entry right before the single commit
at the end -- no need to stage the row twice.

A block's life, and what each stage writes:

  inspection  -> block file only, piecemeal (Section.INSPECTION). The build
                 file doesn't exist yet; there's no build name to name it.
  PB1         -> block file (full overwrite) + build file named after
                 pb1_build_name, + parts/notes.
  PB2         -> same, named after pb2_build_name.
  full build  -> same, named after full_build_name.

PB1/PB2/full build are the SAME operation with a different name source --
hence one implementation parameterised by build_name_key, not three.

Stale files: the build file's name is derived from the build name, so each
stage writes a file at a NEW path rather than overwriting the previous one.
The previous path is read off the staged entry (it's still the old value at
that point -- canonical_to_db_kwargs never produces a *_file_path key, so
staging can't have clobbered it) and deleted AFTER the commit succeeds.
Deletion is deliberately last and outside the rollback path, because
roll_back_db_changes cannot un-delete a file: a leftover file is a nuisance,
a save the user has to redo is worse.

Known non-atomicity: if the block file writes and the build file then fails,
the DB rolls back but the block file on disk has already changed. Accepted,
because block file content is fully regenerable from the Build_Info row --
the next successful save corrects it.
"""

from dataclasses import dataclass
from typing import Optional

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
    failure_cause: Optional[str] = None   # "db", "block file", "build file", ...
    error: Optional[Exception] = None
    warning: Optional[str] = None         # save succeeded, cleanup didn't


def _save_files_and_info(
    canonical: dict,
    section: Optional[fr.Section] = None,
    build_name_key: Optional[str] = None,
    parts_list: Optional[list[dict]] = None,
    notes_list: Optional[list[dict]] = None,
) -> SaveResult:
    """The one save path for everything block/build.

    section=None        -> block file is a full overwrite (canonical must be
                           complete). section=Section.X -> piecemeal write
                           touching only that section's tokens.
    build_name_key=None -> block file only, no parts/notes, no build file.
                           Otherwise the canonical field the build file's
                           name comes from ("pb1_build_name" etc.).
    """
    writes_build_file = build_name_key is not None

    # Guard BEFORE anything is staged or written. A blank build name renders
    # a file called " 3-02b.txt" -- leading space, and colliding with every
    # other unnamed build on this block. This should also be a red flag at
    # the route so the user gets a real message; this is the backstop.
    if writes_build_file and not canonical.get(build_name_key):
        return SaveResult(
            success=False,
            failure_cause="missing build name",
            error=ValueError(f"{build_name_key} is blank -- cannot name the build file"),
        )

    try:
        entry = db_service.stage_upsert_build_info(canonical)
        if writes_build_file:
            db_service.stage_replace_build_parts_and_notes(canonical, parts_list or [], notes_list or [])
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    # Read the OLD paths off the staged entry before overwriting them below.
    old_block_file_path = entry.block_file_path
    old_build_file_path = entry.build_file_path

    try:
        if section is None:
            block_file_path = file_service.save_block_file(canonical, config.block_file_directory)
        else:
            block_file_path = file_service.save_block_file_section(canonical, section, config.block_file_directory)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="block file", error=e)

    build_file_path = old_build_file_path
    if writes_build_file:
        try:
            # Substituted canonical is scoped to this call ONLY -- it must
            # not reach stage_upsert_build_info above, or a PB1 save would
            # write the PB1 name into Build_Info.full_build_name.
            build_canonical = fr.with_build_name_from(canonical, build_name_key)
            build_file_path = file_service.save_build_file(build_canonical, config.build_file_directory)
        except Exception as e:
            traceback.print_exc()
            db_service.roll_back_db_changes()
            return SaveResult(success=False, failure_cause="build file", error=e)

    entry.block_file_path = block_file_path
    entry.build_file_path = build_file_path

    try:
        db_service.commit_db_changes()
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    return SaveResult(success=True, warning=_clean_up_stale_files(
        (old_block_file_path, block_file_path),
        (old_build_file_path, build_file_path),
    ))


def _clean_up_stale_files(*path_pairs) -> Optional[str]:
    """Deletes any previous file the save has just superseded at a different
    path. Runs only after a successful commit. Failure here is reported as a
    warning, never as a failed save -- the data is already safely committed
    and the only consequence is an orphaned file on disk.

    The block file is included even though its path is stable (identity-only),
    because that stops being true the moment someone edits a serial number or
    revision -- cheap insurance, no-ops otherwise."""
    problems = []
    for old_path, new_path in path_pairs:
        try:
            file_service.delete_stale_file(old_path, new_path)
        except OSError as e:
            traceback.print_exc()
            problems.append(f"{old_path} ({e})")
    if problems:
        return "Saved, but could not remove superseded file(s): " + "; ".join(problems)
    return None


def save_inspection_info(canonical: dict) -> SaveResult:
    """The one stage that writes a block file and nothing else -- there's no
    build name yet, so there's nothing to name a build file after."""
    return _save_files_and_info(canonical, section=fr.Section.INSPECTION)


def save_pb1_info(canonical: dict, parts_list: list[dict], notes_list: list[dict]) -> SaveResult:
    return _save_files_and_info(
        canonical,
        build_name_key=fr.BUILD_NAME_KEYS[fr.Section.PB1],
        parts_list=parts_list,
        notes_list=notes_list,
    )


def save_pb2_info(canonical: dict, parts_list: list[dict], notes_list: list[dict]) -> SaveResult:
    return _save_files_and_info(
        canonical,
        build_name_key=fr.BUILD_NAME_KEYS[fr.Section.PB2],
        parts_list=parts_list,
        notes_list=notes_list,
    )


def save_build_info(canonical: dict, parts_list: list[dict], notes_list: list[dict]) -> SaveResult:
    return _save_files_and_info(
        canonical,
        build_name_key=fr.BUILD_NAME_KEYS[fr.Section.FULL_BUILD],
        parts_list=parts_list,
        notes_list=notes_list,
    )


# The old "save full block info" path. Now that prebuilds carry parts, there's
# no coherent "block info without a build file" state, so this is deliberately
# the same operation as save_build_info rather than a fourth variant. Kept as a
# name so the existing route keeps working; delete both once the UI stops
# pointing at it.
save_block_info = save_build_info


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