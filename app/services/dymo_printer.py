import os
from typing import Callable, Optional
from win32com.client import Dispatch
import pythoncom
import xml.etree.ElementTree as ET
import copy
from app.services import date_converter as dc
from pathlib import Path
from app.services import string_utilities as su

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINTER_NAME = "DYMO LabelWriter 450 Turbo"

# ---------------------------------------------------------------------------
# Layout configuration per full-build template.
#
# max_slots_first_page / max_slots_continuation_page and input_y_offset are
# TODOs: measure them by test-printing, they are not derived from anything
# here. continuation_label must exist on disk (a copy of the base template
# with the header block removed) before multi-page builds will work.
# ---------------------------------------------------------------------------
FULL_BUILD_LAYOUTS = {
	"full_build_225.label": {
		"continuation_label": "full_build_225_continued.label",
		"starting_row_y": 720,
		"space_between_rows": 225,
		"max_slots_first_page": 13,
		"max_slots_continuation_page": 11,
		"input_y_offset": 0,
	},
	"full_build_270.label": {
		"continuation_label": "full_build_270_continued.label",
		"starting_row_y_first": 720,
		"starting_row_y_continued": 450,
		"space_between_rows": 270,
		"max_slots_first_page": 9,
		"max_slots_continuation_page": 10,
		"input_y_offset": -20,
	},
}

MULTI_LINE_PART_TYPES = {"DIODE", "PCB"}
LIMITED_CHARACTER_FIELDS = {"INDIUM_INPUT": 18, "NOTE_INPUT": 53, "PCB_MODIFICATIONS_INPUT": 53}
PART_TYPES_WITH_LOTS = {"DIODE", "PCB", "MMIC"}
NON_PRINTED_PART_TYPES = {"BCMESH", "CONNECTOR", "MA PARTS", "MISC", "SP OTHER", "CABLE", "FILTER", "INVENTORY", "PMP"}


def limit_input_characters(input_string, character_limit):
	if len(input_string) > character_limit:
		input_string =  input_string[0:(character_limit - 3)] + "..."
	return input_string


def print_engine(label_name: str, label_field_populator: callable, form_data: dict, label_preparer: Optional[Callable] = None):
	"""Wrapper function for the various print calls

	This function acts as the setup, teardown, and facilitator for the other print calls.
	It sets up the connection, calls the appropriate populator and preparation function for the labels, and closes down the connection.

	A label_preparer may return either a single path (single-label jobs, unchanged
	behavior) or a list of (label_path, page_data) tuples for jobs that spill onto
	multiple physical labels. Each entry is printed as its own job.

	@param label_name the file name of the appropriate label (string)
	@param label_field_populator the populator function for the label (callable)
	@param form_data the data from the input forms that are to be put into the label (dict)
	@param label_preparer an optional additional label preparer function for full build labels, default None (callable)
	@return None Return value of type (None)
	"""
	label_path = os.path.join(BASE_DIR, "labels", label_name)

	if label_preparer:
		prepared = label_preparer(label_path, form_data)
	else:
		prepared = [(label_path, form_data)]

	# Back-compat: a preparer that still returns a bare path string.
	if isinstance(prepared, str):
		prepared = [(prepared, form_data)]

	pythoncom.CoInitialize()
	try:
		for page_path, page_data in prepared:
			label_com = Dispatch('Dymo.DymoAddIn')
			label_text = Dispatch('Dymo.DymoLabels')

			if not label_com.Open(page_path):
				raise FileNotFoundError(f"Label file not found: {page_path}")

			label_com.SelectPrinter(PRINTER_NAME)

			label_text = label_field_populator(label_text, page_data)

			label_com.StartPrintJob()
			label_com.Print(1, False)
			label_com.EndPrintJob()

	finally:
		label_directory = Path(os.path.join(BASE_DIR, "labels"))
		all_temp_labels = list(label_directory.glob("*temp*.label"))
		
		# for temp_path in all_temp_labels:
		# 	temp_path.unlink()

		pythoncom.CoUninitialize()


def populate_inspection_label_fields(label_text, form_data: dict):
	"""Populates the inspection label

	This function populates specifically the inspection label

	@param label_text the XML object to be modified (string?)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return label_text Return value of type (string)
	"""
	label_text.SetField('BLOCK_ENGRAVING_INPUT', form_data.get("block-engraving-input", ""))
	label_text.SetField('BLOCK_SN_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BLOCK_DATE_INPUT', dc.iso_date_to_labview(form_data.get("inspection-date-input", "")))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("inspection-initials-input", ""))

	return label_text


