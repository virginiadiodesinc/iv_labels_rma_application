"""
field_registry.py

Single source of truth for how a piece of data's *name* and *shape* change as it
moves between: HTML form input -> canonical dict -> DB columns -> LabView block/build
file lines.

Everything downstream of form-parsing (validators, yellow-flag checks, the save
orchestrator, file writers, DB upserts) operates on the CANONICAL dict. Canonical
values are real Python types (date objects, not strings) and true blanks are
represented as None or "" -- NOT the "X" placeholder. The "X" placeholder is a
file-formatting concern and is only ever introduced at the point a file line is
rendered, in `render_line()` below. This keeps "sanitize" (form -> canonical) and
"format for a target" (canonical -> file/db) as two clearly separate steps instead
of a blend, which was the confusion in the old sanitize_fields.py.

Scope of this first pass: the Build_Info scalar fields shared by the block file
and build file (identity, inspection, PB1, PB2). Parts, notes, and the IV file use
the same underlying ideas (Token/LineTemplate, FieldSpec) but need their own
template shapes -- see the bottom of this file for how to extend.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Callable, Optional, Union


# ---------------------------------------------------------------------------
# Sections -- used for piecemeal file writes: "which tokens am I allowed to
# touch when only the PB1 form was submitted, vs. the whole file."
# ---------------------------------------------------------------------------

class Section(Enum):
    IDENTITY = "identity"      # block_engraving, block_serial_number, block_revision
    INSPECTION = "inspection"
    PB1 = "pb1"
    PB2 = "pb2"
    FULL_BUILD = "full_build"
    YELLOW_FLAG = "yellow_flag"
    IV_PARAMETERS = "iv_parameters"
    BUILD_PARTS = "build_parts"
    NOTES = "notes"


# ---------------------------------------------------------------------------
# FieldSpec -- one row per canonical field. Any of the "which surfaces does
# this field appear on" attributes can be None, meaning "this field doesn't
# exist there." That's expected and normal (see cleanout_date, pb2_passfail
# below), not a gap to fill in.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldSpec:
    canonical: str                              # e.g. "inspection_date" -- also the DB column name where one exists
    section: Section
    value_type: type = str                      # str, date, int
    form_name: Optional[str] = None             # e.g. "inspection-date-input"; None if no form input
    db_model: Optional[str] = None              # e.g. "Build_Info"; None if DB has no column for this
    db_column: Optional[str] = None             # only set if it differs from `canonical`
    callable_name: Optional[str] = None         # e.g. validate_block_name_listed; None if no relevant callable


# ---------------------------------------------------------------------------
# The registry itself. This list is the thing you edit when a field is added,
# renamed, or removed anywhere in the system -- not the routes, not the file
# writers, not the adapters.
# ---------------------------------------------------------------------------

FIELDS: list[FieldSpec] = [
    # --- identity ---
    FieldSpec("block_engraving", Section.IDENTITY, str,
              form_name="block-engraving-input", db_model="Build_Info"),
    FieldSpec("block_serial_number", Section.IDENTITY, str,
              form_name="block-serial-number-input", db_model="Build_Info"),
    FieldSpec("block_revision", Section.IDENTITY, str,
              form_name="block-revision-input", db_model="Build_Info"),

    # --- inspection ---
    FieldSpec("inspection_date", Section.INSPECTION, date,
              form_name="inspection-date-input", db_model="Build_Info"),
    FieldSpec("inspection_initials", Section.INSPECTION, str,
              form_name="inspection-initials-input", db_model="Build_Info"),

    # --- DB-only, no form or file counterpart yet (flagging honestly, per your models.py) ---
    FieldSpec("cleanout_date", Section.INSPECTION, date, db_model="Build_Info"),
    FieldSpec("cleanout_initials", Section.INSPECTION, str, db_model="Build_Info"),

    # --- PB1 ---
    FieldSpec("pb1_build_name", Section.PB1, str,
              form_name="pb1-build-name-input", db_model="Build_Info"),
    FieldSpec("pb1_date", Section.PB1, date,
              form_name="pb1-date-input", db_model="Build_Info"),
    FieldSpec("pb1_initials", Section.PB1, str,
              form_name="pb1-initials-input", db_model="Build_Info"),

    # --- PB2 ---
    FieldSpec("pb2_build_name", Section.PB2, str,
              form_name="pb2-build-name-input", db_model="Build_Info"),
    FieldSpec("pb2_date", Section.PB2, date,
              form_name="pb2-date-input", db_model="Build_Info"),
    FieldSpec("pb2_initials", Section.PB2, str,
              form_name="pb2-initials-input", db_model="Build_Info"),
    FieldSpec("pb2_inspection_initials", Section.PB2, str,
              form_name="pb2-inspection-initials-input", db_model="Build_Info"),

    # pb2_passfail / pb2_bond_wire_pads / pb2_components are permanently
    # deprecated (per your confirmation) -- no FieldSpec for them at all
    # anymore, since nothing reads or writes them. They're just blank
    # literals in _pb2_line() below.

    # --- full build ---
    FieldSpec("full_build_name", Section.FULL_BUILD, str,
              form_name="full-build-name-input", db_model="Build_Info"),
    FieldSpec("full_build_date", Section.FULL_BUILD, date,
              form_name="full-build-date-input", db_model="Build_Info"),
    FieldSpec("full_build_initials", Section.FULL_BUILD, str,
              form_name="full-build-initials-input", db_model="Build_Info"),

    # --- yellow flags ---
    # canonical name doubles as the Yellow_Flags column name unless overridden
    FieldSpec("unlisted_block_name", Section.YELLOW_FLAG, bool,
                db_model="Yellow_Flags", callable_name="validate_block_name_listed"),
    FieldSpec("unlisted_build_name", Section.YELLOW_FLAG, bool,
                db_model="Yellow_Flags",  callable_name="validate_build_name_listed"),
    FieldSpec("mismatched_bom", Section.YELLOW_FLAG, bool,
                db_model="Yellow_Flags",  callable_name="validate_bom_matches"),

    # --- IV parameters ---
    FieldSpec("points_per_decade", Section.IV_PARAMETERS, int, db_model="IV_Info", form_name="iv-points-per-decade"),
    FieldSpec("ideality", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="n"),
    FieldSpec("saturation_current", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="is"),
    FieldSpec("series_resistance", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="rs"),
    FieldSpec("mean_squared_error", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="mean-squared-error"),
    FieldSpec("r_squared_error", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="r-squared-error"),
    # polarity is a NAME match already, but the DB column is an Enum
    # (Polarity.POSITIVE/NEGATIVE), not the raw "+"/"-" string the form
    # sends -- db_column alone can't fix that, it's a value-type mismatch,
    # not a name mismatch. See stage_add_iv_info's explicit override, same
    # pattern as block_id/iv_id.
    FieldSpec("polarity", Section.IV_PARAMETERS, str, db_model="IV_Info", form_name="iv-polarity"),
    FieldSpec("hysteresis_standard_deviation", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="hysteresis-std"),
    FieldSpec("hysteresis_mean", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="hysteresis-mean"),
    FieldSpec("hysteresis_maximum", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="hysteresis-max"),
    FieldSpec("hysteresis_minimum", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="hysteresis-min"),
    FieldSpec("reverse_breakdown_current", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="reverse-current"),
    FieldSpec("reverse_breakdown_voltage", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="reverse-voltage"),
    # PARAMETERS WITHOUT DB VERSIONS - USUALLY CALCULATED VIA THE NUMBERS
    FieldSpec("series_resistance_4pt", Section.IV_PARAMETERS, float, form_name="rs-4pt"),
    FieldSpec("series_resistance_alternate", Section.IV_PARAMETERS, float, form_name="rs-1"),
    FieldSpec("series_resistance_3pt", Section.IV_PARAMETERS, float, form_name="rs-3pt"),

    # --- IV numbers ---
    # these are literally strings of the entire list of values
    # We have little to no interest in storing them point by point
    # So this may be folded into the IV_Info table later too.
    FieldSpec("voltage_up_string", Section.IV_PARAMETERS, str, db_model="IV_Points", db_column="voltage_up_mv", form_name="iv-voltage-up"),
    FieldSpec("voltage_down_string", Section.IV_PARAMETERS, str, db_model="IV_Points", db_column="voltage_down_mv", form_name="iv-voltage-down"),
    # voltage_average_string: no obvious source field yet -- "iv-measurement-values"
    # is a candidate (its values are consistently ~1/1000th of iv-voltage-up/down's,
    # which smells like the unit-conversion question you flagged earlier as
    # deferred) but I don't want to guess the mapping wrong. Confirm before wiring.
    FieldSpec("voltage_average_string", Section.IV_PARAMETERS, str, db_model="IV_Points"),
    FieldSpec("current", Section.IV_PARAMETERS, str, db_model="IV_Points", db_column="current_ua", form_name="iv-source-values"),
    # temperature_string/heat_voltage_string: heat-current-list/heat-voltage-list/
    # temperature-list exist on the form but are all empty in your sample submission
    # (no heat test taken) -- leaving unwired until heat files are actually next up.
    FieldSpec("temperature_string", Section.IV_PARAMETERS, str, db_model="IV_Points"),
    FieldSpec("heat_voltage_string", Section.IV_PARAMETERS, str, db_model="IV_Points"),

    # --- IV related fields that aren't parameters? ---
    FieldSpec("iv_file_path", Section.IV_PARAMETERS, str, db_model="IV_Info"),
    FieldSpec("iv_diode_name", Section.IV_PARAMETERS, str, db_model="IV_Info", db_column="diode"),
    FieldSpec("iv_diode_lot", Section.IV_PARAMETERS, str, db_model="IV_Info", db_column="diode_lot"),
    FieldSpec("iv_circuit_name", Section.IV_PARAMETERS, str, db_model="IV_Info", db_column="circuit"),
    FieldSpec("iv_circuit_lot", Section.IV_PARAMETERS, str, db_model="IV_Info", db_column="circuit_lot"),
    FieldSpec("iv_assembly_number", Section.IV_PARAMETERS, int, db_model="IV_Info", db_column="assembly_number", form_name="iv-assembly-number"),
    FieldSpec("iv_date", Section.IV_PARAMETERS, date, db_model="IV_Info"),

    # --- IV identity -- separate canonical names from block_engraving/etc.
    # per the Case B decision (IV's identity can genuinely diverge from the
    # main block/build panel). No db_model -- these only exist to build the
    # IV_Info.build_id FK string and the .iv file's identity line, not
    # stored as their own columns.
    FieldSpec("iv_block_engraving", Section.IV_PARAMETERS, str, form_name="iv-block-engraving"),
    FieldSpec("iv_block_serial_number", Section.IV_PARAMETERS, str, form_name="iv-block-sn"),
    FieldSpec("iv_block_revision", Section.IV_PARAMETERS, str, form_name="iv-block-revision"),
    FieldSpec("iv_build_name", Section.IV_PARAMETERS, str, form_name="iv-build-name"),
    FieldSpec("additional_info", Section.IV_PARAMETERS, str, db_model="IV_Info", db_column="additional_information", form_name="iv-additional-info"),
    FieldSpec("temperature", Section.IV_PARAMETERS, float, db_model="IV_Info", form_name="temperature"),
    # --- part related fields (some overlap with IV here) ---
    # ALL PARTS
    FieldSpec("part_name", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    FieldSpec("part_lot", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    FieldSpec("part_quantity", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    # ONLY PCB
    FieldSpec("part_modifications", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    # POTENTIALLY MULTIPLE
    FieldSpec("part_serial_number", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    # ONLY DIODES
    FieldSpec("part_temperature", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    FieldSpec("part_reverse_breakdown_voltage", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    FieldSpec("part_indium", Section.BUILD_PARTS, str, db_model="Build_Parts"),
    FieldSpec("subassembly_tag", Section.BUILD_PARTS, str, db_model="Build_Parts"),

    # --- note related fields ---
    FieldSpec("note_text", Section.NOTES, str, db_model="Notes"),
    FieldSpec("note_type", Section.NOTES, str, db_model="Notes"),

]

BY_CANONICAL: dict[str, FieldSpec] = {f.canonical: f for f in FIELDS}
BY_FORM_NAME: dict[str, FieldSpec] = {f.form_name: f for f in FIELDS if f.form_name}


# ---------------------------------------------------------------------------
# form -> canonical
#
# This is the ONLY place "" becomes None. Downstream code never has to
# guess whether an empty string means "user left it blank" -- it's None.
# ---------------------------------------------------------------------------

def canonical_from_form(form) -> dict:
    """form is anything supporting `in` and .get(key, default) -- request.form
    works directly. Fields whose form_name isn't present in `form` at all are
    left OUT of the result entirely -- not set to None. That distinction
    matters: canonical_to_db_kwargs and stage_upsert_build_info only touch
    keys that are actually present, so a PB1-only submission's canonical
    dict never mentions inspection_date/pb2_build_name/etc. at all, and a
    DB upsert built from it can't accidentally null out sections it wasn't
    asked to change. A field that IS present but left blank by the user
    still correctly becomes None (a real, intentional "clear this field")."""
    result = {}
    for spec in FIELDS:
        if not spec.form_name:
            continue
        if spec.form_name not in form:
            continue
        raw = (form.get(spec.form_name, "") or "").strip()
        if raw == "":
            result[spec.canonical] = None
            continue
        if spec.value_type is date:
            result[spec.canonical] = _parse_iso_date(raw)
        elif spec.value_type in (int, float):
            result[spec.canonical] = spec.value_type(raw)
        else:
            result[spec.canonical] = raw

    # block_revision defaults to "A" when blank -- this is a real business rule,
    # not a generic "blank becomes X" rule, so it stays here rather than being
    # folded into the loop above. Only applies if block_revision was actually
    # part of this submission (it always should be -- every block-related
    # form needs the identity fields to know which record it's writing to).
    if "block_revision" in result and not result["block_revision"]:
        result["block_revision"] = "A"
    if "iv_block_revision" in result and not result["iv_block_revision"]:
            result["iv_block_revision"] = "A"

    return result

def merge_yellow_flags(canonical: dict, yellow_flag_dict: dict) -> dict:
    """yellow_flag_dict is {key: [flag_is_raised, message]}, from
    validate_yellow_flags.check_yellow_flags. Merges just the booleans into
    canonical under the same keys the YELLOW_FLAG FieldSpecs above use, so
    they ride canonical_to_db_kwargs(canonical, "Yellow_Flags") the same way
    every other field rides its own db_model -- no separate DB-mapping
    function needed for yellow flags specifically."""
    merged = dict(canonical)
    for key, (flag, _message) in yellow_flag_dict.items():
        if key in BY_CANONICAL:
            merged[key] = flag
    return merged


def _parse_iso_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# canonical -> db kwargs
# ---------------------------------------------------------------------------

def canonical_to_db_kwargs(canonical: dict, db_model: str) -> dict:
    """Pulls out just the fields that belong to the given model, keyed by
    real column name. Fields with db_model=None (pb2_passfail etc.) are
    correctly excluded -- there's nowhere in the DB for them to go."""
    kwargs = {}
    for spec in FIELDS:
        if spec.db_model != db_model:
            continue
        if spec.canonical not in canonical:
            continue
        column = spec.db_column or spec.canonical
        kwargs[column] = canonical[spec.canonical]
    return kwargs


