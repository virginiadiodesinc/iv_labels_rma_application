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

# AN ATTEMPT AT A DYNAMIC VALIDATION WRAPPER
def validate_info(canonical: dict, validate_callable_list: list[callable]):
    all_errors = []
    for validate_callable in validate_callable_list:
        new_errors = validate_callable(canonical)
        all_errors.extend(new_errors)
    return all_errors