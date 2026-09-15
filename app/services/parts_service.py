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
PART_FIELDS = [
    ("part_type", "part_type", str),
    ("part_name", "part", str),
    ("quantity", "quantity", int),
    ("subassembly_tag", "part-tag", str),
    ("reverse_breakdown_voltage", "diode-row-reverse-voltage-input", str),
    ("temperature", "diode-row-temperature-input", str),
    ("indium", "diode-row-indium-input", str),
    ("modifications", "pcb-modifications-input", str),
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
    lot_values = _resolve_lots(form)

    parts = []
    for i in range(row_count):
        part = {}
        for canonical, form_name, value_type in PART_FIELDS:
            values = form.getlist(form_name)
            raw = values[i] if i < len(values) else ""
            part[canonical] = int(raw) if (value_type is int and raw) else raw
        part["part_lot"] = lot_values[i] if i < len(lot_values) else ""
        parts.append(part)
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
    return None  # doesn't match either convention -- dropped, not a guess


def assign_parts_to_build_slots(parts: list) -> dict:
    """Returns slot-name -> rendered string, meant to be merged into
    canonical before BUILD_FILE_TEMPLATE renders -- same pattern as
    merge_yellow_flags: compute a dict elsewhere, merge it in, then every
    slot is just an ordinary Field("diode1") etc. token at render time."""
    slots = {}
    diodes, circuits, filters = [], [], []
    mmic = pcb = None

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
            # else: CIRCUIT-typed but matched neither Z nor F -- dropped
        elif ptype == "MMIC" and mmic is None:
            mmic = part
        elif ptype == "PCB" and pcb is None:
            pcb = part
        # else: any other type, or a 3rd+ MMIC/PCB -- dropped from the file

    if len(diodes) >= 1:
        slots["diode1"] = _format_part_lot(diodes[0])
        slots["qty_chips1"] = str(diodes[0].get("quantity", ""))
        slots["indium"] = diodes[0].get("indium", "")
        slots["Vbr"] = diodes[0].get("reverse_breakdown_voltage", "")
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

    if mmic:
        slots["MMIC"] = mmic["part_name"]
        slots["MMIC_lot"] = mmic["part_lot"]
    if pcb:
        slots["PCB"] = _format_part_lot(pcb)

    return slots