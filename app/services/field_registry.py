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
    FieldSpec("points_per_decade", Section.IV, int, db_model="IV_Info"),
    FieldSpec("ideality", Section.IV, float, db_model="IV_Info"),
    FieldSpec("saturation_current", Section.IV, float, db_model="IV_Info"),
    FieldSpec("series_resistance", Section.IV, float, db_model="IV_Info"),
    FieldSpec("mean_squared_error", Section.IV, float, db_model="IV_Info"),
    FieldSpec("r_squared_error", Section.IV, float, db_model="IV_Info"),
    FieldSpec("polarity", Section.IV, str, db_model="IV_Info"),
    FieldSpec("hysteresis_standard_deviation", Section.IV, float, db_model="IV_Info"),
    FieldSpec("hysteresis_mean", Section.IV, float, db_model="IV_Info"),
    FieldSpec("hysteresis_maximum", Section.IV, float, db_model="IV_Info"),
    FieldSpec("hysteresis_minimum", Section.IV, float, db_model="IV_Info"),
    FieldSpec("reverse_breakdown_current", Section.IV, float, db_model="IV_Info"),
    FieldSpec("reverse_breakdown_voltage", Section.IV, float, db_model="IV_Info"),

    # --- IV numbers ---
    # these are literally strings of the entire list of values
    # We have little to no interest in storing them point by point
    # So this may be folded into the IV_Info table later too.
    FieldSpec("voltage_up_string", Section.IV, str, db_model="IV_Points"),
    FieldSpec("voltage_down_string", Section.IV, str, db_model="IV_Points"),
    FieldSpec("voltage_average_string", Section.IV, str, db_model="IV_Points"),
    FieldSpec("current", Section.IV, str, db_model="IV_Points"),
    FieldSpec("temperature_string", Section.IV, str, db_model="IV_Points"),

    # --- IV related fields that aren't parameters? ---
    FieldSpec("iv_file_path", Section.IV, str, db_model="IV_Info"),
    FieldSpec("iv_diode_name", Section.IV, str, db_model="IV_Info"),
    FieldSpec("iv_diode_lot", Section.IV, str, db_model="IV_Info"),
    FieldSpec("iv_circuit_name", Section.IV, str, db_model="IV_Info"),
    FieldSpec("iv_circuit_lot", Section.IV, str, db_model="IV_Info"),
    FieldSpec("iv_assembly_number", Section.IV, str, db_model="IV_Info"),
    FieldSpec("iv_date", Section.IV, str, db_model="IV_Info"),

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
    """form is anything with .get(key, default) -- request.form works directly."""
    result = {}
    for spec in FIELDS:
        if not spec.form_name:
            continue
        raw = (form.get(spec.form_name, "") or "").strip()
        if raw == "":
            result[spec.canonical] = None
            continue
        if spec.value_type is date:
            result[spec.canonical] = _parse_iso_date(raw)
        else:
            result[spec.canonical] = raw

    # block_revision defaults to "A" when blank -- this is a real business rule,
    # not a generic "blank becomes X" rule, so it stays here rather than being
    # folded into the loop above.
    if result.get("block_revision") is None:
        result["block_revision"] = "A"

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
    placeholder: str = ""


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

