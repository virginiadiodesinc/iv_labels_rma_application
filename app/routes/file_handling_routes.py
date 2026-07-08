import os
from flask import Blueprint, render_template, request
from app.db.queries import *
from app.services import build_file_converter as build_converter, block_file_converter as block_converter, iv_file_converter as iv_converter
import plotly.express as px
import pandas as pd
from app.services.write_MicroA_files import write_block_file, write_IV_file, write_build_file, write_heat_test_file
from app.services import postprocess as pp
from datetime import datetime
import webview
from app import config
from app.services.date_converter import *
from app.services.process_and_sanitize_entry import *
from app.db import JB2_queries as jb2
import re

file_bp = Blueprint("file", __name__)

iv_file_directory = config.iv_file_directory
block_file_directory = config.block_file_directory
build_file_directory = config.build_file_directory

@file_bp.post("/populate_info_from_block_file/")
def populate_info_from_block_file():
	"""Populates the various input fields with information from a (likely LabView) block file

	This function uses a LabView block file to populate all the block (inspection, PB1, PB2) fields


	@return block-forms-container Return value of type (template partial)
	"""
	uploaded_file_path = request.form.get("block-file-path")

	if uploaded_file_path and uploaded_file_path.endswith(".txt"):
		with open(uploaded_file_path, "r") as block_file:
			block_dict = block_converter.convert_block_file(block_file)

		return render_template("partials/block-forms/block-forms-container.html", block=block_dict)
	return "No file uploaded", 204

