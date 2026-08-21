from flask import Blueprint, request, render_template
from app.services.process_and_sanitize_entry import *
from app.services.date_converter import string_to_python_date
from app.services import db_service
from app.services import postprocess as pp
from app.services import field_registry as fr
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
    if block_revision == "":
        block_revision = "A"
    block = retrieve_build_info(block_engraving, block_serial_number, block_revision)[0]
    parts = retrieve_build_parts(block_engraving, block_serial_number, block_revision)
    notes = retrieve_notes(block_engraving, block_serial_number, block_revision)
    return render_template("partials/block-forms/block-and-build-population.html", block=block, parts=parts, notes=notes)

@db_bp.post("/trigger_inspection_info_save")
def trigger_inspection_info_save():
    route = "save_inspection_info"
    return render_template("partials/generic/generic-save-dialog.html", route=route)

@db_bp.post("/attempt_save_inspection_info")
def attempt_save_inspection_info():
    block_data = request.form

    if block_data.get("block-revision-input", "").strip() == "":
        db_block_rev = "A"
    else:
        db_block_rev = block_data.get("block-revision-input", "").strip()

    if validate_block_info(block_data.get("block-engraving-input", "")) == True:
        block_engraving = request.form.get("block-engraving-input", "").strip()
        block_serial_number = request.form.get("block-serial-number-input", "").strip()
        block_revision = db_block_rev
        inspection_date = string_to_python_date(request.form.get("inspection-date-input", "")) if (request.form.get("inspection-date-input", "") != "") else None
        inspection_initials = request.form.get("inspection-initials-input", "").strip()
        if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
            updates = {
                "inspection_date": inspection_date,
                "inspection_initials": inspection_initials
            }
            update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
            return "", 200
        elif retrieve_build_info(block_engraving, block_serial_number, block_revision) == []:
            new_entry = {
                "block_id": block_engraving+" "+block_serial_number+" "+block_revision,
                "block_engraving": block_engraving,
                "block_serial_number": block_serial_number,
                "block_revision": block_revision,
                "inspection_date": inspection_date,
                "inspection_initials": inspection_initials
            }

            add_table_entry(db_session, Build_Info, **new_entry)
            return "", 200
    else:
        route = "save_inspection_info"
        return render_template("partials/build-page/confirm-block-file-save.html", route=route)

@db_bp.post("/confirm_save_inspection_info")
def confirm_save_inspection_info():
    block_data = request.form
    
    if block_data.get("block-revision-input", "").strip() == "":
        db_block_rev = "A"
    else:
        db_block_rev = block_data.get("block-revision-input", "").strip()

    block_engraving = request.form.get("block-engraving-input", "").strip()
    block_serial_number = request.form.get("block-serial-number-input", "").strip()
    block_revision = db_block_rev
    inspection_date = string_to_python_date(request.form.get("inspection-date-input", "")) if (request.form.get("inspection-date-input", "") != "") else None
    inspection_initials = request.form.get("inspection-initials-input", "").strip()
    if retrieve_build_info(block_engraving, block_serial_number, block_revision) != []:
        updates = {
            "inspection_date": inspection_date,
            "inspection_initials": inspection_initials
        }
        update_table_entry(db_session, Build_Info, block_engraving+" "+block_serial_number+" "+block_revision, **updates)
        return "", 200
    elif retrieve_build_info(block_engraving, block_serial_number, block_revision) == []:
        new_entry = {
            "block_id": block_engraving+" "+block_serial_number+" "+block_revision,
            "block_engraving": block_engraving,
            "block_serial_number": block_serial_number,
            "block_revision": block_revision,
            "inspection_date": inspection_date,
            "inspection_initials": inspection_initials
        }

        add_table_entry(db_session, Build_Info, **new_entry)
        return "", 200

@db_bp.post("/trigger_pb1_info_save")
def trigger_pb1_info_save():
    route = "save_pb1_info"
    return render_template("partials/generic/generic-save-dialog.html", route=route)

@db_bp.post("/attempt_save_pb1_info")
def attempt_save_pb1_info():
    block_data = request.form
    
    if block_data.get("block-revision-input", "").strip() == "":
        db_block_rev = "A"
    else:
        db_block_rev = block_data.get("block-revision-input", "").strip()

    if validate_block_info(block_data.get("block-engraving-input", "")) == True:	
        block_engraving = request.form.get("block-engraving-input", "").strip()
        block_serial_number = request.form.get("block-serial-number-input", "").strip()
        block_revision = db_block_rev
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
            return "", 200
        
        elif retrieve_build_info(block_engraving, block_serial_number, block_revision) == []:
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
            return "", 200
    else:
        route = "save_pb1_info"
        return render_template("partials/build-page/confirm-block-file-save.html", route=route)

@db_bp.post("/confirm_save_pb1_info")
def confirm_save_pb1_info():
    block_data = request.form
        
    if block_data.get("block-revision-input", "").strip() == "":
        db_block_rev = "A"
    else:
        db_block_rev = block_data.get("block-revision-input", "").strip()

    block_engraving = request.form.get("block-engraving-input", "").strip()
    block_serial_number = request.form.get("block-serial-number-input", "").strip()
    block_revision = db_block_rev
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
        return "", 200
    
    elif retrieve_build_info(block_engraving, block_serial_number, block_revision) == []:
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
        return "", 200

@db_bp.post("/trigger_pb2_info_save")
def trigger_pb2_info_save():
    route = "save_pb2_info"
    return render_template("partials/generic/generic-save-dialog.html", route=route)

