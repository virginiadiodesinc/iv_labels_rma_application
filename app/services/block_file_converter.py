from app.services import date_converter as dc

def convert_block_file(file):
	file_content = file.read()
	lines = file_content.splitlines()
	block_info = {}
	
	for index, line in enumerate(lines):
		# FIRST LINE: Block Engraving, PB1 Name (optional)
		if index == 0:
			split_line = line.split()
			block_info["block_engraving"] = split_line[0]
			if len(split_line) > 1:
				block_info["pb1_build_name"] = split_line[1]

		# SECOND LINE: Serial Number, Rev Letter (optional, empty is assumed to be Rev A)
		if index == 1:
			split_line = line.split()
			if split_line[0][-1].isalpha():
				serial_number = split_line[0][:-1]
				revision_letter = split_line[0][-1]
			else:
				serial_number = split_line[0]
				revision_letter = "A"
			block_info["block_revision"] = revision_letter
			block_info["block_serial_number"] = serial_number

		# THIRD LINE: Inspection Date
		if index == 2:
			split_line = line.split()
			block_info["inspection_date"] = dc.labview_date_to_iso(split_line[0])
		
		# FOURTH LINE: Inspector Initials
		if index == 3:
			split_line = line.split()
			block_info["inspection_initials"] = split_line[0]

		# FIFTH LINE: PB1 Date
		if index == 4:
			split_line = line.split()
			block_info["pb1_date"] = dc.labview_date_to_iso(split_line[0])

		# SIXTH LINE: PB1 Initials, PB2 Build Name (optional), PB2 Date (optional), 
		# PB2 Initials (optional), PB2 Pass/Fail (optional), PB2 Bond Pads (optional),
		# PB2 Components (optional), PB2 Inspection Initials (optional)
		if index == 5:
			split_line = line.split(";")
			block_info["pb1_initials"] = split_line[0]
			if len(split_line) > 1:
				block_info["pb2_build_name"] = split_line[1]
			if len(split_line) > 2:
				block_info["pb2_date"] = dc.labview_date_to_iso(split_line[2])
			if len(split_line) > 3:
				block_info["pb2_initials"] = split_line[3]
			if len(split_line) > 4:
				block_info["pb2_pass_fail"] = split_line[4]
			if len(split_line) > 5:
				block_info["pb2_bond_pads_count"] = split_line[5]
			if len(split_line) > 6:
				block_info["pb2_components_count"] = split_line[6]
			if len(split_line) > 7:
				block_info["pb2_inspection_initials"] = split_line[7]

	return block_info