def populate_pb1_label_fields(label_text, form_data: dict):
	"""Populates the pb1 label

	This function populates specifically the inspection label

	@param label_text the XML object to be modified (string?)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return label_text Return value of type (string)
	"""
	label_text.SetField('BUILD_NAME_INPUT', form_data.get("pb1-build-name-input", ""))
	label_text.SetField('BLOCK_SN_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BLOCK_DATE_INPUT', dc.iso_date_to_labview(form_data.get("pb1-date-input", "")))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("pb1-initials-input", ""))

	return label_text


def populate_pb2_label_fields(label_text, form_data: dict):
	"""Populates the pb2 label

	This function populates specifically the inspection label

	@param label_text the XML object to be modified (string?)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return label_text Return value of type (string)
	"""
	label_text.SetField('BUILD_NAME_INPUT', form_data.get("pb2-build-name-input", ""))
	label_text.SetField('BLOCK_SN_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BLOCK_DATE_INPUT', dc.iso_date_to_labview(form_data.get("pb2-date-input", "")))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("pb2-initials-input", ""))
	label_text.SetField('INSPECTOR_INPUT', form_data.get("pb2-inspection-initials-input", ""))

	return label_text


# ---------------------------------------------------------------------------
# Full build label: shared parsing so prepare() and populate() can never
# disagree about what a "row" is.
# ---------------------------------------------------------------------------

def _parse_full_build_rows(form_data: dict):
	"""Parses the full-build form into a header dict plus an ordered list of
	row dicts, each tagged with a 'slots' cost (1 normally, 2 for DIODE/PCB
	parts, which get a second line).

	@param form_data the raw form submission (dict-like, supports .getlist)
	@return (header, rows) header is a dict of the fixed fields; rows is the
			ordered list of part rows followed by note rows
	"""
	parts = form_data.getlist("part")
	lots = form_data.getlist("lot-select")
	custom_lots = form_data.getlist("custom-lot-input")
	part_types = form_data.getlist("part_type")
	quantities = form_data.getlist("quantity")

	reverse_voltages = form_data.getlist("diode-row-reverse-voltage-input")
	temperatures = form_data.getlist("diode-row-temperature-input")
	indium_list = form_data.getlist("diode-row-indium-input")

	pcb_modifications = form_data.getlist("pcb-modifications-input")

	notes = form_data.getlist("note")
	note_types = form_data.getlist("note_type")

	resolved_lots = []
	custom_index = 0
	for lot in lots:
		if lot == "Other":
			resolved_lots.append(custom_lots[custom_index])
			custom_index += 1
		else:
			resolved_lots.append(lot)

	rows = []
	diode_index = 0
	pcb_index = 0
	for part, lot, part_type, quantity in zip(parts, resolved_lots, part_types, quantities):
		if part_type in NON_PRINTED_PART_TYPES:
			continue

		row = {"kind": "part", "part": part, "lot": lot, "type": part_type, "quantity": quantity, "slots": 1}

		if part_type == "DIODE":
			row["reverse_voltage"] = reverse_voltages[diode_index]
			row["temperature"] = temperatures[diode_index]
			row["indium"] = indium_list[diode_index]
			row["slots"] = 2
			diode_index += 1

		elif part_type == "PCB":
			row["modifications"] = pcb_modifications[pcb_index]
			row["slots"] = 2
			pcb_index += 1

		rows.append(row)

	for note, note_type in zip(notes, note_types):
		rows.append({"kind": "note", "note": note, "type": note_type, "slots": 1})

	lv_style_build_name = su.get_build_name_with_suffix(form_data.get("full-build-name-input"), form_data.get("block-engraving-input"))
	lv_style_block_serial_number = form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", "")
	lv_style_build_name_with_sn_and_rev = lv_style_build_name + " " + lv_style_block_serial_number

	header = {
		"build_name": lv_style_build_name_with_sn_and_rev,
		"build_date": dc.iso_date_to_labview(form_data.get("full-build-date-input", "")),
		"build_initials": form_data.get("full-build-initials-input", ""),
	}

	return header, rows


