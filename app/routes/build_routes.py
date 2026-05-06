from flask import Blueprint, request, render_template

build_bp = Blueprint("build", __name__)

@build_bp.post("/check_custom_lot/")
def check_custom_lot():
	selected_lot = request.form.get("lot-select")
	
	return render_template("partials/build-page/custom-lot-input.html", selected_lot=selected_lot)

@build_bp.get("/clear_build_parts")
def clear_build_parts():
	return render_template("partials/block-forms/clear-build-parts-response.html", items=[], notes=[])

@build_bp.get("/add_empty_part_row/")
def add_empty_part_row():
	return render_template("partials/build-page/part-row.html", part=None)

@build_bp.get("/add_empty_note_row/")
def add_empty_note_row():
	return render_template("partials/build-page/note-row.html", note=None)

@build_bp.post("/add_part_rows_from_bom_list/")
def add_part_rows_from_bom():
	indices = request.form.getlist("bom-part-check")
	rows = []

	for index in indices:
		part_name = request.form.get(f"bom_part_name_{index}")
		part_quantity = request.form.get(f"bom_part_quantity_{index}")
		part_type = request.form.get(f"bom_part_type_{index}")
		rows.append(
			render_template("partials/build-page/part-row.html", part={"part_name": part_name, "part_quantity": part_quantity, "part_type": part_type, "part_lot": ""})
		)
	return "".join(rows)