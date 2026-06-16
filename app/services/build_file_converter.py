import os
from app.services import date_converter as dc

# RETURNS A DICTIONARY WITH ALL THE BUILD INFO EXTRACTED FROM THE FILE, INCLUDING A LIST OF PARTS AND A LIST OF NOTES
# The expected format of the returned dict is as follows:
# {
# 	"full_build_name": "BUILD_NAME",
# 	"block_engraving": "ENGRAVING",
# 	"pb1_build_name": "PB1_BUILD_NAME",
# 	"block_revision": "REVISION",
# 	"block_serial_number": "SERIAL_NUMBER",
# 	"inspection_date": "INSPECTION_DATE",
# 	"inspection_initials": "INSPECTOR_INITIALS",
# 	"pb1_date": "PB1_DATE",
# 	"pb1_initials": "PB1_INSPECTOR_INITIALS",
# 	"pb2_build_name": "PB2_BUILD_NAME",
# 	"pb2_date": "PB2_DATE",
# 	"pb2_initials": "PB2_INSPECTOR_INITIALS",
# 	"pb2_pass_fail": "PB2_PASS_FAIL",
# 	"pb2_bond_pads_count": "PB2_BOND_PADS
# 	"pb2_components_count": "PB2_COMPONENTS",
# 	"diode_1": "DIODE_1_NAME",
# 	"diode_1_chip_count": "DIODE_1_CHIP_COUNT",
# 	"circuit_1": "CIRCUIT_1_NAME",
# 	"diode_2": "DIODE_2_NAME",
# 	"diode_2_chip_count": "DIODE_2_CHIP_COUNT",
# 	"circuit_2": "CIRCUIT_2_NAME",
# 	"pcb_info": "PCB_INFO",
# 	"indium_info": "INDIUM_INFO",
# 	"vbr": "VBR",
# 	"mmic_name": "MMIC_NAME",
# 	"mmic_lot": "MMIC_LOT",
# 	"notes": ["NOTE_1", "NOTE_2", ...]
# }


def convert_build_file(file):
	"""Converts a build file to a pattern which can be used to populate the fields of the forms on the page
	
	This function converts a build file to our input field format

	@param file Build File.
	@return build_info Return value of type(dict)
	
	"""
	file_content = file.read()
	lines = file_content.splitlines()
	build_info = {}
	file_name = file.name
	file_name = file_name.replace(".txt", "")

	build_name = file_name.split(os.sep)[-1].split("_")[0].upper()
	build_serial_number_with_possible_letter = file_name.split(os.sep)[-1].split()[1]
	build_serial_number = file_name.split(os.sep)[-1].split()[1][:-1]
	build_rev_letter = file_name.split(os.sep)[-1].split()[1][-1]

	if not build_rev_letter.isalpha():
		build_serial_number = build_serial_number_with_possible_letter
		build_rev_letter = "A"
	else:
		build_rev_letter = build_rev_letter.upper()

	build_info["full_build_name"] = build_name

	for index, line in enumerate(lines):
		# FIRST LINE: Block Engraving, PB1 Name (optional)
		if index == 0:
			split_line = line.split()
			build_info["block_engraving"] = split_line[0]
			if len(split_line) > 1:
				build_info["pb1_build_name"] = split_line[1]

		# SECOND LINE: Serial Number, Rev Letter (optional, empty is assumed to be Rev A)
		if index == 1:
			build_info["block_revision"] = build_rev_letter
			build_info["block_serial_number"] = build_serial_number

		# THIRD LINE: Inspection Date
		if index == 2:
			split_line = line.split()
			build_info["inspection_date"] = dc.labview_date_to_iso(split_line[0])
		
		# FOURTH LINE: Inspector Initials
		if index == 3:
			split_line = line.split()
			build_info["inspection_initials"] = split_line[0]

		# FIFTH LINE: PB1 Date
		if index == 4:
			split_line = line.split()
			build_info["pb1_date"] = dc.labview_date_to_iso(split_line[0])

		# SIXTH LINE: PB1 Initials, PB2 Build Name (optional), PB2 Date (optional), 
		# PB2 Initials (optional), PB2 Pass/Fail (optional), PB2 Bond Pads (optional),
		# PB2 Components (optional), PB2 Inspection Initials (optional)
		if index == 5:
			split_line = line.split(";")
			build_info["pb1_initials"] = split_line[0]
			if len(split_line) > 1:
				build_info["pb2_build_name"] = split_line[1]
			if len(split_line) > 2:
				build_info["pb2_date"] = dc.labview_date_to_iso(split_line[2])
			if len(split_line) > 3:
				build_info["pb2_initials"] = split_line[3]
			if len(split_line) > 4:
				build_info["pb2_pass_fail"] = split_line[4]
			if len(split_line) > 5:
				build_info["pb2_bond_pads_count"] = split_line[5]
			if len(split_line) > 6:
				build_info["pb2_components_count"] = split_line[6]
			if len(split_line) > 7:
				build_info["pb2_inspection_initials"] = split_line[7]

		# SEVENTH LINE: Diode 1
		if index == 6:
			build_info["diode_1"] = line
		
		# EIGHTH LINE: Diode 1 chip count
		if index == 7:
			build_info["diode_1_chip_count"] = line

		# NINTH LINE: Builder Initials
		if index == 8:

			build_info["full_build_initials"] = line

		# TENTH LINE: Build Date
		if index == 9:
			build_info["full_build_date"] = dc.labview_date_to_iso(line)

		# ELEVENTH LINE: Circuit 1
		if index == 10:
			build_info["circuit_1"] = line

		# TWELFTH LINE: Indium Info (optional)
		if index == 11:
			build_info["indium_info"] = line
			
		# THIRTEENTH LINE: VBR (optional)
		if index == 12:
			build_info["vbr"] = line

		# FOURTEENTH LINE: MMIC Name (optional)
		if index == 13:
			build_info["mmic_name"] = line
		
		# FIFTEENTH LINE: MMIC Lot Number (optional)
		if index == 14:
			build_info["mmic_lot"] = line

		# SIXTEENTH LINE: Notes (optional)
		if index == 15:
			build_info["notes"] = []
			if len(line) > 0:
				build_info["notes"].append(line)

		# SEVENTEENTH LINE: PCB Info (optional)
		if index == 16:
			build_info["pcb_info"] = line
		
		# EIGHTEENTH LINE: Filter 1 (optional)
		if index == 17:
			build_info["filter_1"] = line

		# NINETEENTH LINE: Diode 2 (optional)
		if index == 18:
			build_info["diode_2"] = line

		# TWENTIETH LINE: Diode 2 Chip Count (optional)
		if index == 19:
			build_info["diode_2_chip_count"] = line

		# TWENTY-FIRST LINE: Builder Initials Again (optional)
		if index == 20:
			build_info["full_build_initials_again"] = line

		# TWENTY-SECOND LINE: Build Date Again (optional)
		if index == 21:
			build_info["full_build_date_again"] = dc.labview_date_to_iso(line)

		# TWENTY-THIRD LINE: Circuit 2 (optional)
		if index == 22:
			build_info["circuit_2"] = line

		# TWENTY-FOURTH THROUGH TWENTY-NINTH LINES: Additional Notes (optional)
		if index >= 23 and index <= 28:
			if len(line) > 0:
				build_info["notes"].append(line)

		# TWENTY-NINTH LINE: Filter 2 (optional)
		if index == 28:
			build_info["filter_2"] = line
	
	return build_info

