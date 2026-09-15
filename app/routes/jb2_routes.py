from flask import Blueprint, request, render_template
from app.db import JB2_queries as jb2

jb2_bp = Blueprint("jb2", __name__)

@jb2_bp.get("/search_jb2_components/")
def search_jb2_components():
	"""Searches JB2 components (ie built parts)
	
	This function searches JB2 for all built components including the string entered in the BOM search field.
	This is effectively for search suggestions/auto-complete.

	@return bom-suggestion-results Return value of type (template partial)
	"""
	component_name = request.args.get("component-name")
	results = jb2.get_Build_Name_List(component_name)
	
	return render_template("partials/search/bom-suggestion-results.html", search_results=results)

@jb2_bp.get("/get_jb2_bom_from_build_name/")
def get_jb2_bom_from_build_name():
	"""Populates a JB2 BOM from a given build name
	
	This function generates all parts (and sub-parts in case this build has a PB2) for a given component in JB2.
	It will populate a list of all parts in any build and sub-build.

	@return bom-list Return value of type (template partial)
	"""
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
	"""Searches for all existing lots of a given part in JB2
	
	This function searches and lists (in the lot-input dropdown) all lots that exist for a part in JB2.

	@return lot-input Return value of type (template partial)
	"""
	part = request.args.get("part")
	lot = request.args.get("lot", "")
	lot_list = jb2.get_Lots(part)


	return render_template("partials/build-page/lot-input.html", lot_list=lot_list, current_lot=lot)