def build_block_id(canonical: dict) -> str:
    """The composite primary key Build_Info actually uses. Lives here, not in
    queries.py, because it's domain logic about what identifies a block --
    queries.py should stay agnostic about that."""
    return f"{canonical['block_engraving']} {canonical['block_serial_number']} {canonical['block_revision']}"


# ---------------------------------------------------------------------------
# canonical -> file lines
#
# A line is an ordered list of Tokens joined by a separator. A Token is either
# a Field (pull a value from canonical, falling back to a placeholder if
# blank) or a Literal (fixed text -- e.g. the mysterious "12" "12" in row 1;
# left as literals here since I don't know what they represent -- worth
# confirming with you before this goes further). Each Field token also
# carries the Section that "owns" it, which is what piecemeal writing uses
# to decide which tokens in an existing line to touch vs. leave alone.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Literal:
    text: str


@dataclass(frozen=True)
class Field:
    canonical: str
    placeholder: str = ""


@dataclass(frozen=True)
class Computed:
    """For values that don't correspond 1:1 to a canonical field -- e.g.
    block_sn, which is block_serial_number + block_revision glued together
    for display. Never store this as its own canonical field; derive it."""
    name: str
    fn: Callable[[dict], str]
    placeholder: str = "X"


@dataclass(frozen=True)
class Glued:
    """A small group of tokens joined with NO separator, nested inside a
    line that's otherwise separated normally -- e.g. IV row 0's 'B{sn}' or
    'Cir{circuit}', where the line as a whole is space-joined but this one
    piece needs its prefix touching the value. This replaces needing a
    dedicated function (like _block_sn_preceded_by_b) per prefix+field
    combination -- the prefix is just a Literal inside the group."""
    tokens: list  # list[Token] -- Literal/Field/Computed, or even nested Glued


