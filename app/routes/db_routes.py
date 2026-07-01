from flask import Blueprint, request, render_template
from app.services.process_and_sanitize_entry import *
from app.services.date_converter import string_to_python_date
from app.services import postprocess as pp
from app.db import JB2_queries as jb2
from pathlib import Path
import plotly.express as px
import pandas as pd

db_bp = Blueprint("db", __name__)

@db_bp.post("/submit_feedback")
def submit_feedback():
	initials = request.form.get("User_Initials", "").strip()
	feedback = request.form.get("User_Feedback", "").strip()

	if not initials or not feedback: return "<p style='color:red;'>All fields are required.</p>"

	if len(initials) != 3: return "<p style='color:red;'>Initials must be exactly 3 characters.</p>"

	sanitize_and_save_feedback(initials, feedback)
	return "<p>Feedback saved successfully.</p>"

@db_bp.post("/populate_block_info")
def populate_block_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != [] and retrieve_build_parts(block_engraving, block_serial_number, block_revision) == []:
		block = retrieve_build_info(block_engraving, block_serial_number, block_revision)[0]
		return render_template("partials/block-forms/block-and-build-population.html", block=block)
	elif retrieve_build_info(block_engraving, block_serial_number, block_revision) != [] and retrieve_build_parts(block_engraving, block_serial_number, block_revision) != []:
		block = retrieve_build_info(block_engraving, block_serial_number, block_revision)[0]
		items = retrieve_build_parts(block_engraving, block_serial_number, block_revision)
		return render_template("partials/block-forms/block-and-build-population.html", block=block, items=items)