def _paginate_rows(rows, max_slots_first_page, max_slots_continuation_page):
	"""Packs rows into pages of slots, never splitting a multi-slot row
	across two pages.

	@param rows ordered list of row dicts, each with a 'slots' key
	@param max_slots_first_page slot budget of the first (headered) page
	@param max_slots_continuation_page slot budget of every following page
	@return list of pages, each a list of row dicts
	"""
	pages = []
	current_page = []
	current_slots = 0
	budget = max_slots_first_page

	for row in rows:
		if current_page and current_slots + row["slots"] > budget:
			pages.append(current_page)
			current_page = []
			current_slots = 0
			budget = max_slots_continuation_page

		current_page.append(row)
		current_slots += row["slots"]

	if current_page:
		pages.append(current_page)

	return pages


def _clone_template_rows(xml_tree, template_prefix, new_prefix, base_y, input_y_offset):
	"""Clones every ObjectInfo whose TextObject name starts with
	template_prefix, repositions it at base_y, and renames it under
	new_prefix. INPUT objects get nudged by input_y_offset so their text
	(which often contains literal underscores in part numbers) clears the
	underline row instead of blending into it.

	@param xml_tree the ElementTree root being built up
	@param template_prefix name prefix identifying the source template objects
	@param new_prefix name prefix to give the cloned objects
	@param base_y the Y position (twips) for this row's line
	@param input_y_offset additional Y nudge applied only to *_INPUT objects
	@return None
	"""
	for obj_info in xml_tree.findall(".//ObjectInfo"):
		text_obj = obj_info.find("TextObject")
		if text_obj is None:
			continue
		name = text_obj.find("Name").text
		if not name.startswith(template_prefix):
			continue

		clone = copy.deepcopy(obj_info)
		bounds = clone.find("Bounds")
		y = base_y + input_y_offset if name.endswith("_INPUT") else base_y
		bounds.set("Y", str(y))

		name_node = clone.find("TextObject/Name")
		base_name = name.replace(template_prefix, "")
		name_node.text = f"{new_prefix}{base_name}"

		xml_tree.append(clone)


def _strip_template_objects(xml_tree, template_prefixes):
	"""Removes every ObjectInfo whose TextObject name starts with any of the
	given prefixes. Run once all clones for a page have been made.

	@param xml_tree the ElementTree root being built up
	@param template_prefixes iterable of name prefixes to strip
	@return None
	"""
	for obj_info in xml_tree.findall(".//ObjectInfo"):
		text_obj = obj_info.find("TextObject")
		if text_obj is None:
			continue
		name = text_obj.find("Name").text
		if any(name.startswith(prefix) for prefix in template_prefixes):
			xml_tree.remove(obj_info)


def _render_page(template_path, page_rows, layout, page_suffix):
	"""Builds one physical label's XML: clones a row/second-line/note object
	for each row on this page, then strips the leftover template objects.

	@param template_path path to the base .label file for this page
	@param page_rows the rows (part/note dicts) assigned to this page
	@param layout the FULL_BUILD_LAYOUTS entry for this label family
	@param page_suffix string used to make the temp file name unique
	@return path to the rendered temp .label file
	"""
	with open(template_path, "r", encoding="utf-8") as f:
		label_xml = f.read()

	xml_tree = ET.fromstring(label_xml)

	
	if "continued" in template_path:
		starting_row_y = layout["starting_row_y_continued"]
	else:
		starting_row_y = layout["starting_row_y_first"]
	space_between_rows = layout["space_between_rows"]
	input_y_offset = layout["input_y_offset"]

	slot = 0
	part_index = 0
	note_index = 0
	for row in page_rows:
		row_y = starting_row_y + slot * space_between_rows

		if row["kind"] == "part":
			_clone_template_rows(xml_tree, "ROW_TEMPLATE_", f"ROW_{part_index}_", row_y, input_y_offset)
			if row["type"] == "DIODE":
				_clone_template_rows(
					xml_tree, "DIODE_ROW_TEMPLATE_", f"ROW_{part_index}_DIODE_",
					row_y + space_between_rows, input_y_offset,
				)
			elif row["type"] == "PCB":
				_clone_template_rows(
					xml_tree, "PCB_ROW_TEMPLATE_", f"ROW_{part_index}_PCB_",
					row_y + space_between_rows, input_y_offset,
				)
			if row["type"] not in PART_TYPES_WITH_LOTS:
				_strip_template_objects(xml_tree, [f"ROW_{part_index}_LOT"])

			part_index += 1
		
		else:
			_clone_template_rows(xml_tree, "NOTE_TEMPLATE_", f"NOTE_ROW_{note_index}_", row_y, input_y_offset)
			note_index += 1

		slot += row["slots"]

	_strip_template_objects(
		xml_tree,
		("ROW_TEMPLATE_", "NOTE_TEMPLATE_", "DIODE_ROW_TEMPLATE_", "PCB_ROW_TEMPLATE_"),
	)

	temp_label_path = template_path.replace(".label", f"_temp_{page_suffix}.label")
	new_xml = ET.tostring(xml_tree, encoding="unicode")
	with open(temp_label_path, "w", encoding="utf-8") as f:
		f.write(new_xml)

	return temp_label_path