Token = Union[Literal, Field, Computed, Glued]


@dataclass(frozen=True)
class LineTemplate:
    line_index: int
    tokens: list[Token]
    separator: str = " "


def _block_sn(canonical: dict) -> str:
    rev = canonical.get("block_revision") or "A"
    suffix = "" if rev == "A" else rev
    return f"{canonical.get('block_serial_number') or ''}{suffix}"


def _iv_block_sn(canonical: dict) -> str:
    """Same idea as _block_sn, but reading IV's own separate identity
    fields -- IV's block/serial/revision can genuinely diverge from the
    main block/build panel's, per the Case B decision."""
    rev = canonical.get("iv_block_revision") or "A"
    suffix = "" if rev == "A" else rev
    return f"{canonical.get('iv_block_serial_number') or ''}{suffix}"


def _format_saturation_current(canonical: dict):
    """Is: needs the same LabView-style scientific notation the heat file
    uses (format_labview_scientific, defined further down -- fine, since
    this function's body isn't evaluated until it's actually called at
    render time, well after the whole module has finished loading)."""
    value = canonical.get("saturation_current")
    if value is None:
        return None
    return format_labview_scientific(value, 3)


def build_block_id_from_iv(canonical: dict) -> str:
    """Same string shape as build_block_id, but from IV's own identity
    fields -- this is what IV_Info.build_id (the FK to Build_Info) gets
    set to."""
    return f"{canonical.get('iv_block_engraving') or ''} {canonical.get('iv_block_serial_number') or ''} {canonical.get('iv_block_revision') or ''}"


