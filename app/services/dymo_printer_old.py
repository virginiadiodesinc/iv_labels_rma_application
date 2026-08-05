import os
from typing import Callable, Optional
from win32com.client import Dispatch
import pythoncom
import xml.etree.ElementTree as ET
import copy
from app.services import date_converter as dc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINTER_NAME = "DYMO LabelWriter 450 Turbo"

def print_engine(label_name: str, label_field_populator: callable, form_data: dict, label_preparer: Optional[Callable] = None):
	"""Wrapper function for the various print calls

	This function acts as the setup, teardown, and facilitator for the other print calls. 
	It sets up the connection, calls the appropriate populator and preparation function for the labels, and closes down the connection.

	@param label_name the file name of the appropriate label (string)
	@param label_field_populator the populator function for the label (callable)
	@param form_data the data from the input forms that are to be put into the label (dict)
	@param label_preparer an optional additional label preparer function for full build labels, default None (callable)
	@return None Return value of type (None)	
	"""
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
	"""Populates the inspection label
	
	This function populates specifically the inspection label

	@param label_text the XML object to be modified (string?)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return label_text Return value of type (string)
	"""
	# inspection-block-engraving: WR6.5R10
	# inspection-block-serial-number: 3-01
	# inspection-date: 10/21/2025
	# inspection-initials: BKB
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
	# pb1-build-name: VDI6.5SHM_R10
	# pb1-block-serial-number: 3-01
	# pb1-date: 10/22/2025
	# pb1-initials: BKB
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
	label_text.SetField('BLOCK_DATE_INPUT', dc.iso_date_to_labview(form_data.get("pb2-date-input", "")))
	label_text.SetField('PREBUILD_INIT_INPUT', form_data.get("pb2-initials-input", ""))
	label_text.SetField('INSPECTOR_INPUT', form_data.get("pb2-inspection-initials-input", ""))

	return label_text

def populate_full_build_label_fields(label_text, form_data: dict):
	"""Populates the full build label
	
	This function populates specifically the inspection label

	@param label_text the XML object to be modified (string?)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return label_text Return value of type (string)
	"""

	# BASIC PART FIELDS
	parts = form_data.getlist("part")
	lots  = form_data.getlist("lot-select")
	custom_lots = form_data.getlist("custom-lot-input")
	part_types = form_data.getlist("part_type")

	# EXTRA DIODE FIELDS
	reverse_voltages = form_data.getlist("diode-row-reverse-voltage-input")
	temperatures = form_data.getlist("diode-row-temperature-input")

	# EXTRA PCB FIELDS
	pcb_serial_numbers = form_data.getlist("pcb-sn-input")
	pcb_deviations = form_data.getlist("pcb-deviations-input")

	# BASIC NOTE FIELDS
	notes = form_data.getlist("note")
	note_types = form_data.getlist("note_type")

	for index, lot in enumerate(lots):
		custom_index = 0
		if lot == "Other":
			lots[index] = custom_lots[custom_index]
			custom_index += 1

	part_rows = [{"part": p, "lot": l, "type": t} for p, l, t in zip(parts, lots, part_types)]
	note_rows = [{"note": n, "type": t} for n, t in zip(notes, note_types)]

	diode_index = 0
	pcb_index = 0

	for index, part in enumerate(part_rows):
		if part["type"] == "DIODE":
			part["reverse_voltage"] = reverse_voltages[diode_index]
			part["temperature"] = temperatures[diode_index]
			diode_index = diode_index + 1
		elif part["type"] == "PCB":
			part["serial_number"] = pcb_serial_numbers[pcb_index]
			part["deviations"] = pcb_deviations[pcb_index]
			pcb_index = pcb_index + 1

	print(part_rows)
	print(note_rows)

	label_text.SetField('BUILD_NAME_INPUT', form_data.get("full-build-name-input", ""))
	label_text.SetField('BLOCK_SERIAL_NUMBER_INPUT', form_data.get("block-serial-number-input", "") + form_data.get("block-revision-input", ""))
	label_text.SetField('BUILD_DATE_INPUT', dc.iso_date_to_labview(form_data.get("full-build-date-input", "")))
	label_text.SetField('BUILD_INITIALS_INPUT', form_data.get("full-build-initials-input", ""))

	for i in range(len(part_rows)):
		label_text.SetField(f'ROW_{i}_PART_TITLE', part_rows[i]['type'][0:4])
		label_text.SetField(f'ROW_{i}_PART_INPUT', part_rows[i]['part'])
		label_text.SetField(f'ROW_{i}_LOT_INPUT', part_rows[i]['lot'])

	for i in range(len(note_rows)):
		label_text.SetField(f'NOTE_ROW_{i}_TITLE', notes[i]['type'][0:4])
		label_text.SetField(f'NOTE_ROW_{i}_INPUT', notes[i]['note'])

	return label_text

def prepare_full_build_label(label_path: str, form_data: dict, starting_row_y=630, space_between_rows=225):
	"""Prepares the inspection label
	
	This function prepares the dynamic number fields for the full build label.
	This is the only label which requires this as the other labels have a predetermined number of fields.

	@param label_text the XML object to be modified (string?)
	@param form_data the object containing the input fields to be added to the label (dict)
	@return temp_label_path Return value of type (string)
	"""

	parts = form_data.getlist("part")
	notes = form_data.getlist("note")

	part_row_count = len(parts)
	note_row_count = len(notes)
	
	with open(label_path, "r", encoding="utf-8") as f:
		label_xml = f.read()

	xml_tree = ET.fromstring(label_xml)

	# 14.4 per .01 inch; 1 inch = 1440
	# row text/input fields have a height of 180; 180 / 14.4 = 12.5 units, .125 inches
	# full distance between rows is 270; 270 / 14.4 = 18.75 units, .1875 inches; 90 / 14.4 = extra 6.25 units, .625 inches between rows
	# 720 + row * 270
	# or 225? / .3125 extra inches
	# which would be 630 + row * 225
	
	starting_row_y = 720  # Y position of the first row
	space_between_rows = 270	# Spacing between rows
	for i in range(part_row_count):
		for obj_info in xml_tree.findall(".//ObjectInfo"):	
			text_obj = obj_info.find("TextObject")
			if text_obj is not None and text_obj.find("Name").text.startswith("ROW_TEMPLATE_"):
				clone = copy.deepcopy(obj_info)
				
				# calculate new Y
				bounds = clone.find("Bounds")
				bounds.set("Y", str(starting_row_y + i * space_between_rows))

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
				bounds.set("Y", str(starting_row_y + (i + part_row_count) * space_between_rows))

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