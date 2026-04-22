import os

from flask import Blueprint, render_template, request, current_app
from app.db.database import db_session
from app.db.queries import *
from app.db import JB2_queries as jb2
from app.services import build_file_converter as build_converter, block_file_converter as block_converter, dymo_printer as printer, iv_file_converter as iv_converter
import plotly.express as px
import pandas as pd
from app.services.keithley_236_functions import SMU_K236
from app.services.write_MicroA_files import write_block_file, write_IV_file, write_build_file
from app.services import postprocess as pp
from datetime import datetime
import webview

bp = Blueprint("main", __name__)

iv_file_directory = os.path.abspath('I:/')
block_file_directory = os.path.abspath('K:/block')
build_file_directory = os.path.abspath('K:/build')

@bp.get("/")
def index():
	return render_template("base.html")

@bp.get("/build")
def get_build_page():
	return render_template("build-page.html")

@bp.get("/iv")
def get_iv_page():
	return render_template("iv-page.html")

@bp.get("/iv_and_build")
def get_iv_and_build_page():
	return render_template("iv-and-build-page.html")

@bp.get("/search_jb2_components/")
def search_jb2_components():
	component_name = request.args.get("component-name")
	results = jb2.get_Build_Name_List(component_name)
	return render_template("partials/search/bom-suggestion-results.html", search_results=results)

@bp.get("/get_jb2_bom_from_build_name/")
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

	for index, sub_part in enumerate(sub_parts):
		sub_part["starting_index"] = len(parts)
		if (index > 0):
			sub_part["starting_index"] += len(sub_parts[index-1]["sub_parts"])

	return render_template("partials/build-page/bom-list.html", build_name=build_name, bom_parts=parts, sub_parts=sub_parts)

@bp.get("/add_empty_part_row/")
def add_empty_part_row():
	return render_template("partials/build-page/part-row.html", part=None)

@bp.get("/add_empty_note_row/")
def add_empty_note_row():
	return render_template("partials/build-page/note-row.html", note=None)

@bp.get("/search_part_lots/")
def search_part_lots():
	part = request.args.get("part")
	lot_list = jb2.get_Lots(part)
	return render_template("partials/build-page/lot-input.html", lot_list=lot_list)

@bp.post("/add_part_rows_from_bom_list/")
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

@bp.post("/print/full_build/")
def print_full_build():
	full_build_info = request.form
	printer.print_engine("full_build.label", printer.populate_full_build_label_fields, full_build_info, printer.prepare_full_build_label)
	return "", 204

@bp.post("/print/inspection_label/")
def print_block_inspection():
	inspection_info = request.form
	printer.print_engine("inspection.label", printer.populate_inspection_label_fields, inspection_info)
	return "", 204

@bp.post("/print/pb1_label/")
def print_pb1_label():
	pb1_info = request.form
	printer.print_engine("pb1.label", printer.populate_pb1_label_fields, pb1_info)
	return "", 204

@bp.post("/print/pb2_label/")
def print_pb2_label():
	pb2_info = request.form
	printer.print_engine("pb2.label", printer.populate_pb2_label_fields, pb2_info)
	return "", 204

