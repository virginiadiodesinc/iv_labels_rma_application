from dataclasses import dataclass, field
from typing import Callable
import csv
from pathlib import Path
from flask import render_template
from app import config
from app.db import JB2_queries as jb2



CONFIG_DIR = Path(__file__).resolve().parent
CURRENT_TESTED_BUILDS_FILE = CONFIG_DIR / "current_tested_builds.txt"

# ---------------------------------------------------------------------------
# Pure validators: value -> [is_valid, message]
# ---------------------------------------------------------------------------

def validate_block_name_listed(block_engraving):
    with open(config.block_list_file) as f:
        full_csv_list = list(csv.reader(f))
    file_found = any(block_engraving.strip() == entry[0] for entry in full_csv_list)
    message = "This block engraving was not found in the block engraving list" if not file_found else ""
    return [file_found, message]


def validate_build_name_listed(build_name):
    with open(config.build_list_file) as f:
        full_csv_list = list(csv.reader(f))
    file_found = any(build_name.strip() == entry[0] for entry in full_csv_list)
    message = "This build name was not found in the build name list" if not file_found else ""
    return [file_found, message]


def validate_parts_listed(part_list):
    parts_listed = bool(part_list)
    message = "This build does not have any parts listed" if not parts_listed else ""
    return [parts_listed, message]


def validate_current_test_note_added(note_list):
    current_test_note_added = any(note["type"] == "current_test" for note in note_list)
    message = "This build is supposed to receive a current test but has no current test note listed" if not current_test_note_added else ""
    return [current_test_note_added, message]


def validate_rework_info_note_added(note_list):
    rework_info_note_added = any(note["type"] == "rework_info" for note in note_list)
    message = "This build is some revision beyond the first but has no rework info note listed" if not rework_info_note_added else ""
    return [rework_info_note_added, message]


def validate_bom_matches(build_name, part_list):
    bom = jb2.get_BOM(build_name)
    part_comparison_dict = {}
    for bom_part in bom[:]:
        if bom_part["part_type"] == "BLOCK":
            bom.remove(bom_part)
        if "PB2" in bom_part["part_name"]:
            sub_bom = jb2.get_BOM(bom_part["part_name"])
            bom.remove(bom_part)
            bom.extend(sub_bom)

    for bom_part in bom:
        part_name = bom_part["part_name"]
        part_representation = {
            "theoretical_quantity": bom_part["part_quantity"],
            "actual_quantity": 0
        }
        if part_name in part_comparison_dict:
            part_name["theoretical_quantity"] = part_name["theoretical_quantity"] + part_representation["theoretical_quantity"]
        else:
            part_comparison_dict[part_name] = part_representation

    for actual_part in part_list:
        part_name = actual_part["part_name"]
        if part_name in part_comparison_dict:
            part_comparison_dict[part_name]["actual_quantity"] = part_comparison_dict[part_name]["actual_quantity"] + actual_part["quantity"]
        else:
            part_representation = {
            "theoretical_quantity": 0,
            "actual_quantity": actual_part["quantity"]
            }
            part_comparison_dict[part_name] = part_representation
            
    accurate_to_bom = True
    mismatched_parts_dict = {}
    for part_name, quantities in part_comparison_dict.items():
        if quantities["theoretical_quantity"] != quantities["actual_quantity"]:
            accurate_to_bom = False
            mismatched_parts_dict[part_name] = quantities

    message = render_template("partials/generic/bom_comparison.html", bom_comparison=mismatched_parts_dict)
    return [accurate_to_bom, message]




# ---------------------------------------------------------------------------
# Check machinery
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlagContext:
    """Everything a yellow-flag check might need. Every check and every
    `applies` predicate receives the whole thing and takes what it wants,
    so the loop never has to know which inputs a given check uses."""
    canonical: dict
    parts: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _always(ctx: FlagContext) -> bool:
    return True


