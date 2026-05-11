import os
from flask import Blueprint, render_template, request
from app.db.queries import *
from app.services import build_file_converter as build_converter, block_file_converter as block_converter, iv_file_converter as iv_converter
import plotly.express as px
import pandas as pd
from app.services.write_MicroA_files import write_block_file, write_IV_file, write_build_file
from app.services import postprocess as pp
from datetime import datetime
import webview
from app import config
from app.services import date_converter as dc

file_bp = Blueprint("file", __name__)

iv_file_directory = config.iv_file_directory
block_file_directory = config.block_file_directory
build_file_directory = config.build_file_directory

@file_bp.post("/populate_info_from_block_file/")
def populate_info_from_block_file():
	uploaded_file_path = request.form.get("block-file-path")

	if uploaded_file_path and uploaded_file_path.endswith(".txt"):
		with open(uploaded_file_path, "r") as block_file:
			block_dict = block_converter.convert_block_file(block_file)

		return render_template("partials/block-forms/block-forms-container.html", block=block_dict)
	return "No file uploaded", 204

@file_bp.post("/populate_info_from_build_file/")
def populate_info_from_build_file():
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

		part_rows = [
			{"part_name": diode_1_full_name, "part_quantity": diode_1_quantity, "part_type": "DIODE", "part_lot": diode_1_lot},
			{"part_name": circuit_1_full_name, "part_quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_1_lot},
			{"part_name": diode_2_full_name, "part_quantity": diode_2_quantity, "part_type": "DIODE", "part_lot": diode_2_lot},
			{"part_name": circuit_2_full_name, "part_quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_2_lot},
			{"part_name": pcb_info_full_name, "part_quantity": 1, "part_type": "PCB", "part_lot": pcb_info_lot},
			{"part_name": filter_1_full_name, "part_quantity": 1, "part_type": "FILTER", "part_lot": filter_1_lot},
			{"part_name": filter_2_full_name, "part_quantity": 1, "part_type": "FILTER", "part_lot": filter_2_lot}
		]

		note_rows = []
		for note in build_dict.get("notes", []):
			note_rows.append({"text": note})
		note_rows.append(build_dict.get("vbr", ""))
		note_rows.append(build_dict.get("indium_info", ""))

		return render_template("partials/block-forms/build-file-population-response.html", block=build_dict, parts=part_rows, notes=note_rows)

	return "No file uploaded", 204

@file_bp.post("/populate_info_from_iv_file/")
def populate_info_from_iv_file():

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

		return render_template("partials/iv-page/iv-file-population-response.html", iv_data=full_iv_dict, iv_curve=iv_curve)
	
	return "No file uploaded", 204

@file_bp.post("/upload_iv_file/")
def upload_iv_file():
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
	block_data = request.form
	block_rev = block_data.get("block-revision-input", "") if block_data.get("block-revision-input", "") != "A" else ""
	block_dict = {
		"block_engraving": block_data.get("block-engraving-input", ""),
		"block_sn": block_data.get("block-serial-number-input", "") + block_rev,
		"inspection_date": dc.iso_date_to_labview(block_data.get("inspection-date-input", "")),
		"inspection_initials": block_data.get("inspection-initials-input", ""),
		"PB1_name": block_data.get("pb1-build-name-input", ""),
		"PB1_date": dc.iso_date_to_labview(block_data.get("pb1-date-input", "")),
		"PB1_initials": block_data.get("pb1-initials-input", ""),
		"PB2_name": block_data.get("pb2-build-name-input", ""),
		"PB2_date": dc.iso_date_to_labview(block_data.get("pb2-date-input", "")),
		"PB2_initials": block_data.get("pb2-initials-input", ""),
		"PB2_passfail": block_data.get("pb2-pass-fail-input", ""),
		"PB2_bond_wire_pads": block_data.get("pb2-bond-pads-count-input", ""),
		"PB2_components": block_data.get("pb2-components-count-input", ""),
		"PB2_inspection": block_data.get("pb2-inspector-initials-input", "")
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

	return "Block file written", 204

@file_bp.post("/save_build_file/")
def save_build_file():
	build_data = request.form
	part_types = build_data.getlist("part_type")
	parts = build_data.getlist("part")
	lots = build_data.getlist("lot-select")
	custom_lots = build_data.getlist("custom-lot-input")
	quantities = build_data.getlist("quantity")
	notes = build_data.getlist("note")
	note_types = build_data.getlist("note_type")

	for index, lot in enumerate(lots):
		custom_index = 0
		if lot == "Other":
			lots[index] = custom_lots[custom_index]
			custom_index += 1

	all_part_information = list(zip(parts, part_types, lots, quantities))
	all_note_information = list(zip(notes, note_types))

	block_rev = build_data.get("block-revision-input", "") if build_data.get("block-revision-input", "") != "A" else ""
	block_suffix = "_R" + build_data.get("block-engraving-input", "")[-1] if build_data.get("block-engraving-input", "") else ""
	build_name = build_data.get("full-build-name-input", "") + block_suffix if block_suffix else ""

	block_dict = {
		"block_engraving": build_data.get("block-engraving-input", ""),
		"block_sn": build_data.get("block-serial-number-input", "") + block_rev,
		"inspection_date": dc.iso_date_to_labview(build_data.get("inspection-date-input", "")),
		"inspection_initials": build_data.get("inspection-initials-input", ""),
		"PB1_name": build_data.get("pb1-build-name-input", ""),
		"PB1_date": dc.iso_date_to_labview(build_data.get("pb1-date-input", "")),
		"PB1_initials": build_data.get("pb1-initials-input", ""),
		"PB2_name": build_data.get("pb2-build-name-input", ""),
		"PB2_date": dc.iso_date_to_labview(build_data.get("pb2-date-input", "")),
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
	build_dict["assembly_date1"] = dc.iso_date_to_labview(build_data.get("full-build-date-input", ""))
	build_dict["circuit1"] = all_circuit_information[0][0] + "_LOT" + all_circuit_information[0][2] if len(all_circuit_information) > 0 else ""
	build_dict["filter1"] = all_filter_information[0][0] + "_LOT" + all_filter_information[0][2] if len(all_filter_information) > 0 else ""

	build_dict["diode2"] = all_diode_information[1][0] + "_LOT" + all_diode_information[1][2] if len(all_diode_information) > 1 else ""
	build_dict["qty_chips2"] = all_diode_information[1][3] if len(all_diode_information) > 1 else ""
	build_dict["assembly_initials2"] = build_data.get("full-build-initials-input", "")
	build_dict["assembly_date2"] = dc.iso_date_to_labview(build_data.get("full-build-date-input", ""))
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
	if path and path[0] and path[0].endswith(".txt"):
		with open(path[0], "w") as file:
			for index, line in enumerate(content_rows):
				file.write(line)
				if index < len(content_rows) - 1:
					file.write("\n")

	return "Build file written", 204

@file_bp.post("/save_iv_file/")
def save_iv_file():
	iv_data = request.form

	current_datetime = datetime.now()
	formatted_date = current_datetime.strftime("%#m/%#d/%Y")
	formatted_time = current_datetime.strftime("%#I:%M %p")

	block_build_full_sn = iv_data.get("iv-block-sn", "X") + iv_data.get("iv-block-revision", "A")

	info_dict = {
		"build_name": iv_data.get("iv-build-name", "X"),
		"build_sn": block_build_full_sn,
		"diode": iv_data.get("iv-diode", "X"),
		"circuit": iv_data.get("iv-circuit", "X"),
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

	file_name, content_rows = write_IV_file(info_dict, iv_dict, Vup_list, Vdown_list, I_source_list)

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

	return "IV file written", 204