@bp.post("/take_iv/")
def take_iv():
	SMU_controls = request.form

	SMU = SMU_K236()
	translated_settings = {
		"delay_toggle": SMU_controls.get("default-delay"),
		"integration_time": SMU_controls.get("integration-time"),
		"filter_count": SMU_controls.get("filter-readings"),
		"compliance_voltage": float(SMU_controls.get("compliance-voltage")),
		"polarity": SMU_controls.get("polarity"),
		"points_per_decade": SMU_controls.get("points-per-decade"),
		"sweep_delay": float(SMU_controls.get("sweep-delay")) if SMU_controls.get("sweep-delay") else 0,
		"maximum_current": SMU_controls.get("maximum-current") + "mA",
		"reverse_polarity_start_current": SMU_controls.get("reverse-current"),
		"reverse_compliance_voltage": SMU_controls.get("reverse-compliance")
	}

	print(translated_settings)

	SMU.update_settings(**translated_settings)

	source_values, voltage_up_values, voltage_down_values = SMU.takeIV()

	reverse_source = ''
	reverse_measure = ''
	if SMU_controls.get('reverse-breakdown-test') == 'on':
		reverse_source, reverse_measure = SMU.takeReverseBreakdown()

	process = pp.IV_curve(source_values, voltage_up_values, voltage_down_values, reverse_source, reverse_measure)
	process_dict = process.calc_IV_parameters()

	max_current = process_dict["Imax"]

	iv_dict ={
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
		"reverse_voltage": process_dict["Reverse Voltage(V)"],
		"rs_1" : process_dict["Rs_1"],
		"rs_4pt": process_dict["Rs_4pt"],
		"rs_3pt": process_dict["Rs 3pt"],
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

	source_values = source_values.split(",")
	voltage_up_values = voltage_up_values.split(",")
	voltage_down_values = voltage_down_values.split(",")
	voltage_avg_values = [str((float(up) + float(down)) / 2) for up, down in zip(voltage_up_values, voltage_down_values)]

	# source_values = [float(value) * 1e6 for value in source_values] # convert to microamps
	# voltage_values = [float(value) * 1e-3 for value in voltage_values] # convert to millivolts
	df = pd.DataFrame({
		"Current (uA)": [abs(float(source_value)) for source_value in source_values],
		"Voltage (mV)": [abs(float(voltage_avg_value)) for voltage_avg_value in voltage_avg_values]
	})

	fig = px.scatter(df, x="Voltage (mV)", y="Current (uA)", labels={"x": "Voltage (mV)", "y": "Current (uA)"}, title=None, log_x=False, log_y=True)
	fig.update_traces(mode='lines+markers')

	if abs(df["Voltage (mV)"].astype(float).max() - df["Voltage (mV)"].astype(float).min()) < 100:
		fig.update_xaxes(range=[df["Voltage (mV)"].astype(float).min() - 25, df["Voltage (mV)"].astype(float).min() + 75])

	iv_curve = {} 
	iv_curve["figure"] = fig.to_html(full_html=False)
	iv_curve["iv_source_values"] = ",".join(source_values)
	iv_curve["iv_measurement_values"] = ",".join(voltage_avg_values)
	iv_curve["iv_voltage_up"] = ",".join(voltage_up_values)
	iv_curve["iv_voltage_down"] = ",".join(voltage_down_values)
	iv_curve["polarity"] = SMU_controls.get("polarity", "")
	iv_curve["points_per_decade"] = SMU_controls.get("points-per-decade", "")

	return render_template("partials/iv-page/run-iv-response.html", iv_curve=iv_curve, iv_data=iv_dict)

@bp.get("/get_empty_plot")
def get_empty_plot():
	df = pd.DataFrame({
		"Voltage (mV)": [],
		"Current (uA)": []
	})

	fig = px.scatter(df, x="Voltage (mV)", y="Current (uA)", labels={"x": "Voltage (mV)", "y": "Current (uA)"}, title=None, log_y=True)
	fig.update_traces(mode='lines+markers')

	if abs(df["Voltage (mV)"].astype(float).max() - df["Voltage (mV)"].astype(float).min()) < 100:
		fig.update_xaxes(range=[df["Voltage (mV)"].astype(float).min() - 25, df["Voltage (mV)"].astype(float).min() + 75])

	iv_curve = {} 
	iv_curve["figure"] = fig.to_html(full_html=False)
	iv_curve["iv_source_values"] = ""
	iv_curve["iv_measurement_values"] = ""

	return render_template("partials/iv-page/iv-plot-figure.html", iv_curve=iv_curve)

@bp.post("/update_keithley_settings/")
def update_keithley_settings():
	SMU_controls = request.form
	
	translated_settings = {
		"delay_toggle": SMU_controls.get("default-delay"),
		"integration_time": SMU_controls.get("integration-time"),
		"filter_count": SMU_controls.get("filter-readings"),
		"compliance_voltage": float(SMU_controls.get("compliance-voltage")),
		"polarity": SMU_controls.get("polarity"),
		"points_per_decade": SMU_controls.get("points-per-decade"),
		"sweep_delay": float(SMU_controls.get("sweep-delay")) if SMU_controls.get("sweep-delay") else 0,
		"maximum_current": SMU_controls.get("maximum-current") + "mA",
		"reverse_polarity_start_current": SMU_controls.get("reverse-current"),
		"reverse_compliance_voltage": SMU_controls.get("reverse-compliance")
	}

	SMU = SMU_K236()
	SMU.update_settings(**translated_settings)

	return render_template("partials/iv-page/iv-gui-controls.html", current_settings=translated_settings)

@bp.post("/default_keithley_settings/")
def default_keithley_settings():
	SMU = SMU_K236()
	default_settings = SMU.update_settings()

	return render_template("partials/iv-page/iv-gui-controls.html", current_settings=default_settings)

@bp.post("/populate_info_from_block_file/")
def populate_info_from_block_file():
	uploaded_file_path = request.form.get("block-file-path")

	if uploaded_file_path and uploaded_file_path.endswith(".txt"):
		with open(uploaded_file_path, "r") as block_file:
			block_dict = block_converter.convert_block_file(block_file)

		return render_template("partials/block-forms/block-forms-container.html", block=block_dict)
	return "No file uploaded", 204

@bp.post("/populate_info_from_build_file/")
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

@bp.post("/save_block_file/")
def save_block_file():
	block_data = request.form
	block_rev = block_data.get("block-revision-input", "") if block_data.get("block-revision-input", "") != "A" else ""
	block_dict = {
		"block_engraving": block_data.get("block-engraving-input", ""),
		"block_sn": block_data.get("block-serial-number-input", "") + block_rev,
		"inspection_date": block_data.get("inspection-date-input", ""),
		"inspection_initials": block_data.get("inspection-initials-input", ""),
		"PB1_name": block_data.get("pb1-build-name-input", ""),
		"PB1_date": block_data.get("pb1-date-input", ""),
		"PB1_initials": block_data.get("pb1-initials-input", ""),
		"PB2_name": block_data.get("pb2-build-name-input", ""),
		"PB2_date": block_data.get("pb2-date-input", ""),
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

@bp.post("/save_build_file/")
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
		"inspection_date": build_data.get("inspection-date-input", ""),
		"inspection_initials": build_data.get("inspection-initials-input", ""),
		"PB1_name": build_data.get("pb1-build-name-input", ""),
		"PB1_date": build_data.get("pb1-date-input", ""),
		"PB1_initials": build_data.get("pb1-initials-input", ""),
		"PB2_name": build_data.get("pb2-build-name-input", ""),
		"PB2_date": build_data.get("pb2-date-input", ""),
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
	build_dict["assembly_date1"] = build_data.get("full-build-date-input", "")
	build_dict["circuit1"] = all_circuit_information[0][0] + "_LOT" + all_circuit_information[0][2] if len(all_circuit_information) > 0 else ""
	build_dict["filter1"] = all_filter_information[0][0] + "_LOT" + all_filter_information[0][2] if len(all_filter_information) > 0 else ""

	build_dict["diode2"] = all_diode_information[1][0] + "_LOT" + all_diode_information[1][2] if len(all_diode_information) > 1 else ""
	build_dict["qty_chips2"] = all_diode_information[1][3] if len(all_diode_information) > 1 else ""
	build_dict["assembly_initials2"] = build_data.get("full-build-initials-input", "")
	build_dict["assembly_date2"] = build_data.get("full-build-date-input", "")
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
	print(file_name)
	print()
	print(block_dict)
	print()
	print(build_dict)
	print()
	print(build_name)

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

@bp.post("/save_iv_file/")
def save_iv_file():
	iv_data = request.form

	current_datetime = datetime.now()
	formatted_date = current_datetime.strftime("%#m/%#d/%Y")
	formatted_time = current_datetime.strftime("%#I:%M %p")

	block_build_full_sn = iv_data.get("iv-block-sn", "") + iv_data.get("iv-block-revision", "")

	info_dict = {
		"build_name": iv_data.get("iv-build-name", ""),
		"build_sn": block_build_full_sn,
		"diode": iv_data.get("iv-diode", ""),
		"circuit": iv_data.get("iv-circuit", ""),
		"assembly_no": iv_data.get("iv-assembly-number", ""),
		"polarity": iv_data.get("iv-polarity", ""),
		"block_engraving": iv_data.get("iv-block-engraving", ""),
		"block_sn": block_build_full_sn,
		"medium": iv_data.get("iv-additional-info", ""),
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
		"Reverse Voltage(V)": iv_data.get("reverse-voltage", ""),
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

@bp.post("/populate_info_from_iv_file/")
def populate_info_from_iv_file():

	uploaded_file_path = request.form.get("iv-file-path")
	if uploaded_file_path and uploaded_file_path.endswith(".iv"):
		with open(uploaded_file_path, "r") as iv_file:
			iv_dict = iv_converter.convert_iv_file(iv_file)

		source_values = [float(value) for value in iv_dict["current"]]
		voltage_values_tuples = zip([float(value) for value in iv_dict["voltage_up"]], [float(value) for value in iv_dict["voltage_down"]])
		average_voltage_values = [(float(up) + float(down)) / 2 for up, down in voltage_values_tuples]

		# source_values = [float(value) * 1e6 for value in source_values] # convert to microamps
		# voltage_values = [float(value) * 1e-3 for value in voltage_values] # convert to millivolts
		df = pd.DataFrame({
			"Current (uA)": source_values,
			"Voltage (mV)": average_voltage_values
		})

		fig = px.scatter(df, x="Voltage (mV)", y="Current (uA)", labels={"x": "Voltage (mV)", "y": "Current (uA)"}, title=None, log_x = False, log_y=True)
		fig.update_traces(mode='lines+markers')

		if abs(df["Voltage (mV)"].astype(float).max() - df["Voltage (mV)"].astype(float).min()) < 100:
			fig.update_xaxes(range=[df["Voltage (mV)"].astype(float).min() - 25, df["Voltage (mV)"].astype(float).min() + 75])

		iv_curve = {} 
		iv_curve["figure"] = fig.to_html(full_html=False)
		iv_curve["iv_source_values"] = ",".join(str(value) for value in source_values)
		iv_curve["iv_measurement_values"] = ",".join(str(value) for value in average_voltage_values)
		iv_curve["iv_voltage_up"] = ",".join(str(value) for value in iv_dict["voltage_up"])
		iv_curve["iv_voltage_down"] = ",".join(str(value) for value in iv_dict["voltage_down"])

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
			"reverse_voltage": process_dict["Reverse Voltage(V)"],
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

@bp.post("/upload_iv_file/")
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

@bp.post("/upload_block_file/")
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

@bp.post("/upload_build_file/")
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

@bp.post("/check_custom_lot/")
def check_custom_lot():
	selected_lot = request.form.get("lot-select")
	
	return render_template("partials/build-page/custom-lot-input.html", selected_lot=selected_lot)