@db_bp.post("/attempt_save_pb2_info")
def attempt_save_pb2_info():
    block_data = request.form
        
    if block_data.get("block-revision-input", "").strip() == "":
        db_block_rev = "A"
    else:
        db_block_rev = block_data.get("block-revision-input", "").strip()

    if validate_block_info(block_data.get("block-engraving-input", "")) == True:
        block_engraving = request.form.get("block-engraving-input", "").strip()
        block_serial_number = request.form.get("block-serial-number-input", "").strip()
        block_revision = db_block_rev
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
            return "", 200
        
        elif retrieve_build_info(block_engraving, block_serial_number, block_revision) == []:
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
            return "", 200
    else:
        route = "save_pb2_info"
        return render_template("partials/build-page/confirm-block-file-save.html", route=route)

@db_bp.post("/confirm_save_pb2_info")
def confirm_save_pb2_info():
    block_data = request.form
            
    if block_data.get("block-revision-input", "").strip() == "":
        db_block_rev = "A"
    else:
        db_block_rev = block_data.get("block-revision-input", "").strip()

    block_engraving = request.form.get("block-engraving-input", "").strip()
    block_serial_number = request.form.get("block-serial-number-input", "").strip()
    block_revision = db_block_rev
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
        return "", 200
    
    elif retrieve_build_info(block_engraving, block_serial_number, block_revision) == []:
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
        return "", 200
    
@db_bp.post("/open_iv_from_db/")
def open_iv_from_db():
    build_info = request.form
    canonical = fr.canonical_from_form(request.form)
    build_id = fr.build_block_id_from_iv(canonical)

    iv_list = get_table_entries(db_session, IV_Info, build_id=build_id)
    for iv in iv_list:
        iv.iv_path_stem = Path(iv.iv_file_path).stem
        iv_info_dict = {
                    column.name: getattr(iv, column.name)
                    for column in iv.__table__.columns
                }

    # Passing the actual rows now, not just the path stems -- the template
    # needs both: iv.iv_id for the option's VALUE, the stem for what's
    # DISPLAYED. This is the one change that makes populate_iv_from_db (and
    # delete) simple.
    return render_template("partials/iv-page/select-iv-from-db.html", iv_list=iv_list)


@db_bp.post("/populate_iv_from_db/")
def populate_iv_from_db():
    build_info = request.form
    selected_iv_id = build_info.get("selected-iv-id")  # was "selected-iv-path"

    iv = db_service.get_iv_info_by_id(selected_iv_id)
    if iv is None:
        return render_template("partials/generic/error-message.html", errors=["That IV no longer exists."]), 200

    iv_info_dict = {
        column.name: getattr(iv, column.name)
        for column in iv.__table__.columns
    }

    build_name = Path(iv_info_dict['iv_file_path']).stem.split("_")[0]
    iv_curve_points = get_table_entries(db_session, IV_Points, iv_id=iv_info_dict['iv_id'])

    source_values = pp.clean_string_or_list_values(iv_curve_points[0].current_ua, conversion_factor=-6)
    measure_values_up = pp.clean_string_or_list_values(iv_curve_points[0].voltage_up_mv, conversion_factor=-3)
    measure_values_down = pp.clean_string_or_list_values(iv_curve_points[0].voltage_down_mv, conversion_factor=-3)

    polarity_symbol = "+" if iv_info_dict["polarity"].value == "positive" else "-"

    average_voltage_values = [(float(up) + float(down)) / 2 for up, down in zip(measure_values_up, measure_values_down)]
    process_dict = pp.calculate_iv_parameters(source_values, measure_values_up, measure_values_down)
    reverse_current = pp.clean_string_or_list_values(str(iv_info_dict["reverse_breakdown_current"]))
    reverse_voltage = pp.clean_string_or_list_values(str(iv_info_dict["reverse_breakdown_voltage"]))
    reverse_current, reverse_voltage = pp.get_reverse_breakdown_values(reverse_current, reverse_voltage)
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
        "reverse_current": reverse_current,
        "reverse_voltage": reverse_voltage,
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
        "build_sn": build_info.get("iv-block-sn"),
        "build_revision": build_info.get("iv-block-revision"),
        "diode": iv_info_dict["diode"],
        "diode_lot": iv_info_dict["diode_lot"],
        "circuit": iv_info_dict["circuit"],
        "circuit_lot": iv_info_dict["circuit_lot"],
        "assembly_number": iv_info_dict["assembly_number"],
        "subassembly_tag": iv_info_dict["subassembly_tag"],
        "temperature": iv_info_dict["temperature"],
        "additional_info": iv_info_dict["additional_information"],
        "points_per_decade": iv_info_dict["points_per_decade"],
        "build_name": build_name
    }

    full_iv_dict = {**clean_process_dict, **iv_population_dict}

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
    iv_curve["polarity"] = polarity_symbol


    tag_list = ["NA", "1", "2", "A", "B", "A1", "A2", "G1", "G2", "G3", "G4", "W"]

    diode_lots_list = jb2.get_Lots(full_iv_dict["diode"])
    circuit_lots_list = jb2.get_Lots(full_iv_dict["circuit"])

    return render_template("partials/iv-page/iv-from-db-population-response.html", iv_data=full_iv_dict, iv_curve=iv_curve, tags=tag_list, selected_tag=iv_info_dict["subassembly_tag"], diode_lots_list=diode_lots_list, circuit_lots_list=circuit_lots_list, suppress_lot_search=True)


@db_bp.post("/cancel_generic_dialog/")
def cancel_generic_dialog():
    return '<div id="generic-popup"></div>', 200