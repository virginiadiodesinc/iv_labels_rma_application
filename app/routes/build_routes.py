from flask import Blueprint, request, render_template

build_bp = Blueprint("build", __name__)

@build_bp.post("/check_custom_lot/")
def check_custom_lot():
	"""Adds a custom lot field if the lot dropdown select is the Unknown option
	
	This function adds a custom lot input field via a custom-lot-input partial. If the normal lot dropdown
	is N/A or one of the JB2 queried lots, this field doesn't exist. If the lot dropdown choice is custom,
	this custom lot field will appear and be used for all other functions

	@return custom-lot-input.html Return value of type (template partial)
	"""
	selected_lot = request.form.get("lot-select")
	print(selected_lot)
	return render_template("partials/build-page/custom-lot-input.html", selected_lot=selected_lot)

@build_bp.get("/clear_block_info/")
def clear_block_info():
	"""Clears the current block info
	
	This function clears/empties the current block info.

	@return block-forms-container.html Return value of type (template partial)
	"""
	return render_template("partials/block-forms/block-forms-container.html")

@build_bp.get("/clear_build_parts")
def clear_build_parts():
	"""Clears the current list of parts in a build

	This function clears/empties the current list of parts making up the true BOM for a build.

	@return clear-build-parts-response Return value of type (template partial)
	"""
	return render_template("partials/block-forms/clear-build-parts-response.html", parts=[], notes=[])

@build_bp.get("/add_empty_part_row/")
def add_empty_part_row():
	"""Adds an empty part row to build part list

	This function adds an empty part row to the build part list

	@return part-row Return value of type (template partial)	
	"""
	return render_template("partials/build-page/part-row.html", part=None)

@build_bp.get("/add_empty_note_row/")
def add_empty_note_row():
	"""Adds an empty note row to build part list

	This function adds an empty note row to the build note list

	@return note-row Return value of type (template partial)	
	"""
	return render_template("partials/build-page/note-row.html", note=None)

@build_bp.post("/add_part_rows_from_bom_list/")
def add_part_rows_from_bom():
	"""Adds all selected rows from JB2-queried BOM to build part list
	
	This function adds all selected rows from the BOM lookup (selected by checkboxes)
	to the build part list

	@return rows Return value of type (string of multiple template partials)
	"""
	indices = request.form.getlist("bom-part-check")
	rows = []

	for index in indices:
		part_name = request.form.get(f"bom_part_name_{index}")
		part_quantity = request.form.get(f"bom_part_quantity_{index}")
		part_type = request.form.get(f"bom_part_type_{index}")
		rows.append(
			render_template("partials/build-page/part-row.html", part={"part_name": part_name, "quantity": part_quantity, "part_type": part_type, "part_lot": ""})
		)

	return "".join(rows)

@build_bp.post("/import_diode_info_from_iv/")
def import_diode_info_from_iv():
	all_diode_info = request.form
	temperature = all_diode_info.get("temperature")
	if temperature:
		temperature = round(float(temperature), 2)
	reverse_voltage = all_diode_info.get("reverse-voltage")
	if reverse_voltage:
		reverse_voltage = round(float(reverse_voltage), 2)
	return render_template("partials/build-page/diode-row.html", temperature=temperature, reverse_voltage=reverse_voltage)

@build_bp.post("/add_iv_assembly_to_build_parts/")
def add_iv_assembly_to_build_parts():
	iv_assembly_info = request.form
	parts_list = iv_assembly_info.getlist("part")
	lots_list = iv_assembly_info.getlist("lot-select")
	custom_lots_list = iv_assembly_info.getlist("custom-lot-input")

	custom_index = 0
	for index, lot in enumerate(lots_list):
		if lot == "Other":
			lots_list[index] = custom_lots_list[custom_index]
			custom_index += 1

	diode_name = parts_list[0]
	diode_lot = lots_list[0]

	circuit_name = parts_list[1]
	circuit_lot = lots_list[1]

	diode = {"part_name": diode_name, "quantity": 1, "part_type": "DIODE", "part_lot": diode_lot}
	circuit = {"part_name": circuit_name, "quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_lot}


	rows = []
	rows.append(
			render_template("partials/build-page/part-row.html", part=diode)
		)
	rows.append(
			render_template("partials/build-page/part-row.html", part=circuit)
		)
	return "".join(rows)
	