@file_bp.post("/populate_info_from_build_file/")
def populate_info_from_build_file():
	"""Populates the various input fields with information from a (likely LabView) build file

	This function uses a LabView build file to populate all the block (inspection, PB1, PB2) as well as build (part/note list) fields

	@return build-file-population-response Return value of type (template partial)
	"""
	uploaded_file_path = request.form.get("build-file-path")

	if uploaded_file_path and uploaded_file_path.endswith(".txt"):
		with open(uploaded_file_path, "r") as build_file:
			build_dict = build_converter.convert_build_file(build_file)

		part_rows = []
		diode_1_split = build_dict.get("diode_1", "").upper().split("_LOT")
		diode_1_name = diode_1_split[0].strip()
		diode_1_quantity = build_dict.get("diode_1_chip_count")
		diode_1_lot = diode_1_split[1].strip() if len(diode_1_split) > 1 else ""
		diode_1_full_name = build_dict.get("diode_1", "").upper()

		circuit_1_split = build_dict.get("circuit_1", "").upper().split("_LOT")
		circuit_1_name = circuit_1_split[0].strip()
		circuit_1_lot = circuit_1_split[1].strip() if len(circuit_1_split) > 1 else ""
		circuit_1_full_name = build_dict.get("circuit_1", "").upper()


		diode_2_split = build_dict.get("diode_2", "").upper().split("_LOT")
		diode_2_name = diode_2_split[0].strip()
		diode_2_quantity = build_dict.get("diode_2_chip_count")
		diode_2_lot = diode_2_split[1].strip() if len(diode_2_split) > 1 else ""
		diode_2_full_name = build_dict.get("diode_2", "").upper()

		circuit_2_split = build_dict.get("circuit_2", "").upper().split("_LOT")
		circuit_2_name = circuit_2_split[0].strip()
		circuit_2_lot = circuit_2_split[1].strip() if len(circuit_2_split) > 1 else ""
		circuit_2_full_name = build_dict.get("circuit_2", "").upper()

		pcb_info_split = build_dict.get("pcb_info", "").upper().split("_LOT")
		pcb_info_name = pcb_info_split[0].strip()
		pcb_info_lot = pcb_info_split[1].strip() if len(pcb_info_split) > 1 else ""
		pcb_info_full_name = build_dict.get("pcb_info", "").upper()

		filter_1_split = build_dict.get("filter_1", "").upper().split("_LOT")
		filter_1_name = filter_1_split[0].strip()
		filter_1_lot = filter_1_split[1].strip() if len(filter_1_split) > 1 else ""
		filter_1_full_name = build_dict.get("filter_1", "").upper()

		filter_2_split = build_dict.get("filter_2", "").upper().split("_LOT")
		filter_2_name = filter_2_split[0].strip()
		filter_2_lot = filter_2_split[1].strip() if len(filter_2_split) > 1 else ""
		filter_2_full_name = build_dict.get("filter_2", "").upper()

		mmic_name = build_dict.get("mmic_name", "")
		mmic_lot = build_dict.get("mmic_lot", "")


		part_rows = [
			{"part_name": diode_1_full_name, "part_quantity": diode_1_quantity, "part_type": "DIODE", "part_lot": diode_1_lot},
			{"part_name": circuit_1_full_name, "part_quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_1_lot},
			{"part_name": diode_2_full_name, "part_quantity": diode_2_quantity, "part_type": "DIODE", "part_lot": diode_2_lot},
			{"part_name": circuit_2_full_name, "part_quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_2_lot},
			{"part_name": pcb_info_full_name, "part_quantity": 1, "part_type": "PCB", "part_lot": pcb_info_lot},
			{"part_name": filter_1_full_name, "part_quantity": 1, "part_type": "FILTER", "part_lot": filter_1_lot},
			{"part_name": filter_2_full_name, "part_quantity": 1, "part_type": "FILTER", "part_lot": filter_2_lot},
			{"part_name": mmic_name, "part_quantity": 1, "part_type": "MMIC", "part_lot": mmic_lot}
		]

		note_rows = []
		for note in build_dict.get("notes", []):
			note_rows.append({"text": note, "note_type": "GENERIC"})
		note_rows.append({"text": build_dict.get("vbr", ""), "note_type": "GENERIC"})
		note_rows.append({"text": build_dict.get("indium_info"), "note_type": "INDIUM"})

		PART_TYPE_ORDER = ["MMIC", "DIODE", "CIRCUIT", "PCB", "FILTER", "NA", "MISC", "CONNECTOR"]
		part_rows.sort(key=lambda p: PART_TYPE_ORDER.index(p["part_type"]) if p["part_type"] in PART_TYPE_ORDER else 99)

		NOTE_TYPE_ORDER = ["REWORK_SUMMARY", "CURRENT_TEST", "PCB_DEVIATIONS", "INDIUM", "TEMPERATURE", "GENERIC"]
		note_rows.sort(key=lambda p: NOTE_TYPE_ORDER.index(p["note_type"]) if p["note_type"] in NOTE_TYPE_ORDER else 99)

		return render_template("partials/block-forms/build-file-population-response.html", block=build_dict, parts=part_rows, notes=note_rows, populated_build_name=build_dict["full_build_name"])

	return "No file uploaded", 204

@file_bp.post("/populate_info_from_iv_file/")
def populate_info_from_iv_file():
	"""Populates the various input fields with information from a (likely LabView) IV file

	This function uses a LabView IV file to populate all the various related fields (graph, numbers, assembly info)

	@return iv-file-population-response Return value of type (template partial)
	"""

	uploaded_file_path = request.form.get("iv-file-path")
	if uploaded_file_path and uploaded_file_path.endswith(".iv"):
		with open(uploaded_file_path, "r") as iv_file:
			iv_dict = iv_converter.convert_iv_file(iv_file)

		source_values = [float(value) for value in iv_dict["current"]]
		voltage_values_tuples = zip([float(value) for value in iv_dict["voltage_up"]], [float(value) for value in iv_dict["voltage_down"]])
		average_voltage_values = [(float(up) + float(down)) / 2 for up, down in voltage_values_tuples]
		average_voltage_values = [float(value) / 1000.0 for value in average_voltage_values]

		# source_values = [float(value) * 1e6 for value in source_values] # convert to microamps
		# voltage_values = [float(value) * 1e-3 for value in voltage_values] # convert to millivolts
		df = pd.DataFrame({
			"Current (uA)": source_values,
			"Voltage (V)": average_voltage_values
		})

		fig = px.scatter(df, x="Voltage (V)", y="Current (uA)", labels={"x": "Voltage (V)", "y": "Current (uA)"}, title=None, log_x = False, log_y=True)
		fig.update_traces(mode='lines+markers')

		# if abs(df["Voltage (mV)"].astype(float).max() - df["Voltage (mV)"].astype(float).min()) < 100:
		# 	fig.update_xaxes(range=[df["Voltage (mV)"].astype(float).min() - 25, df["Voltage (mV)"].astype(float).min() + 75])

		iv_curve = {} 
		iv_curve["figure"] = fig.to_html(full_html=False)
		iv_curve["iv_source_values"] = ",".join(str(value) for value in source_values)
		iv_curve["iv_measurement_values"] = ",".join(str(value) for value in average_voltage_values)
		iv_curve["iv_voltage_up"] = ",".join(str(value) for value in iv_dict["voltage_up"])
		iv_curve["iv_voltage_down"] = ",".join(str(value) for value in iv_dict["voltage_down"])
		iv_curve["points_per_decade"] = iv_dict["points_per_decade"]
		iv_curve["polarity"] = iv_dict["polarity"]

		process = pp.IV_curve(iv_dict["current"], iv_dict["voltage_up"], iv_dict["voltage_down"])
		process_dict = process.calc_IV_parameters()

		max_current = process_dict["Imax"]

		clean_process_dict = {
			"rs": process_dict["Rs"],
			"ideality": process_dict["n (ideality)"],
			"is": process_dict["Is"],
			"r_squared_error": process_dict["R^2 Error"],
			"mean_squared_error": process_dict["Mean Square Error"],
			"hysteresis_mean": process_dict["Hysteresis Mean (mV)"],
			"hysteresis_std": process_dict["Hysteresis SD (mV)"],
			"hysteresis_max": process_dict["Hysteresis Max (mV)"],
			"hysteresis_min": process_dict["Hysteresis Min (mV)"],
			"reverse_current": process_dict["Reverse Current (uA)"],
			"reverse_voltage": process_dict["Reverse Voltage (V)"],
			"rs_4pt": process_dict["Rs_4pt"],
			"rs_3pt": process_dict["Rs 3pt"],
			"rs_1": process_dict["Rs_1"],
			"pass_heat": process_dict.get("pass_heat", ""),
			"temperature": process_dict.get("temperature", ""),
			"i_max": process_dict['mV @ Imax'],
			"i_max_10": process_dict['mV @ Imax/10'],
			"i_max_100": process_dict['mV @ Imax/100'],
			f"{max_current}mA": process_dict[f'mV @ {max_current}mA'],
			f"{max_current}00uA": process_dict[f'mV @ {max_current}00uA'],
			f"{max_current}0uA": process_dict[f'mV @ {max_current}0uA'],
			f"{max_current}uA": process_dict[f'mV @ {max_current}uA'],
			f"{max_current}00nA": process_dict[f'mV @ {max_current}00nA'],
			"dv1": process_dict["dV1"],
			"dv2": process_dict["dV2"],
			"dv3": process_dict["dV3"],
			"dv4": process_dict["dV4"],
			"dv5": process_dict["dV5"],
			"max_current": max_current
		}
		
		full_iv_dict = {**clean_process_dict, **iv_dict}

		tag_list = ["NA", "1", "2", "A", "B", "A1", "A2", "G1", "G2", "G3", "G4", "W"]

		return render_template("partials/iv-page/iv-file-population-response.html", iv_data=full_iv_dict, iv_curve=iv_curve, tags=tag_list, selected_tag="NA")
	
	return "No file uploaded", 204

@file_bp.post("/upload_iv_file/")
def upload_iv_file():
	"""Uploads an IV file to be used for populating fields
	
	This function is the precursor to its respective populator function.
	You must upload the file, basically getting its file-path, before using it to upload.


	@return iv-file-upload Return value of type(template partial with file path)
	"""
	global iv_file_directory
	path = webview.windows[0].create_file_dialog(
		webview.FileDialog.OPEN,
		allow_multiple=False,
		directory=iv_file_directory,
		file_types= ('IV Files (*.iv)', 'All Files (*.*)')
		)
	if not path:
		path = [""]
	else:
		iv_file_directory = os.path.dirname(path[0])

	return render_template("partials/iv-page/iv-file-upload.html", file_path=path[0])

@file_bp.post("/upload_block_file/")
def upload_block_file():
	"""Uploads a block file to be used for populating fields
	
	This function is the precursor to its respective populator function.
	You must upload the file, basically getting its file-path, before using it to upload.


	@return block-file-upload Return value of type(template partial with file path)
	"""
	path = webview.windows[0].create_file_dialog(
		webview.FileDialog.OPEN,
		allow_multiple=False,
		directory=block_file_directory,
		file_types= ('Block Files (*.txt)', 'All Files (*.*)')
		)
	if not path:
		path = [""]
		
	return render_template("partials/block-forms/block-file-upload.html", file_path=path[0])

@file_bp.post("/upload_build_file/")
def upload_build_file():
	"""Uploads a build file to be used for populating fields
	
	This function is the precursor to its respective populator function.
	You must upload the file, basically getting its file-path, before using it to upload.


	@return build-file-upload Return value of type(template partial with file path)
	"""
	path = webview.windows[0].create_file_dialog(
		webview.FileDialog.OPEN,
		allow_multiple=False,
		directory=build_file_directory,
		file_types= ('Build Files (*.txt)', 'All Files (*.*)')
		)
	if not path:
		path = [""]
		
	return render_template("partials/block-forms/build-file-upload.html", file_path=path[0])

@file_bp.post("/save_block_file/")
def save_block_file():
	"""Saves the data from the relevant input fields to a (LabView Style) block file 
	
	This function saves the data from the block input fields (inspection, PB1, PB2) to 
	the LabView block file in the appropriate spot on the network.

	This function also saves the same data into the database.

	@return write_block_file/update_table_entry Return value of type (2 callables)
	"""
	block_data = request.form

	block_rev = block_data.get("block-revision-input", "") if block_data.get("block-revision-input", "") != "A" else ""
	block_dict = {
		"block_engraving": block_data.get("block-engraving-input", ""),
		"block_sn": block_data.get("block-serial-number-input", "") + block_rev,
		"inspection_date": iso_date_to_labview(block_data.get("inspection-date-input", "")),
		"inspection_initials": block_data.get("inspection-initials-input", ""),
		"PB1_name": block_data.get("pb1-build-name-input", ""),
		"PB1_date": iso_date_to_labview(block_data.get("pb1-date-input", "")),
		"PB1_initials": block_data.get("pb1-initials-input", ""),
		"PB2_name": block_data.get("pb2-build-name-input", ""),
		"PB2_date": iso_date_to_labview(block_data.get("pb2-date-input", "")),
		"PB2_initials": block_data.get("pb2-initials-input", ""),
		#"PB2_passfail": block_data.get("pb2-pass-fail-input", ""),
		#"PB2_bond_wire_pads": block_data.get("pb2-bond-pads-count-input", ""),
		#"PB2_components": block_data.get("pb2-components-count-input", ""),
		"PB2_inspection": block_data.get("pb2-inspection-initials-input", "")
	}
	
	file_name, content_rows = write_block_file(block_dict)
	
	path = webview.windows[0].create_file_dialog(
		webview.FileDialog.SAVE,
		save_filename=file_name,
		directory=block_file_directory
		)

	if path and path[0] and path[0].endswith(".txt"):
		with open(path[0], "w") as file:
			for index, line in enumerate(content_rows):
				file.write(line)
				if index < len(content_rows) - 1:
					file.write("\n")
	
	if retrieve_build_info(block_dict["block_engraving"], block_data.get("block-serial-number-input", ""), block_data.get("block-revision-input", "")) != []:
		
		result = retrieve_build_info(block_dict["block_engraving"], block_data.get("block-serial-number-input", ""), block_data.get("block-revision-input", ""))[0]
		
		updates = {
			"inspection_date": string_to_python_date(block_data.get("inspection-date-input", "")) if (block_data.get("inspection-date-input", "") != "") else result.inspection_date,
			"inspection_initials": block_data.get("inspection-initials-input", "").strip() if (block_data.get("inspection-initials-input", "") != "") else result.inspection_initials,
			"pb1_build_name": block_data.get("pb1-build-name-input", "").strip() if (block_data.get("pb1-build-name-input", "") != "") else result.pb1_build_name,
			"pb1_date": string_to_python_date(block_data.get("pb1-date-input", "")) if (block_data.get("pb1-date-input", "") != "") else result.pb1_date,
			"pb1_initials": block_data.get("pb1-initials-input", "").strip() if (block_data.get("pb1-initials-input", "") != "") else result.pb1_initials,
			"pb2_build_name": block_data.get("pb2-build-name-input", "").strip() if (block_data.get("pb2-build-name-input", "") != "") else result.pb2_build_name,
			"pb2_date": string_to_python_date(block_data.get("pb2-date-input", "")) if (block_data.get("pb2-date-input", "") != "") else result.pb2_date,
			"pb2_initials": block_data.get("pb2-initials-input", "").strip() if (block_data.get("pb2-initials-input", "") != "") else result.pb2_initials,
			"pb2_inspection_initials": block_data.get("pb2-inspection-initials-input", "").strip() if (block_data.get("pb2-inspection-initials-input", "") != "") else result.pb2_inspection
		}

		block_id = block_dict["block_engraving"].strip()+" "+block_data.get("block-serial-number-input", "").strip()+" "+block_data.get("block-revision-input", "").strip()
		
		update_table_entry(db_session, Build_Info, block_id, **updates)

		return "Block file written", 204
	
	elif validate_block_info(block_dict["block_engraving"], block_data.get("block-serial-number-input", ""), block_data.get("block-revision-input", "")):
		
		new_entry = {
			"block_id": block_dict["block_engraving"].strip()+" "+block_data.get("block-serial-number-input", "").strip()+" "+block_data.get("block-revision-input", "").strip(),
			"block_engraving": block_dict["block_engraving"].strip(),
			"block_serial_number": block_data.get("block-serial-number-input", "").strip(),
			"block_revision": block_data.get("block-revision-input", "").strip(),
			"inspection_date": string_to_python_date(block_data.get("inspection-date-input", "")) if (block_data.get("inspection-date-input", "") != "") else None,
			"inspection_initials": block_data.get("inspection-initials-input", "").strip(),
			"pb1_build_name": block_data.get("pb1-build-name-input", "").strip(),
			"pb1_date": string_to_python_date(block_data.get("pb1-date-input", "")) if (block_data.get("pb1-date-input", "") != "") else None,
			"pb1_initials": block_data.get("pb1-initials-input", "").strip(),
			"pb2_build_name": block_data.get("pb2-build-name-input", "").strip(),
			"pb2_date": string_to_python_date(block_data.get("pb2-date-input", "")) if (block_data.get("pb2-date-input", "") != "") else None,
			"pb2_initials": block_data.get("pb2-initials-input", "").strip(),
			"pb2_inspection_initials": block_data.get("pb2-inspection-initials-input", "").strip(),
			"block_file_path": path[0]
		}
		add_table_entry(db_session, Build_Info, **new_entry)
		return "Block file written", 204
	#Future response goes here if data inputs don't pass sanitization check
	return "Block file written", 204

@file_bp.post("/attempt_save_build_file/")
def attempt_save_build_file():
	"""
	Checks the existing list of parts on the Full Build Info form and compares it to the parts on the standard BOM.

	If the parts and quantities don't match, display a dialog box prompting the user to confirm if to save or to cancel.
	"""
	build_data = request.form

	parts = build_data.getlist("part")
	quantities = build_data.getlist("quantity")

	user_parts = list(zip(parts, quantities))

	BOM_for = build_data.get("full-build-name-input", "")
	parts = jb2.get_BOM(BOM_for)
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

	standard_BOM = []

	for entry in parts:
		standard_BOM.append((entry['part_name'], int(float(entry['part_quantity']))))

	for entry in sub_parts:
		for subpart in entry['sub_parts']:
			standard_BOM.append((subpart['part_name'], int(float(subpart['part_quantity']))))

	user_parts_names_set = set()
	for entry in user_parts:
		user_parts_names_set.add(entry[0])
	standard_BOM_names_set = set()
	for entry in standard_BOM:
		standard_BOM_names_set.add(entry[0])

	nonstandard_part_names_set = user_parts_names_set - standard_BOM_names_set #parts the user added that are not on the standard BOM
	missing_parts_names_set = standard_BOM_names_set - user_parts_names_set
	mismatched_quantities_list = []

	for user_part in user_parts:
		for standard in standard_BOM:
			if user_part[0] == standard[0] and int(float(user_part[1])) != standard[1]: #if part names match but BOM quantity does not match that on Full Build Info form
				mismatched_quantities_list.append((user_part[0], int(float(user_part[1])), standard[1])) #name of part, user quantity, BOM quantity for every instance on the Full Build Info form

	for name in nonstandard_part_names_set:
		mismatched_quantities_list.append((name, int(float(user_part[1])), 0)) #adds all parts listed by user but not on BOM

	for name in missing_parts_names_set:
		for standard in standard_BOM:
			if standard[0] == name:
				mismatched_quantities_list.append((name, 0, standard[1])) #adds all parts on BOM not listed by user

	if (not nonstandard_part_names_set) and mismatched_quantities_list == []: #if no mismatches are found save to build file and DB
		part_types = build_data.getlist("part_type")
		parts = build_data.getlist("part")
		lots = build_data.getlist("lot-select")
		custom_lots = build_data.getlist("custom-lot-input")
		quantities = build_data.getlist("quantity")
		notes = build_data.getlist("note")
		note_types = build_data.getlist("note_type")

		custom_index = 0
		for index, lot in enumerate(lots):
			if lot == "Other":
				lots[index] = custom_lots[custom_index]
				custom_index += 1

		all_part_information = list(zip(parts, part_types, lots, quantities))
		all_note_information = list(zip(notes, note_types))

		block_suffix_regex = ""
		block_suffix_pattern = r"[^W][R]([\d])"
		
		regex_block_suffix_match = re.search(block_suffix_pattern, build_data.get("block-engraving-input", ""))
		if regex_block_suffix_match:
			block_suffix_regex = "_R" + regex_block_suffix_match.group(1)

		block_rev = build_data.get("block-revision-input", "") if build_data.get("block-revision-input", "") != "A" else ""
		block_suffix = "_R" + build_data.get("block-engraving-input", "")[-1] if build_data.get("block-engraving-input", "") else ""
		build_name = build_data.get("full-build-name-input", "") + block_suffix_regex

		block_dict = {
			"block_engraving": build_data.get("block-engraving-input", ""),
			"block_sn": build_data.get("block-serial-number-input", "") + block_rev,
			"inspection_date": iso_date_to_labview(build_data.get("inspection-date-input", "")),
			"inspection_initials": build_data.get("inspection-initials-input", ""),
			"PB1_name": build_data.get("pb1-build-name-input", ""),
			"PB1_date": iso_date_to_labview(build_data.get("pb1-date-input", "")),
			"PB1_initials": build_data.get("pb1-initials-input", ""),
			"PB2_name": build_data.get("pb2-build-name-input", ""),
			"PB2_date": iso_date_to_labview(build_data.get("pb2-date-input", "")),
			"PB2_initials": build_data.get("pb2-initials-input", ""),
			"PB2_passfail": build_data.get("pb2-pass-fail-input", ""),
			"PB2_bond_wire_pads": build_data.get("pb2-bond-pads-count-input", ""),
			"PB2_components": build_data.get("pb2-components-count-input", ""),
			"PB2_inspection": build_data.get("pb2-inspector-initials-input", "")
		}

		all_diode_information = [part for part in all_part_information if part[1] == "DIODE"]
		all_circuit_information = [part for part in all_part_information if part[1] == "CIRCUIT"]
		all_filter_information = [part for part in all_part_information if part[1] == "FILTER"]
		pcb_information = [part for part in all_part_information if part[1] == "PCB"]
		MMIC_information = [part for part in all_part_information if part[1] == "MMIC"]

		build_dict = {}

		build_dict["diode1"] = all_diode_information[0][0] + "_LOT" + all_diode_information[0][2] if len(all_diode_information) > 0 else ""
		build_dict["qty_chips1"] = all_diode_information[0][3] if len(all_diode_information) > 0 else ""
		build_dict["assembly_initials1"] = build_data.get("full-build-initials-input", "")
		build_dict["assembly_date1"] = iso_date_to_labview(build_data.get("full-build-date-input", ""))
		build_dict["circuit1"] = all_circuit_information[0][0] + "_LOT" + all_circuit_information[0][2] if len(all_circuit_information) > 0 else ""
		build_dict["filter1"] = all_filter_information[0][0] + "_LOT" + all_filter_information[0][2] if len(all_filter_information) > 0 else ""

		build_dict["diode2"] = all_diode_information[1][0] + "_LOT" + all_diode_information[1][2] if len(all_diode_information) > 1 else ""
		build_dict["qty_chips2"] = all_diode_information[1][3] if len(all_diode_information) > 1 else ""
		build_dict["assembly_initials2"] = build_data.get("full-build-initials-input", "")
		build_dict["assembly_date2"] = iso_date_to_labview(build_data.get("full-build-date-input", ""))
		build_dict["circuit2"] = all_circuit_information[1][0] + "_LOT" + all_circuit_information[1][2] if len(all_circuit_information) > 1 else ""
		build_dict["filter2"] = all_filter_information[1][0] + "_LOT" + all_filter_information[1][2] if len(all_filter_information) > 1 else ""

		build_dict["MMIC"] = MMIC_information[0][0] if len(MMIC_information) > 0 else ""
		build_dict["MMIC_lot"] = MMIC_information[0][2] if len(MMIC_information) > 0 else ""
		build_dict["PCB"] = pcb_information[0][0] + "_LOT" + pcb_information[0][2] if len(pcb_information) > 0 else ""
		
		indium_note = [note for note in all_note_information if note[1] == "INDIUM"]
		vbr_note = [note for note in all_note_information if note[1] == "VBR"]
		other_notes = [note for note in all_note_information if note[1] != "INDIUM" and note[1] != "VBR"]

		build_dict["indium"] = indium_note[0][0] if len(indium_note) > 0 else ""
		build_dict["Vbr"] = vbr_note[0][0] if len(vbr_note) > 0 else ""

		build_dict["notes"] = ""
		for i in range(1, 7):
			build_dict[f"notes{i}"] = ""
		
		for index, note in enumerate(other_notes):
			if (index == 0):
				build_dict["notes"] = note[0]
			else:
				if (index <= 6):
					build_dict[f"notes{index}"] = note[0]

		# PARTS : diode1, qty_chips1, assembly_initials1, assembly_date1, circuit1 MMIC, MMIC_lot, PCB, filter1, diode2, qty_chips2,
		# assembly_initials2, assembly_date2, circuit2 filter2
		# NOTES: notes, indium, Vbr, notes1, notes2, notes3, notes4, notes5, notes6
		file_name, content_rows = write_build_file(block_dict, build_dict, build_name)

		path = webview.windows[0].create_file_dialog(
			webview.FileDialog.SAVE,
			save_filename=file_name,
			directory=build_file_directory
			)
		
		if path is None: #Someone closed out the save dialog box without actually saving the file
			return "", 200
		else:
			if path and path[0] and path[0].endswith(".txt"):
				with open(path[0], "w") as file:
					for index, line in enumerate(content_rows):
						file.write(line)
						if index < len(content_rows) - 1:
							file.write("\n")

			db_session.execute(
				delete(Build_Parts).where(Build_Parts.block_id == build_data.get("block-engraving-input", "")+" "+build_data.get("block-serial-number-input", "")+" "+build_data.get("block-revision-input", "A"))
			)

			for part, part_type, lot, quantity in all_part_information:
				add_table_entry(
					db_session,
					Build_Parts,
					block_id=build_data.get("block-engraving-input", "")+" "+build_data.get("block-serial-number-input", "")+" "+build_data.get("block-revision-input", "A"),
					part_name=part,
					quantity=int(float(quantity)),
					part_type=part_type,
					part_lot=lot
				)
			print("adding build info to db")
			updates = {
					"build_file_path": path[0],
					"full_build_name": BOM_for,
					"full_build_initials": build_data.get("full-build-initials-input", ""),
					"full_build_date": string_to_python_date(build_data.get("full-build-date-input", "")) if (build_data.get("full-build-date-input", "")) != "" else None
				}
			update_table_entry(db_session, Build_Info, build_data.get("block-engraving-input", "")+" "+build_data.get("block-serial-number-input", "")+" "+build_data.get("block-revision-input", ""), **updates)
			return "Build file written", 204
	else:
		print("Mismatched quantities found")
		return render_template("partials/build-page/confirm-build-file-save.html", differences=mismatched_quantities_list)

@file_bp.post("/confirm_build_file_save/")
def confirm_build_file_save():
	"""
	Saves the data from the relevant input fields to a (LabView Style) build file 
	
	This function saves the data from the block input fields (inspection, PB1, PB2) 
	as well as the build input fields (part/note list) 
	to the LabView build file in the appropriate spot on the network.

	This function also saves the same data into the database.

	@return write_build_file/update_table_entry Return value of type (2 callables)
	"""
	build_data = request.form

	part_types = build_data.getlist("part_type")
	parts = build_data.getlist("part")
	lots = build_data.getlist("lot-select")
	custom_lots = build_data.getlist("custom-lot-input")
	quantities = build_data.getlist("quantity")
	notes = build_data.getlist("note")
	note_types = build_data.getlist("note_type")

	custom_index = 0
	for index, lot in enumerate(lots):
		if lot == "Other":
			lots[index] = custom_lots[custom_index]
			custom_index += 1

	all_part_information = list(zip(parts, part_types, lots, quantities))
	all_note_information = list(zip(notes, note_types))

	block_suffix_regex = ""
	block_suffix_pattern = r"[^W][R]([\d])"
	
	regex_block_suffix_match = re.search(block_suffix_pattern, build_data.get("block-engraving-input", ""))
	if regex_block_suffix_match:
		block_suffix_regex = "_R" + regex_block_suffix_match.group(1)

	block_rev = build_data.get("block-revision-input", "") if build_data.get("block-revision-input", "") != "A" else ""
	block_suffix = "_R" + build_data.get("block-engraving-input", "")[-1] if build_data.get("block-engraving-input", "") else ""
	build_name = build_data.get("full-build-name-input", "") + block_suffix_regex

	block_dict = {
		"block_engraving": build_data.get("block-engraving-input", ""),
		"block_sn": build_data.get("block-serial-number-input", "") + block_rev,
		"inspection_date": iso_date_to_labview(build_data.get("inspection-date-input", "")),
		"inspection_initials": build_data.get("inspection-initials-input", ""),
		"PB1_name": build_data.get("pb1-build-name-input", ""),
		"PB1_date": iso_date_to_labview(build_data.get("pb1-date-input", "")),
		"PB1_initials": build_data.get("pb1-initials-input", ""),
		"PB2_name": build_data.get("pb2-build-name-input", ""),
		"PB2_date": iso_date_to_labview(build_data.get("pb2-date-input", "")),
		"PB2_initials": build_data.get("pb2-initials-input", ""),
		"PB2_passfail": build_data.get("pb2-pass-fail-input", ""),
		"PB2_bond_wire_pads": build_data.get("pb2-bond-pads-count-input", ""),
		"PB2_components": build_data.get("pb2-components-count-input", ""),
		"PB2_inspection": build_data.get("pb2-inspector-initials-input", "")
	}

	all_diode_information = [part for part in all_part_information if part[1] == "DIODE"]
	all_circuit_information = [part for part in all_part_information if part[1] == "CIRCUIT"]
	all_filter_information = [part for part in all_part_information if part[1] == "FILTER"]
	pcb_information = [part for part in all_part_information if part[1] == "PCB"]
	MMIC_information = [part for part in all_part_information if part[1] == "MMIC"]

	build_dict = {}

	build_dict["diode1"] = all_diode_information[0][0] + "_LOT" + all_diode_information[0][2] if len(all_diode_information) > 0 else ""
	build_dict["qty_chips1"] = all_diode_information[0][3] if len(all_diode_information) > 0 else ""
	build_dict["assembly_initials1"] = build_data.get("full-build-initials-input", "")
	build_dict["assembly_date1"] = iso_date_to_labview(build_data.get("full-build-date-input", ""))
	build_dict["circuit1"] = all_circuit_information[0][0] + "_LOT" + all_circuit_information[0][2] if len(all_circuit_information) > 0 else ""
	build_dict["filter1"] = all_filter_information[0][0] + "_LOT" + all_filter_information[0][2] if len(all_filter_information) > 0 else ""

	build_dict["diode2"] = all_diode_information[1][0] + "_LOT" + all_diode_information[1][2] if len(all_diode_information) > 1 else ""
	build_dict["qty_chips2"] = all_diode_information[1][3] if len(all_diode_information) > 1 else ""
	build_dict["assembly_initials2"] = build_data.get("full-build-initials-input", "")
	build_dict["assembly_date2"] = iso_date_to_labview(build_data.get("full-build-date-input", ""))
	build_dict["circuit2"] = all_circuit_information[1][0] + "_LOT" + all_circuit_information[1][2] if len(all_circuit_information) > 1 else ""
	build_dict["filter2"] = all_filter_information[1][0] + "_LOT" + all_filter_information[1][2] if len(all_filter_information) > 1 else ""

	build_dict["MMIC"] = MMIC_information[0][0] if len(MMIC_information) > 0 else ""
	build_dict["MMIC_lot"] = MMIC_information[0][2] if len(MMIC_information) > 0 else ""
	build_dict["PCB"] = pcb_information[0][0] + "_LOT" + pcb_information[0][2] if len(pcb_information) > 0 else ""
	
	indium_note = [note for note in all_note_information if note[1] == "INDIUM"]
	vbr_note = [note for note in all_note_information if note[1] == "VBR"]
	other_notes = [note for note in all_note_information if note[1] != "INDIUM" and note[1] != "VBR"]

	build_dict["indium"] = indium_note[0][0] if len(indium_note) > 0 else ""
	build_dict["Vbr"] = vbr_note[0][0] if len(vbr_note) > 0 else ""

	build_dict["notes"] = ""
	for i in range(1, 7):
		build_dict[f"notes{i}"] = ""
	
	for index, note in enumerate(other_notes):
		if (index == 0):
			build_dict["notes"] = note[0]
		else:
			if (index <= 6):
				build_dict[f"notes{index}"] = note[0]

	# PARTS : diode1, qty_chips1, assembly_initials1, assembly_date1, circuit1 MMIC, MMIC_lot, PCB, filter1, diode2, qty_chips2,
	# assembly_initials2, assembly_date2, circuit2 filter2
	# NOTES: notes, indium, Vbr, notes1, notes2, notes3, notes4, notes5, notes6
	file_name, content_rows = write_build_file(block_dict, build_dict, build_name)

	path = webview.windows[0].create_file_dialog(
		webview.FileDialog.SAVE,
		save_filename=file_name,
		directory=build_file_directory
		)
	
	if path is None: #Someone closed out the save dialog box without actually saving the file
		return "", 200

	else:
		if path and path[0] and path[0].endswith(".txt"):
			with open(path[0], "w") as file:
				for index, line in enumerate(content_rows):
					file.write(line)
					if index < len(content_rows) - 1:
						file.write("\n")

		db_session.execute(
			delete(Build_Parts).where(Build_Parts.block_id == build_data.get("block-engraving-input", "")+" "+build_data.get("block-serial-number-input", "")+" "+build_data.get("block-revision-input", "A"))
		)

		for part, part_type, lot, quantity in all_part_information:
			add_table_entry(
				db_session,
				Build_Parts,
				block_id=build_data.get("block-engraving-input", "")+" "+build_data.get("block-serial-number-input", "")+" "+build_data.get("block-revision-input", "A"),
				part_name=part,
				quantity=int(float(quantity)),
				part_type=part_type,
				part_lot=lot
			)
		
		updates = {
				"build_file_path": path[0],
				"full_build_name": build_data.get("full-build-name-input", ""),
				"full_build_initials": build_data.get("full-build-initials-input", ""),
				"full_build_date": string_to_python_date(build_data.get("full-build-date-input", "")) if (build_data.get("full-build-date-input", "")) != "" else None
			}
		
		update_table_entry(db_session, Build_Info, build_data.get("block-engraving-input", "")+" "+build_data.get("block-serial-number-input", "")+" "+build_data.get("block-revision-input", ""), **updates)
		
		return "", 200

@file_bp.post("/cancel_build_file_save/")
def cancel_build_file_save():
	return "", 200

@file_bp.post("/save_iv_file/")
def save_iv_file():
	iv_data = request.form
	global iv_file_directory

	current_datetime = datetime.now()
	formatted_date = current_datetime.strftime("%#m/%#d/%Y")
	formatted_time = current_datetime.strftime("%#I:%M %p")

	block_build_full_sn = iv_data.get("iv-block-sn", "X") + iv_data.get("iv-block-revision", "A")

	full_diode_info = "X"
	full_circuit_info = "X"

	parts = iv_data.getlist("part")
	lots = iv_data.getlist("lot-select")

	diode_name = parts[0]
	diode_lot = lots[0]
	full_diode_info = "" + diode_name + "_LOT" + diode_lot

	circuit_name = parts[1]
	circuit_lot = lots[1]
	full_circuit_info = "" + circuit_name + "_LOT" + circuit_lot

	info_dict = {
		"build_name": iv_data.get("iv-build-name", "X"),
		"build_sn": block_build_full_sn,
		"diode": full_diode_info,
		"circuit": full_circuit_info,
		"assembly_no": iv_data.get("iv-assembly-number", "X"),
		"polarity": iv_data.get("iv-polarity", ""),
		"block_engraving": iv_data.get("iv-block-engraving", "X"),
		"block_sn": block_build_full_sn,
		"medium": iv_data.get("iv-additional-info", "X"),
		"date": formatted_date,
		"time": formatted_time
	}

	iv_dict = {
		"Points/Decade": iv_data.get("iv-points-per-decade", ""),
		"n (ideality)": iv_data.get("n", ""),
		"Is": iv_data.get("is", ""),
		"Rs": iv_data.get("rs", ""),
		"Mean Square Error": iv_data.get("mean-squared-error", ""),
		"R^2 Error": iv_data.get("r-squared-error", ""),
		"Polarity": iv_data.get("iv-polarity", ""),
		"Hysteresis SD (mV)": iv_data.get("hysteresis-std", ""),
		"Hysteresis Mean (mV)": iv_data.get("hysteresis-mean", ""),
		"Hysteresis Max (mV)": iv_data.get("hysteresis-max", ""),
		"Hysteresis Min (mV)": iv_data.get("hysteresis-min", ""),
		"Reverse Current (uA)": iv_data.get("reverse-current", ""),
		"Reverse Voltage (V)": iv_data.get("reverse-voltage", ""),
	}

	Vup_list = iv_data.get("iv-voltage-up", "").split(",")
	Vdown_list = iv_data.get("iv-voltage-down", "").split(",")
	I_source_list = iv_data.get("iv-source-values", "").split(",")

	heat_current_list = iv_data.get("heat-current-list", "").split(",")
	heat_voltage_list = iv_data.get("heat-voltage-list", "").split(",")
	temperature_list = iv_data.get("temperature-list", "").split(",")
	combined_heat_list = [*heat_current_list, *heat_voltage_list, *temperature_list]
	heat_test_taken = all([heat_current_list, heat_voltage_list, temperature_list]) and any(combined_heat_list)

	file_name, content_rows = write_IV_file(info_dict, iv_dict, Vup_list, Vdown_list, I_source_list)

	if heat_test_taken:
		if ", w_heat" not in file_name:
			file_name = file_name.replace(".iv", ", w_heat.iv")

	path = webview.windows[0].create_file_dialog(
		webview.FileDialog.SAVE,
		save_filename=file_name,
		directory=iv_file_directory
		)
	if path and path[0] and path[0].endswith(".iv"):
		with open(path[0], "w") as file:
			for index, line in enumerate(content_rows):
				file.write(line)
				if index < len(content_rows) - 1:
					file.write("\n")
		
		iv_file_directory = os.path.dirname(path[0])

	if heat_test_taken:
		heat_file_name, heat_content_rows = write_heat_test_file(file_name, heat_current_list, heat_voltage_list, temperature_list,
															formatted_date, formatted_time,
															iv_data.get("n", ""), iv_data.get("is", ""))
		
		heat_file = os.path.join(config.heat_data_directory, heat_file_name)
		with open(heat_file, "w") as heat_file:
			for index, line in enumerate(heat_content_rows):
				heat_file.write(line)
				if index < len(heat_content_rows) - 1:
					heat_file.write("\n")

	if (iv_data.getlist("custom-lot-input") != []) and len(iv_data.getlist("custom-lot-input")) == 2:
		print("Both Custom")
		diode_lot = iv_data.getlist("custom-lot-input")[0]
		circuit_lot = iv_data.getlist("custom-lot-input")[1]
	elif (iv_data.getlist("custom-lot-input") != []) and (iv_data.getlist("lot-select")[0] == "Other") and (iv_data.getlist("lot-select")[1] != "Other"):
		diode_lot = iv_data.getlist("custom-lot-input")[0]
		circuit_lot = iv_data.getlist("lot-select")[1]
	elif(iv_data.getlist("custom-lot-input") != []) and (iv_data.getlist("lot-select")[1] == "Other") and (iv_data.getlist("lot-select")[0] != "Other"):
		print("Circuit Custom")
		diode_lot = iv_data.getlist("lot-select")[0]
		circuit_lot = iv_data.getlist("custom-lot-input")[0]
	else:
		print("Both Standard")
		diode_lot = iv_data.getlist("lot-select")[0]
		circuit_lot = iv_data.getlist("lot-select")[1]

	iv_info_dict = {
		"build_id": iv_data.get("iv-block-engraving", "")+" "+iv_data.get("iv-block-sn", "")+" "+iv_data.get("iv-block-revision", "A"),
		"diode": iv_data.get("iv-diode-name", "X"),
		"diode_lot": diode_lot,
		"circuit": iv_data.get("iv-circuit-name", "X"),
		"circuit_lot": circuit_lot,
		"assembly_no": iv_data.get("iv-assembly-number", "X"),
		"subassembly_tag": iv_data.get("part-tag", "X"),
		"iv_date": current_datetime.date(),
		"points_per_decade": int(iv_dict["Points/Decade"]),
		"ideality": float(iv_dict["n (ideality)"]),
		"saturation_current": float(iv_dict["Is"]),
		"series_resistance": float(iv_dict["Rs"]),
		"mean_square_error": float(iv_dict["Mean Square Error"]),
		"r_squared_error": float(iv_dict["R^2 Error"]),
		"polarity": Polarity.POSITIVE if iv_dict["Polarity"] == "+" else Polarity.NEGATIVE,
		"hysteresis_standard_deviation": float(iv_dict["Hysteresis SD (mV)"]),
		"hysteresis_mean": float(iv_dict["Hysteresis Mean (mV)"]),
		"hysteresis_maximum": float(iv_dict["Hysteresis Max (mV)"]),
		"hysteresis_minimum": float(iv_dict["Hysteresis Min (mV)"]),
		"reverse_current": float(iv_dict["Reverse Current (uA)"]),
		"reverse_voltage": float(iv_dict["Reverse Voltage (V)"]),
		"iv_file_path": path[0]
	}

	iv_info = add_table_entry(
		db_session,
		IV_Info,
		**iv_info_dict
				 )

	iv_points_dict = {
		"iv_id": iv_info.iv_id,
		"voltage_up_mv": iv_data.get("iv-voltage-up", "").replace(r'\r', '').replace(r'\n', ''),
		"voltage_down_mv": iv_data.get("iv-voltage-down", "").replace(r'\r', '').replace(r'\n', ''),
		"current_ua": iv_data.get("iv-source-values").replace(r'\r', '').replace(r'\n', '')
	}

	add_table_entry(
		db_session,
		IV_Points,
		**iv_points_dict
	)	

	return "IV file written", 204