from app.services import build_file_converter as build_converter

def populate_info_from_build_file(build_file_path):
	"""Populates the various input fields with information from a (likely LabView) build file

	This function uses a LabView build file to populate all the block (inspection, PB1, PB2) as well as build (part/note list) fields

	@return build-file-population-response Return value of type (template partial)
	"""

	if build_file_path and build_file_path.endswith(".txt"):
		with open(build_file_path, "r") as build_file:
			build_dict = build_converter.convert_build_file(build_file)

		part_rows = []

		diode_1_full_text = build_dict.get("diode_1", "")
		diode_1_name, diode_1_lot, diode_1_extra = su.separate_part_and_lot(diode_1_full_text)
		diode_1_quantity = build_dict.get("diode_1_chip_count")

		circuit_1_full_text = build_dict.get("circuit_1", "")
		circuit_1_name, circuit_1_lot, circuit_1_extra = su.separate_part_and_lot(circuit_1_full_text)

		filter_1_full_text = build_dict.get("filter_1", "")
		filter_1_name, filter_1_lot, filter_1_extra = su.separate_part_and_lot(filter_1_full_text)

		diode_2_full_text = build_dict.get("diode_2", "")
		diode_2_name, diode_2_lot, diode_2_extra = su.separate_part_and_lot(diode_2_full_text)
		diode_2_quantity = build_dict.get("diode_2_chip_count")

		circuit_2_full_text = build_dict.get("circuit_2", "")
		circuit_2_name, circuit_2_lot, circuit_2_extra = su.separate_part_and_lot(circuit_2_full_text)

		filter_2_full_text = build_dict.get("filter_2", "")
		filter_2_name, filter_2_lot, filter_2_extra = su.separate_part_and_lot(filter_2_full_text)

		pcb_full_text = build_dict.get("pcb_info", "")
		pcb_name, pcb_lot, pcb_extra = su.separate_part_and_lot(pcb_full_text)

		mmic_name = build_dict.get("mmic_name", "")
		mmic_lot = build_dict.get("mmic_lot", "")


		part_rows = [
			{"part_name": diode_1_name, "quantity": diode_1_quantity, "part_type": "DIODE", "part_lot": diode_1_lot},
			{"part_name": circuit_1_name, "quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_1_lot},
			{"part_name": diode_2_name, "quantity": diode_2_quantity, "part_type": "DIODE", "part_lot": diode_2_lot},
			{"part_name": circuit_2_name, "quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_2_lot},
			{"part_name": pcb_name, "quantity": 1, "part_type": "PCB", "part_lot": pcb_lot},
			{"part_name": filter_1_name, "quantity": 1, "part_type": "FILTER", "part_lot": filter_1_lot},
			{"part_name": filter_2_name, "quantity": 1, "part_type": "FILTER", "part_lot": filter_2_lot},
			{"part_name": mmic_name, "quantity": 1, "part_type": "MMIC", "part_lot": mmic_lot}
		]

		for part in part_rows[:]:
			part_name_without_whitespace = re.sub(r"\s+", "", part["part_name"]).lower()
			if (part_name_without_whitespace == "" or part_name_without_whitespace == "na" or part_name_without_whitespace == "n/a"):
				part_rows.remove(part)

		note_rows = []
		for note in build_dict.get("notes", []):
			note_rows.append({"note": note, "type": Note_Type.GENERIC})
		note_rows.append({"note": build_dict.get("vbr", ""), "type": Note_Type.GENERIC})
		note_rows.append({"note": build_dict.get("indium_info", ""), "type": Note_Type.GENERIC})

		for note in note_rows[:]:
			if not note:
				note_rows.remove(note)
				continue

			note_without_whitespace = re.sub(r"\s+", "", note["note"]).lower()
			if (note_without_whitespace == "" or note_without_whitespace == "na" or note_without_whitespace == "n/a"):
				note_rows.remove(note)

		return render_template("partials/block-forms/build-file-population-response.html", block=build_dict, parts=part_rows, notes=note_rows, populated_build_name=build_dict["full_build_name"])

	return "No file uploaded", 204