def iv_identity_as_block_identity(canonical: dict) -> dict:
    """Translates IV's own identity fields into the plain
    block_engraving/block_serial_number/block_revision keys
    stage_upsert_build_info expects, so an IV save can ensure its parent
    Build_Info row exists (per the FK constraint) without needing its own
    upsert function. Deliberately ONLY these three keys -- so if this
    creates a new Build_Info row, it's a genuinely minimal stub; if the row
    already exists, this just re-sets the same three values it already
    had, thanks to canonical_from_form's absent-vs-blank fix (a dict with
    only these three keys can never null out anything else on that row)."""
    return {
        "block_engraving": canonical.get("iv_block_engraving"),
        "block_serial_number": canonical.get("iv_block_serial_number"),
        "block_revision": canonical.get("iv_block_revision"),
    }


def _format_time_12h(hour: int, minute: int) -> str:
    """12-hour time, no leading zero on the hour, AM/PM suffix -- e.g.
    '12:22 PM' or '9:05 AM'. Built manually rather than via strftime's
    %#I/%-I, since those flags are platform-specific (Windows vs.
    Linux/Mac) -- same reasoning as why _stringify builds dates manually
    instead of using strftime."""
    hour12 = hour % 12 or 12
    period = "AM" if hour < 12 else "PM"
    return f"{hour12}:{minute:02d} {period}"


