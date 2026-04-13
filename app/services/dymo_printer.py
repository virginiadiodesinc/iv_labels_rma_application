import os
from typing import Callable, Optional
from win32com.client import Dispatch
import pythoncom
import xml.etree.ElementTree as ET
import copy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINTER_NAME = "DYMO LabelWriter 450 Turbo"

def print_engine(label_name: str, label_field_populator: callable, form_data: dict, label_preparer: Optional[Callable] = None):
	label_path = os.path.join(BASE_DIR, "labels", label_name)

	if label_preparer:
		label_path = label_preparer(label_path, form_data)

	pythoncom.CoInitialize()
	try:
		label_com = Dispatch('Dymo.DymoAddIn')
		label_text = Dispatch('Dymo.DymoLabels')

		if not label_com.Open(label_path):
			raise FileNotFoundError(f"Label file not found: {label_path}")

		label_com.SelectPrinter(PRINTER_NAME)

		label_text = label_field_populator(label_text, form_data)

		label_com.StartPrintJob()
		label_com.Print(1, False)
		label_com.EndPrintJob()
	
	finally:
		pythoncom.CoUninitialize()

def populate_inspection_label_fields(label_text, form_data: dict):
	# inspection-block-engraving: WR6.5R10
	# inspection-block-serial-number: 3-01
	# inspection-date: 10/21/2025
	# inspection-initials: BKB
	label_text.SetField('BLOCK_ENGRAVING_INPUT', form_data.get("block-engraving-input", ""))
	label_text.SetField('BLOCK_SN_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BLOCK_DATE_INPUT', form_data.get("inspection-date-input", ""))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("inspection-initials-input", ""))

	return label_text

def populate_pb1_label_fields(label_text, form_data: dict):
	# pb1-build-name: VDI6.5SHM_R10
	# pb1-block-serial-number: 3-01
	# pb1-date: 10/22/2025
	# pb1-initials: BKB
	label_text.SetField('BUILD_NAME_INPUT', form_data.get("pb1-build-name-input", ""))
	label_text.SetField('BLOCK_SN_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BLOCK_DATE_INPUT', form_data.get("pb1-date-input", ""))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("pb1-initials-input", ""))

	return label_text

def populate_pb2_label_fields(label_text, form_data: dict):
	# pb2-build-name: VDI6.5SHM_R10
	# pb2-block-serial-number: 3-01
	# pb2-date: 10/23/2025
	# pb2-initials: BKB
	# pb2-pass-fail: PASS
	# pb2-bond-wire-pads: 10
	# pb2-components: 5
	# pb2-inspector: ELT
	label_text.SetField('BUILD_NAME_INPUT', form_data.get("pb2-build-name-input", ""))
	label_text.SetField('BLOCK_SN_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BLOCK_DATE_INPUT', form_data.get("pb2-date-input", ""))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("pb2-initials-input", ""))
	label_text.SetField('PASS_FAIL_INPUT', form_data.get("pb2-pass-fail-input", ""))
	label_text.SetField('BOND_WIRE_PADS_INPUT', form_data.get("pb2-bond-pads-count-input", ""))
	label_text.SetField('COMPONENTS_INPUT', form_data.get("pb2-components-count-input", ""))
	label_text.SetField('INSPECTOR_INPUT', form_data.get("pb2-inspector-initials-input", ""))

	return label_text

def populate_full_build_label_fields(label_text, form_data: dict):
	parts = form_data.getlist("part")
	lots  = form_data.getlist("lot-select")
	custom_lots = form_data.getlist("custom-lot-input")
	notes = form_data.getlist("note")

	for index, lot in enumerate(lots):
		custom_index = 0
		if lot == "Other":
			lots[index] = custom_lots[custom_index]
			custom_index += 1

	part_rows = [{"part": p, "lot": l} for p, l in zip(parts, lots)]

	label_text.SetField('BUILD_NAME_INPUT', form_data.get("full-build-name-input", ""))
	label_text.SetField('BLOCK_SERIAL_NUMBER_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))

	for i in range(len(part_rows)):
		label_text.SetField(f'ROW_{i}_PART_INPUT', part_rows[i]['part'])
		label_text.SetField(f'ROW_{i}_LOT_INPUT', part_rows[i]['lot'])

	for i in range(len(notes)):
		label_text.SetField(f'NOTE_ROW_{i}_INPUT', notes[i])

	return label_text

def prepare_full_build_label(label_path: str, form_data: dict):

	parts = form_data.getlist("part")
	notes = form_data.getlist("note")

	part_row_count = len(parts)
	note_row_count = len(notes)
	
	with open(label_path, "r", encoding="utf-8") as f:
		label_xml = f.read()

	xml_tree = ET.fromstring(label_xml)

	# distance between rows is 187.2?
	# 14.4 per .1 inch?
	# 187.2 / 14.4 = 13
	starting_row_y = 374.4  # Y position of the first row
	row_spacing = 187.2	# Spacing between rows
	for i in range(part_row_count):
		for obj_info in xml_tree.findall(".//ObjectInfo"):	
			text_obj = obj_info.find("TextObject")
			if text_obj is not None and text_obj.find("Name").text.startswith("ROW_TEMPLATE_"):
				clone = copy.deepcopy(obj_info)
				
				# calculate new Y
				bounds = clone.find("Bounds")
				bounds.set("Y", str(starting_row_y + i * row_spacing))

				# rename object
				name_node = clone.find("TextObject/Name")
				base_name = name_node.text.replace("ROW_TEMPLATE_", "")
				name_node.text = f"ROW_{i}_{base_name}"

				# append cloned row
				xml_tree.append(clone)

	for i in range(note_row_count):
		for obj_info in xml_tree.findall(".//ObjectInfo"):	
			text_obj = obj_info.find("TextObject")
			if text_obj is not None and text_obj.find("Name").text.startswith("NOTE_TEMPLATE_"):
				clone = copy.deepcopy(obj_info)
				
				# calculate new Y
				bounds = clone.find("Bounds")
				bounds.set("Y", str(starting_row_y + (i + part_row_count) * row_spacing))

				# rename object
				name_node = clone.find("TextObject/Name")
				base_name = name_node.text.replace("NOTE_TEMPLATE_", "")
				name_node.text = f"NOTE_ROW_{i}_{base_name}"

				# append cloned row
				xml_tree.append(clone)

	for obj_info in xml_tree.findall(".//ObjectInfo"):
		text_obj = obj_info.find("TextObject")
		if text_obj is not None and (text_obj.find("Name").text.startswith("ROW_TEMPLATE_") or text_obj.find("Name").text.startswith("NOTE_TEMPLATE_")):
			xml_tree.remove(obj_info)

	temp_label_path = label_path.replace(".label", "_temp.label")
	new_xml = ET.tostring(xml_tree, encoding="unicode")
	with open(temp_label_path, "w", encoding="utf-8") as f:
		f.write(new_xml)

	return temp_label_path