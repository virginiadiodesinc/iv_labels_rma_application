"""
parts_service.py

Two jobs, kept separate:
  parts_from_form   -- parallel form lists -> one dict per submitted part row.
                        This is what the DB side uses directly, one row per
                        Build_Parts insert, no slotting involved.
  assign_parts_to_build_slots -- takes that same list and buckets it into the
                        fixed named slots the build file actually has room
                        for. Anything that doesn't fit a slot is dropped from
                        the file (per your Q5 answer) -- it's still in the DB
                        from parts_from_form, just not in the file.
"""

# (canonical_key, form_name, value_type)
REQUIRED_PART_FIELDS = [
    ("part_type", "part_type", str),
    ("part_name", "part", str),
    ("quantity", "quantity", int),
    ("subassembly_tag", "part-tag", str),
]

OPTIONAL_PART_FIELDS = [
    ("reverse_breakdown_voltage", "diode-row-reverse-voltage-input", str, "DIODE"),
    ("temperature", "diode-row-temperature-input", str, "DIODE"),
    ("indium", "diode-row-indium-input", str, "DIODE"),
    ("modifications", "pcb-modifications-input", str, "PCB"),
]

IMPORTANT_MMIC_SUBSTRINGS = [
    "TSC",
    "T04",
    "APP",
    "ALP",
    "ALN"
]


def _resolve_lots(form) -> list:
    """lot-select holds each row's dropdown choice (a real historical lot, or
    Choose/Unknown/NA/Other). Rows where the user picked "Other" get their
    value replaced by the next entry in the custom-lot list, in submission
    order -- same logic as the old custom_lot_handler, just inlined here
    since it only has one caller. The hidden 'lot' field is deliberately NOT
    read here -- per your answer, it's load-time-only, not the save value."""
    lot_selects = form.getlist("lot-select")
    custom_lots = form.getlist("custom-lot-input")
    resolved = []
    custom_index = 0
    for lot in lot_selects:
        if lot == "Other":
            resolved.append(custom_lots[custom_index] if custom_index < len(custom_lots) else "")
            custom_index += 1
        else:
            resolved.append(lot)
    return resolved


def parts_from_form(form) -> list:
    """One dict per submitted part row, in submission order. Every
    getlist() call is positionally aligned -- index i across all of them is
    the same row, since every part-row.html renders the same fields
    (diode/pcb ones just sit CSS-hidden, not removed from the DOM, for
    non-diode/non-pcb rows -- their default 'NA' values just ride along
    harmless for rows that don't use them)."""
    row_count = len(form.getlist("part"))
    part_types = form.getlist("part_type")
    lot_values = _resolve_lots(form)

    special_part_starting_indexes = {
        "DIODE": part_types.index("DIODE") if "DIODE" in part_types else 99,
        "PCB": part_types.index("PCB") if "PCB" in part_types else 99
    }

    parts = []
    for i in range(row_count):
        part = {}
        for canonical, form_name, value_type in REQUIRED_PART_FIELDS:
            values = form.getlist(form_name)
            raw = values[i] if i < len(values) else None
            part[canonical] = int(raw) if (value_type is int and raw) else raw
        
        part["part_lot"] = lot_values[i] if i < len(lot_values) else ""
        parts.append(part)

    for i in range(row_count):
        for canonical, form_name, value_type, relevant_part in OPTIONAL_PART_FIELDS:
            relevant_index_modifier = special_part_starting_indexes[relevant_part]
            values = form.getlist(form_name)
            modified_index = i + relevant_index_modifier
            raw = values[i] if i < len(values) else None
            if modified_index >= row_count:
                continue
            parts[modified_index][canonical] = int(raw) if (value_type is int and raw) else raw
            
    return parts


def notes_from_form(form) -> list:
    row_count = len(form.getlist("note"))
    notes = []
    note_text = form.getlist("note")
    note_types = form.getlist("note_type")
    for i in range(row_count):
        note = {"note": note_text[i], "type": note_types[i]}
        notes.append(note)
    return notes


def iv_parts_from_form(form) -> dict:
    parts_list = form.getlist("part")
    lots_list = _resolve_lots(form)

    return {
            "iv_diode_name": parts_list[0] if len(parts_list) > 0 else None,
            "iv_diode_lot": lots_list[0] if len(lots_list) > 0 else None,
            "iv_circuit_name": parts_list[1] if len(parts_list) > 1 else None,
            "iv_circuit_lot": lots_list[1] if len(lots_list) > 1 and len(parts_list) > 1 else None,
        }