def stamp_iv_datetime(canonical: dict) -> dict:
    """Adds iv_date (a real date -- reused as-is for both the IV_Info DB
    column and the file line, via _stringify's existing date handling) and
    iv_time_of_day (a pre-formatted string, since _stringify only
    special-cases date objects, not time-of-day) using the current moment.
    Call this once, right before saving -- this isn't something the user
    submits (no form_name for either), and it can't be a Computed token,
    since Computed tokens must stay pure functions of canonical, not the
    system clock. Same reasoning as why enrich_with_build_suffix is a
    separate explicit step rather than baked into rendering."""
    now = datetime.now()
    canonical = dict(canonical)
    canonical["iv_date"] = now.date()
    canonical["iv_time_of_day"] = _format_time_12h(now.hour, now.minute)
    return canonical


def _pb2_line() -> LineTemplate:
    return LineTemplate(
        line_index=5,
        separator=";",
        tokens=[
            Field("pb1_initials"),
            Field("pb2_build_name"),
            Field("pb2_date"),
            Field("pb2_initials"),
            Literal(""),
            Literal(""),
            Literal(""),
            Field("pb2_inspection_initials"),
        ],
    )

# --- IV file ---
# Row 0's mixed prefix-gluing (B{sn}, Cir{circuit}, A#{assembly_no}) is
# handled by Glued -- see field_registry's Glued docs. Uses IV's own
# identity fields throughout (iv_block_engraving, iv_diode_name, etc.),
# never the block/build ones -- Case B, fully separate.
#
# PB2 has an update path (piecemeal); IV does not, per your confirmation
# that IV always overwrites -- so IV only ever needs render_new_line, never
# update_existing_line.
IV_FILE_TEMPLATE: list[LineTemplate] = [
    LineTemplate(0, separator=" ", tokens=[
        Field("iv_full_build_name_with_suffix"),  # enrich_with_build_suffix must run first -- see below
        Glued([Literal("B"), Computed("iv_block_sn", _iv_block_sn)]),
        Glued([Field("iv_diode_name"), Literal("_LOT"), Field("iv_diode_lot")]),
        Glued([Literal("Cir"), Glued([Field("iv_circuit_name"), Literal("_LOT"), Field("iv_circuit_lot")])]),
        Glued([Literal("A#"), Field("iv_assembly_number")]),
        Field("polarity"),
        Field("iv_block_engraving"),
        Computed("iv_block_sn", _iv_block_sn),
        Field("additional_info", placeholder="X"),
    ]),
    # Single space between date and time below -- your example
    # "5/19/2026  12:22 PM" reads like it might have two spaces; if that's
    # deliberate rather than a typing artifact, change separator to "  ".
    LineTemplate(1, tokens=[Field("iv_date"), Field("iv_time_of_day")]),
    LineTemplate(2, tokens=[Literal("Points/Decade:"), Field("points_per_decade")]),
    LineTemplate(3, tokens=[Literal("n (ideality):"), Field("ideality")]),
    LineTemplate(4, tokens=[Literal("Is:"), Computed("saturation_current", _format_saturation_current)]),
    LineTemplate(5, tokens=[Literal("Rs:"), Field("series_resistance")]),
    LineTemplate(6, tokens=[Literal("Mean Square Error:"), Field("mean_squared_error")]),
    LineTemplate(7, tokens=[Literal("R^2 Error:"), Field("r_squared_error")]),
    LineTemplate(8, tokens=[Literal("Polarity:"), Field("polarity")]),  # colon was missing -- old row was 'Polarity: ' + value
    LineTemplate(9, tokens=[Literal("Hysteresis SD (mV) ="), Field("hysteresis_standard_deviation")]),
    LineTemplate(10, tokens=[Literal("Hysteresis Mean (mV) ="), Field("hysteresis_mean")]),
    LineTemplate(11, tokens=[Literal("Hysteresis Max (mV) ="), Field("hysteresis_maximum")]),
    LineTemplate(12, tokens=[Literal("Hysteresis Min (mV) ="), Field("hysteresis_minimum")]),
    LineTemplate(13, tokens=[Literal("Reverse Current (uA):"), Field("reverse_breakdown_current")]),
    LineTemplate(14, tokens=[Literal("Reverse Voltage (V):"), Field("reverse_breakdown_voltage")]),
    # separator="\t" is a guess matching the data rows below -- the old
    # source has this as literal groups of spaces
    # ('Voltage Up (mV)    Voltage Down (mV)    Current (uA)'), which reads
    # as either "someone typed spaces to fake a tab stop" or "it's genuinely
    # space-delimited and the data rows below it are the odd one out."
    # Worth checking an actual historical .iv file rather than guessing from
    # the Python source, since both are plausible.
    LineTemplate(15, separator="\t", tokens=[Literal("Voltage Up (mV)"), Literal("Voltage Down (mV)"), Literal("Current (uA)")])
    # rows 16-37 (and beyond) to be filled in later, but something like:
    # LineTemplate(row, separator="\t", tokens=[Field("row_voltage_up"), Field("row_voltage_down"), Field("row_current")])
]