@dataclass(frozen=True)
class YellowFlagCheck:
    """
    key      -- MUST match a canonical name on a YELLOW_FLAG FieldSpec in
                field_registry.py, so check_yellow_flags' output can be
                merged straight into canonical via merge_yellow_flags.
    check    -- FlagContext -> [is_valid, message]. This lambda is the one
                place that knows how to pull inputs out of the context, so
                the validate_* functions above stay pure.
    applies  -- FlagContext -> bool. When False the flag is reported as not
                raised (and stored as such, which clears stale flags on a
                re-save). Defaults to always applying.
    """
    key: str
    check: Callable[[FlagContext], list]
    applies: Callable[[FlagContext], bool] = _always


def check_yellow_flags(ctx: FlagContext, checks: list) -> dict:
    """Returns {key: [flag_is_raised, message]}."""
    result = {}
    for c in checks:
        if not c.applies(ctx):
            result[c.key] = [False, ""]
            continue
        is_valid, message = c.check(ctx)
        result[c.key] = [not is_valid, message]
    return result


def any_flag_raised(yellow_flag_dict: dict) -> bool:
    return any(flag for flag, _message in yellow_flag_dict.values())


# ---------------------------------------------------------------------------
# Applicability predicates
# ---------------------------------------------------------------------------

def is_reworked_revision(ctx: FlagContext) -> bool:
    return (ctx.canonical.get("block_revision") or "A").strip().upper() not in ("", "A")


def needs_current_test(ctx: FlagContext) -> bool:
    return (ctx.canonical.get("full_build_name") in CURRENT_TESTED_BUILDS_LIST)


# ---------------------------------------------------------------------------
# Check lists, composed from shared pieces
# ---------------------------------------------------------------------------

_BLOCK_CHECKS = [
    YellowFlagCheck(
        "unlisted_block_name",
        lambda c: validate_block_name_listed(c.canonical.get("block_engraving") or ""),
    ),
]

UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS = _BLOCK_CHECKS

PREBUILD_YELLOW_FLAG_CHECKS = _BLOCK_CHECKS + [
    YellowFlagCheck(
        "unlisted_build_name",
        lambda c: validate_build_name_listed(c.canonical.get("full_build_name") or ""),
    ),
    YellowFlagCheck(
        "no_parts_listed",
        lambda c: validate_parts_listed(c.parts),
    ),
]

FULL_BUILD_YELLOW_FLAG_CHECKS = _BLOCK_CHECKS + [
    YellowFlagCheck(
        "unlisted_build_name",
        lambda c: validate_build_name_listed(c.canonical.get("full_build_name") or ""),
    ),
    YellowFlagCheck(
        "no_parts_listed",
        lambda c: validate_parts_listed(c.parts),
    ),
    YellowFlagCheck(
        "rework_info_note_missing",
        lambda c: validate_rework_info_note_added(c.notes),
        applies=is_reworked_revision,
    ),
    YellowFlagCheck(
        "current_test_note_missing",
        lambda c: validate_current_test_note_added(c.notes),
        applies=needs_current_test,
    ),
    YellowFlagCheck(
        "mismatched_bom",
        lambda c: validate_bom_matches(c.canonical.get("full_build_name"), c.parts),
        ),
]

IV_YELLOW_FLAG_CHECKS = [
    YellowFlagCheck(
        "unlisted_block_name",
        lambda c: validate_block_name_listed(c.canonical.get("iv_block_engraving") or ""),
    ),
    YellowFlagCheck(
        "unlisted_build_name",
        lambda c: validate_build_name_listed(c.canonical.get("iv_build_name") or ""),
    ),
]

# Not yet wired to the DB/registry: each new key above (no_parts_listed,
# missing_rework_info_note, missing_current_test_note) needs a
# Yellow_Flags column in models.py and a YELLOW_FLAG FieldSpec in
# field_registry.py before merge_yellow_flags will persist it. Same goes for
# "unlisted_build_name" if it doesn't have one yet.


# ---------------------------------------------------------------------------
# Creating the current tested build list
# ---------------------------------------------------------------------------

def _load_plain_text_list(path):
    """One entry per line. Blank lines and lines starting with # are
    ignored, so you can paste a raw listing and comment out lines instead
    of deleting them if you're not sure yet."""
    names = set()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    names.add(line)
    return names


CURRENT_TESTED_BUILDS_LIST = _load_plain_text_list(CURRENT_TESTED_BUILDS_FILE)