def prepare_full_build_label(label_path: str, form_data: dict):
	"""Prepares the full build label(s)

	Parses the submitted rows, packs them across as many physical labels as
	needed (never splitting a DIODE/PCB row's second line onto a different
	label than its first), and renders one temp .label file per page. The
	first page uses the requested template (with header fields); every
	following page uses that layout's continuation template.

	@param label_path path to the requested base template (e.g. full_build_270.label)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return list of (page_label_path, page_form_data) tuples, one per physical label,
			ready to be handed to print_engine
	"""
	label_dir = os.path.dirname(label_path)
	label_name = os.path.basename(label_path)
	layout = FULL_BUILD_LAYOUTS[label_name]

	header, rows = _parse_full_build_rows(form_data)
	pages = _paginate_rows(rows, layout["max_slots_first_page"], layout["max_slots_continuation_page"])

	prepared = []
	total_pages = len(pages)
	for page_number, page_rows in enumerate(pages, start=1):
		is_first_page = page_number == 1
		template_name = label_name if is_first_page else layout["continuation_label"]
		template_path = os.path.join(label_dir, template_name)

		page_label_path = _render_page(template_path, page_rows, layout, f"page{page_number}")

		only_build_name_header = {"build_name": header["build_name"]}

		page_form_data = {
			"header": header if is_first_page else only_build_name_header,
			"rows": page_rows,
			"page_number": page_number,
			"total_pages": total_pages,
		}
		prepared.append((page_label_path, page_form_data))

	return prepared


def populate_full_build_label_fields(label_text, page_data: dict):
	"""Populates one full build label page

	Fills in the header fields (first page only) and every part/note row
	assigned to this page. Row indices here are local to the page, matching
	the naming _render_page used when cloning objects for that same page.

	@param label_text the XML object to be modified
	@param page_data one entry from prepare_full_build_label's returned list:
		   {"header": dict|None, "rows": [...], "page_number": int, "total_pages": int}
	@return label_text Return value of type (string)
	"""
	header = page_data["header"]
	rows = page_data["rows"]

	if header is not None:
		label_text.SetField('BUILD_NAME_INPUT', header["build_name"])
		if len(header) > 1:
			label_text.SetField('BUILD_DATE_INPUT', header["build_date"])
			label_text.SetField('BUILD_INITIALS_INPUT', header["build_initials"])

	part_index = 0
	note_index = 0
	for row in rows:
		if row["kind"] == "part":
			label_text.SetField(f'ROW_{part_index}_PART_TITLE', row["type"][0:5])
			label_text.SetField(f'ROW_{part_index}_PART_INPUT', row["part"])

			if row["type"] in PART_TYPES_WITH_LOTS:
				label_text.SetField(f'ROW_{part_index}_LOT_INPUT', row["lot"])

			if row["type"] == "DIODE":
				label_text.SetField(f'ROW_{part_index}_DIODE_REVERSE_VOLTAGE_INPUT', row["reverse_voltage"])
				label_text.SetField(f'ROW_{part_index}_DIODE_TEMPERATURE_INPUT', row["temperature"])
				label_text.SetField(f'ROW_{part_index}_DIODE_INDIUM_INPUT', limit_input_characters(row["indium"], LIMITED_CHARACTER_FIELDS["INDIUM_INPUT"]))
				label_text.SetField(f'ROW_{part_index}_DIODE_QUANTITY_INPUT', row["quantity"])
			elif row["type"] == "PCB":
				label_text.SetField(f'ROW_{part_index}_PCB_modification_INPUT', limit_input_characters(row["modifications"], LIMITED_CHARACTER_FIELDS["PCB_MODIFICATIONS_INPUT"]))

			part_index += 1
		else:
			label_text.SetField(f'NOTE_ROW_{note_index}_TITLE', row["type"][0:4])
			label_text.SetField(f'NOTE_ROW_{note_index}_INPUT', limit_input_characters(row["note"], LIMITED_CHARACTER_FIELDS["NOTE_INPUT"]))
			note_index += 1

	return label_text