# --- Heat test file ---
# This does NOT get a HEAT_FILE_TEMPLATE list -- line 1 has three different
# separators within a single line (space, tab, then semicolons), which is
# more heterogeneous than LineTemplate/Glued handle (Glued groups a
# no-separator sub-section inside a UNIFORMLY-separated line; this line
# isn't uniformly separated at all). Built directly in file_service.py's
# save_heat_test_file, same reasoning as the Vup/Vdown/Isource IV data rows
# bypassing LineTemplate. Line 2 (plain tab-separated headers) and the data
# rows are simple enough to build directly there too, for consistency.

BLOCK_FILE_TEMPLATE: list[LineTemplate] = [
    LineTemplate(0, [Field("block_engraving"), Field("pb1_build_name")]),
    LineTemplate(1, [Computed("block_sn", _block_sn), Literal("12"), Literal("12")]),
    LineTemplate(2, [Field("inspection_date")]),
    LineTemplate(3, [Field("inspection_initials")]),
    LineTemplate(4, [Field("pb1_date")]),
    _pb2_line(),
]

BUILD_FILE_TEMPLATE: list[LineTemplate] = [
    LineTemplate(0, [Field("block_engraving"), Field("pb1_build_name")]),
    LineTemplate(1, [Computed("block_sn", _block_sn), Literal("12"), Literal("12")]),
    LineTemplate(2, [Field("inspection_date")]),
    LineTemplate(3, [Field("inspection_initials")]),
    LineTemplate(4, [Field("pb1_date")]),
    _pb2_line(),
    # rows 6-29: diode/circuit/parts/notes. The diode1/qty_chips1/circuit1/
    # indium/Vbr/MMIC/MMIC_lot/PCB/filter1/diode2/qty_chips2/circuit2/filter2
    # tokens below aren't FieldSpecs in FIELDS -- they're slot names produced
    # by parts_service.assign_parts_to_build_slots(), merged into canonical
    # before this template renders (same pattern as merge_yellow_flags).
    # assembly_initials1/2 and assembly_date1/2 both just reuse
    # full_build_initials/full_build_date directly per your Q3 answer --
    # no separate slot-producing step needed for those two.
    LineTemplate(6, [Field("diode1")]),
    LineTemplate(7, [Field("qty_chips1")]),
    LineTemplate(8, [Field("full_build_initials")]),   # assembly_initials1
    LineTemplate(9, [Field("full_build_date")]),        # assembly_date1
    LineTemplate(10, [Field("circuit1")]),
    LineTemplate(11, [Field("indium")]),
    LineTemplate(12, [Field("Vbr")]),
    LineTemplate(13, [Field("MMIC")]),
    LineTemplate(14, [Field("MMIC_lot")]),
    LineTemplate(15, [Field("notes")]),        # mapping from note-row entries -- still open, see chat
    LineTemplate(16, [Field("PCB")]),
    LineTemplate(17, [Field("filter1")]),
    LineTemplate(18, [Field("diode2")]),
    LineTemplate(19, [Field("qty_chips2")]),
    LineTemplate(20, [Field("full_build_initials")]),   # assembly_initials2 -- same value as row 8
    LineTemplate(21, [Field("full_build_date")]),        # assembly_date2 -- same value as row 9
    LineTemplate(22, [Field("circuit2")]),
    LineTemplate(23, [Field("notes1")]),       # mapping from note-row entries -- still open, see chat
    LineTemplate(24, [Field("notes2")]),
    LineTemplate(25, [Field("notes3")]),
    LineTemplate(26, [Field("notes4")]),
    LineTemplate(27, [Field("notes5")]),
    LineTemplate(28, [Field("notes6")]),
    LineTemplate(29, [Field("filter2")]),
]