# --- IV file: not built out yet (that needs diode/circuit/assembly_no/
# polarity/medium FieldSpecs added to FIELDS first, which is a bigger step
# than today's scope), but here's row 0 worked out to prove Glued handles
# the ugly part. The old write_IV_file version of this line was:
#
#   build_name_with_suffix + ' B' + build_sn + ' ' + diode + ' Cir' + circuit
#   + ' A#' + assembly_no + ' ' + polarity + ' ' + block_engraving + ' '
#   + block_sn + ' ' + medium
#
# As a LineTemplate, once the relevant FieldSpecs exist:
#
#   LineTemplate(0, separator=" ", tokens=[
#       Computed("full_build_name_with_suffix", ...),
#       Glued([Literal("B"), Field("build_serial_number")]),
#       Field("diode_name"),
#       Glued([Literal("Cir"), Field("circuit_name")]),
#       Glued([Literal("A#"), Field("assembly_no")]),
#       Field("polarity"),
#       Field("block_engraving"),
#       Computed("block_sn", _block_sn),
#       Field("medium"),
#   ])
#
# That's the whole line -- no new machinery beyond Glued, and it reads in
# the same order as the old concatenation did. The "Label: value" lines
# (rows 2-13, Points/Decade etc.) need nothing new either -- they're just
# LineTemplate(i, [Literal("Points/Decade: "), Field("points_per_decade")],
# separator="") -- a two-token line with an empty separator already does it.
#
# The Vup/Vdown/Isource data rows and the tab-separated header are a
# different kind of problem entirely -- a variable-length list of numeric
# rows, not named fields -- and don't belong in this registry at all. Render
# those the same way write_IV_file always did (zip the three lists, format,
# join with '\t'), just without going through FieldSpec/LineTemplate.
#
# PB2 has an update path (piecemeal); IV does not, per your confirmation
# that IV always overwrites -- so IV only ever needs render_new_line, never
# update_existing_line.
IV_FILE_TEMPLATE: list[LineTemplate] = [
    LineTemplate(0, separator=" ", tokens=[
        Computed("full_build_name_with_suffix", ...),
        Glued([Literal("B"), Field("build_serial_number")]),
        Field("diode_name"),
        Glued([Literal("Cir"), Field("circuit_name")]),
        Glued([Literal("A#"), Field("assembly_no")]),
        Field("polarity"),
        Field("block_engraving"),
        Computed("block_sn", _block_sn),
        Field("medium"),
    ]),
    LineTemplate(1, tokens=[Literal("Date"), Literal("Time"), Literal("AM/PM")]),
    LineTemplate(2, tokens=[Literal("Points/Decade:"), Field("points_per_decade")]),
    LineTemplate(3, tokens=[Literal("n (ideality):"), Field("points_per_decade")]),
    LineTemplate(4, tokens=[Literal("Is:"), Field("points_per_decade")]),
    LineTemplate(5, tokens=[Literal("Rs:"), Field("points_per_decade")]),
    LineTemplate(6, tokens=[Literal("Mean Square Error:"), Field("points_per_decade")]),
    LineTemplate(7, tokens=[Literal("R^2 Error:"), Field("points_per_decade")]),
    LineTemplate(8, tokens=[Literal("Polarity"), Field("points_per_decade")]),
    LineTemplate(9, tokens=[Literal("Hysteresis SD (mV) ="), Field("points_per_decade")]),
    LineTemplate(10, tokens=[Literal("Hysteresis Mean (mV) ="), Field("points_per_decade")]),
    LineTemplate(11, tokens=[Literal("Hysteresis Max (mV) ="), Field("points_per_decade")]),
    LineTemplate(12, tokens=[Literal("Hysteresis Min (mV) ="), Field("points_per_decade")]),
    LineTemplate(13, tokens=[Literal("Reverse Current (uA):"), Field("points_per_decade")]),
    LineTemplate(14, tokens=[Literal("Reverse Voltage (V):"), Field("points_per_decade")]),
    LineTemplate(15, separator="\t", tokens=[Literal("Voltage Up (mV)"), Literal("Voltage Down (mV)"), Literal("Current (uA)")])
    # rows 16-37 (and beyond) to be filled in later, but something like:
    # LineTemplate(row, separator="\t", tokens=[Field("row_voltage_up"), Field("row_voltage_down"), Field("row_current")])
]

# added difficulty because it uses a mix of tabs, spaces, and semicolons
HEAT_FILE_TEMPLATE: list[LineTemplate] = [
    LineTemplate(0, separator=" ", tokens=[
    Literal("Date"),
    Literal("Time"),
    Literal("AM/PM\t"),
    Computed("full_build_name_with_suffix", ...),
    Glued([Literal("B"), Field("build_serial_number")]),
    Field("diode_name"),
    Glued([Literal("Cir"), Field("circuit_name")]),
    Glued([Literal("A#"), Field("assembly_no")]),
    Field("polarity"),
    Field("block_engraving"),
    Computed("block_sn", _block_sn),
    Field("medium"),
    ]),
]

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
    # rows 6-29 (diode/circuit/parts/notes) are a separate repeating-group
    # concern -- see the note at the bottom of this file.
]


# ---------------------------------------------------------------------------
# Filename / label construction -- these reuse _block_sn rather than storing
# a redundant copy of it, same idea as the line templates above.
# ---------------------------------------------------------------------------

def block_file_name(canonical: dict) -> str:
    """Matches the old write_block_file naming: '<engraving> <sn+rev>.txt', lowercased."""
    return f"{canonical.get('block_engraving') or ''} {_block_sn(canonical)}.txt".lower()


def enrich_with_build_suffix(canonical: dict, lookup_fn) -> dict:
    """Adds 'full_build_name_with_suffix' by looking up the block engraving's
    suffix (old su.get_build_name_with_suffix, which reads block_engravings.csv).
    This does file I/O, which is why it's a separate explicit step rather than
    a Computed token -- Computed tokens stay pure functions of the canonical
    dict so render_new_line/update_existing_line never touch disk themselves.
    Only call this where you actually need the suffixed name (full build
    saves, print labels) -- inspection/PB1/PB2 saves don't need it."""
    canonical = dict(canonical)
    if canonical.get("full_build_name") and canonical.get("block_engraving"):
        canonical["full_build_name_with_suffix"] = lookup_fn(
            canonical["full_build_name"], canonical["block_engraving"]
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
        return _stringify(value) if value not in (None, "") else token.placeholder
    if isinstance(token, Computed):
        value = token.fn(canonical)
        return value if value not in (None, "") else token.placeholder
    if isinstance(token, Glued):
        return "".join(_render_token(t, canonical) for t in token.tokens)
    raise TypeError(f"Unknown token type: {token!r}")


def _stringify(value) -> str:
    if isinstance(value, date):
        # LabView files use M/D/YYYY -- adjust if that's not actually right,
        # this is a guess based on the old iso_date_to_labview naming.
        return f"{value.month}/{value.day}/{value.year}"
    return str(value)


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
