from app import config
import csv


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


def validate_bom_matches(build_name, part_list):
    return


def validate_lots_chosen_for_all_parts(part_list):
    return


def validate_current_test_note_added(note_list):
    return


def validate_rework_summary_note_added(note_list):
    return


# Each check is (key, selector, check_fn):
#   key       -- MUST match a canonical name on a YELLOW_FLAG FieldSpec in
#                field_registry.py, so check_yellow_flags' output can be
#                merged straight into canonical via merge_yellow_flags.
#   selector  -- canonical dict -> the single value check_fn actually looks
#                at. Usually just one field ("block_engraving"); this is
#                where your PB1-vs-PB2-vs-full-build-name case would live if
#                a flag ever needs to consider more than one field -- e.g.
#                `lambda c: c.get("full_build_name") or c.get("pb1_build_name")`
#                -- without check_fn itself needing to know about the whole
#                canonical shape.
#   check_fn  -- takes the selected value, returns [is_valid, message].

UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS = [
    ("unlisted_block_name", lambda c: c.get("block_engraving") or "", validate_block_name_listed),
]

# "unlisted_build_name" needs a Yellow_Flags.unlisted_build_name column
# added to models.py before it gets a FieldSpec + a check here -- see the
# note in field_registry.py.


def check_yellow_flags(canonical: dict, checks: list) -> dict:
    """Returns {key: [flag_is_raised, message]}."""
    yellow_flag_dict = {}
    for key, selector, check_fn in checks:
        is_valid, message = check_fn(selector(canonical))
        yellow_flag_dict[key] = [not is_valid, message]
    return yellow_flag_dict


def any_flag_raised(yellow_flag_dict: dict) -> bool:
    return any(flag for flag, _message in yellow_flag_dict.values())