# ---------------------------------------------------------------------------
# Filename / label construction -- these reuse _block_sn rather than storing
# a redundant copy of it, same idea as the line templates above.
# ---------------------------------------------------------------------------

def block_file_name(canonical: dict) -> str:
    """Matches the old write_block_file naming: '<engraving> <sn+rev>.txt', lowercased."""
    return f"{canonical.get('block_engraving') or ''} {_block_sn(canonical)}.txt".lower()

def build_file_name(canonical: dict) -> str:
    """Matches the old write_block_file naming: '<build_name> <sn+rev>.txt', lowercased."""
    return f"{canonical.get('full_build_name_with_suffix') or ''} {_block_sn(canonical)}.txt".lower()


def enrich_with_build_suffix(
    canonical: dict,
    lookup_fn,
    build_name_key: str = "full_build_name",
    block_engraving_key: str = "block_engraving",
    output_key: str = "full_build_name_with_suffix",
) -> dict:
    """Adds the suffixed build name by looking up the block engraving's
    suffix (old su.get_build_name_with_suffix, which reads block_engravings.csv).
    This does file I/O, which is why it's a separate explicit step rather than
    a Computed token -- Computed tokens stay pure functions of the canonical
    dict so render_new_line/update_existing_line never touch disk themselves.
    Only call this where you actually need the suffixed name (full build
    saves, IV saves, print labels) -- inspection/PB1/PB2 saves don't need it.

    Defaults match the block/build case; IV saves call this with
    build_name_key="iv_build_name", block_engraving_key="iv_block_engraving",
    output_key="iv_full_build_name_with_suffix" -- IV's identity is separate
    from block/build's per the Case B decision, so its enriched name needs
    its own key too, not a shared one."""
    canonical = dict(canonical)
    if canonical.get(build_name_key) and canonical.get(block_engraving_key):
        canonical[output_key] = lookup_fn(
            canonical[build_name_key], canonical[block_engraving_key]
        )
    return canonical

def _build_label(canonical: dict) -> str:
    """'BUILD_R10 3-02B' style label -- e.g. for print labels, and this is
    also exactly what the old write_build_file used for its file name.
    Requires enrich_with_build_suffix to have run first."""
    suffix_name = canonical.get("full_build_name_with_suffix") or canonical.get("full_build_name") or ""
    return f"{suffix_name} {_block_sn(canonical)}"