@db_bp.post("/save_inspection_info") #add some intelligent return statements
def save_inspection_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	inspection_date = string_to_python_date(request.form.get("inspection-date-input", "")) if (request.form.get("inspection-date-input", "") != "") else None
	inspection_initials = request.form.get("inspection-initials-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
		updates = {
			"inspection_date": inspection_date,
			"inspection_initials": inspection_initials
		}
		update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
		
		return
	elif validate_block_info(block_engraving, block_serial_number, block_revision):
		new_entry = {
			"block_id": block_engraving+" "+block_serial_number+" "+block_revision,
			"block_engraving": block_engraving,
			"block_serial_number": block_serial_number,
			"block_revision": block_revision,
			"inspection_date": inspection_date,
			"inspection_initials": inspection_initials
		}
		print(new_entry)
		add_table_entry(db_session, Build_Info, **new_entry)
		
		return
	else:
		print("Invalid block information entered, no block information has been added.") #Remove this when sanitizing functionality is added.
		return
	
@db_bp.post("/save_pb1_info")
def save_pb1_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	pb1_build_name = request.form.get("pb1-build-name-input", "").strip()
	pb1_date = string_to_python_date(request.form.get("pb1-date-input", "")) if (request.form.get("pb1-date-input", "") != "") else None
	pb1_initials = request.form.get("pb1-initials-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
		updates = {
			"pb1_build_name": pb1_build_name,
			"pb1_date": pb1_date,
			"pb1_initials": pb1_initials
		}
		update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
		
		return
	elif validate_block_info(block_engraving, block_serial_number, block_revision):
		new_entry = {
			"block_id": block_engraving+" "+block_serial_number+" "+block_revision,
			"block_engraving": block_engraving,
			"block_serial_number": block_serial_number,
			"block_revision": block_revision,
			"pb1_build_name": pb1_build_name,
			"pb1_date": pb1_date,
			"pb1_initials": pb1_initials
		}
		add_table_entry(db_session, Build_Info, **new_entry)
		
		return
	else:
		print("Invalid block information entered, no block information has been added.") #Remove this when sanitizing functionality is added.
		return

@db_bp.post("/save_pb2_info")
def save_pb2_info():
	block_engraving = request.form.get("block-engraving-input", "").strip()
	block_serial_number = request.form.get("block-serial-number-input", "").strip()
	block_revision = request.form.get("block-revision-input", "").strip()
	pb2_build_name = request.form.get("pb2-build-name-input", "").strip()
	pb2_date = string_to_python_date(request.form.get("pb2-date-input", "")) if (request.form.get("pb2-date-input", "") != "") else None
	pb2_initials = request.form.get("pb2-initials-input", "").strip()
	pb2_inspection_initials = request.form.get("pb2-inspection-initials-input", "").strip()
	if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
		updates = {
			"pb2_build_name": pb2_build_name,
			"pb2_date": pb2_date,
			"pb2_initials": pb2_initials,
			"pb2_inspection_initials": pb2_inspection_initials
		}
		update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
		
		return
	elif validate_block_info(block_engraving, block_serial_number, block_revision):
		new_entry = {
			"block_id": block_engraving+" "+block_serial_number+" "+block_revision,
			"block_engraving": block_engraving,
			"block_serial_number": block_serial_number,
			"block_revision": block_revision,
			"pb2_build_name": pb2_build_name,
			"pb2_date": pb2_date,
			"pb2_initials": pb2_initials,
			"pb2_inspection_initials": pb2_inspection_initials
		}
		add_table_entry(db_session, Build_Info, **new_entry)
		
		return
	else:
		print("Invalid block information entered, no block information has been added.") #Remove this when sanitizing functionality is added.
		return
	
@db_bp.post("/open_iv_from_db/")
def open_iv_from_db():
	build_info = request.form

	build_id_query = build_info.get("iv-block-engraving")+" "+build_info.get("iv-block-sn")+" "+build_info.get("iv-block-revision", "A")

	ivs = get_table_entries(db_session,
							IV_Info,
							build_id=build_id_query)
	
	file_paths = [Path(iv.iv_file_path).stem for iv in ivs]

	return render_template("partials/iv-page/select-iv-from-db.html", file_paths=file_paths)

@db_bp.post("/populate_iv_from_db/")
def populate_iv_from_db():
	print("route launched")
	build_info = request.form
	selected_path = build_info.get("selected-iv-path")
	build_id_query = build_info.get("iv-block-engraving")+" "+build_info.get("iv-block-sn")+" "+build_info.get("iv-block-revision", "A")

	ivs = get_table_entries(db_session,
							IV_Info,
							build_id=build_id_query)

	for iv in ivs:
		if Path(iv.iv_file_path).stem == selected_path:
			iv_info_dict = {
    					column.name: getattr(iv, column.name)
    					for column in iv.__table__.columns
					}
			break
	print("iv build info pulled from DB")
	iv_curve_points = get_table_entries(db_session,
										IV_Points,
										iv_id=iv_info_dict['iv_id'])
	print("iv curve info pulled from DB")
	source_values = iv_curve_points[0].current_ua.split(',')
	measure_values_up = iv_curve_points[0].voltage_up_mv.split(',')
	measure_values_down = iv_curve_points[0].voltage_down_mv.split(',')

	average_voltage_values = [(float(up) + float(down)) / 2 for up, down in zip(measure_values_up, measure_values_down)]
	print("starting postprocess")
	db_iv = pp.IV_curve(source_values, measure_values_up, measure_values_down)
	process_dict = db_iv.calc_IV_parameters()
	print("postprocess calculated")
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

	iv_population_dict = {
		"block_name": build_info.get("iv-block-engraving"),
		"block_sn": build_info.get("iv-block-sn"),
		"block_revision": build_info.get("iv-block-revision"),
		"diode": iv_info_dict["diode"],
		"diode_lot": iv_info_dict["diode_lot"],
		"circuit": iv_info_dict["circuit"],
		"circuit_lot": iv_info_dict["circuit_lot"],
		"assembly_number": iv_info_dict["assembly_no"],
		"subassembly_tag": iv_info_dict["subassembly_tag"]
	}

	full_iv_dict = {**clean_process_dict, **iv_population_dict}

	print("IV info dictionaries created")
	df = pd.DataFrame({
			"Current (uA)": source_values,
			"Voltage (V)": average_voltage_values
		})

	fig = px.scatter(df, x="Voltage (V)", y="Current (uA)", labels={"x": "Voltage (V)", "y": "Current (uA)"}, title=None, log_x = False, log_y=True)
	fig.update_traces(mode='lines+markers')

	iv_curve = {} 
	iv_curve["figure"] = fig.to_html(full_html=False)
	iv_curve["iv_source_values"] = ",".join(str(value) for value in source_values)
	iv_curve["iv_measurement_values"] = ",".join(str(value) for value in average_voltage_values)
	iv_curve["iv_voltage_up"] = ",".join(str(value) for value in measure_values_up)
	iv_curve["iv_voltage_down"] = ",".join(str(value) for value in measure_values_down)
	iv_curve["points_per_decade"] = iv_info_dict["points_per_decade"]
	iv_curve["polarity"] = iv_info_dict["polarity"]


	tag_list = ["N/A", "1", "2", "A", "B", "A1", "A2", "G1", "G2", "G3", "G4", "W"]

	diode_lots_list = jb2.get_Lots(full_iv_dict["diode"])
	circuit_lots_list = jb2.get_Lots(full_iv_dict["circuit"])

	return render_template("partials/iv-page/iv-from-db-population-response.html", iv_data=full_iv_dict, iv_curve=iv_curve, tags=tag_list, selected_tag=iv_info_dict["subassembly_tag"], diode_lots_list=diode_lots_list, circuit_lots_list=circuit_lots_list, suppress_lot_search=True)
	
@db_bp.post("/cancel_iv_selection/")
def cancel_iv_selection():
    return ""