def _format_part_lot(part: dict) -> str:
    return f"{part['part_name']}_LOT{part['part_lot']}"


def _classify_circuit_or_filter(part_name: str):
    """Only ever called for parts already typed CIRCUIT -- FILTER/FILTER
    MESH are unrelated types per your Q2 answer and never reach this."""
    suffix = part_name.rsplit("-", 1)[-1]
    if suffix.startswith("Z"):
        return "circuit"
    if suffix.startswith("F"):
        return "filter"
    else:
        return "circuit"


def sort_parts_by_priority(parts: list, priorities: list, priority_function: callable):
    return sorted(parts, key=lambda part: priority_function(part, priorities))


def prioritize_part_by_substring(part: dict, priorities: list):
    for index, priority in enumerate(priorities):
        if priority in part["part_name"]:
            return index
    return len(priorities)



def assign_parts_and_notes_to_build_slots(parts: list, notes: list) -> dict:
    """Returns slot-name -> rendered string, meant to be merged into
    canonical before BUILD_FILE_TEMPLATE renders -- same pattern as
    merge_yellow_flags: compute a dict elsewhere, merge it in, then every
    slot is just an ordinary Field("diode1") etc. token at render time."""
    slots = {}
    diodes, circuits, filters, mmics, pcbs, extras = [], [], [], [], [], []
    mmic = pcb = None

    note_index = 0
    for note in notes:
        if note_index > 6:
            break
        note_text = note["note"]
        note_key = "notes" if note_index == 0 else f"notes{note_index}"
        slots[note_key] = note_text
        note_index += 1

    for part in parts:
        ptype = part["part_type"]
        if ptype == "DIODE":
            diodes.append(part)
        elif ptype == "CIRCUIT":
            classification = _classify_circuit_or_filter(part["part_name"])
            if classification == "circuit":
                circuits.append(part)
            elif classification == "filter":
                filters.append(part)
        elif ptype == "MMIC":
            mmics.append(part)
        elif ptype == "PCB":
            pcbs.append(part)
        else:
            extras.append(part)

    if len(diodes) >= 1:
        slots["diode1"] = _format_part_lot(diodes[0])
        slots["qty_chips1"] = str(diodes[0].get("quantity", ""))
        slots["indium"] = diodes[0].get("indium", "NA")
        slots["Vbr"] = diodes[0].get("reverse_breakdown_voltage", "NA")
    if len(diodes) >= 2:
        slots["diode2"] = _format_part_lot(diodes[1])
        slots["qty_chips2"] = str(diodes[1].get("quantity", ""))

    if len(circuits) >= 1:
        slots["circuit1"] = _format_part_lot(circuits[0])
    if len(circuits) >= 2:
        slots["circuit2"] = _format_part_lot(circuits[1])

    if len(filters) >= 1:
        slots["filter1"] = _format_part_lot(filters[0])
    if len(filters) >= 2:
        slots["filter2"] = _format_part_lot(filters[1])

    if mmics:
        mmics = sort_parts_by_priority(mmics, IMPORTANT_MMIC_SUBSTRINGS, prioritize_part_by_substring)
        slots["MMIC"] = mmics[0]["part_name"]
        slots["MMIC_lot"] = mmics[0]["part_lot"]
    if pcbs:
        slots["PCB"] = _format_part_lot(pcbs[0])
        if pcbs[0]["modifications"] and note_index <= 6:
            note_key = "notes" if note_index == 0 else f"notes{note_index}"
            slots[note_key] = pcbs[0]["modifications"]
            note_index += 1


    if len(mmics) >= 2:
        extras = mmics[1:] + extras
    if len(pcbs) >= 2:
        extras = pcbs[1:] + extras
    if len(diodes) >= 3:
        extras = diodes[2:] + extras
    if len(circuits) >= 3:
        extras = circuits[2:] + extras

    for extra in extras:
        if note_index <= 6:
            note_key = "notes" if note_index == 0 else f"notes{note_index}"
            slots[note_key] = _format_part_lot(extra)
            note_index += 1
        else:
            break

    return slots


"""
Parsing for the data-comparison page's Parts / Notes edit forms. Kept
separate from parts_from_form on purpose: that parser fills diode/PCB fields
by position and relies on the main page's JS, and here every field is
editable on every part type.

Edit rows are named by a per-row uid (same trick as the filters):
    part_uid                      one hidden input per row, DOM order = row order
    part_type-<uid>, part_name-<uid>, ... one input per column
    note_uid, note_type-<uid>, note-<uid>
so a row's fields can never pair with another row's, whatever is deleted,
added or reordered.

These lists mirror part-row.html / note-row.html. If you like, point those
templates at the part_types() / subassembly_tags() / note_types() globals so
there's one copy.
"""

