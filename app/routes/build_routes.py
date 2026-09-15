from flask import Blueprint, request, render_template
from app.services import parts_service

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
	iv_parts_list = parts_service.parts_from_form(request.form)

	iv_form_fields = {
				"temperature": "temperature",
				"reverse-voltage": "reverse_breakdown_voltage",
				}
	diode_info = iv_parts_list[0]


	for iv_field, part_field in iv_form_fields.items():
		diode_info[part_field] = request.form.get(iv_field)
		if diode_info[part_field] and diode_info[part_field].isnumeric():
			diode_info[part_field] = round(diode_info[part_field], 2)

	print("D", diode_info)

	return render_template("partials/build-page/diode-row.html", part=diode_info)


@build_bp.post("/add_iv_assembly_to_build_parts/")
def add_iv_assembly_to_build_parts():
	iv_parts_list = parts_service.parts_from_form(request.form)

	iv_form_fields = {
					"temperature": "temperature",
					"reverse-voltage": "reverse_breakdown_voltage",
					}

	diode_info = iv_parts_list[0]
	diode_info["part_type"] = "DIODE"
	diode_info["quantity"] = 1
	
	circuit_info = iv_parts_list[1]
	circuit_info["part_type"] = "CIRCUIT"
	circuit_info["quantity"] = 1
	circuit_info["subassembly_tag"] = diode_info["subassembly_tag"]

	for iv_field, part_field in iv_form_fields.items():
		diode_info[part_field] = request.form.get(iv_field)
		if diode_info[part_field] and diode_info[part_field].isnumeric():
			diode_info[part_field] = round(diode_info[part_field], 2)

	print("C", circuit_info)
	print("D", diode_info)

	rows = []
	rows.append(
			render_template("partials/build-page/part-row.html", part=diode_info)
		)
	rows.append(
			render_template("partials/build-page/part-row.html", part=circuit_info)
		)
	return "".join(rows)


@build_bp.post("/import_block_identifiers_to_iv/")
def import_block_identifiers_to_iv():
	block_build_identifiers = request.form

	print(block_build_identifiers)

	iv_data = {
		"block_name": block_build_identifiers.get("block-engraving-input", ""),
		"build_sn": block_build_identifiers.get("block-serial-number-input", ""),
		"build_revision": block_build_identifiers.get("block-revision-input", ""),
		"build_name": block_build_identifiers.get("full-build-name-input", ""),
	}

	return render_template("partials/iv-page/block-identifier-to-iv-side-import.html", iv_data=iv_data)


@build_bp.post("/import_iv_identifiers_to_block/")
def import_iv_identifiers_to_block():
	iv_block_identifiers = request.form

	block = {
		"block_engraving": iv_block_identifiers.get("iv-block-engraving", ""),
		"block_serial_number": iv_block_identifiers.get("iv-block-sn", ""),
		"block_revision": iv_block_identifiers.get("iv-block-revision", ""),
	}

	return render_template("partials/block-forms/iv-identifier-to-block-side-import.html", block=block)