# ---------------------------------------------------------------------------
# Rendering a single token / line
# ---------------------------------------------------------------------------

def _render_token(token: Token, canonical: dict) -> str:
    if isinstance(token, Literal):
        return token.text
    if isinstance(token, Field):
        value = canonical.get(token.canonical)
        return stringify(value) if value not in (None, "") else token.placeholder
    if isinstance(token, Computed):
        value = token.fn(canonical)
        return value if value not in (None, "") else token.placeholder
    if isinstance(token, Glued):
        return "".join(_render_token(t, canonical) for t in token.tokens)
    raise TypeError(f"Unknown token type: {token!r}")


def stringify(value) -> str:
    if isinstance(value, date):
        # LabView files use M/D/YYYY -- adjust if that's not actually right,
        # this is a guess based on the old iso_date_to_labview naming.
        return f"{value.month}/{value.day}/{value.year}"
    return str(value)


def format_labview_scientific(value: float, decimals: int = 5) -> str:
    """Matches the heat file's number format: uppercase E, no leading zero
    on the exponent (E+0, not E+00), N decimal digits in the mantissa.
    Python's default :e format gives lowercase e, a fixed decimal count,
    and a minimum 2-digit exponent -- none of which match the sample file,
    so this is built manually, same reasoning as stringify()'s date
    handling avoiding strftime's platform-specific quirks."""
    formatted = f"{value:.{decimals}e}"
    if formatted == "inf":
        return formatted
    mantissa, exponent = formatted.split("e")
    exponent_sign = exponent[0]
    exponent_digits = exponent[1:].lstrip("0") or "0"
    return f"{mantissa}E{exponent_sign}{exponent_digits}"


def render_new_line(template: LineTemplate, canonical: dict) -> str:
    """Used when creating a file for the first time -- every token gets a
    fresh value or its placeholder."""
    parts = [_render_token(t, canonical) for t in template.tokens]
    return template.separator.join(parts)


def update_existing_line(template: LineTemplate, existing_line: str, canonical: dict, section: Section) -> str:
    """Used for piecemeal writes to a file that already exists. Only tokens
    whose Section matches the section being saved get overwritten; every
    other token's raw text is preserved exactly as read from disk, even if
    we don't know what it means (this is what lets PB1 saves leave PB2's
    already-written data alone without needing to understand it)."""
    existing_tokens = existing_line.split(template.separator)
    # Pad in case the line on disk is shorter than the template expects
    # (e.g. an old-format file written before a field existed).
    while len(existing_tokens) < len(template.tokens):
        existing_tokens.append("")

    new_tokens = []
    for i, token in enumerate(template.tokens):
        owns_this_token = isinstance(token, (Field, Computed)) and _section_of(token) == section
        if owns_this_token:
            new_tokens.append(_render_token(token, canonical))
        else:
            new_tokens.append(existing_tokens[i])
    return template.separator.join(new_tokens)


def _section_of(token: Union[Field, Computed]) -> Optional[Section]:
    canonical_name = token.canonical if isinstance(token, Field) else token.name
    spec = BY_CANONICAL.get(canonical_name)
    return spec.section if spec else None


# ---------------------------------------------------------------------------
# Extending this to the rest of the system
# ---------------------------------------------------------------------------
#
# PARTS / NOTES (build file rows 6-29, Build_Parts / Notes tables):
#   These are a repeating group, not a flat set of named fields -- there's a
#   variable-length list of (part_name, part_type, lot, quantity, tag) rows in
#   the DB, mapped onto a *fixed* set of named file lines (diode1, diode2,
#   circuit1, circuit2...). That mapping ("first DIODE-type part found goes to
#   diode1, second to diode2") is itself a rule worth pulling out of the route
#   and into one function -- e.g. `assign_parts_to_build_slots(parts: list) ->
#   dict` -- so BUILD_FILE_TEMPLATE's rows 6-29 can be defined the same way as
#   above (Field("diode1"), Field("diode2"), ...) once that assignment has
#   already happened. I'd tackle this once the scalar-field flow above is
#   working end to end, since it's a genuinely separate problem (list ->
#   fixed slots) layered on top of this one.
#
# IV FILE:
#   Different shape again -- "Label: value" lines instead of packed
#   multi-field lines, and (per write_IV_file) no piecemeal-update case at
#   all currently, just a single always-new file. A LabeledLineTemplate
#   (Literal(label) + Field, joined by ": ") would reuse Field/Literal/
#   render_new_line as-is; it just wouldn't need update_existing_line, since
#   there's no piecemeal IV save to support yet.
