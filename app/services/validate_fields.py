from app import config
import csv

def validate_block_identification_fields(block_engraving, block_serial_number, block_revision):
    return validate_field_list[block_engraving, block_serial_number, block_revision]


def validate_inspection_info_fields(inspection_date, inspection_initials):
    return validate_field_list[inspection_date, inspection_initials]


def validate_field_list(field_list):
    for field in field_list:
        if not field:
            return False
    return True


def validate_bom(component):
    return


def validate_block_name_listed(block_engraving):
    block_engravings_file = open(config.block_list_file)
    block_engravings_reader = csv.reader(block_engravings_file)
    full_csv_list = list(block_engravings_reader)

    file_found = False
    for entry in full_csv_list:
        if block_engraving.strip() == entry[0]:
            file_found = True

    block_engravings_file.close()
    return file_found


def validate_build_name_listed(build_name):
    build_names_file = open(config.build_list_file)
    build_names_reader = csv.reader(build_names_file)
    full_csv_list = list(build_names_reader)

    file_found = False
    for entry in full_csv_list:
        if build_name.strip() == entry[0]:
            file_found = True

    build_names_file.close()
    return file_found


block_file_fields_list = [
    "block_engraving",
    "block_sn", 
    "inspection_date",
    "inspection_initials",
    "PB1_name",
    "PB1_date",
    "PB1_initials",
    "PB2_name",
    "PB2_date",
    "PB2_initials",
    "PB2_inspection"
]

input_form_fields_list = [
    "block-engraving-input", 
    "block-serial-number-input",
    "block-revision-input",
    "inspection-date-input",
    "inspection-initials-input",
    "pb1-build-name-input",
    "pb1-date-input",
    "pb1-initials-input",
    "pb2-build-name-input",
    "pb2-date-input",
    "pb2-initials-input",
    "pb2-inspection-initials-input"
]

# block_file_to_input_fields_correspondence = {
# 	"block_engraving": block_data.get("block-engraving-input", ""),
# 	"block_sn": block_data.get("block-serial-number-input", "") + block_rev,
# 	"inspection_date": iso_date_to_labview(block_data.get("inspection-date-input", "")),
# 	"inspection_initials": block_data.get("inspection-initials-input", ""),
# 	"PB1_name": block_data.get("pb1-build-name-input", ""),
# 	"PB1_date": iso_date_to_labview(block_data.get("pb1-date-input", "")),
# 	"PB1_initials": block_data.get("pb1-initials-input", ""),
# 	"PB2_name": block_data.get("pb2-build-name-input", ""),
# 	"PB2_date": iso_date_to_labview(block_data.get("pb2-date-input", "")),
# 	"PB2_initials": block_data.get("pb2-initials-input", ""),
# 	#"PB2_passfail": block_data.get("pb2-pass-fail-input", ""),
# 	#"PB2_bond_wire_pads": block_data.get("pb2-bond-pads-count-input", ""),
# 	#"PB2_components": block_data.get("pb2-components-count-input", ""),
# 	"PB2_inspection": block_data.get("pb2-inspection-initials-input", "")
# }