PART_TYPES = ['CIRCUIT', 'DIODE', 'FILTER MESH', 'MMIC', 'PCB', 'VAC',
              'BCMESH', 'CONNECTOR', 'MA PARTS', 'MISC', 'SP OTHER',
              'CABLE', 'FILTER', 'INVENTORY', 'PMP']

SUBASSEMBLY_TAGS = ['NA', '1', '2', '3', 'A', 'B', 'A1', 'A2', 'G1', 'G2', 'G3', 'G4', 'W']

# Note_Type member NAMES, in note-row.html's order.
NOTE_TYPES = ["GENERIC", "CURRENT_TEST", "REWORK_SUMMARY", "FAST_CART_NUMBER", "CAPA_NUMBER", "JOB_NUMBER"]

# Build_Parts columns, in the edit table's column order.
PART_EDIT_COLUMNS = [
    "part_type", "part_name", "part_lot", "quantity", "subassembly_tag",
    "reverse_breakdown_voltage", "temperature", "indium", "modifications",
]

# Blank -> 'NA', same default the main page's inputs carry.
NA_DEFAULT_COLUMNS = {"subassembly_tag", "reverse_breakdown_voltage", "temperature", "indium", "modifications"}


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


# ---------- parts ----------

def part_row_for_display(part: dict) -> dict:
    """Any part dict (DB-sourced or raw form) -> all-string row for the edit
    table, with the NA defaults applied. Also used by db_service to normalize
    rows before diffing, so an untouched legacy row (None where the form
    shows 'NA') doesn't count as a change."""
    row = {col: _clean(part.get(col)) for col in PART_EDIT_COLUMNS}
    for col in NA_DEFAULT_COLUMNS:
        row[col] = row[col] or "NA"
    return row


def blank_part_row() -> dict:
    return part_row_for_display({"part_type": PART_TYPES[0], "quantity": 1})


def raw_part_rows(form) -> list:
    """Exactly what the user typed, row by row, no coercion. Used to re-show
    the form after an error."""
    return [
        {col: _clean(form.get(f"{col}-{uid}")) for col in PART_EDIT_COLUMNS}
        for uid in form.getlist("part_uid")
    ]


def parts_from_edit_form(form) -> list:
    """Rows ready for Build_Parts inserts, in DOM order. Only checks what the
    database itself needs (a name, a lot, a whole-number quantity); no red or
    yellow flag rules, so wrong data can always be corrected or removed.
    Raises ValueError listing every problem at once."""
    parts, errors = [], []
    for n, raw in enumerate(raw_part_rows(form), start=1):
        part = part_row_for_display(raw)
        if not part["part_type"]:
            errors.append(f"Part {n}: type is blank.")
        if not part["part_name"]:
            errors.append(f"Part {n}: name is blank.")
        if not part["part_lot"]:
            errors.append(f"Part {n}: lot is blank (use NA or Unknown if it isn't known).")
        try:
            part["quantity"] = int(part["quantity"])
        except ValueError:
            errors.append(f"Part {n}: quantity must be a whole number.")
        parts.append(part)
    if errors:
        raise ValueError(" ".join(errors))
    return parts


# ---------- notes ----------

def note_row_for_display(note: dict) -> dict:
    """type as the Note_Type NAME (uppercase), matching the select's values."""
    text = note.get("note")
    return {"type": _clean(note.get("type")).upper(), "note": "" if text is None else str(text)}


def raw_note_rows(form) -> list:
    return [
        {"type": _clean(form.get(f"note_type-{uid}")).upper(), "note": form.get(f"note-{uid}") or ""}
        for uid in form.getlist("note_uid")
    ]


def notes_from_edit_form(form) -> list:
    """Same dict shape as notes_from_form ({"type": lowercase, "note": text}),
    so stage_replace_notes and assign_parts_and_notes_to_build_slots take it
    unchanged."""
    notes, errors = [], []
    for n, raw in enumerate(raw_note_rows(form), start=1):
        text = raw["note"].strip()
        if raw["type"] not in NOTE_TYPES:
            errors.append(f"Note {n}: unknown type.")
        if not text:
            errors.append(f"Note {n}: text is blank.")
        notes.append({"type": raw["type"].lower(), "note": text})
    if errors:
        raise ValueError(" ".join(errors))
    return notes
