from flask import Blueprint, request, render_template
from app.db import JB2_queries as jb2

jb2_bp = Blueprint("jb2", __name__)

@jb2_bp.get("/search_jb2_components/")
def search_jb2_components():
	component_name = request.args.get("component-name")
	results = jb2.get_Build_Name_List(component_name)
	
	return render_template("partials/search/bom-suggestion-results.html", search_results=results)

@jb2_bp.get("/get_jb2_bom_from_build_name/")
def get_jb2_bom_from_build_name():
	build_name = request.args.get("component-name")
	parts = jb2.get_BOM(build_name)
	sub_parts = []

	for part in parts:
		if part["part_type"] == "COMPONENT":
			parts.remove(part)
			sub_part = {
				"name": part["part_name"],
				"sub_parts": jb2.get_BOM(part["part_name"])
			}
			sub_parts.append(sub_part)
		if part["part_type"] == "BLOCK":
			parts.remove(part)

	for sub_part_entry in sub_parts:
		for sub_part in sub_part_entry["sub_parts"]:
			if sub_part["part_type"] == "BLOCK":
				sub_part_entry["sub_parts"].remove(sub_part)

	for index, sub_part in enumerate(sub_parts):
		sub_part["starting_index"] = len(parts)
		if (index > 0):
			sub_part["starting_index"] += len(sub_parts[index-1]["sub_parts"])

	return render_template("partials/build-page/bom-list.html", build_name=build_name, bom_parts=parts, sub_parts=sub_parts)

@jb2_bp.get("/search_part_lots/")
def search_part_lots():
	part = request.args.get("part")
	lot_list = jb2.get_Lots(part)

	return render_template("partials/build-page/lot-input.html", lot_list=lot_list)