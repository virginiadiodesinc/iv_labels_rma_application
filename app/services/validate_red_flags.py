def validate_block_identification(canonical: dict) -> list[str]:
    errors = []
    if not canonical.get("block_engraving"):
        errors.append("Block engraving is required.")
    if not canonical.get("block_serial_number"):
        errors.append("Block serial number is required.")
    return errors


def validate_inspection_info(canonical: dict) -> list[str]:
    errors = []
    if not canonical.get("inspection_date"):
        errors.append("Inspection date is required.")
    if not canonical.get("inspection_initials"):
        errors.append("Inspection initials are required.")
    return errors


def validate_pb1_info(canonical: dict) -> list[str]:
    errors = []
    if not canonical.get("pb1_build_name"):
        errors.append("PB1 build name is required.")
    if not canonical.get("pb1_date"):
        errors.append("PB1 date is required.")
    if not canonical.get("pb1_initials"):
        errors.append("PB1 initials are required.")
    return errors


def validate_pb2_info(canonical: dict) -> list[str]:
    errors = []
    if not canonical.get("pb2_build_name"):
        errors.append("PB2 build name is required.")
    if not canonical.get("pb2_date"):
        errors.append("PB2 date is required.")
    if not canonical.get("pb2_initials"):
        errors.append("PB2 initials are required.")
    if not canonical.get("pb2_inspection_initials"):
        errors.append("PB2 inspection initials are required.")
    return errors


def validate_full_build_info(canonical: dict) -> list[str]:
    errors = []
    if not canonical.get("full_build_name"):
        errors.append("Full build name is required.")
    if not canonical.get("full_build_initials"):
        errors.append("Full build initials are required.")
    if not canonical.get("full_build_date"):
        errors.append("Full build date is required.")
    return errors


def validate_all_lots_chosen(parts_list: list[dict]) -> list[str]:
    errors = []
    for part in parts_list:
        if part['part_lot'] == "Choose":
            errors.append(f"{part['part_name']} has no selected lot. Please select something (including NA or Unknown) for the lot value.")
    return errors

def validate_iv_lots_chosen(iv_parts_dict: dict) -> list[str]:
    errors = []
    if iv_parts_dict["iv_diode_lot"] == "Choose":
        errors.append(f"{iv_parts_dict['iv_diode_name']} has no selected lot. Please select something (including NA or Unknown) for the lot value.")
    if iv_parts_dict["iv_circuit_name"] and iv_parts_dict["iv_circuit_lot"] and iv_parts_dict["iv_circuit_lot"] == "Choose":
        errors.append(f"{iv_parts_dict['iv_circuit_name']} has no selected lot. Please select something (including NA or Unknown) for the lot value.")
    return errors


def validate_iv_identification(canonical: dict) -> list[str]:
    errors = []
    if not canonical.get("iv_block_engraving"):
        errors.append("IV block engraving is required.")
    if not canonical.get("iv_block_serial_number"):
        errors.append("IV block serial number is required.")
    if not canonical.get("iv_build_name"):
            errors.append("IV build name is required.")
    if not canonical.get("iv_diode_name"):
        errors.append("Diode part name is required.")
    return errors


# AN ATTEMPT AT A DYNAMIC VALIDATION WRAPPER
def validate_info(canonical: dict, validate_callable_list: list[callable]):
    all_errors = []
    for validate_callable in validate_callable_list:
        new_errors = validate_callable(canonical)
        all_errors.extend(new_errors)
    return all_errors